# T5 · Verificación independiente y dos correcciones (Juan Pablo)

Reproduje la ingesta de Camilo en un clon completamente limpio, en un directorio aparte, sin tocar el trabajo original hasta confirmar qué fallaba. Encontré y corregí dos problemas reales; el diseño de `src/ingesta/cargar_cruda.py` —idempotencia por ETag, inmutabilidad forzada, versionado— no cambió.

## Corrección 1 · La imagen de MinIO ya no existe

`docker compose up -d minio` desde un clon limpio fallaba:

```
Error: failed to resolve reference "docker.io/minio/minio:RELEASE.2024-06-13T19-44-58Z": not found
```

MinIO retira del registro público las versiones que van quedando viejas; la etiqueta que estaba anclada dejó de existir. Se ancló por **digest** en su lugar (`minio/minio@sha256:14cea...`), consistente con `jupyter` y `db` en el mismo `docker-compose.yml`, que ya usaban digest. Un digest no puede desaparecer del registro de la misma forma que una etiqueta.

## Corrección 2 · La cruda no era byte a byte lo que envía el proveedor

Con la imagen corregida, la ingesta cargó sin error, pero el SHA-256 reportado (`aebc6cbf...`) no coincidía con el que T1 documentó para la misma partición (`9a8dc75a...`), pese a tener exactamente las mismas 141.007 filas.

Comparé el archivo descargado de MinIO contra el original de T1 byte a byte: mismo número de filas, **tamaño distinto** (18.568.884 contra 21.953.076 bytes). La causa: Socrata entrega el CSV con **todos los campos citados** (`"0011027030","0240",...`), pero `download_source()` reconstruía la salida con `csv.writer`, que solo cita cuando hace falta. El contenido —los valores— era idéntico; el formato de bytes, no.

Esto no es un detalle cosmético para T5: la sección 4 de `T5_lago.md` define la cruda como *"el dato tal como llegó del proveedor, sin transformar"*. Reserializar el CSV con otro estilo de comillas es una transformación, aunque preserve cada valor.

**La corrección:** `download_source()` ahora concatena los bytes de cada página de la API directamente, usando `csv.reader` únicamente para contar filas y decidir cuándo detener la paginación —nunca para reescribir la salida—. Tras el cambio:

```
SHA256 · 9a8dc75af1969e21ad7e13bddd9fad0291ebbeba2a0b1418cd4237f81a5155be
```

Coincide **exacto** con el hash que T1 documentó para el 22 de junio de 2026, y el tamaño en MinIO (`ContentLength`) es 21.953.076 bytes, igual al original.

## Resto de la verificación, sin hallazgos

| Prueba | Resultado |
|---|---|
| Los tres buckets se crean (`lago-crudo`, `lago-refinado`, `lago-curado`) | Correcto |
| Versionado habilitado en `lago-crudo` | Correcto |
| Ruta particionada (`cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/...`) | Correcto, predecible sin preguntar |
| Segunda ejecución con el mismo dato | `YA EXISTE · contenido identico · no se sobrescribe` |
| `--demo-versioning`: versión anterior recuperable | Sí, y su SHA-256 vuelve a coincidir con el original |

## Conclusión

Con las dos correcciones, un clon limpio reproduce la ingesta completa sin intervención manual, y el objeto en la capa cruda es ahora **verificablemente idéntico**, byte a byte, al que T1 midió y al que la API entrega — no una reconstrucción equivalente en valores. Ambos hallazgos y su corrección están en `src/ingesta/cargar_cruda.py` y `docker-compose.yml`.
