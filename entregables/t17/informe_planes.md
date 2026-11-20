# Informe de tres planes · equipo-2

IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean

Un plan de ejecución es la evidencia de cuántos datos se leyeron, cuáles se pudieron evitar y por qué. Este informe lee tres planes con sus variantes de diagnóstico y los respalda con las métricas de `bitacora_planes.jsonl`. Cada plan lleva los mismos cuatro apartados.

**Datos del informe.** Volumen: ampliación del equipo (426 medidores, 1.226.880 lecturas, sector dominante S-SUR 54,9 %). Día de la consulta A: `2024-04-14` (día de mayor consumo total según `datalake_equipo/totales_control.csv`, suma de los cuatro sectores). Spark 3.5.3, AQE apagada en A/B/C/C-forzada, encendida en C-aqe, `spark.sql.shuffle.partitions=8`, umbral de difusión por omisión (~10 MiB), columnas de partición como texto con ceros, `explain` en modo `formatted`.

---

## Plan A · Consumo por sector de un día (con su variante A-fecha)

**1. Qué se pidió y qué esperaban.**
Consumo por sector del día 2024-04-14, filtrando por `anio='2024'`, `mes='04'`, `dia='14'` (columnas de la ruta). Hipótesis (antes de medir): Spark poda particiones usando los tres literales del filtro y lee **1 solo archivo**; `PartitionFilters` debe aparecer en el plan con los tres predicados. A-fecha filtra por `fecha = 2024-04-14`, que está guardada dentro del archivo: Spark no puede podar y lee los 120 archivos, con el mismo resultado.

**2. Dónde se resolvió cada filtro.**
- **A:** el filtro se resolvió **en la ruta** (`PartitionFilters`). El plan muestra `PartitionFilters: [isnotnull(anio), isnotnull(mes), isnotnull(dia), (anio = 2024), (mes = 04), (dia = 14)]`. Spark enumera las carpetas `anio=2024/mes=04/dia=14/` y abre solo el archivo que hay allí.
- **A-fecha:** el filtro se resolvió **dentro del archivo** (`PushedFilters: [IsNotNull(fecha), EqualTo(fecha,2024-04-14)]`). No hay `PartitionFilters`; el lector de Parquet aplica el predicado a nivel de row group (puede saltar grupos de filas si las estadísticas los descartan) pero tiene que abrir los 120 archivos para comprobarlo.

**3. Qué se leyó.**

| Campo de la bitácora | A | A-fecha |
|---|---|---|
| `partition_filters` | `[isnotnull(anio)…(dia = 14)]` | `""` (vacío) |
| `pushed_filters` | `""` (vacío) | `[IsNotNull(fecha), EqualTo(fecha,2024-04-14)]` |
| `read_schema` | (columnas del parquet) | (columnas del parquet) |
| `archivos_leidos` | **1** | **120** |
| `filas_salida_escaneo` | 10 224 | 10 224 |
| `etapas · tareas` | 2 · 9 | 2 · 12 |
| `hash_resultado` (iguales) | `1bc729f1a88f…` | `1bc729f1a88f…` |
| `diferencia_max_independiente` | 2,0 × 10⁻¹² | 2,0 × 10⁻¹² |

**4. Qué no pudo evitarse y por qué.**
A-fecha devuelve las mismas 10.224 filas leídas que A porque el día 2024-04-14 tiene 10.224 lecturas (426 medidores × 24 horas) en ambas consultas. La diferencia es que A-fecha tuvo que abrir los 120 archivos: `fecha` es una columna almacenada dentro de cada archivo Parquet; Spark puede usar sus estadísticas de row group para saltar grupos, pero no puede saber en qué archivo (carpeta de día) caen las filas sin abrir los 120. Archivos abiertos ≠ grupos de filas saltados: en este caso cada archivo tiene un solo grupo de filas de 4.800 filas, así que no hay salto posible dentro del archivo.

---

## Plan B · Lecturas con presión alta

**1. Qué se pidió y qué esperaban.**
Lecturas con `presion_bar > 3.5` bar por sector. Hipótesis (antes de medir): `presion_bar` no es columna de partición ni está ordenada en la capa; Spark empuja el predicado al lector Parquet (`PushedFilters`) pero debe abrir los **120 archivos** para aplicarlo fila a fila (o grupo a grupo). Sin poda.

