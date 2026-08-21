"""T6 · Tabla comparativa de codecs de Parquet sobre la fuente real.

Lee el CSV crudo **desde la capa cruda del lago** (MinIO, poblada por
T5), no desde el archivo local: es el insumo que la tarea declara
("el CSV crudo del lago de la sesión 5"). Convierte con los tres
codecs de la guía (snappy, gzip, zstd) y mide, sobre la MISMA muestra
para los tres, tamaño, tiempo de escritura y tiempo de lectura
selectiva — cada tiempo como la mediana de tres repeticiones, para no
dejar que la primera lectura (sin caché) infle el número.

La lectura selectiva usa las mismas dos columnas de la agregación de
T4 (`departamento`, `valorobservado`): es un patrón de consulta real
del proyecto, no una elección arbitraria.

Uso:
    python3 src/refinar/medir_codecs.py --date 2026-06-22
"""
import argparse
import os
import tempfile
import time
from datetime import date

import boto3
import pyarrow.csv as pv
import pyarrow.parquet as pq
from botocore.client import Config

CODECS = ["snappy", "gzip", "zstd"]
COLUMNAS_CONSULTA = ["departamento", "valorobservado"]
PREFIX = "cruda/ideam_precipitacion"
BUCKET_CRUDO = "lago-crudo"


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(signature_version="s3v4"),
    )


def object_key(day: date) -> str:
    return "{0}/anio={1:04d}/mes={2:02d}/dia={3:02d}/precipitacion_{1:04d}-{2:02d}-{3:02d}.csv".format(
        PREFIX, day.year, day.month, day.day
    )


def descargar_crudo(s3, day: date, destino: str) -> None:
    key = object_key(day)
    try:
        s3.download_file(BUCKET_CRUDO, key, destino)
    except s3.exceptions.ClientError as exc:
        raise RuntimeError(
            "No se encontró la partición cruda en el lago ({0}/{1}). "
            "Ejecute primero la ingesta de T5: "
            "python3 src/ingesta/cargar_cruda.py --date {2}".format(
                BUCKET_CRUDO, key, day.isoformat()
            )
        ) from exc


def mediana_tiempo(funcion, repeticiones=3):
    """Ejecuta varias veces y devuelve la mediana; descarta el efecto
    de la primera corrida, que suele ser más lenta sin caché tibia."""
    tiempos = []
    for _ in range(repeticiones):
        t0 = time.perf_counter()
        funcion()
        tiempos.append(time.perf_counter() - t0)
    tiempos.sort()
    return tiempos[len(tiempos) // 2]


def main():
    parser = argparse.ArgumentParser(description="Mide los tres codecs de Parquet sobre la fuente real")
    parser.add_argument("--date", default="2026-06-22", help="Fecha de la partición cruda, YYYY-MM-DD")
    parser.add_argument("--repeticiones", type=int, default=3)
    args = parser.parse_args()
    day = date.fromisoformat(args.date)

    s3 = s3_client()
    with tempfile.TemporaryDirectory() as tmp:
        csv_local = os.path.join(tmp, "muestra.csv")
        print("Descargando la partición cruda desde el lago ({0}/{1})...".format(BUCKET_CRUDO, object_key(day)))
        descargar_crudo(s3, day, csv_local)

        tabla = pv.read_csv(csv_local)
        print("Filas:", tabla.num_rows, "| Columnas:", tabla.num_columns)

        tam_csv = os.path.getsize(csv_local)
        print("CSV:", "{0:,}".format(tam_csv), "bytes")
        print()

        resultados = []
        for codec in CODECS:
            ruta = os.path.join(tmp, "muestra_{0}.parquet".format(codec))

            t_escritura = mediana_tiempo(
                lambda ruta=ruta, codec=codec: pq.write_table(tabla, ruta, compression=codec),
                args.repeticiones,
            )
            tam = os.path.getsize(ruta)
            t_lectura = mediana_tiempo(
                lambda ruta=ruta: pq.read_table(ruta, columns=COLUMNAS_CONSULTA),
                args.repeticiones,
            )
            resultados.append((codec, tam, t_escritura, t_lectura))

        print("{0:<10}{1:>16}{2:>16}{3:>18}{4:>14}".format(
            "Formato", "Tamaño (bytes)", "Escritura (s)", "Lectura sel. (s)", "vs CSV"
        ))
        print("{0:<10}{1:>16,}{2:>16}{3:>18}{4:>14}".format("CSV", tam_csv, "-", "-", "-"))
        lineas = []
        for codec, tam, te, tl in resultados:
            reduccion = 100 * (1 - tam / tam_csv)
            linea = "{0:<10}{1:>16,}{2:>16.4f}{3:>18.4f}{4:>13.1f}%".format(
                codec, tam, te, tl, reduccion
            )
            print(linea)
            lineas.append(linea)

    print()
    print("Repeticiones por medición:", args.repeticiones, "(se reporta la mediana)")
    return tam_csv, resultados


if __name__ == "__main__":
    main()
