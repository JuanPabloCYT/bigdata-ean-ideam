#!/usr/bin/env python3
"""T15 · Pipeline de carga distribuida del acueducto (PySpark).

Modos (uno por invocación; cada invocación abre su propia SparkSession y
agrega una línea a bitacora_carga_spark.jsonl):

  carga        Lee la capa cruda, agrega por (fecha, sector) con `metodo`,
               escribe la capa consolidada, calcula hash y reconcilia contra
               la referencia. (Se usa para las corridas de reproducibilidad.)
  sweep        Mide solo la agregacion reduceByKey con `particiones-mezcla`
               (sin escribir): etapas, tareas, bytes de mezcla y tiempo.
  bytes_tarea  groupByKey por SECTOR (no por (fecha,sector)) con 8 particiones:
               registra los bytes leidos por tarea (Shuffle Read Size).
  aqe          groupBy de DataFrame por (fecha, sector) con AQE on/off y
               spark.sql.shuffle.partitions=200: cuenta las tareas de la etapa
               de reduccion.
  cache        Mide la primera (fria) y segunda (cacheada) lectura del mismo
               DataFrame y lee la pestana Storage.

El motor es PySpark 3.5.3 sobre Java 21 en modo local (Docker apagado).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, LongType, StringType, DoubleType,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BITACORA = os.path.join(REPO, "practica", "s15-carga-spark", "resultados", "bitacora_carga_spark.jsonl")

CSV_SCHEMA = StructType([
    StructField("medidor_id", LongType(), True),
    StructField("fecha", StringType(), True),
    StructField("sector", StringType(), True),
    StructField("consumo", DoubleType(), True),
    StructField("quality_flag", StringType(), True),
])

# Sectores (copia local para el partitioner de bytes_tarea; debe ser
# serializable para los workers).
SECTORES = [
    "RESIDENCIAL", "INDUSTRIAL", "COMERCIAL", "OFICIAL", "RURAL",
    "COMUNITARIO", "INSTITUCIONAL", "SERVICIOS",
]

# --------------------------------------------------------------------------- #
# Bitacora: lee la interfaz de Spark (REST) con los mismos campos que la
# pestana Stages: stageId, numTasks, shuffleWriteBytes, shuffleReadBytes.
# --------------------------------------------------------------------------- #
class Bitacora:
    def __init__(self, spark, equipo, master, aqe, ruta, jsonl_path=BITACORA):
        self.spark = spark
        self.sc = spark.sparkContext
        self.app_id = self.sc.applicationId
        self.equipo = equipo
        self.master = master
        self.aqe = aqe
        self.ruta = ruta
        self.jsonl_path = jsonl_path
        self.base = self._discover_base()
        self.last_max_stage = -1

    def _discover_base(self):
        for port in range(4040, 4060):
            url = "http://localhost:%d/api/v1/applications" % port
            try:
                apps = json.load(urllib.request.urlopen(url, timeout=2))
                for a in apps:
                    if a.get("id") == self.app_id:
                        return "http://localhost:%d/api/v1/applications/%s/" % (port, a["id"])
            except Exception:
                continue
        return None

    def _stages(self):
        if not self.base:
            return []
        try:
            return json.load(urllib.request.urlopen(self.base + "stages", timeout=3))
        except Exception:
            return []

    def _stage_tasks(self, stage_id):
        try:
            return json.load(urllib.request.urlopen(
                self.base + "stages/%d/0?details=true" % stage_id, timeout=3))
        except Exception:
            return {}

    def record(self, modo, volumen, metodo, n, t0, t1, extra=None):
        time.sleep(0.4)
        stages = [s for s in self._stages() if s.get("stageId", -1) > self.last_max_stage]
        stages.sort(key=lambda s: s.get("stageId", -1))
        if stages:
            self.last_max_stage = max(s.get("stageId", -1) for s in stages)
        etapas = len(stages)
        tareas = sum(s.get("numTasks", 0) for s in stages)
        sh_w = sum(s.get("shuffleWriteBytes", 0) or 0 for s in stages)
        sh_r = sum(s.get("shuffleReadBytes", 0) or 0 for s in stages)
        line = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "equipo": self.equipo, "modo": modo, "volumen": volumen,
            "metodo": metodo, "particiones_mezcla": n,
            "particiones_entrada": (stages[0].get("numTasks", 0) if stages else 0),
            "etapas": etapas, "tareas": tareas,
            "shuffle_write_bytes": sh_w, "shuffle_read_bytes": sh_r,
            "tiempo_s": round(t1 - t0, 4),
            "master": self.master, "aqe": self.aqe, "ruta": self.ruta,
            "app_id": self.app_id, "stages": [
                {"stageId": s.get("stageId"), "numTasks": s.get("numTasks"),
                 "shuffleWriteBytes": s.get("shuffleWriteBytes"),
                 "shuffleReadBytes": s.get("shuffleReadBytes"),
                 "name": (s.get("name") or "")[:60]} for s in stages],
            "extra": extra or {},
        }
        os.makedirs(os.path.dirname(self.jsonl_path), exist_ok=True)
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return line

    def skip(self):
        """Avanza last_max_stage sin registrar (para acciones que no se miden)."""
        time.sleep(0.3)
        stages = self._stages()
        if stages:
            self.last_max_stage = max(s.get("stageId", -1) for s in stages)


def build_session(master, driver_memory, aqe, shuffle_part, app_name):
    b = (SparkSession.builder.master(master).appName(app_name)
         .config("spark.ui.enabled", "true")
         .config("spark.ui.port", "4040")
         .config("spark.ui.port.maxRetries", "20")
         .config("spark.sql.adaptive.enabled", str(aqe).lower())
         .config("spark.sql.shuffle.partitions", str(shuffle_part)))
    if driver_memory:
        b = b.config("spark.driver.memory", driver_memory)
    spark = b.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def leer_input(spark, ruta, volumen):
    if volumen == "base":
        root = os.path.join(REPO, "datalake")
    else:
        root = os.path.join(REPO, "datalake_equipo")
    if ruta == "csv_contraste":
        d = os.path.join(root, "csv_contraste")
        return spark.read.option("header", "true").schema(CSV_SCHEMA).csv(d)
    d = os.path.join(root, "cruda")
    return spark.read.parquet(d)


def referencia_path(volumen):
    if volumen == "base":
        return os.path.join(REPO, "datalake", "consolidada", "consolidada.parquet")
    return os.path.join(REPO, "datalake_equipo", "totales_control.csv")


OUT_SCHEMA = StructType([
    StructField("fecha", StringType(), True),
    StructField("sector", StringType(), True),
    StructField("consumo", DoubleType(), True),
])


def build_agg(df, metodo, n):
    """Devuelve el RDD/DF agregado (para medir con .count())."""
    if metodo == "reduceByKey":
        rdd = df.select("fecha", "sector", "consumo").rdd.map(
            lambda r: ((r.fecha, r.sector), float(r.consumo)))
        return rdd.reduceByKey(lambda a, b: a + b, n)
    if metodo == "groupByKey":
        rdd = df.select("fecha", "sector", "consumo").rdd.map(
            lambda r: ((r.fecha, r.sector), [float(r.consumo)]))
        return rdd.groupByKey(n).mapValues(lambda xs: sum(xs))
    return df.groupBy("fecha", "sector").agg(F.sum("consumo").alias("consumo"))


def build_out(spark, agg, metodo):
    """Construye el DataFrame de salida (fecha, sector, consumo redondeado a
    6) con esquema explicito (sin inferencia, para no disparar un job extra)."""
    if metodo == "groupby_df":
        return agg.withColumn("consumo", F.round("consumo", 6))
    rdd = agg.map(lambda kv: (kv[0][0], kv[0][1], round(float(kv[1]), 6)))
    return spark.createDataFrame(rdd, schema=OUT_SCHEMA)


def hash_salida(spark, salida):
    rows = (spark.read.parquet(salida).orderBy("fecha", "sector")
            .select("fecha", "sector", "consumo").collect())
    buf = "\n".join("%s|%s|%.6f" % (r.fecha, r.sector, float(r.consumo)) for r in rows)
    return hashlib.sha256(buf.encode()).hexdigest(), len(rows)


def reconciliar(spark, salida, volumen):
    out = spark.read.parquet(salida)
    if volumen == "base":
        ref = spark.read.parquet(referencia_path(volumen))
    else:
        ref = spark.read.option("header", "true").schema(
            StructType([StructField("fecha", StringType()), StructField("sector", StringType()),
                        StructField("consumo", DoubleType())])).csv(referencia_path(volumen))
    j = out.alias("o").join(ref.alias("r"), ["fecha", "sector"], "full_outer")
    diff = j.select(F.abs(F.col("o.consumo") - F.col("r.consumo")).alias("d")).agg(
        F.max("d").alias("mx"), F.count("d").alias("n")).collect()[0]
    filas_out = out.count()
    filas_ref = ref.count()
    dup = out.groupBy("fecha", "sector").count().filter("count > 1").count()
    return {"filas_out": filas_out, "filas_ref": filas_ref,
            "diff_max": float(diff.mx) if diff.mx is not None else 0.0,
            "duplicados": dup}


# --------------------------------------------------------------------------- #
# Modos
# --------------------------------------------------------------------------- #
def modo_carga(args, write_output):
    spark = build_session(args.master, args.driver_memory, args.aqe, args.particiones_mezcla,
                           "carga_%s_%s" % (args.volumen, args.metodo))
    bt = Bitacora(spark, args.equipo, args.master, args.aqe, args.ruta)
    df = leer_input(spark, args.ruta, args.volumen)
    df.cache()
    df.count()          # materializa la cache (etapa de scan); no se mide
    bt.skip()
    agg = build_agg(df, args.metodo, args.particiones_mezcla)
    t0 = time.time(); agg.count(); t1 = time.time()
    line = bt.record("carga", args.volumen, args.metodo, args.particiones_mezcla, t0, t1)
    res = {"bitacora": line}
    if write_output:
        salida = os.path.join(REPO, "datalake_equipo" if args.volumen != "base" else "datalake",
                               "consolidada_spark")
        os.makedirs(os.path.dirname(salida), exist_ok=True)
        out = build_out(spark, agg, args.metodo)
        out.coalesce(1).write.mode("overwrite").parquet(salida)
        bt.skip()
        h, nfilas = hash_salida(spark, salida)
        rec = reconciliar(spark, salida, args.volumen)
        res.update({"filas": nfilas, "hash": h, "duplicados": rec["duplicados"],
                    "filas_out": rec["filas_out"], "filas_ref": rec["filas_ref"],
                    "diff_max": rec["diff_max"]})
    spark.stop()
    print("RESULT " + json.dumps(res, ensure_ascii=False))


def modo_sweep(args):
    spark = build_session(args.master, args.driver_memory, args.aqe, args.particiones_mezcla,
                           "sweep_%d" % args.particiones_mezcla)
    bt = Bitacora(spark, args.equipo, args.master, args.aqe, args.ruta)
    df = leer_input(spark, args.ruta, args.volumen)
    df.cache()
    df.count()
    bt.skip()
    agg = build_agg(df, "reduceByKey", args.particiones_mezcla)
    t0 = time.time(); agg.count(); t1 = time.time()
    line = bt.record("sweep", args.volumen, "reduceByKey", args.particiones_mezcla, t0, t1)
    spark.stop()
    print("RESULT " + json.dumps({"bitacora": line}, ensure_ascii=False))


def modo_bytes_tarea(args):
    spark = build_session(args.master, args.driver_memory, False, 8, "bytes_tarea")
    bt = Bitacora(spark, args.equipo, args.master, False, args.ruta)
    df = leer_input(spark, "parquet", args.volumen)
    df.cache(); df.count(); bt.skip()
    # Un sector por particion (partitioner por indice) para que cada tarea reciba
    # un sector: la tarea i recibe SECTORES[i]; la del sector dominante lee mas.
    rdd = df.select("sector", "consumo").rdd.map(lambda r: (r.sector, float(r.consumo)))
    # groupByKey con partitionFunc por indice: cada sector en su propia particion
    # (tarea i recibe SECTORES[i]); la del sector dominante lee mas bytes.
    agg = rdd.groupByKey(8, partitionFunc=lambda s: SECTORES.index(s)).mapValues(sum)
    t0 = time.time(); agg.count(); t1 = time.time()
    pmap = {i: [SECTORES[i]] for i in range(len(SECTORES))}
    # etapa de reduccion = la segunda etapa (mayor stageId con shuffleReadBytes>0)
    stages = sorted([s for s in bt._stages() if s.get("stageId", -1) > bt.last_max_stage],
                    key=lambda s: s.get("stageId", -1))
    reduce_stage = None
    for s in stages:
        if (s.get("shuffleReadBytes") or 0) > 0:
            reduce_stage = s
    tareas = []
    if reduce_stage:
        det = bt._stage_tasks(reduce_stage["stageId"])
        for tk in det.get("tasks", {}).values():
            tm = tk.get("taskMetrics") or {}
            srm = tm.get("shuffleReadMetrics") or {}
            bytes_leidos = (srm.get("localBytesRead") or 0) + (srm.get("remoteBytesRead") or 0)
            idx = tk.get("index")
            tareas.append({"indice": idx, "bytes": bytes_leidos,
                           "dur_ms": tk.get("duration"),
                           "sector": "+".join(pmap.get(idx, []))})
    line = bt.record("bytes_tarea", args.volumen, "groupByKey", 8, t0, t1,
                     extra={"tareas": tareas})
    spark.stop()
    print("RESULT " + json.dumps({"bitacora": line}, ensure_ascii=False))


def modo_aqe(args):
    spark = build_session(args.master, args.driver_memory, args.aqe, 200, "aqe_%s" % args.aqe)
    bt = Bitacora(spark, args.equipo, args.master, args.aqe, args.ruta)
    df = leer_input(spark, "parquet", args.volumen)
    df.cache(); df.count(); bt.skip()
    agg = df.groupBy("fecha", "sector").agg(F.sum("consumo").alias("consumo"))
    t0 = time.time(); agg.collect(); t1 = time.time()  # materializa los 480 grupos
    stages = sorted([s for s in bt._stages() if s.get("stageId", -1) > bt.last_max_stage],
                    key=lambda s: s.get("stageId", -1))
    # la etapa de reduccion es la que MAS lee de la mezcla (shuffleReadBytes)
    shuf = max(stages, key=lambda s: (s.get("shuffleReadBytes") or 0)) if stages else None
    line = bt.record("aqe", args.volumen, "groupby_df", 200, t0, t1,
                     extra={"reduce_tasks": (shuf.get("numTasks") if shuf else 0),
                            "shuffle_write": (shuf.get("shuffleWriteBytes") if shuf else 0)})
    spark.stop()
    print("RESULT " + json.dumps({"bitacora": line}, ensure_ascii=False))


def modo_cache(args):
    spark = build_session(args.master, args.driver_memory, False, 8, "cache")
    bt = Bitacora(spark, args.equipo, args.master, False, args.ruta)
    df = leer_input(spark, "parquet", args.volumen)
    t0 = time.time(); df.count(); t1 = time.time()
    bt.record("cache", args.volumen, "count_fria", 8, t0, t1, extra={"fase": "fria"})
    df.cache()
    t0 = time.time(); df.count(); t1 = time.time()  # materializa la cache
    bt.skip()
    t0 = time.time(); df.count(); t1 = time.time()  # segunda vez, desde cache
    bt.record("cache", args.volumen, "count_cacheada", 8, t0, t1, extra={"fase": "caliente"})
    # Storage: tamaño del RDD cacheado
    time.sleep(0.6)
    storage = {}
    try:
        storage = json.load(urllib.request.urlopen(bt.base + "storage", timeout=3))
    except Exception:
        pass
    rdds = (storage.get("rdds") or []) if isinstance(storage, dict) else (storage if isinstance(storage, list) else [])
    mem = sum((r.get("memoryUsed") or 0) for r in rdds)
    line_extra = {"storage_mem_bytes": mem, "num_rdds": len(rdds)}
    spark.stop()
    print("RESULT " + json.dumps({"storage_mem_bytes": mem, "num_rdds": len(rdds)}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equipo", required=True)
    ap.add_argument("--modo", required=True,
                    choices=["carga", "sweep", "bytes_tarea", "aqe", "cache"])
    ap.add_argument("--volumen", default="ampliacion", choices=["base", "ampliacion"])
    ap.add_argument("--metodo", default="reduceByKey", choices=["reduceByKey", "groupByKey", "groupby_df"])
    ap.add_argument("--particiones-mezcla", type=int, default=8)
    ap.add_argument("--ruta", default="parquet", choices=["parquet", "csv_contraste"])
    ap.add_argument("--master", default="local[2]")
    ap.add_argument("--driver-memory", default=None)
    ap.add_argument("--aqe", default="false", choices=["true", "false"])
    args = ap.parse_args()
    if args.modo == "carga":
        modo_carga(args, write_output=True)
    elif args.modo == "sweep":
        modo_sweep(args)
    elif args.modo == "bytes_tarea":
        modo_bytes_tarea(args)
    elif args.modo == "aqe":
        modo_aqe(args)
    elif args.modo == "cache":
        modo_cache(args)


if __name__ == "__main__":
    main()
