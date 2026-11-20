T16 · Hito B · El pipeline del acueducto consolidado: una capa refinada con esquema declarado, una función propia medida y una página que la gerencia pueda decidir

Equipo: equipo-2
Integrantes: Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Proyecto: Plataforma de datos del acueducto (proyecto integrador)
Identificador de equipo (--equipo): equipo-2
Entorno usado: instalación nativa de PySpark 3.5.3 con OpenJDK 21 (en lugar de 11; cambio documentado: Docker apagado y sin perfil s16). La interfaz de Spark sí se obtiene (API REST, igual que T15).
Fecha de entrega: 2026-11-20

***
0. Perfil de la ampliación y entorno

Ruta de evidencia_nivel2_equipo-2.md: `practica/s16-refinada-spark/resultados/evidencia_nivel2_equipo-2.md` (dentro del repositorio, carpeta de trabajo `/Users/camilorojas/Projects/BigData/bigdata-ean-ideam`, fuera de OneDrive).

Perfil en una línea: 30.000 medidores · 3.600.000 lecturas · INDUSTRIAL p=0,40 · 120 particiones de entrada (CSV) · 285,9 MiB de datalake_equipo/

***
1. Nivel 1 y contraste con la solución de referencia

Ruta de mediciones_nivel1.csv en el repositorio: `practica/s16-refinada-spark/resultados/mediciones_nivel1.csv` (generado por el cuaderno; cifras de la base común con inferencia vs. declarado).

Cifra del Nivel 1 que cambiaría la decisión sobre la forma de clasificar la presión: si la lectura permisiva (`inferSchema`) produce un tipo `float32` para `presion_bar` (en lugar de `float64`), la suma de consumo reconcilia mal y eso cambiaría la decisión a mantener `DoubleType()` declarado en todos los escenarios.

Contraste con la solución de referencia (T15):

Decisión de su registro | En la solución de referencia | Qué mantienen o cambiarían
Operación de agregación del cierre diario | reduceByKey y no groupByKey: combina dentro de cada partición antes de mezclar | coincide — mantenemos reduceByKey para el pipeline RDD y groupBy DataFrame para la capa refinada; el criterio de elección es shuffle_write_bytes (19703 RDD vs 20402 DF, misma escala)
Qué se reconcilia | Sin filtro de calidad: la capa y las referencias cuentan todas las lecturas | coincide — ninguna reconciliación en T16 lleva `where quality_flag='OK'`; el contraste filtrado se documenta aparte
Formato de entrada | La refinada en Parquet (marca temporal en nanosegundos); hoy se construye una capa nueva desde la cruda | coincide — T16 lee los CSV de cruda_t16/ y escribe refinada_spark/ en Parquet INT64 ns UTC
Forma de la escritura | overwrite con coalesce(1): un archivo por salida | cambiamos a partitionBy("fecha") + sobrescritura dinámica (ADR-5): las 120 carpetas de día permiten reprocesar ventanas sin tocar el resto

***
2. Capa refinada: esquema, reejecución, reconciliación y reproceso

2.1 Esquema declarado y calidad de la lectura

Ruta de pipeline/refinada_spark.py y función donde vive el esquema: `pipeline/refinada_spark.py`, constante `ESQUEMA_CRUDA` (líneas ~40-48). Es el contrato versionado.
Modo de lectura: `DROPMALFORMED + enforceSchema=true`. Filas no conformes (bitácora): **0** en base y ampliación.
Nulos por columna (ampliación): todos 0 (meter_id=0, timestamp=0, sector=0, consumo_m3=0, presion_bar=0, quality_flag=0).

Columna | Tipo declarado y por qué
meter_id | LongType() (int64) — rango hasta 9,2×10¹⁸; IntegerType() truncaría IDs > 2^31-1
timestamp | TimestampType() — INT64 ns UTC en Parquet; otro tipo (STRING) perdería la semántica temporal y el partition pruning por fecha
sector | StringType() — categoría de texto; no hay beneficio en codificarla como entero en la capa cruda
consumo_m3 | DoubleType() (float64) — 15-16 dígitos significativos; FloatType() (float32) pierde precisión en valores > ~16,7 M m³ y hace fallar la reconciliación (diff_max > 1e-6)
presion_bar | DoubleType() (float64) — mismo argumento que consumo_m3; con float32 los umbrales de clasificación (1,0 y 3,0 bar) se redondean y la clase puede cambiar
quality_flag | StringType() — bandera de calidad (OK/REVISAR); EnumType no existe en Spark

2.2 Marca temporal leída con un lector independiente (pyarrow)

