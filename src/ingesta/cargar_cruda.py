"""Ingesta reproducible de la fuente cruda del proyecto al lago de objetos.

Uso normal:
    python src/ingesta/cargar_cruda.py

La fuente se descarga de Socrata por fecha y se carga en la capa cruda
con una clave determinista:
    cruda/ideam_precipitacion/anio=YYYY/mes=MM/dia=DD/precipitacion_YYYY-MM-DD.csv

La carga normal es idempotente: si el objeto ya existe y su ETag coincide,
se omite. Si existe con contenido distinto, falla en vez de sobrescribirlo.
Eso implementa la regla de cruda inmutable.

La opcion --demo-versioning es deliberadamente explicita y solo sirve para
producir la evidencia de T5: crea una segunda version del mismo objeto.
No forma parte de la ingesta normal.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
from datetime import date
from urllib.parse import urlencode

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

SOURCE_ID = "s54a-sgyg"
DEFAULT_DATE = date(2026, 6, 22)
BUCKETS = {
    "raw": "lago-crudo",
    "refined": "lago-refinado",
    "curated": "lago-curado",
}
PREFIX = "cruda/ideam_precipitacion"


def settings():
    return {
        "endpoint": os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        "access_key": os.getenv("MINIO_ROOT_USER", "minioadmin"),
        "secret_key": os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123"),
        "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    }


def s3_client():
    cfg = settings()
    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        region_name=cfg["region"],
        config=Config(signature_version="s3v4"),
    )


def source_url(day: date) -> str:
    next_day = date.fromordinal(day.toordinal() + 1)
    params = {
        "$where": (
            "fechaobservacion >= '{0}T00:00:00' AND "
            "fechaobservacion < '{1}T00:00:00'"
        ).format(day.isoformat(), next_day.isoformat()),
        "$order": "fechaobservacion,codigoestacion,codigosensor,:id",
        "$limit": "50000",
    }
    return "https://www.datos.gov.co/resource/{0}.csv?{1}".format(
        SOURCE_ID, urlencode(params)
    )


def download_source(day: date) -> bytes:
    import requests

    # Se concatenan los BYTES tal como los entrega la API, sin pasar
    # por csv.reader/csv.writer para producir la salida. Socrata cita
    # todos los campos ("0011027030","0240",...); si se reconstruye el
    # CSV con csv.writer, este solo cita cuando hace falta, y el
    # archivo resultante -aunque contenga los mismos valores- deja de
    # ser byte a byte lo que el proveedor envio. Para la capa cruda
    # esa diferencia importa: "sin transformar" incluye el formato,
    # no solo los valores. csv.reader se usa unicamente para CONTAR
    # filas y decidir cuando parar de paginar, nunca para reescribir.
    pages = []
    offset = 0
    url_base = source_url(day)
    header = None
    while True:
        url = url_base + "&$offset=" + str(offset)
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        chunk = response.content
        if not chunk.strip():
            break
        text = chunk.decode("utf-8-sig")
        row_count = sum(1 for _ in csv.reader(io.StringIO(text))) - 1
        if row_count <= 0:
            break
        chunk_header, _, chunk_body = chunk.partition(b"\n")
        if header is None:
            header = chunk_header
            pages.append(chunk_header + b"\n" + chunk_body)
        else:
            pages.append(chunk_body)
        if row_count < 50000:
            break
        offset += 50000

    if not pages:
        raise RuntimeError("La API no devolvio registros para " + day.isoformat())

    body = b"".join(pages)
    if not body.endswith(b"\n"):
        body += b"\n"
    return body


def object_key(day: date) -> str:
    return "{0}/anio={1:04d}/mes={2:02d}/dia={3:02d}/precipitacion_{1:04d}-{2:02d}-{3:02d}.csv".format(
        PREFIX, day.year, day.month, day.day
    )


def ensure_buckets(s3) -> None:
    for bucket in BUCKETS.values():
        try:
            s3.head_bucket(Bucket=bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            s3.create_bucket(Bucket=bucket)
        if bucket == BUCKETS["raw"]:
            s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})


def head_object(s3, bucket: str, key: str):
    try:
        return s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def upload_immutable(s3, body: bytes, day: date) -> str:
    bucket = BUCKETS["raw"]
    key = object_key(day)
    digest = hashlib.md5(body).hexdigest()
    existing = head_object(s3, bucket, key)
    if existing:
        remote_etag = str(existing.get("ETag", "")).strip('"')
        if remote_etag == digest:
            print("YA EXISTE · contenido identico · no se sobrescribe")
            return key
        raise RuntimeError(
            "Objeto existente con contenido distinto. La capa cruda es inmutable: "
            "corrija la fuente/proceso y escriba una nueva ruta o version controlada."
        )

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="text/csv; charset=utf-8",
        Metadata={
            "fuente": "IDEAM / Socrata " + SOURCE_ID,
            "fecha-observacion": day.isoformat(),
            "sha256": hashlib.sha256(body).hexdigest(),
        },
    )
    print("CARGADO · s3://{0}/{1}".format(bucket, key))
    print("SHA256 · " + hashlib.sha256(body).hexdigest())
    return key


def demo_versioning(s3, body: bytes, day: date) -> None:
    bucket = BUCKETS["raw"]
    key = object_key(day)
    original = head_object(s3, bucket, key)
    if not original:
        raise RuntimeError("Ejecute primero la ingesta normal para crear el objeto.")

    marker = body + b"\n# T5 versioning demonstration\n"
    result = s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=marker,
        ContentType="text/csv; charset=utf-8",
    )
    version_id = result.get("VersionId")
    versions = s3.list_object_versions(Bucket=bucket, Prefix=key)
    ids = [v.get("VersionId") for v in versions.get("Versions", []) if v.get("Key") == key]
    print("VERSION NUEVA · " + str(version_id))
    print("VERSIONES RECUPERABLES · " + str(ids))
    if len(ids) < 2:
        raise RuntimeError("No se evidencio una version anterior recuperable.")

    old = next(v for v in versions["Versions"] if v.get("VersionId") != version_id)
    recovered = s3.get_object(Bucket=bucket, Key=key, VersionId=old["VersionId"])["Body"].read()
    print("VERSION ANTERIOR RECUPERADA · " + old["VersionId"])
    print("SHA256 VERSION ANTERIOR · " + hashlib.sha256(recovered).hexdigest())


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga la fuente cruda del IDEAM a MinIO")
    parser.add_argument("--date", default=DEFAULT_DATE.isoformat(), help="Fecha de observacion YYYY-MM-DD")
    parser.add_argument("--demo-versioning", action="store_true", help="Solo para generar evidencia de versionado")
    args = parser.parse_args()
    day = date.fromisoformat(args.date)

    s3 = s3_client()
    ensure_buckets(s3)
    body = download_source(day)
    upload_immutable(s3, body, day)
    if args.demo_versioning:
        demo_versioning(s3, body, day)


if __name__ == "__main__":
    main()
