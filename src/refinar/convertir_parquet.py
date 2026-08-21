"""T6 · Convierte la partición cruda a Parquet y puebla la capa refinada.

Lee el CSV desde `lago-crudo` (nunca lo toca ni lo reescribe), lo
convierte a Parquet con el codec que `medir_codecs.py` justificó
(zstd, ver docs/T6_formato.md) y lo escribe en `lago-refinado`, bajo
la misma convención de partición por fecha que ya usa la cruda.

La escritura es idempotente por el mismo criterio que T5: si el
objeto ya existe con el mismo contenido (mismo hash del Parquet
generado), no se reemplaza; si existe con contenido distinto, falla
en vez de sobrescribir en silencio.

Uso:
    python3 src/refinar/convertir_parquet.py --date 2026-06-22
    python3 src/refinar/convertir_parquet.py --date 2026-06-22 --codec gzip
"""
import argparse
import hashlib
import io
import os
import tempfile
from datetime import date

import boto3
import pyarrow.csv as pv
import pyarrow.parquet as pq
from botocore.client import Config
from botocore.exceptions import ClientError

CODEC_ELEGIDO = "zstd"
PREFIX_CRUDA = "cruda/ideam_precipitacion"
PREFIX_REFINADA = "refinada/ideam_precipitacion"
BUCKET_CRUDO = "lago-crudo"
BUCKET_REFINADO = "lago-refinado"


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(signature_version="s3v4"),
    )


def clave_cruda(day: date) -> str:
    return "{0}/anio={1:04d}/mes={2:02d}/dia={3:02d}/precipitacion_{1:04d}-{2:02d}-{3:02d}.csv".format(
        PREFIX_CRUDA, day.year, day.month, day.day
    )


def clave_refinada(day: date) -> str:
    return "{0}/anio={1:04d}/mes={2:02d}/dia={3:02d}/precipitacion_{1:04d}-{2:02d}-{3:02d}.parquet".format(
        PREFIX_REFINADA, day.year, day.month, day.day
    )


def head_object(s3, bucket: str, key: str):
    try:
        return s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Convierte la cruda a Parquet en la capa refinada")
    parser.add_argument("--date", default="2026-06-22", help="Fecha de la partición, YYYY-MM-DD")
    parser.add_argument("--codec", default=CODEC_ELEGIDO, choices=["snappy", "gzip", "zstd"])
    args = parser.parse_args()
    day = date.fromisoformat(args.date)

    s3 = s3_client()

    # La cruda nunca se toca: se lee, nunca se escribe de vuelta.
    key_cruda = clave_cruda(day)
    with tempfile.TemporaryDirectory() as tmp:
        csv_local = os.path.join(tmp, "cruda.csv")
        try:
            s3.download_file(BUCKET_CRUDO, key_cruda, csv_local)
        except ClientError as exc:
            raise RuntimeError(
                "No se encontró la partición cruda ({0}/{1}). Ejecute primero "
                "T5: python3 src/ingesta/cargar_cruda.py --date {2}".format(
                    BUCKET_CRUDO, key_cruda, day.isoformat()
                )
            ) from exc

        tabla = pv.read_csv(csv_local)
        parquet_local = os.path.join(tmp, "refinada.parquet")
        pq.write_table(tabla, parquet_local, compression=args.codec)

        with open(parquet_local, "rb") as fh:
            cuerpo = fh.read()
        digest = hashlib.md5(cuerpo).hexdigest()

        key_refinada = clave_refinada(day)
        existente = head_object(s3, BUCKET_REFINADO, key_refinada)
        if existente:
            etag_remoto = str(existente.get("ETag", "")).strip('"')
            if etag_remoto == digest:
                print("YA EXISTE · contenido identico · no se sobrescribe")
                return
            raise RuntimeError(
                "El Parquet de refinada ya existe con contenido distinto "
                "(¿cambió el codec o los datos?). Use una clave nueva o "
                "borre el objeto anterior antes de regenerar."
            )

        s3.put_object(
            Bucket=BUCKET_REFINADO,
            Key=key_refinada,
            Body=cuerpo,
            ContentType="application/octet-stream",
            Metadata={
                "fuente": "IDEAM / Socrata s54a-sgyg",
                "fecha-observacion": day.isoformat(),
                "codec": args.codec,
                "origen-crudo": key_cruda,
                "filas": str(tabla.num_rows),
            },
        )
        print("CARGADO · s3://{0}/{1}".format(BUCKET_REFINADO, key_refinada))
        print("Codec:", args.codec)
        print("Tamaño Parquet:", "{0:,}".format(len(cuerpo)), "bytes")
        print("Tamaño CSV original:", "{0:,}".format(os.path.getsize(csv_local)), "bytes")
        print("Filas:", tabla.num_rows)


if __name__ == "__main__":
    main()
