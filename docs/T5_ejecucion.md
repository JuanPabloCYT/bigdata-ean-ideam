# T5 · Ejecución reproducible del lago

## 1. Preparar el clon

```bash
git clone https://github.com/JuanPabloCYT/bigdata-ean-ideam.git
cd bigdata-ean-ideam
cp .env.example .env
```

> `main` ya contiene todo el trabajo de T5 y un commit más que la rama `t5-lago-crudo` donde se desarrolló; no hace falta cambiar de rama.

No se descarga ningún CSV al repositorio. La ingesta obtiene la partición directamente de la API de Socrata.

## 2. Levantar MinIO

```bash
docker compose up -d minio
```

Comprobar:

```bash
docker compose ps minio
```

La consola web queda en `http://localhost:9001` y la API S3 en `http://localhost:9000`.

## 3. Instalar dependencias

Con Python 3:

```bash
python3 -m pip install -r requirements.txt
```

## 4. Ejecutar la ingesta

```bash
python3 src/ingesta/cargar_cruda.py --date 2026-06-22
```

El script crea los buckets si faltan, activa el versionado de `lago-crudo`, descarga la partición diaria y la carga con esta clave:

```text
cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv
```

Una segunda ejecución con el mismo dato debe ser idempotente:

```text
YA EXISTE · contenido identico · no se sobrescribe
```

## 5. Comprobar los tres buckets y el versionado

La comprobación puede hacerse desde la consola de MinIO. Deben existir:

```text
lago-crudo
lago-refinado
lago-curado
```

En `lago-crudo`, la opción de versionado debe aparecer habilitada.

También puede verificarse con Python/boto3:

```bash
python3 - <<'PY'
import boto3, os
from botocore.client import Config

s3 = boto3.client(
    's3',
    endpoint_url=os.getenv('S3_ENDPOINT', 'http://localhost:9000'),
    aws_access_key_id=os.getenv('MINIO_ROOT_USER', 'minioadmin'),
    aws_secret_access_key=os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin123'),
    region_name='us-east-1',
    config=Config(signature_version='s3v4'),
)
print(s3.get_bucket_versioning(Bucket='lago-crudo'))
print(s3.list_objects_v2(Bucket='lago-crudo', Prefix='cruda/ideam_precipitacion/')['Contents'][0]['Key'])
PY
```

Debe aparecer `Status: Enabled` y la ruta particionada.

## 6. Evidencia del versionado

Después de ejecutar la ingesta normal, ejecutar:

```bash
python3 src/ingesta/cargar_cruda.py --date 2026-06-22 --demo-versioning
```

Este comando modifica deliberadamente una copia/version del objeto para demostrar la capacidad del almacenamiento de objetos. No debe usarse como operación normal de producción.

La salida esperada incluye:

```text
VERSION NUEVA · <id>
VERSIONES RECUPERABLES · [<id-nuevo>, <id-anterior>]
VERSION ANTERIOR RECUPERADA · <id-anterior>
SHA256 VERSION ANTERIOR · <hash>
```

La existencia del ID anterior después de sobrescribir prueba que el objeto anterior sigue recuperable.

## 7. Criterio de reproducibilidad

Un clon limpio debe poder repetir los mismos pasos y obtener:

1. los mismos tres buckets;
2. versionado habilitado en `lago-crudo`;
3. la misma ruta para una fecha dada;
4. el mismo contenido para la misma partición de la fuente;
5. una segunda ejecución normal que no duplique ni modifique el objeto.

La única dependencia externa es la fuente pública IDEAM/Socrata; por eso la URL, el dataset y la fecha están fijados en `src/ingesta/cargar_cruda.py`.

## 8. Detener el lago

```bash
docker compose down
```

Para borrar también el estado persistido de MinIO y comenzar desde cero:

```bash
docker compose down -v
```

**Advertencia:** `-v` elimina el volumen `minio_data` y, por tanto, las versiones almacenadas. Solo usar para una prueba limpia.
