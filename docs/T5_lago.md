# T5 · La fuente cruda en el lago

**IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean**  
**Fuente:** Precipitación del IDEAM, conjunto Socrata `s54a-sgyg`.

## 1. Mapa del lago

El lago usa tres buckets de almacenamiento de objetos, separados por responsabilidad:

| Capa | Bucket | Propósito | Regla |
|---|---|---|---|
| Cruda | `lago-crudo` | Fuente original tal como llega del proveedor | **Inmutable** |
| Refinada | `lago-refinado` | Datos tipados, limpiados y normalizados | Reprocesable desde cruda |
| Curada | `lago-curado` | Datos preparados para análisis/consumo | Reprocesable desde refinada |

En T5 solo se ingesta la capa **cruda**. Las otras dos quedan creadas y vacías para que el mapa del lago sea estable desde el principio.

## 2. Convención de rutas

La fuente del equipo se publica bajo esta plantilla:

```text
cruda/ideam_precipitacion/anio=YYYY/mes=MM/dia=DD/precipitacion_YYYY-MM-DD.csv
```

Ejemplo para la partición del 22 de junio de 2026:

```text
s3://lago-crudo/cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv
```

La fecha de la partición es `fechaobservacion`, no la fecha en que alguien ejecutó el script. Así, el objeto representa de forma estable el día del dato.

### Prueba de predicción

Dada la fuente `ideam_precipitacion` y la fecha `2026-06-22`, una persona nueva puede escribir la ruta completa sin consultar al equipo:

```text
cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv
```

La ruta contiene la fuente y sus tres componentes de fecha como claves `anio`, `mes` y `dia`; no depende de carpetas reales del sistema de archivos.

### La misma convención en las otras dos capas

T5 solo ingesta la cruda, pero el nivel 3 de la práctica pide la convención **completa del lago**, no solo la que ya se usa. Las otras dos capas siguen el mismo patrón de partición por fecha; lo que cambia es el formato del archivo y, en la curada, que el grano ya no es el registro crudo sino un agregado.

| Capa | Plantilla de ruta | Ejemplo real (22/06/2026) | Cuándo se llena |
|---|---|---|---|
| Cruda | `cruda/<fuente>/anio=YYYY/mes=MM/dia=DD/<archivo>.csv` | `cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv` | T5, ya ingestada |
| Refinada | `refinada/<fuente>/anio=YYYY/mes=MM/dia=DD/<archivo>.parquet` | `refinada/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.parquet` | T6, cuando la cruda se convierta a Parquet tipado |
| Curada | `curada/<fuente>/<agregacion>/anio=YYYY/mes=MM/<archivo>.parquet` | `curada/ideam_precipitacion/promedio_departamento/anio=2026/mes=06/promedio_departamento_2026-06.parquet` | Cuando se modele un consumo específico (p. ej. la agregación de T4, promedio por departamento) |

La curada pierde el nivel `dia=` porque su grano ya no es la observación diaria: es el resultado de una agregación (como la de T4), que se recalcula por período más amplio, no por partición cruda. Esa es la diferencia real entre las capas, no solo el formato de archivo: cruda y refinada conservan el grano original del dato; curada tiene el grano que la pregunta de negocio necesite.

## 3. Por qué se particiona por fecha

La fuente se consulta y se ingiere incrementalmente por `fechaobservacion`. La partición diaria permite:

1. cargar solo el día nuevo sin recorrer todo el histórico;
2. localizar un día concreto directamente;
3. reprocesar una fecha específica en refinada sin tocar las demás;
4. mantener el mismo patrón cuando T6 lea la cruda para convertirla a Parquet.

La fuente ya fue medida en T1 por partición diaria, por lo que esta convención conserva la unidad natural de ingesta del proyecto.

## 4. Inmutabilidad de la cruda

`lago-crudo` tiene **versionado de objetos habilitado**.

**Por qué el versionado protege la inmutabilidad, y no solo la política del script.** El script de ingesta ya impide sobrescribir por diseño (ver más abajo): si el contenido difiere, falla en vez de reemplazar. Pero esa es una regla de la aplicación, no del almacenamiento — cualquier otra herramienta con acceso directo a MinIO (la consola web, otro script, un error humano) sí podría sobrescribir el objeto sin pasar por esa regla. El versionado es la garantía que no depende de que nadie respete la convención: aunque algo sobrescriba `lago-crudo` por fuera del script, MinIO conserva la versión anterior como una versión más, no la borra. La inmutabilidad de la cruda no depende entonces de la disciplina de quien la usa, sino de una propiedad del almacenamiento que ni el propio equipo puede desactivar por accidente con una operación normal de escritura.

La ingesta normal, además, es idempotente y no sobrescribe un objeto existente:

- si la clave no existe, se crea;
- si existe y el contenido tiene el mismo ETag, la ejecución termina sin duplicar ni modificar;
- si existe con contenido diferente, el script falla deliberadamente en vez de editar la cruda.

La corrección de un error **no se hace editando el objeto crudo existente**. Se conserva el original y el proceso posterior documenta/corrige el problema en una nueva versión controlada o, preferiblemente, en la capa refinada. La cruda representa lo que se recibió del proveedor.

El argumento `--demo-versioning` del script es una excepción exclusivamente para la evidencia de la tarea: sobrescribe un objeto de prueba y demuestra que la versión anterior sigue recuperable. No es el modo normal de ingesta.

## 5. Reproducibilidad

Desde un clon limpio:

```bash
cp .env.example .env
docker compose up -d minio
pip install -r requirements.txt
python src/ingesta/cargar_cruda.py
```

El script crea, si no existen, los tres buckets y activa el versionado de `lago-crudo`. Después descarga la partición del IDEAM mediante su API y carga la clave determinista.

La carga no depende de que un CSV haya sido previamente guardado en el repositorio: el dato crudo no se versiona en Git por su tamaño. La fuente y la consulta están declaradas en el código, y el mismo día de observación produce la misma ruta.

## 6. Evidencia esperada

Para la partición del 22/06/2026 se debe observar:

```text
lago-crudo/
└── cruda/
    └── ideam_precipitacion/
        └── anio=2026/
            └── mes=06/
                └── dia=22/
                    └── precipitacion_2026-06-22.csv
```

El script imprime el SHA-256 del contenido cargado. Para una ejecución posterior con el mismo dato imprime `YA EXISTE · contenido identico · no se sobrescribe`.

La prueba de versionado se ejecuta de forma explícita:

```bash
python src/ingesta/cargar_cruda.py --demo-versioning
```

La salida debe mostrar una `VERSION NUEVA`, al menos dos IDs en `VERSIONES RECUPERABLES` y `VERSION ANTERIOR RECUPERADA`.

## 7. Relación con el resto del proyecto

- **T1:** definió y midió la fuente IDEAM y su unidad diaria de ingesta.
- **T3:** proyectó el volumen y recomendó almacenamiento replicado para el dato crudo.
- **T4:** procesó la misma fuente con MapReduce.
- **T5:** deposita esa fuente en la primera capa navegable del lago.
- **T6:** podrá leer `lago-crudo` y transformar las particiones a Parquet/refinada.

## 8. Regla para el analista nuevo

Si necesita el dato de una fecha concreta, no tiene que preguntar al equipo: tome la fuente `ideam_precipitacion`, escriba `anio`, `mes` y `dia` con dos dígitos y use el nombre de archivo correspondiente. La ruta es una convención, no conocimiento tribal.
