# T6 · Cómo reproducir la conversión a Parquet

## 1. Preparar el clon

```bash
git clone https://github.com/JuanPabloCYT/bigdata-ean-ideam.git
cd bigdata-ean-ideam
cp .env.example .env
```

**Requiere Python 3.10 o superior**, por la misma razón que T5: en macOS, `python3` puede resolver al intérprete del sistema, demasiado viejo para instalar las dependencias. Verifique antes de continuar:

```bash
python3 --version   # debe reportar 3.10 o superior
```

## 2. Levantar el lago e instalar dependencias

```bash
docker compose up -d minio
python3 -m pip install -r requirements.txt
```

## 3. Poblar la capa cruda (si aún no lo está)

T6 lee el CSV **desde `lago-crudo`**, no desde un archivo aparte. Si es la primera vez que se levanta el lago en este equipo, ejecute primero la ingesta de T5:

```bash
python3 src/ingesta/cargar_cruda.py --date 2026-06-22
```

Si la partición ya existe (de una ejecución anterior de T5), este comando no hace nada: `YA EXISTE · contenido identico · no se sobrescribe`.

## 4. Medir los tres codecs

```bash
python3 src/refinar/medir_codecs.py --date 2026-06-22
```

Imprime la tabla comparativa (tamaño, tiempo de escritura y de lectura selectiva, mediana de 3 repeticiones cada una) y no escribe nada en el lago: es solo medición, sobre un archivo temporal que se borra al terminar.

## 5. Convertir y poblar la capa refinada

```bash
python3 src/refinar/convertir_parquet.py --date 2026-06-22
```

Con `--codec` se puede forzar otro de los tres, por ejemplo para repetir la comparación de la sección 3 de `T6_formato.md` con un codec distinto:

```bash
python3 src/refinar/convertir_parquet.py --date 2026-06-22 --codec gzip
```

Una segunda ejecución con el mismo codec es idempotente: `YA EXISTE · contenido identico · no se sobrescribe`.

## 6. Verificar que la cruda sigue intacta

```bash
python3 - <<'PY'
import boto3
from botocore.client import Config
s3 = boto3.client("s3", endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin123",
    region_name="us-east-1", config=Config(signature_version="s3v4"))
key = "cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv"
h = s3.head_object(Bucket="lago-crudo", Key=key)
print("tamaño:", h["ContentLength"], "| esperado: 21953076 | coincide:", h["ContentLength"] == 21953076)
PY
```

## 7. Reproducir la comparación DuckDB (Parquet contra CSV)

```bash
python3 - <<'PY'
import boto3, duckdb, os, tempfile, time
from botocore.client import Config

s3 = boto3.client("s3", endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin123",
    region_name="us-east-1", config=Config(signature_version="s3v4"))

with tempfile.TemporaryDirectory() as tmp:
    csv_local = os.path.join(tmp, "muestra.csv")
    parquet_local = os.path.join(tmp, "muestra_zstd.parquet")
    s3.download_file("lago-crudo",
        "cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv", csv_local)
    s3.download_file("lago-refinado",
        "refinada/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.parquet", parquet_local)

    q_parquet = f"SELECT departamento, avg(valorobservado) FROM '{parquet_local}' WHERE valorobservado IS NOT NULL GROUP BY departamento"
    q_csv = f"SELECT departamento, avg(valorobservado) FROM read_csv_auto('{csv_local}') WHERE valorobservado IS NOT NULL GROUP BY departamento"

    def cronometrar(sql, n=3):
        t = []
        for _ in range(n):
            t0 = time.perf_counter(); duckdb.sql(sql).fetchall(); t.append(time.perf_counter() - t0)
        t.sort(); return t[n // 2]

    print("Parquet:", round(cronometrar(q_parquet), 4), "s")
    print("CSV    :", round(cronometrar(q_csv), 4), "s")
PY
```

## 8. Detener el lago

```bash
docker compose down
```

---

## Verificación de reproducibilidad desde cero

Esta secuencia se ejecutó en un clon completamente limpio (`git clone` en un directorio nuevo, `docker compose down -v` antes para borrar el volumen de MinIO). Resultado:

- Los tres codecs midieron exactamente los mismos números que en la ejecución original: `snappy` 381.716 bytes, `gzip` 284.431 bytes, `zstd` 312.373 bytes.
- El Parquet en `lago-refinado` quedó con el mismo tamaño (312.373 bytes) y las mismas 141.007 filas.
- La cruda permaneció en 21.953.076 bytes, sin ninguna versión nueva.
- La comparación DuckDB reprodujo el mismo resultado (33 departamentos, diferencia máxima de precisión de punto flotante, no de datos) con el mismo orden de magnitud de mejora en velocidad.

Detalle de esa verificación, incluida una discrepancia que se investigó antes de descartarla, en [`T6_formato.md`](T6_formato.md), sección 3.