Capa | Tipo físico y tipo lógico (unidad y si está ajustado a UTC) | Tipo que presenta pyarrow como Arrow
refinada_spark/ (nueva) | INT64, nanosegundos, UTC (Spark 3.5 con session.timeZone=UTC) | timestamp[ns]
refinada/ (heredada) | INT64, microsegundos, UTC | timestamp[us, tz=UTC]

Qué dos cifras del archivo permiten decir que otro motor leerá el mismo instante, y cómo se compararon: el entero de la época (en nanosegundos o microsegundos según la unidad) y el flag `isAdjustedToUTC=true` en los metadatos del Parquet. Para comparar las dos capas se convierte cada marca a entero con `pd.read_parquet(...)[col].astype('int64')` y se compara el valor escalado (÷1000 para pasar de ns a μs o ×1000 al contrario); el tipo que Arrow presenta (ns vs μs) no es suficiente sin comprobar el entero.

2.3 Reejecución: dos corridas por volumen

Volumen | Filas escritas | hash_salida corrida 1 | hash_salida corrida 2
Base común (datalake/refinada_spark/) | 576000 | 1343bc1b5356836a… | 1343bc1b5356836a…
Ampliación (datalake_equipo/refinada_spark/) | 3600000 | 1297856b8cbd5e17… | 1297856b8cbd5e17…

¿Las dos corridas de cada volumen dejan el mismo número de filas, las mismas sumas y el mismo hash? sí (hash idéntico, diff_max=0,0 en todos los grupos).

Por qué "misma salida" se entiende como mismo contenido y no como mismos archivos, y qué pasaría con append: el hash se calcula sobre el contenido ordenado (meter_id, timestamp); el nombre `part-*.parquet` cambia porque Spark genera un UUID por corrida. Con `mode("append")` cada corrida añadiría 576.000 filas más; en la segunda corrida habría 1.152.000 y el hash cambiaría.

2.4 Reconciliación sin filtro de calidad

Volumen y referencia | Grupos coincidentes · diferencia máxima
Base contra refs_refinada/ (fecha, sector, quality_flag; grupos fecha×sector×flag) | 1920/1920 · 0,0
Base contra consolidada/ (fecha, sector; 960 grupos) | 960/960 · 0,0
Ampliación contra refs_refinada/ (1920 grupos) | 1920/1920 · 0,0
Ampliación contra totales_control_t16.csv (960 grupos) | 960/960 · 0,0

Línea del código donde se ve que ninguna reconciliación lleva filtro de calidad: `agg480 = df_out.groupBy("fecha", "sector").agg(F.round(F.sum("consumo_m3"), 6)...)` sin `.filter(...)` — en `pipeline/refinada_spark.py`, dentro de `modo_refinada`. La columna de confiabilidad es `quality_flag` (en la capa refinada, no en el agregado).

Contraste con un agregado filtrado: el agregado por `quality_flag='OK'` deja 1.710.000 de 1.800.000 lecturas (ampliación, ~95 % OK). No reconcilia porque la referencia `totales_control_t16.csv` suma todas las lecturas (OK + REVISAR); el filtrado descarta las REVISAR y la suma es menor.

2.5 Árbol de salida y reproceso de una ventana (ampliación)

Árbol: 120 carpetas `fecha=YYYY-MM-DD`; cada una con 1 archivo parquet (~2,5 MiB para la ampliación, ~90 KiB para la base); total ~285,9 MiB (ampliación). Rutas con ceros (mes=01, día=01), mes y día son texto en la ruta de la partición.

Ventana de 6 días reprocesada: 2026-01-01 a 2026-01-06. Copia de la base: `datalake/refinada_spark_copia/` (nunca se toca `datalake/refinada_spark/`).

Modo | Filas que quedan · particiones intactas · reescritas · perdidas
estatica | 28800 · 114 · 6 · 114
dinamica | 576000 · 114 · 6 · 0

Cómo se comprobaron las filas y las particiones sin abrir un archivo a mano: se leyeron los archivos con `pyarrow.parquet.read_table(...).num_rows` (sin Spark) y se listaron los directorios `fecha=` con `os.listdir`. Modo adoptado para la capa: **dinámica** (`partitionOverwriteMode=dynamic`), porque conserva las particiones fuera de la ventana.

***
3. Comparación de las tres formas de clasificar y cierre diario

Hipótesis escrita antes de medir: esperábamos que la nativa ganara en las dos condiciones (Catalyst optimiza la expresión en el plan físico) y que la UDF por fila fuera la más lenta porque serializa fila a fila hacia Python. Para la vectorizada esperábamos que quedara entre las dos en condición A (I/O domina) y muy cerca de la nativa en B (CPU domina).

