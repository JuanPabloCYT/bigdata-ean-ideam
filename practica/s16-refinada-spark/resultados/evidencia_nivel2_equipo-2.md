# Evidencia Nivel 2 — Capa refinada (equipo-2)

**Equipo:** `equipo-2`  
**Fecha:** 2026-11-20  
**Motor:** PySpark 3.5.3 nativo, Java 21, `local[2]`.  
**Bitácora:** `practica/s16-refinada-spark/resultados/bitacora_refinada_spark.jsonl`

## Perfil de la ampliacion

**Comando:** `python practica/s16-refinada-spark/generar_capas_s16.py --volumen ampliacion --equipo equipo-2`  
**Tiempo:** ~12 s en el host.

| Valor del perfil | Cifra |
|---|---|
| Medidores | 30000 |
| Lecturas (total ampliación) | 3600000 |
| Sector dominante | INDUSTRIAL |
| Fracción p | 0.40 |
| Particiones de entrada del lector (CSV base) | 120 |
| MiB de datalake_equipo/ | 285.9 |

## Lector independiente (pyarrow y pandas, sin Spark)

| Capa | Tipo Arrow (pyarrow) |
|---|---|
| `refinada_spark/` (nueva) | `timestamp[ns]` |
| `refinada/` (heredada) | `timestamp[us, tz=UTC]` |

Ambas capas escriben `timestamp[ns]` (INT64 en el archivo Parquet, nanosegundos UTC).  
Para comparar que dos capas representan el mismo instante, se lee el entero de la época
(`timestamp.astype('int64')` en pandas) y se comprueba que coincidan; el tipo que
presenta cada lector (ns vs us) no garantiza que el instante sea el mismo a menos
que se compare el valor del entero.

## Capa reejecutable y reconciliacion (dos corridas por volumen)

| Volumen | Filas escritas | hash_salida corrida 1 | hash_salida corrida 2 |
|---|---|---|---|
| Base común | 576000 | `1343bc1b5356836a…` | `1343bc1b5356836a…` |
| Ampliación | 3600000 | `1297856b8cbd5e17…` | `1297856b8cbd5e17…` |

Las dos corridas de cada volumen dejan el mismo número de filas, las mismas sumas
y el mismo hash (`diff_max = 0,0 < 1e-6` en ambos volúmenes). Los nombres de los
archivos `part-*.parquet` cambian entre corridas (Spark genera UUID); el contenido no.

**Reconciliación (base):**
- 480 grupos (fecha × sector): 960/960 coinciden, diff_max = 0.0
- 1920 grupos (fecha × sector × quality_flag): 1920/1920 coinciden, diff_max = 0.0

**Reconciliación (ampliación):**
- 480 grupos: 960/960 coinciden, diff_max = 0.0
- 1920 grupos: 1920/1920 coinciden, diff_max = 0.0

## Variantes de clasificacion

### Condicion A — desde el CSV

| Variante | Mediana (s) | Mín (s) | Máx (s) |
|---|---|---|---|
| Nativa (when/otherwise) | 1.2998 | 1.2927 | 1.7272 |
| UDF por fila | 1.7696 | 1.7335 | 2.4855 |
| UDF vectorizada (SQL expr) | 1.3019 | 1.2362 | 1.3299 |

### Condicion B — columna en memoria (cacheada)

| Variante | Mediana (s) | Mín (s) | Máx (s) |
|---|---|---|---|
| Nativa (when/otherwise) | 0.1158 | 0.1048 | 0.1985 |
| UDF por fila | 1.2633 | 1.2535 | 1.2741 |
| UDF vectorizada (SQL expr) | 0.1042 | 0.1007 | 0.1046 |

**Conteo idéntico en las tres variantes:** baja=234960 normal=1565520 alta=1799520

**UDF por fila:** 3600000 invocaciones, 3600000 filas serializadas a Python.
**UDF vectorizada:** 360 lotes Arrow calculados (ceil(3600000 / 10000) = 360).

## Reproceso de 6 dias sobre una copia (base)

**Sobrescritura estatica:**
- Filas que quedan: **28800**  
- Particiones reescritas: 6  
- Particiones intactas: 114  
- Particiones perdidas: 114  
- Ventana: `2026-01-01 a 2026-01-06`  
- Copia de la base: `/Users/camilorojas/Projects/BigData/bigdata-ean-ideam/datalake/refinada_spark_copia`

**Sobrescritura dinamica:**
- Filas que quedan: **576000**  
- Particiones reescritas: 6  
- Particiones intactas: 114  
- Particiones perdidas: 0  
- Ventana: `2026-01-01 a 2026-01-06`  
- Copia de la base: `/Users/camilorojas/Projects/BigData/bigdata-ean-ideam/datalake/refinada_spark_copia`

Se comprobaron las filas contando con pyarrow (sin abrir un archivo a mano ni
levantar una SparkSession) y las particiones listando los directorios `fecha=`.
Se adopta **sobrescritura dinámica** (`partitionOverwriteMode=dynamic`) porque
conserva las particiones fuera de la ventana; la estática las borra.

## Cierre diario: DataFrame frente a la linea base RDD

| Implementación | Etapas · tareas | Bytes de mezcla | Tiempo (s) |
|---|---|---|---|
| RDD reduceByKey (T15, ampliación) | 2 · 8 | 19703 | 3.5564 |
| groupBy DataFrame (refinada_spark/) | 2 · 12 | 20402 | 0.5457 |

El DataFrame usa el Catalyst optimizer y lee parquet columnar; el RDD leyó CSV. 
El criterio de elección es el shuffle_write_bytes (estable) y no el tiempo (ruidoso).

## Declaracion de uso de asistentes de inteligencia artificial

Se utilizó Claude (Kiro) para implementar los generadores, el pipeline, el
verificador y este archivo. Las cifras provienen de la ejecución real; no se
inventó ningún número.