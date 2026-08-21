# Práctica S06 · Formatos de archivo y compresión

Sesión 6 · Juan Pablo Castro

A diferencia de S03 y S04, esta práctica no necesita Docker ni clúster: PyArrow y DuckDB son librerías de Python. Solo necesita MinIO levantado (de T5), porque T6 lee el CSV crudo **desde el lago**, no desde un archivo aparte.

El código vive en [`src/refinar/`](../../src/refinar/); el informe completo en [`docs/T6_formato.md`](../../docs/T6_formato.md) y los comandos exactos en [`docs/T6_ejecucion.md`](../../docs/T6_ejecucion.md).

## Qué hay en `resultados/`

| Archivo | Contenido |
|---|---|
| `tabla_comparativa.txt` | Salida de `src/refinar/medir_codecs.py`: tamaño, tiempo de escritura y de lectura selectiva de los tres codecs, mediana de 3 repeticiones |
| `consulta_duckdb.txt` | Comparación de la misma consulta (promedio por departamento) sobre Parquet contra CSV, con la verificación de que el resultado es el mismo dentro de la precisión de punto flotante |

## Cómo reproducir

```bash
cd ~/Desktop/Code/proyecto-ideam-precipitacion
docker compose up -d minio
python3 -m pip install -r requirements.txt
python3 src/ingesta/cargar_cruda.py --date 2026-06-22      # si la cruda no está poblada
python3 src/refinar/medir_codecs.py --date 2026-06-22
python3 src/refinar/convertir_parquet.py --date 2026-06-22
```

Detalle completo, con el codec elegido y por qué, en [`docs/T6_formato.md`](../../docs/T6_formato.md).
