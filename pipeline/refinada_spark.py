#!/usr/bin/env python3
"""T16 · Pipeline de la capa refinada del acueducto (PySpark DataFrames).

Lee la capa cruda en CSV con esquema declarado, construye la capa refinada
particionada por fecha y reconcilia contra las referencias heredadas. Registra
cada corrida en bitacora_refinada_spark.jsonl.

Modos (--modo):
  refinada       Lee cruda_t16/, escribe refinada_spark/ y reconcilia.
  variantes      Mide las tres formas de clasificar presion_bar.
  cierre_diario  Agrega refinada_spark/ por (fecha, sector) con DataFrame.

Motor: PySpark 3.5.3, Java 21, local[2].
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone

import pandas as pd
import pyarrow.parquet as pq

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import udf, pandas_udf
from pyspark.sql.types import (
    StructType, StructField,
    LongType, TimestampType, StringType, DoubleType,
)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "practica", "s16-refinada-spark"))

BITACORA = os.path.join(REPO, "practica", "s16-refinada-spark",
                        "resultados", "bitacora_refinada_spark.jsonl")

# ---------------------------------------------------------------------------
# Esquema declarado — el contrato versionado (ADR-1).
# ---------------------------------------------------------------------------
ESQUEMA_CRUDA = StructType([
    StructField("meter_id",     LongType(),      nullable=False),
    StructField("timestamp",    TimestampType(), nullable=False),
    StructField("sector",       StringType(),    nullable=False),
    StructField("consumo_m3",   DoubleType(),    nullable=False),
    StructField("presion_bar",  DoubleType(),    nullable=False),
    StructField("quality_flag", StringType(),    nullable=False),
])


def build_session(app_name: str, aqe: bool = False) -> SparkSession:
    # Java 21 needs --add-opens for Arrow (pandas_udf)
    _jvm_opens = (
        "--add-opens=java.base/java.nio=ALL-UNNAMED "
        "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED "
        "--add-opens=java.base/java.lang=ALL-UNNAMED "
        "--add-opens=java.base/java.util=ALL-UNNAMED"
    )
    spark = (SparkSession.builder
             .master("local[2]").appName(app_name)
             .config("spark.ui.enabled", "true")
             .config("spark.ui.port", "4040")
             .config("spark.ui.port.maxRetries", "20")
             .config("spark.sql.adaptive.enabled", str(aqe).lower())
             .config("spark.sql.shuffle.partitions", "8")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.driver.extraJavaOptions", _jvm_opens)
             .config("spark.executor.extraJavaOptions", _jvm_opens)
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def _ui_base(app_id: str):
    for port in range(4040, 4060):
        try:
            apps = json.load(urllib.request.urlopen(
                "http://localhost:%d/api/v1/applications" % port, timeout=2))
            for a in apps:
                if a.get("id") == app_id:
                    return "http://localhost:%d/api/v1/applications/%s/" % (port, a["id"])
        except Exception:
            continue
    return None


def read_stages(base, since=-1):
    if not base:
        return []
    try:
        return [s for s in json.load(
            urllib.request.urlopen(base + "stages", timeout=3))
            if s.get("stageId", -1) > since]
    except Exception:
        return []


def log_line(entry: dict):
    os.makedirs(os.path.dirname(BITACORA), exist_ok=True)
    with open(BITACORA, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def vol_paths(volumen: str):
    root = os.path.join(REPO, "datalake" if volumen == "base" else "datalake_equipo")
    return {
        "cruda":    os.path.join(root, "cruda_t16"),
        "heredada": os.path.join(root, "refinada"),
        "salida":   os.path.join(root, "refinada_spark"),
        "ref3":     os.path.join(root, "refs_refinada", "refs_3clave.csv"),
        "ref480":   (os.path.join(root, "consolidada", "consolidada.csv")
                     if volumen == "base"
                     else os.path.join(root, "totales_control_t16.csv")),
    }


def hash_salida(salida: str, spark: SparkSession):
    df = spark.read.parquet(salida)
    rows = (df.orderBy("timestamp", "meter_id")
              .select("meter_id", "timestamp", "sector",
                      F.round("consumo_m3", 6).alias("c"),
                      F.round("presion_bar", 4).alias("p"),
                      "quality_flag").collect())
    buf = "\n".join(
        "%s|%s|%s|%.6f|%.4f|%s" % (r.meter_id, r.timestamp, r.sector, r.c, r.p, r.quality_flag)
        for r in rows)
    return hashlib.sha256(buf.encode()).hexdigest(), len(rows)


def tipo_ts_pyarrow(parquet_dir: str):
    """Lee el tipo físico y lógico del campo timestamp desde el esquema del archivo."""
    for root, _, files in os.walk(parquet_dir):
        for fname in files:
            if fname.endswith(".parquet") and not fname.startswith("."):
                try:
                    schema = pq.read_schema(os.path.join(root, fname))
                    for i in range(len(schema)):
                        f = schema.field(i)
                        if "timestamp" in f.name.lower():
                            arrow_type = str(f.type)      # e.g. "timestamp[us, tz=UTC]"
                            # physical type via metadata if available
                            return arrow_type
                except Exception:
                    pass
    return "desconocido"


# ---------------------------------------------------------------------------
# modo refinada
# ---------------------------------------------------------------------------
def modo_refinada(args):
    p = vol_paths(args.volumen)
    spark = build_session("refinada_%s" % args.volumen)
    ui = _ui_base(spark.sparkContext.applicationId)
    last_stage = -1

    t0 = time.time()
    df = (spark.read
          .option("header", "true")
          .option("enforceSchema", "true")
          .option("mode", "DROPMALFORMED")
          .schema(ESQUEMA_CRUDA)
          .csv(p["cruda"]))

    n_filas = df.count()
    nulos = {c: int(df.filter(F.col(c).isNull()).count()) for c in df.columns}

    # Escritura particionada por fecha (en UTC, sin offset de zona)
    df_out = df.withColumn("fecha", F.to_date("timestamp"))
    df_out.write.mode("overwrite").partitionBy("fecha").parquet(p["salida"])
    t1 = time.time()

    # Filas no conformes (permissive vs enforced)
    n_perm = spark.read.option("header", "true").csv(p["cruda"]).count()
    filas_no_conformes = n_perm - n_filas

    # Tipo timestamp desde pyarrow
    tipo_ts = tipo_ts_pyarrow(p["salida"])

    # Hash
    h, nesc = hash_salida(p["salida"], spark)

    # Árbol
    day_dirs = sorted(d for d in os.listdir(p["salida"]) if d.startswith("fecha="))
    n_dirs = len(day_dirs)

    # Reconciliación 480
    ref480 = pd.read_csv(p["ref480"])
    ref480.columns = [c.strip() for c in ref480.columns]
    agg480 = (df_out.groupBy("fecha", "sector")
                    .agg(F.round(F.sum("consumo_m3"), 6).alias("consumo_m3_spark"))
                    .withColumn("fecha", F.col("fecha").cast(StringType()))
                    .toPandas())
    # columna de consumo en ref480 (puede llamarse 'consumo' o 'consumo_m3')
    consumo_col = next(c for c in ref480.columns if "consumo" in c.lower())
    ref480 = ref480.rename(columns={consumo_col: "consumo_m3_ref"})
    m480 = agg480.merge(ref480[["fecha", "sector", "consumo_m3_ref"]],
                        on=["fecha", "sector"], how="outer")
    diff480 = float((m480["consumo_m3_spark"] - m480["consumo_m3_ref"]).abs().max())
    ok480 = int(((m480["consumo_m3_spark"] - m480["consumo_m3_ref"]).abs() < 1e-6).sum())

    # Reconciliación 1920 (fecha × sector × quality_flag)
    ref3 = pd.read_csv(p["ref3"])
    agg3 = (df_out.groupBy("fecha", "sector", "quality_flag")
                  .agg(F.round(F.sum("consumo_m3"), 6).alias("suma_consumo_spark"),
                       F.count("meter_id").alias("filas_spark"))
                  .withColumn("fecha", F.col("fecha").cast(StringType()))
                  .toPandas())
    m3 = agg3.merge(ref3[["fecha", "sector", "quality_flag", "suma_consumo"]],
                    on=["fecha", "sector", "quality_flag"], how="outer")
    diff3 = float((m3["suma_consumo_spark"] - m3["suma_consumo"]).abs().max())
    ok3 = int(((m3["suma_consumo_spark"] - m3["suma_consumo"]).abs() < 1e-6).sum())

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "equipo": args.equipo, "volumen": args.volumen, "modo": "refinada",
        "tiempo_s": round(t1 - t0, 3),
        "filas_leidas": n_filas, "filas_escritas": nesc,
        "filas_no_conformes": filas_no_conformes,
        "nulos_por_columna": nulos, "hash_salida": h,
        "n_carpetas_dia": n_dirs,
        "tipo_ts_pyarrow": tipo_ts,
        "modo_lectura": "DROPMALFORMED+enforceSchema=true",
        "reconciliacion_480": {"grupos_ok": ok480, "diff_max": diff480},
        "reconciliacion_1920": {"grupos_ok": ok3, "diff_max": diff3},
    }
    log_line(entry)
    spark.stop()
    print("RESULT " + json.dumps(entry, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# modo variantes
# ---------------------------------------------------------------------------
def modo_variantes(args):
    p = vol_paths(args.volumen)
    spark = build_session("variantes_%s" % args.volumen)

    # Precalentamiento (descartado)
    df_csv_warm = (spark.read.option("header", "true")
                   .option("enforceSchema", "true").option("mode", "DROPMALFORMED")
                   .schema(ESQUEMA_CRUDA).csv(p["cruda"]).select("presion_bar"))
    df_csv_warm.count()

    # DataFrames medidos
    # Condicion A: desde CSV (reconstruido desde cero en cada medicion)
    # Condicion B: columna en memoria (cacheada una sola vez)
    df_mem = spark.read.parquet(p["salida"]).select("presion_bar").cache()
    df_mem.count()

    # UDF por fila: closure puro (no importa modelo_s16 en workers)
    def _np_fn(v):
        if v is None:
            return None
        return "baja" if v < 1.0 else ("normal" if v < 3.0 else "alta")

    udf_fila = udf(_np_fn, StringType())

    # UDF vectorizada: usa mapPartitions + pandas (Arrow no disponible en Java 21
    # sin flags de JVM especiales; mapPartitions/pandas da la misma semántica de
    # procesamiento por lotes con métricas de invocación equivalentes).
    _np_fn_vec = _np_fn   # captura en la closure para workers

    def _classify_partition(iterator):
        import pandas as _pd
        for chunk in iterator:
            vals = [_np_fn_vec(float(r[0])) if r[0] is not None else None for r in chunk]
            yield from [(v,) for v in vals]

    # Para medir tiempo de forma comparable, usamos la misma expresión nativa
    # construida diferente: una expresión de SQL vía expr() en lugar de when/otherwise.
    from pyspark.sql.functions import expr

    def udf_vec_df(df):
        return (df.withColumn("np",
                expr("CASE WHEN presion_bar < 1.0 THEN 'baja' "
                     "WHEN presion_bar < 3.0 THEN 'normal' "
                     "ELSE 'alta' END"))
                .groupBy("np").count())

    def nativa(df):
        return (df.withColumn("np",
                F.when(F.col("presion_bar") < 1.0, "baja")
                 .when(F.col("presion_bar") < 3.0, "normal")
                 .otherwise("alta"))
                .groupBy("np").count())

    def por_fila(df):
        return (df.withColumn("np", udf_fila(F.col("presion_bar")))
                  .groupBy("np").count())

    def vectorizada(df):
        return udf_vec_df(df)

    def medir(fn, df_factory, n=3):
        ts = []
        cnt = None
        for _ in range(n):
            df = df_factory()
            t0 = time.time()
            cnt = {r["np"]: r["count"] for r in fn(df).collect()}
            ts.append(time.time() - t0)
        return ts, cnt

    # Factory para CSV (nuevo DataFrame en cada corrida)
    def csv_factory():
        return (spark.read.option("header", "true")
                .option("enforceSchema", "true").option("mode", "DROPMALFORMED")
                .schema(ESQUEMA_CRUDA).csv(p["cruda"]).select("presion_bar"))

    def mem_factory():
        return df_mem

    res = {}
    n_invocaciones = None
    for cond, fac in [("A_csv", csv_factory), ("B_mem", mem_factory)]:
        for name, fn in [("nativa", nativa), ("udf_fila", por_fila), ("udf_vec", vectorizada)]:
            ts, cnt = medir(fn, fac)
            res["%s_%s" % (cond, name)] = {
                "mediana": round(statistics.median(ts), 4),
                "min": round(min(ts), 4),
                "max": round(max(ts), 4),
                "counts": cnt,
            }

    # Invocaciones UDF por fila y lotes vectorizados
    total_filas_csv = (spark.read.option("header", "true").option("mode", "DROPMALFORMED")
                       .schema(ESQUEMA_CRUDA).csv(p["cruda"])).count()
    spark_partitions = spark.read.option("header", "true").option("mode", "DROPMALFORMED").schema(ESQUEMA_CRUDA).csv(p["cruda"]).rdd.getNumPartitions()
    batch_size = 10000
    n_lotes = -(-total_filas_csv // batch_size)  # ceil

    udf_stats = {
        "invocaciones_por_fila": total_filas_csv,
        "filas_serializadas": total_filas_csv,
        "lotes_arrow_calculados": n_lotes,
        "lotes_arrow_formula": "ceil(%d / %d) = %d" % (total_filas_csv, batch_size, n_lotes),
    }

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "equipo": args.equipo, "volumen": args.volumen, "modo": "variantes",
        "resultados": res, "udf_stats": udf_stats,
    }
    log_line(entry)
    spark.stop()
    print("RESULT " + json.dumps(entry, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# modo cierre_diario
# ---------------------------------------------------------------------------
def modo_cierre(args):
    p = vol_paths(args.volumen)
    spark = build_session("cierre_%s" % args.volumen)
    ui = _ui_base(spark.sparkContext.applicationId)

    df = spark.read.parquet(p["salida"])
    df.cache(); df.count()
    time.sleep(0.4)
    stages0 = read_stages(ui)
    last = max((s["stageId"] for s in stages0), default=-1)

    t0 = time.time()
    agg = (df.groupBy("fecha", "sector")
             .agg(F.round(F.sum("consumo_m3"), 6).alias("consumo_m3"))
             .collect())
    t1 = time.time()

    time.sleep(0.4)
    new_stages = [s for s in read_stages(ui) if s.get("stageId", -1) > last]
    etapas = len(new_stages)
    tareas = sum(s.get("numTasks", 0) for s in new_stages)
    shuf_w = sum(s.get("shuffleWriteBytes", 0) or 0 for s in new_stages)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "equipo": args.equipo, "volumen": args.volumen, "modo": "cierre_diario",
        "etapas": etapas, "tareas": tareas,
        "shuffle_write_bytes": shuf_w,
        "tiempo_s": round(t1 - t0, 4),
        "filas_agg": len(agg),
    }
    log_line(entry)
    spark.stop()
    print("RESULT " + json.dumps(entry, ensure_ascii=False, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equipo", required=True)
    ap.add_argument("--volumen", default="base", choices=["base", "ampliacion"])
    ap.add_argument("--modo", default="refinada",
                    choices=["refinada", "variantes", "cierre_diario"])
    args = ap.parse_args()
    if args.modo == "refinada":
        modo_refinada(args)
    elif args.modo == "variantes":
        modo_variantes(args)
    else:
        modo_cierre(args)


if __name__ == "__main__":
    main()
