# T16 · Registro de decisiones de arquitectura (ADR)

**Equipo:** `equipo-2` · **Fecha:** 2026-11-20
**Volumen ampliación:** 30.000 medidores · 3.600.000 lecturas · INDUSTRIAL p=0,40 · 120 días.
**Motor:** PySpark 3.5.3, Java 21, `local[2]`.
**Evidencia:** [`practica/s16-refinada-spark/resultados/evidencia_nivel2_equipo-2.md`](../practica/s16-refinada-spark/resultados/evidencia_nivel2_equipo-2.md)

---

## ADR-1 · Esquema: inferido o declarado, y dónde vive (obligatoria)

**Estado:** aceptada
**Contexto:** los 120 CSV de la capa cruda llegan sin tipos. La pregunta: ¿Spark infiere el esquema o lo recibe declarado? ¿Dónde vive la definición?
**Opciones:** (a) inferencia automática (`inferSchema=true`), (b) esquema declarado en `ESQUEMA_CRUDA` en `pipeline/refinada_spark.py`, (c) DDL externo en SQL.
**Evidencia:** con `inferSchema=true` Spark lee el CSV dos veces (un pasada extra para inferir tipos); con esquema declarado una sola lectura. Con el esquema declarado, `filas_no_conformes = 0` (ampliación: 3.600.000 filas leídas = 3.600.000 escritas). Nulos por columna: todos 0 (ampliación). La inferencia puede colapsar `meter_id` a `int32` si todos los valores caben y luego fallar con valores fuera de rango; `LongType()` es seguro en cualquier rango.
**Decisión:** esquema declarado en `ESQUEMA_CRUDA` en `pipeline/refinada_spark.py` (el contrato versionado), con `enforceSchema=true` y `mode=DROPMALFORMED`. El esquema vive en el pipeline, no en un DDL externo, para que el lector y el escritor sean el mismo archivo y no puedan desincronizarse.
**Alternativa descartada y su costo:** inferencia automática — costo: una pasada extra sobre los 285,9 MiB del CSV de la ampliación para inferir tipos, `meter_id` inferido como `int32` podría romper con medidores > 2^31-1, y los tipos inferidos cambian si el CSV de un día tiene solo valores pequeños.
**Consecuencias:** los nuevos CSV deben respetar el orden y los tipos de `ESQUEMA_CRUDA`; si llega un CSV con columnas en otro orden, `enforceSchema=true` lo detecta (las filas no conformes se cuentan).
**Cifra que obligaría a revisarla:** si `filas_no_conformes > 0` en producción (indica que la fuente cambió el esquema).

## ADR-2 · Modo de lectura y correspondencia de columnas

**Estado:** aceptada
**Contexto:** los CSV pueden llegar con columnas desordenadas o con un campo no parseable. ¿Qué modo usar?
**Opciones:** `PERMISSIVE` (fila con nulos en columnas fallidas), `DROPMALFORMED` (descarta la fila entera), `FAILFAST` (aborta el job).
**Evidencia:** `filas_no_conformes = 0` en la ampliación (3.600.000 CSV bien formados). Con `enforceSchema=true` un CSV con columnas en orden distinto se detecta como no conforme y se descarta (no queda corrupción silenciosa). Con `PERMISSIVE` la fila corrupta entraría con nulos y contaminaría la suma de consumo.
**Decisión:** `DROPMALFORMED + enforceSchema=true`. Las filas corruptas se descartan, el job termina y los conteos se registran en la bitácora. Si `filas_no_conformes > 0` la bitácora lo evidencia.
**Alternativa descartada y su costo:** `PERMISSIVE` — las filas con campos no parseables entran con nulos en `consumo_m3`; la suma reconciliaría mal y el problema quedaría oculto hasta que alguien compare los totales.
**Consecuencias:** las filas descartadas no entran a la capa refinada; hay que monitorear `filas_no_conformes` en la bitácora.
**Cifra que obligaría a revisarla:** tasa de `filas_no_conformes / filas_leidas` > 0,1 % (indicaría problema sistemático en la fuente, no ruido).

## ADR-3 · Tipo de la marca temporal, de los números y de las columnas de la ruta

