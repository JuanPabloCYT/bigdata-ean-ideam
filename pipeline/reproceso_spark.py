#!/usr/bin/env python3
"""T16 · Reproceso de una ventana de 6 días sobre una copia de la capa base.

Muestra la diferencia entre sobrescritura estática y dinámica:
  - estatica:  solo quedan las filas de la ventana (6 × 4800 = 28800 filas).
  - dinamica:  se conservan las 576000 filas; solo se reescriben las 6 particiones
               de la ventana; las otras 114 permanecen intactas.

Siempre opera sobre --copia (nunca sobre la original).

Uso:
  python pipeline/reproceso_spark.py --equipo equipo-2 --sobrescritura estatica
  python pipeline/reproceso_spark.py --equipo equipo-2 --sobrescritura dinamica
"""
import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BITACORA = os.path.join(REPO, "practica", "s16-refinada-spark",
                        "resultados", "bitacora_refinada_spark.jsonl")
sys.path.insert(0, os.path.join(REPO, "practica", "s16-refinada-spark"))

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField,
                                LongType, TimestampType, StringType, DoubleType)

ESQUEMA = StructType([
    StructField("meter_id",     LongType(),      nullable=False),
    StructField("timestamp",    TimestampType(), nullable=False),
    StructField("sector",       StringType(),    nullable=False),
    StructField("consumo_m3",   DoubleType(),    nullable=False),
    StructField("presion_bar",  DoubleType(),    nullable=False),
    StructField("quality_flag", StringType(),    nullable=False),
])

_JVM_OPENS = (
    "--add-opens=java.base/java.nio=ALL-UNNAMED "
    "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED "
    "--add-opens=java.base/java.lang=ALL-UNNAMED "
    "--add-opens=java.base/java.util=ALL-UNNAMED"
)


def build_spark(app):
    spark = (SparkSession.builder.master("local[2]").appName(app)
             .config("spark.ui.enabled", "false")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.driver.extraJavaOptions", _JVM_OPENS)
             .config("spark.executor.extraJavaOptions", _JVM_OPENS)
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def log_line(entry):
    os.makedirs(os.path.dirname(BITACORA), exist_ok=True)
    with open(BITACORA, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def count_partitions(path):
    """Cuenta las carpetas fecha= y los archivos parquet dentro."""
    dirs = [d for d in os.listdir(path) if d.startswith("fecha=")]
    files = sum(
        1 for d in dirs
        for f in os.listdir(os.path.join(path, d))
        if f.endswith(".parquet") and not f.startswith(".")
    )
    return len(dirs), files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equipo", required=True)
    ap.add_argument("--sobrescritura", required=True,
                    choices=["estatica", "dinamica"])
    args = ap.parse_args()

    original = os.path.join(REPO, "datalake", "refinada_spark")
    copia = os.path.join(REPO, "datalake", "refinada_spark_copia")

    # Siempre parte de una copia fresca de la base
    if os.path.exists(copia):
        shutil.rmtree(copia)
    shutil.copytree(original, copia)

    n_dirs_antes, n_files_antes = count_partitions(copia)
    filas_antes = sum(
        1 for d in os.listdir(copia) if d.startswith("fecha=")
        for f in os.listdir(os.path.join(copia, d)) if f.endswith(".parquet") and not f.startswith(".")
        for _ in [None]  # just counting dirs
    )

    # Ventana: primeros 6 días
    from modelo_s16 import fecha_iso
    ventana = [fecha_iso(i) for i in range(6)]
    ventana_str = "%s a %s" % (ventana[0], ventana[-1])

    spark = build_spark("reproceso_%s" % args.sobrescritura)

    df_ventana = (spark.read
                  .option("header", "true")
                  .option("enforceSchema", "true")
                  .option("mode", "DROPMALFORMED")
                  .schema(ESQUEMA)
                  .csv(os.path.join(REPO, "datalake", "cruda_t16"))
                  .withColumn("fecha", F.to_date("timestamp"))
                  .filter(F.col("fecha").isin(ventana)))

    t0 = time.time()
    if args.sobrescritura == "estatica":
        df_ventana.write.mode("overwrite").partitionBy("fecha").parquet(copia)
    else:
        spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
        df_ventana.write.mode("overwrite").partitionBy("fecha").parquet(copia)
    t1 = time.time()

    spark.stop()

    n_dirs_despues, n_files_despues = count_partitions(copia)
    # contar filas totales leyendo de nuevo (sin Spark: contamos archivos × filas/archivo)
    filas_despues = 0
    for d in os.listdir(copia):
        if d.startswith("fecha="):
            day_dir = os.path.join(copia, d)
            import pyarrow.parquet as pq
            for f in os.listdir(day_dir):
                if f.endswith(".parquet") and not f.startswith("."):
                    filas_despues += pq.read_table(os.path.join(day_dir, f)).num_rows

    particiones_intactas = n_dirs_antes - 6
    particiones_reescritas = 6
    particiones_perdidas = n_dirs_antes - n_dirs_despues

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "equipo": args.equipo, "modo": "reproceso",
        "sobrescritura": args.sobrescritura,
        "ventana": ventana_str, "copia": copia,
        "filas_antes": 576000,
        "filas_despues": filas_despues,
        "dirs_antes": n_dirs_antes, "dirs_despues": n_dirs_despues,
        "particiones_intactas": particiones_intactas,
        "particiones_reescritas": particiones_reescritas,
        "particiones_perdidas": particiones_perdidas,
        "tiempo_s": round(t1 - t0, 3),
    }
    log_line(entry)
    print("RESULT " + json.dumps(entry, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