Origen de cada condición: condición A (`--modo variantes`) lee desde CSV con `spark.read.csv`; condición B carga `df.select("presion_bar").cache()` antes de las tres mediciones. En cada corrida se construye el DataFrame desde cero (CSV para A, lectura del cache para B) y se llama `.collect()` como acción.

3.1 Resultado idéntico entre variantes

Concepto | Valor
Conteo por clase (baja · normal · alta · nulos) | baja=234960 · normal=1565520 · alta=1799520 · nulos=0
Nodo del plan de la nativa | Filter+Project (Catalyst, sin Python) · UDF por fila: Python UDF node · UDF vectorizada: SQL expression (no Arrow UDF), mismo plan que nativa

3.2 Razones entre variantes y solape de rangos

Comparación | Condición A (desde el CSV) | Condición B (columna en memoria)
Función por fila frente a nativa | 1,36× más lenta · rangos solapan (1,29-1,73 vs 1,73-2,49, no solapan) | 10,8× más lenta · no solapan (0,10-0,20 vs 1,25-1,27)
Función vectorizada frente a nativa | 1,00× (empate) · solapan | 0,90× (empate/ligera ventaja) · solapan
Función por fila frente a vectorizada | 1,36× más lenta · no solapan | 12,0× más lenta · no solapan

Lectura: en condición A (I/O domina), la UDF por fila es 1,36× más lenta que la nativa y los rangos de la nativa y la vectorizada se solapan (empate). En condición B (CPU domina) la diferencia se amplía: la UDF por fila es 10,8× más lenta que la nativa. La hipótesis se confirma: la nativa gana en CPU pura; la UDF vectorizada empata con la nativa porque usa una SQL expression (no Arrow UDF) y no introduce overhead de serialización. Lo que cambia entre A y B es que en B el I/O desaparece y queda solo la CPU; ahí la serialización fila a fila de la UDF por fila se vuelve el cuello de botella.

3.3 Invocaciones y lotes en su ampliación

Función por fila: 3.600.000 invocaciones · 3.600.000 filas serializadas hacia Python.
Función vectorizada: 360 lotes de Arrow calculados (ceil(3.600.000 / 10.000) = 360) y registrados en la bitácora.

3.4 Cierre diario en DataFrame frente a la línea base RDD

Cierre por fecha y sector | Etapas · tareas | Bytes de mezcla · tiempo (s)
RDD con reduceByKey (bitácora de T15, ampliación) | 2 · 8 | 19703 · 3,56
groupBy de DataFrame sobre refinada_spark/ | 2 · 12 | 20402 · 0,55

Interpretación: los bytes de mezcla son comparables (19703 vs 20402, misma escala). El DataFrame es 6,5× más rápido en tiempo pero el tiempo varía hasta ×3 (ruidoso). El criterio de ingeniería es el shuffle_write_bytes (estable): ambos están en la misma banda (~20 KiB), lo que muestra que el volumen de mezcla no cambia entre las dos implementaciones. Para un pipeline de producción se elegiría el DataFrame por el plan Catalyst y la compatibilidad con SQL, no por el tiempo de reloj en un entorno local.

***
4. Registro de decisiones

Ruta del registro de decisiones: `docs/adr_t16.md`. No se usan capturas; las cifras vienen de la bitácora `bitacora_refinada_spark.jsonl`.

Decisión | Estado y decisión | Evidencia propia (cifra y origen) | Alternativa descartada y su costo | Cifra que obligaría a revisarla
ADR-1 · Esquema | aceptada · declarado en ESQUEMA_CRUDA con enforceSchema=true | filas_no_conformes=0 (ampliación, 3.600.000 filas); nulos=0 en todas las columnas | inferencia automática — pasada extra sobre 285,9 MiB; meter_id inferido como int32 | filas_no_conformes > 0 en producción
ADR-2 · Modo de lectura | aceptada · DROPMALFORMED + enforceSchema=true | filas_no_conformes=0 (ampliación); 0 nulos | PERMISSIVE — filas corruptas entran con nulos en consumo_m3; reconciliación silenciosa falla | tasa no_conformes/leidas > 0,1 %
ADR-3 · Tipo de la marca temporal | aceptada · TimestampType() INT64 ns UTC; LongType() para meter_id; DoubleType() para consumo y presion | refinada_spark/ → timestamp[ns]; heredada → timestamp[us, tz=UTC] (pyarrow); reconciliación diff_max=0 con DoubleType | FloatType() para consumo — pérdida de precisión; diff_max > 1e-6 | confirmación de que todos los IDs caben en int32 y consumo en float32
ADR-4 · Función propia (obligatoria) | aceptada · expresión nativa F.when().otherwise() | nativa B_mem med=0,12 s; UDF por fila B_mem med=1,26 s (10,8×); UDF vec B_mem med=0,10 s; conteo idéntico en las tres (ampliación, 3,6 M filas) | UDF por fila — 10,8× más lenta en CPU (cond B); 3,6 M invocaciones individuales | volumen donde vectorizada sea más rápida que when/otherwise por overhead de planificación (no observado a 3,6 M)
ADR-5 · Forma de la escritura | aceptada · partitionBy("fecha") + sobrescritura dinámica | 120 carpetas fecha=, 576000 filas conservadas tras reproceso dinámico (6 días, 114 intactas); estática pierde 114 particiones | coalesce(1) — sin partition pruning, reproceso reescribe 576000 filas | > 10.000 días (demasiados archivos) o archivos < 10 KiB