**Estado:** aceptada
**Contexto:** ¿Qué tipo físico usar para `timestamp`? ¿`meter_id` como `int32` o `int64`? ¿`consumo_m3` y `presion_bar` como `float32` o `float64`?
**Opciones:** `TimestampType()` (INT64 μs UTC en Parquet), INT96 (legacy); `LongType()` vs `IntegerType()` para meter_id; `DoubleType()` vs `FloatType()` para consumo y presion.
**Evidencia (pyarrow):** `refinada_spark/` → `timestamp[ns]`; `refinada/` heredada → `timestamp[us, tz=UTC]`. Ambas son INT64, unidades diferentes (ns vs μs). Para comparar que representan el mismo instante hay que comparar el entero de la época (no el tipo que Arrow presenta). `consumo_m3` con `float32` pierde 2 decimales de precisión en valores >1000 m³; con `float64` la reconciliación da `diff_max=0` exactamente.
**Decisión:** `TimestampType()` (INT64 ns UTC, que es lo que PySpark 3.5 escribe con la config UTC), `LongType()` para `meter_id` (seguro hasta 9,2×10¹⁸), `DoubleType()` para `consumo_m3` y `presion_bar` (64 bits, reconcilia exactamente).
**Alternativa descartada y su costo:** `FloatType()` para consumo — costo: pérdida de precisión en valores > ~16,7 M m³ (fallo de reconciliación); `IntegerType()` para meter_id — trunca IDs > 2.147.483.647.
**Consecuencias:** los archivos son algo más grandes (8 bytes por campo numérico vs 4); la reconciliación es exacta.
**Cifra que obligaría a revisarla:** si se confirma que todos los meter_id caben en 32 bits y todos los consumos en float32, se podría bajar para reducir disco.

## ADR-4 · Función propia frente a expresión nativa (obligatoria)

**Estado:** aceptada
**Contexto:** clasificar `presion_bar` en baja/normal/alta. ¿Usar `F.when().otherwise()` (nativa Catalyst) o una UDF?
**Opciones:** expresión nativa (`when/otherwise`), UDF por fila (`udf`), UDF vectorizada (`pandas_udf` / SQL expression).
**Evidencia (ampliación, 3.600.000 filas):**

| Variante | Condición A (CSV) med (s) | Condición B (memoria) med (s) |
|---|---|---|
| Nativa | 1,30 | 0,12 |
| UDF por fila | 1,77 | 1,26 |
| UDF vectorizada | 1,30 | 0,10 |

Conteo idéntico (baja=234.960, normal=1.565.520, alta=1.799.520) en las tres variantes. En condición A (I/O domina) nativa y vectorizada empatan; en B (CPU domina) la UDF por fila es 10,8× más lenta que la nativa. Los rangos de nativa y vectorizada se solapan en ambas condiciones; el de la UDF por fila no se solapa con la nativa en condición B. 3.600.000 invocaciones individuales vs 360 lotes de 10.000 filas.
**Decisión:** expresión nativa (`F.when().otherwise()`). No serializa datos a Python, el Catalyst optimizer la incluye en el plan físico y en condición B es la más rápida. La UDF vectorizada es una alternativa válida si la lógica no se puede expresar con SQL, pero aquí puede.
**Alternativa descartada y su costo:** UDF por fila — 3.600.000 invocaciones individuales, serialización fila a fila, 10,8× más lenta que la nativa en condición B (1,26 s vs 0,12 s).
**Consecuencias:** la clasificación vive en el plan Catalyst y se puede ver en el `explain()` del DataFrame; si la lógica cambia a algo no expresable en SQL, habrá que pasar a UDF vectorizada.
**Cifra que obligaría a revisarla:** si el volumen diario supera el umbral donde la UDF vectorizada (por lotes) es más rápida que `when/otherwise` por overhead de planificación; a 3,6 M filas no se observa diferencia.

## ADR-5 · Forma de la escritura

**Estado:** aceptada
**Contexto:** ¿cómo escribir la capa refinada? ¿Uno o varios archivos? ¿Particionada por qué columna? ¿Qué modo de sobrescritura para el reproceso?
**Opciones:** `coalesce(1)` (un archivo) vs `partitionBy("fecha")` (un directorio por día); sobrescritura estática vs dinámica para el reproceso.
**Evidencia (árbol, base):** `partitionBy("fecha")` produce 120 carpetas `fecha=YYYY-MM-DD`, una por día, con archivos de ~90 KiB cada uno (576.000 filas / 120 días = 4.800 filas/día). El reproceso de 6 días con sobrescritura dinámica conserva 576.000 filas (114 particiones intactas + 6 reescritas = 120); la estática deja 28.800 filas (solo las 6 de la ventana; 114 perdidas).
**Decisión:** `partitionBy("fecha")` con sobrescritura dinámica para el reproceso (`partitionOverwriteMode=dynamic`). El árbol facilita el reproceso por ventana y la lectura filtrada por fecha (partition pruning).
**Alternativa descartada y su costo:** `coalesce(1)` — un solo archivo, sin partition pruning, el reproceso de 6 días reescribe los 576.000 registros.
**Consecuencias:** 120 archivos pequeños (~90 KiB); leer un día es rápido por partition pruning; el reproceso de N días solo toca N archivos.
**Cifra que obligaría a revisarla:** si el número de días crece a >10.000 (demasiados archivos pequeños) o si los archivos por día bajan de 10 KiB (overhead de metadatos supera los datos).

---

**Decisiones justificadas con cifras propias en total:** 5 (ADR-1 y ADR-4 obligatorias; más ADR-2, ADR-3 y ADR-5).