**2. Dónde se resolvió el filtro.**
El filtro aparece en `PushedFilters: [IsNotNull(presion_bar), GreaterThan(presion_bar,3.5)]`. No hay `PartitionFilters`. El lector de Parquet aplica el predicado a nivel de row group usando las estadísticas del pie del archivo (mínimo y máximo de `presion_bar` por grupo): si el máximo del grupo es ≤ 3,5 puede saltar el grupo entero. En esta capa con un solo row group de 4.800 filas por archivo y valores de presión que varían entre ~0,5 y ~5,0 bar, ningún grupo se salta.

**3. Qué se leyó.**

| Campo de la bitácora | B |
|---|---|
| `partition_filters` | `""` (vacío) |
| `pushed_filters` | `[IsNotNull(presion_bar), GreaterThan(presion_bar,3.5)]` |
| `archivos_leidos` | 120 |
| `filas_salida_escaneo` | 1 226 880 (todas) |
| `etapas · tareas` | 2 · 12 |
| `hash_resultado` | `c8a643d4d1dd…` |
| `diferencia_max_independiente` | 1,8 × 10⁻¹² |

**4. Qué no pudo evitarse y por qué.**
El predicado queda empujado (el lector lo evalúa) pero aun así se leen los 120 archivos porque no hay información de partición que permita descartar carpetas completas. Las estadísticas de `presion_bar` por archivo (mínimo ~0,5, máximo ~5,0 en todos los archivos) no permiten saltar ningún archivo: todos contienen lecturas por encima y por debajo de 3,5 bar.

---

## Plan C · Consumo por estrato (con variantes C-forzada y C-aqe)

**1. Qué se pidió y qué esperaban.**
Consumo por estrato de las lecturas confiables (`es_confiable = true`), uniendo con `medidores.parquet` (426 filas, ~5 KB). Hipótesis (antes de medir): `medidores.parquet` pesa ~5 KB, muy por debajo del umbral de difusión por omisión (~10 MiB), por lo que Spark debería elegir **BroadcastHashJoin**: difunde la tabla de medidores a todos los ejecutores y evita la mezcla. C-forzada con umbral -1 obliga a **SortMergeJoin**: al menos 2 `Sort` (uno por cada lado) y 3 `Exchange` (uno por cada lado más la agrupación final). C-aqe con AQE activa debería conservar BroadcastHashJoin porque AQE puede cambiar la estrategia en tiempo de ejecución si ve que un lado es pequeño.

**2. Dónde se resolvió la unión y qué estrategia usó.**
- **C (omisión):** `BroadcastHashJoin`. La tabla de medidores se difunde; no hay mezcla de datos de lecturas. `n_exchange=1` (solo el agrupador final), `n_sort=0`.
- **C-forzada:** `SortMergeJoin`. Con umbral -1 la difusión queda desactivada. `n_exchange=3`, `n_sort=2`. Los bytes de mezcla saltan a 9,5 MB (vs 704 B en C con difusión).
- **C-aqe:** `BroadcastHashJoin`. AQE observa en tiempo de ejecución que el lado de medidores es pequeño y aplica la difusión aunque el plan inicial pudiera ser otro. Los hashes del plan inicial y final están registrados en la bitácora.

**3. Qué se leyó.**

| Campo de la bitácora | C | C-forzada | C-aqe |
|---|---|---|---|
| `archivos_leidos` | 120 | 120 | 120 |
| `filas_salida_escaneo` | 1 226 880 | 1 226 880 | 1 226 880 |
| `estrategia_union` | BroadcastHashJoin | SortMergeJoin | BroadcastHashJoin |
| `n_exchange` | 1 | 3 | 1 |
| `n_sort` | 0 | 2 | 0 |
| `etapas · tareas` | 3 · 13 | 4 · 21 | 3 · 6 |
| `bytes_mezcla` | 704 | 9 541 106 | 704 |
| `hash_resultado` (iguales) | `c0db0e7c5589…` | `c0db0e7c5589…` | `c0db0e7c5589…` |

**4. Qué no pudo evitarse y por qué.**
Con BroadcastHashJoin (C y C-aqe) no hay mezcla de las lecturas (solo 704 B, el agrupador final), pero sí hay que leer los 120 archivos de lecturas porque no hay poda posible: `es_confiable` no es columna de partición. Con SortMergeJoin (C-forzada) se fuerza ordenar y mezclar los 1,2 M de lecturas confiables con los 426 medidores: la mezcla crece a 9,5 MB y las tareas pasan de 13 a 21.

---

*Informe generado el 2026-11-20. Bitácora: `bitacora_planes.jsonl`. Código: `pipeline/planes_s17.py`. Equipo-2.*