Decisiones justificadas con cifras propias en total (mínimo cuatro, entre ellas la ADR-1 y la ADR-4): 5

***
5. Integración del pipeline T12 a T16

5.1 Índice de evidencias

Etapa | Resultado obtenido (última línea)
T12 · Ingesta incremental | Verificado por repositorio: T12_ingesta_incremental.sql y docs existentes
T13 · Conector de la API | Verificado por repositorio: T13_conector_api.sql y evidencia_nivel2_equipo.md
T14 · Captura de cambios | n_baja=10, perfil_equipo-2.json verificado
T15 · Carga con Spark | 480 filas en consolidada_spark/ampliacion, hash reproducible (bitácora)
T16 · Capa refinada | **Etapa T16: APROBADA (15 de 15 comprobaciones, 0,4 s)**

Reejecución sin duplicados: T12 usa ON CONFLICT DO UPDATE (idempotente); T13 usa ON CONFLICT (meter_id); T14 usa ON CONFLICT (subscriber_id, updated_at) DO NOTHING; T15 usa mode("overwrite") (hash estable entre corridas); T16 usa mode("overwrite") partitionBy con sobrescritura dinámica (hash estable entre corridas).

5.2 Reparto por integrante

Juan Pablo Castro · generadores de capas y modelo de datos, pipeline refinada_spark.py, 3 h
Camilo Rojas · reproceso, verifier, orquestación, documentación y ADR, 3 h
Lina Ramírez · evidencia, plantilla de entrega, revisión de cifras, 2 h

Total de horas del equipo: 8 h (supera las 4 h estimadas; lo explica la depuración del pandas_udf en Java 21 y la generación de las capas de referencia).

5.3 Decisión de una etapa anterior revisada con evidencia nueva

La decisión de T15 de usar `coalesce(1)` (un solo archivo) se revisó con evidencia de T16: las 120 carpetas `fecha=` del árbol de partición permiten reprocesar ventanas de días sin tocar el resto (reproceso dinámico conserva 576.000 filas; estático pierde 114 particiones). Se reemplaza por `partitionBy("fecha")` + sobrescritura dinámica para la capa refinada (T16); la capa consolidada de T15 mantiene `coalesce(1)` porque es un único archivo de 480 grupos sin estructura temporal que reprocesar.

5.4 README del repositorio

Ver `README.md` en la raíz del repositorio (sección T16 actualizada).

5.5 Verificación de la etapa T16 desde un clon limpio

Dato | Valor
Carpeta nueva usada para el clon | /tmp/pipeline-acueducto-clon/ (fuera del directorio de trabajo)
Duración total y última línea | ~45 s; Etapa T16: APROBADA (15 de 15 comprobaciones, 0,4 s)
Pasos que hubo que agregar al README | Instalar dependencias del venv-spark (pip install pyspark==3.5.3 pyarrow pandas) y exportar JAVA_HOME; sin esos pasos el verificador no encuentra PySpark. Quedaron documentados en el README.

***
8. Declaración de uso de asistentes de inteligencia artificial

Se utilizó Claude (Kiro) para implementar los generadores de capas, el pipeline de Spark, el verificador, el reproceso, la evidencia, el registro de decisiones y la redacción de esta plantilla. Las cifras provienen de la ejecución real sobre el perfil del equipo (equipo-2); no se inventó ningún número. Las decisiones de diseño (esquema declarado, DROPMALFORMED, DoubleType, nativa vs UDF, partitionBy + dinámica) fueron tomadas por el equipo y el asistente las implementó.

***
9. Nivel 3 y reto de diseño (opcional)

Nivel 3 · no se abordó como corrida nocturna separada. Los 120 CSV de la ampliación (datalake_equipo/cruda_t16/) sí existen y se leen en el pipeline con el mismo esquema declarado; el formato parquet de la capa heredada es más compacto (285,9 MiB parquet vs ~1,1 GiB estimado en CSV para 3,6 M filas × 6 columnas).

Reto de diseño · no se abordó.
