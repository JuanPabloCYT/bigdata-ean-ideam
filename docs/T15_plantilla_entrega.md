T15 · La carga distribuida del acueducto que se puede repetir, reconciliar y justificar con lo que muestra la interfaz de Spark

Equipo: equipo-2
Integrantes: Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Proyecto: Plataforma de datos del acueducto (proyecto integrador)
Identificador de equipo (--equipo): equipo-2
Entorno usado: instalación nativa de PySpark 3.5.3 (con OpenJDK 21 en lugar de 11 y en `local[2]`, cambio documentado: Docker apagado y sin perfil s15; el host solo tiene la librería cliente `libpq` y no hay binario de servidor). Las cifras de la interfaz de Spark sí se obtienen (bitácora leída por la API REST de la interfaz).
Fecha: 2026-11-18

***
0. Perfil de la ampliación del equipo

Comando exacto usado para generar la ampliación, tiempo que tomó y dónde corrió: `python practica/s15-carga-spark/generar_ampliacion_s15.py --equipo equipo-2`, ~6 s, en el host (no en contenedor; Docker apagado).

Valor del perfil | Cifra que reporta el generador
Medidores | 30000
Lecturas (total de la ampliación, no un incremento sobre la base) | 1800000
Sector dominante | INDUSTRIAL
Fracción p de medidores del sector dominante | 0.4
Disco ocupado por datalake_equipo/ (MiB) | 62.6

***
1. Carga reejecutable (condición de aceptación 1)

Ruta del script de la carga en el repositorio, modo de escritura y forma de la salida: `pipeline/carga_spark.py`; escritura `coalesce(1).write.mode("overwrite").parquet(...)` (un archivo por corrida). Se eligió `coalesce(1)` frente a `partitionBy(fecha)` porque el contenido (no el nombre del archivo) es lo que se compara y `coalesce(1)` deja un solo archivo fácil de hashear.
Comandos usados (con --equipo en ambos): `python pipeline/carga_spark.py --equipo equipo-2 --modo carga --volumen base` y `python pipeline/carga_spark.py --equipo equipo-2 --modo carga --volumen ampliacion` (cada uno dos corridas).

Volumen | Corrida | Filas de salida | hash_salida | Duplicados
Base común (datalake/consolidada_spark/) | 1 | 480 | 35ad5b73ee1156b37f0d3a4de1a6c6c8c6af28876901e55c197bfe324eb6dbad | 0
Base común | 2 | 480 | 35ad5b73ee1156b37f0d3a4de1a6c6c8c6af28876901e55c197bfe324eb6dbad | 0
Ampliación (datalake_equipo/consolidada_spark/) | 1 | 480 | 27ef88b0f1379d80ee67430ab37703155a6784c8951de4fdae4c349889653e89 | 0
Ampliación | 2 | 480 | 27ef88b0f1379d80ee67430ab37703155a6784c8951de4fdae4c349889653e89 | 0

¿Las dos corridas de cada volumen dejan el mismo número de filas, las mismas sumas y el mismo hash? sí (hash idéntico por volumen, `diff_max = 0,0`, dentro de la tolerancia de 1e-6 por grupo).

Por qué "misma salida" se entiende aquí como mismo contenido y no como mismos archivos, y qué pasaría con un anexado en lugar de overwrite: el contenido (480 filas, mismas sumas, mismo hash) es lo que se compara; el nombre `part-*.parquet` cambia entre corridas y no cuenta. Con `mode("append")` las filas se duplicarían en cada corrida (960, 1440…), el conteo y el hash cambiarían, y no sería idempotente.

***
2. Reconciliación sin filtro de calidad (condición de aceptación 2)

Volumen | Referencia | Filas obtenidas frente a esperadas | Lecturas por sector y día | Diferencia máxima en la suma de consumo | Resultado con tolerancia 1e-6 por grupo
Base común | consolidada/ | 480 frente a 480 | 1200 | 0.0 | cumple
Ampliación | totales_control.csv | 480 frente a 480 | mín=2571, máx=12000 | 0.0 | cumple

Línea del código que muestra que ningún agregado reconciliado lleva filtro de calidad: `build_agg` en `pipeline/carga_spark.py` hace `rdd.map(lambda r: ((r.fecha, r.sector), float(r.consumo))).reduceByKey(...)` (sin `where('quality_flag'='OK')`).

Contraste con un agregado filtrado por quality_flag (que no reconcilia):

Volumen | Lecturas con quality_flag = 'OK' frente al total | ¿Reconcilia el agregado filtrado? | Por qué no
Base común | 547200 frente a 576000 | no | el filtro descarta las lecturas 'REVISAR'; la suma filtrada es menor que la suma total de la referencia
Ampliación | 1710000 frente a 1800000 | no | el agregado filtrado tiene sus propios totales, no los de totales_control.csv

***
3. Bitácora y barrido de configuraciones (condición de aceptación 3)

Rutas en el repositorio de bitacora_carga_spark.jsonl y de evidencia_nivel2_equipo-2.md: `practica/s15-carga-spark/resultados/bitacora_carga_spark.jsonl` y `practica/s15-carga-spark/resultados/evidencia_nivel2_equipo-2.md` (este último contiene la hipótesis y la conclusión de cada configuración).
Configuración común del barrido (master, driver_memory, aqe, método, volumen): `master=local[2]`, `driver_memory` por defecto, `aqe=false`, `método=reduceByKey`, `volumen=ampliacion`. Comando: `python pipeline/carga_spark.py --modo sweep --volumen ampliacion --metodo reduceByKey --particiones-mezcla n`.

3.1 Barrido de particiones de mezcla (al menos tres valores distintos de --particiones-mezcla, tres corridas cada uno)

# | particiones_mezcla | particiones_entrada | Etapas | Tareas | Bytes de mezcla (escritos) | Tiempo mediana (s) | Tiempo mín. y máx. (s)
1 | 4 | 4 | 2 | 8 | 19703 | 3.692 | 3.556 / 4.224
2 | 8 | 4 | 2 | 12 | 23057 | 3.686 | 3.673 / 3.726
3 | 16 | 4 | 2 | 20 | 28740 | 3.882 | 3.806 / 4.005

Verificación de las tareas totales: con reduceByKey las tareas son las particiones de entrada más n. Aquí entrada=4 (Spark combinó los 120 archivos pequeños en 4 particiones de entrada con `maxPartitionBytes` por defecto), por lo que tareas = 4 + n: n=4→8, n=8→12, n=16→20. Cumple la relación (la etapa de scan se materializa aparte con la cache y no se cuenta).

Configuración | Hipótesis (escrita antes de medir) | Pestaña de la interfaz de la que sale la cifra | Conclusión (lo observado, y por separado lo interpretado)
1 (n=4) | Con n=4 hay menos tareas de reducción (entrada+4); cada partición recibe más datos; el tiempo puede subir por desequilibrio o bajar por menos sobrecarga. | Stages | Observado: tareas=8 (= entrada 4 + n 4), bytes de mezcla=19703, mediana=3.692 s. Interpretado: los bytes de mezcla crecen con n; las tareas crecen como entrada+n; el tiempo de reloj varía entre corridas (hasta ×3), por eso se reporta la mediana con mínimo y máximo. La hipótesis del tiempo no se confirma (n=4 no fue más lento).
2 (n=8) | Con n=8, tareas = entrada+8; punto intermedio; los bytes de mezcla escritos son los mismos. | Stages | Observado: tareas=12, bytes de mezcla=23057, mediana=3.686 s. Interpretado: los bytes de mezcla NO son los mismos (crecen con n, 19703→23057→28740); la hipótesis se refuta en parte: más particiones implican más sobrecarga de mezcla, no los mismos bytes.
3 (n=16) | Con n=16 hay más tareas de reducción (entrada+16); los bytes de mezcla se mantienen; el tiempo puede subir por coordinar más tareas. | Stages | Observado: tareas=20, bytes de mezcla=28740, mediana=3.882 s. Interpretado: los bytes de mezcla suben (no se mantienen); el tiempo sube ~5 % (3.882 vs 3.69) por coordinar más tareas. La hipótesis del tiempo se confirma; la de los bytes se refuta.

3.2 Tarea que lee más bytes (groupByKey, clave solo sector, numPartitions=8)

Tarea (índice) | Bytes leídos (Shuffle Read Size) | Sector que recibe | Tiempo de la tarea (ms)
1 | 640932 | INDUSTRIAL | 66
5 | 137738 | COMUNITARIO | 48
(tabla completa de las 8 tareas en evidencia_nivel2_equipo-2.md: cada una recibe un sector; INDUSTRIAL es la mayor, COMUNITARIO la menor con datos)

Causa de que esa tarea lea más bytes, explicada con el perfil de su ampliación (sector dominante y fracción p de la sección 0), y razón entre la mayor y la menor tarea con datos: el sector dominante INDUSTRIAL concentra p=0.4 de los medidores (12000 de 30000), por lo que su partición recibe muchos más bytes; razón mayor/menor ≈ 4.7 (= 12000/2571).
Qué se ve con reduceByKey y la misma clave, y por qué: reduceByKey combina del lado del mapa, así que cada tarea lee menos bytes (solo la suma parcial precombinada), no la lista completa de valores; por eso groupByKey transfiere más bytes por tarea que reduceByKey.
Si la tarea con más bytes no coincide con la más lenta, qué implica: coinciden (la tarea INDUSTRIAL, 66 ms, es también la más lenta); a esta escala el tiempo discrimina poco y los bytes son la señal fiable, pero la coincidencia confirma que los bytes explican el tiempo.

3.3 Contraste con el groupBy de DataFrame (solo si lo usaron en el barrido)

Ejecución adaptativa | spark.sql.shuffle.partitions | Tareas de la etapa de reducción | Bytes de mezcla
Activa | 200 | 1 | (shuffle read de la etapa de reducción, 90279)
Desactivada | 200 | 200 | (shuffle read de la etapa de reducción, 90279)

Qué se configura frente a qué se ejecuta: se configuran 200 particiones de mezcla; con AQE activa Spark coalesce las 200 en 1 tarea (los 480 grupos caben en una partición por su tamaño); con AQE desactivada se ejecutan las 200. Lo que se configura (200) no es lo que se ejecuta con AQE.

***
4. Registro de decisiones corto (condición de aceptación 4)

Ruta del registro de decisiones en el repositorio y ubicación de las capturas, si las usan en lugar de cifras escritas: `docs/adr_t15.md`; no se usan capturas, las cifras vienen de la bitácora (API REST de la interfaz de Spark).

ADR-1 · Número de particiones (obligatoria)
Estado: aceptada
Contexto: se decide `spark.sql.shuffle.partitions` para el reduceByKey sobre la ampliación (1.800.000 lecturas, 480 grupos, sector dominante p=0.4).
Opciones: n=4, n=8, n=16 (barrido 3.1).
Evidencia: n=4 → tareas 8, shuffle 19703, mediana 3.692 s; n=8 → tareas 12, shuffle 23057, 3.686 s; n=16 → tareas 20, shuffle 28740, 3.882 s.
Decisión: n=8.
Alternativa descartada y su costo: n=16 — +25 % de shuffle (28740) y +67 % de tareas (20) con +5 % de tiempo, sin beneficio a esta escala.
Consecuencias: partición del sector dominante acotada; riesgo de que con muy pocos grupos la sobrecarga de 8 no se amortice.
Cifra que obligaría a revisarla: si los bytes de mezcla por partición superan la memoria, o si p (sesgo) crece.

ADR-2 · Operación de agregación
Estado: aceptada
Contexto: reduceByKey frente a groupByKey para sumar consumo por (fecha, sector).
Opciones: reduceByKey (combine map-side) frente a groupByKey (transfiere todos los valores).
Evidencia: con groupByKey por sector, la tarea INDUSTRIAL lee 640932 bytes (4.7× las demás); reduceByKey combina map-side y transfiere solo la suma parcial.
Decisión: reduceByKey.
Alternativa descartada y su costo: groupByKey — la tarea dominante transfiere 640932 bytes (la lista de valores), más red y memoria.
Consecuencias: menos mezcla; riesgo de combine erróneo si la agregación no es asociativa.
Cifra que obligaría a revisarla: si la agregación deja de ser asociativa/conmutativa.

ADR-3 · Uso de caché
Estado: aceptada
Contexto: cachear o no la capa cruda leída para el barrido.
Opciones: MEMORY_ONLY frente a releer el parquet en cada acción.
Evidencia: lectura fría 0.6004 s, cacheada 0.0604 s (~9.9×); los 1.800.000 registros caben en memoria (MEMORY_ONLY, sin derrame).
Decisión: cachear el DataFrame de entrada (MEMORY_ONLY) para pasadas repetidas.
Alternativa descartada y su costo: no cachear — 0.6 s por acción; en 9 corridas, ~5.4 s de más.
Consecuencias: velocidad; riesgo de OOM si los datos no caben.
Cifra que obligaría a revisarla: si el volumen supera la memoria (spill).

ADR-4 · Formato de entrada
Estado: aceptada
Contexto: parquet frente a CSV para la capa cruda.
Opciones: parquet (datalake_equipo/cruda/) frente a CSV (datalake_equipo/csv_contraste/), mismo reduceByKey n=8.
Evidencia: parquet 1.9 MiB, CSV 61 MiB (~32×); tiempo similar (parquet 3.69 s, CSV 3.48 s, dentro del ruido) porque la agregación domina a 1.8 M filas.
Decisión: parquet (columnar, comprimido, con esquema).
Alternativa descartada y su costo: CSV — 61 MiB (~32×) y se reparsea en cada lectura.
Consecuencias: menos disco y parseo; riesgo de que la fuente solo entregue CSV.
Cifra que obligaría a revisarla: si la fuente deja de entregar parquet.

ADR-5 · Tamaño de ejecutores y núcleos (en local: local[N] y memoria del controlador)
Estado: aceptada
Contexto: master local[N] y memoria del controlador en el host (Docker apagado).
Opciones: local[1], local[2], local[*]; memoria por defecto (~1 GiB).
Evidencia: en local[2] hay un ejecutor (el controlador) con 2 núcleos; los 1.8 M registros y la caché caben (sin spill).
Decisión: local[2] con memoria por defecto.
Alternativa descartada y su costo: local[1] — sin paralelismo (más lento); local[*] — compite con el SO del host.
Consecuencias: paralelismo moderado y reproducible; riesgo de OOM si crece el volumen.
Cifra que obligaría a revisarla: si el volumen o la caché superan la memoria del controlador.

Decisiones justificadas en total (mínimo tres, una de ellas la ADR-1): 5

***
5. Contraste con la solución de referencia de la sesión anterior (criterio: contraste con la solución de referencia y documentación)

Decisión de su memo | En la solución de referencia | Qué mantienen o coincide | Qué cambiarían y por qué
Nomenclatura de las tablas | Nombres predecibles para que las etapas siguientes los consuman (maestro_suscriptores, stg_cambios_suscriptor, estado_cdc_suscriptores) | coincide | nada
Valor que se guarda como punto de control (checkpoint) | El mayor updated_at leído, con un centinela antiguo en la primera corrida | coincide | nada
Frontera de la transacción | Cambios y punto de control en una sola transacción | coincide | nada
Método de captura | Consulta por marca temporal, con reconciliación periódica de llaves para las bajas | coincide | nada
Punto ciego de las bajas duras | Se mide, no se supone: bajas generadas frente a bajas capturadas | coincide | nada

***
6. Repositorio e instrucciones de reproducción (condición de aceptación 5)

Enlace al repositorio, identificador del último commit que quieren que se valore y ruta del README: https://github.com/JuanPabloCYT/bigdata-ean-ideam , commit `feat(T15): carga distribuida con Spark + ADR` (último de main), README `README.md` (sección de T15) y `practica/s15-carga-spark/README.md`.
Pasos de reproducción:
1. Levantar el entorno de Spark (sin perfil s15, Docker apagado): `python3.11 -m venv .venv-spark && .venv-spark/bin/pip install pyspark==3.5.3 pyarrow pandas`; `export JAVA_HOME=/opt/homebrew/opt/openjdk@21`; `export PYSPARK_PYTHON=$PWD/.venv-spark/bin/python`. (El perfil s15 de Docker Compose no se usa porque Docker está apagado; se documenta el cambio a PySpark nativo.)
2. Regenerar datalake_equipo/ con el identificador de equipo: `python practica/s15-carga-spark/generar_base_s15.py` y `python practica/s15-carga-spark/generar_ampliacion_s15.py --equipo equipo-2`.
3. Correr la carga sobre la base y sobre la ampliación: `python pipeline/carga_spark.py --equipo equipo-2 --modo carga --volumen base` (dos veces) y `--volumen ampliacion` (dos veces).
4. Ejecutar el barrido y leer sus cifras: `python practica/s15-carga-spark/run_t15.py --equipo equipo-2` corre base×2, ampliación×2, el barrido (n=4/8/16 ×3), bytes por tarea, AQE on/off, caché y contraste CSV; las cifras se leen en `practica/s15-carga-spark/resultados/bitacora_carga_spark.jsonl` y `evidencia_nivel2_equipo-2.md`.
5. Salida y hash esperados: 480 filas, hash base `35ad5b73ee…` y ampliación `27ef88b0f1…` (idénticos entre corridas), `diff_max=0`, 0 duplicados; barrido `tareas=4+n`; bytes por tarea INDUSTRIAL=640932; AQE on→1 / off→200; caché 0.60→0.06 s.
Qué se versiona y qué no: no se subió ningún `.zip` ni las capas `cruda/` y `csv_contraste/` (están en `.gitignore`); sí se versionaron `consolidada_spark/` (base y ampliación), `consolidada/` (referencia base), `totales_control.csv` (referencia ampliación), la bitácora y la evidencia.

***
7. Lectura en inglés (condición de aceptación 6)

7.1 Resumen técnico en inglés (de 150 a 200 palabras)

Apache Spark is a unified engine for large-scale data processing built on Resilient Distributed Datasets (RDDs), read-only partitioned collections that record their lineage — the series of transformations that built them. Unlike MapReduce, which materializes every intermediate result to disk between map and reduce, RDDs keep data in memory across stages and recover lost partitions by recomputing them from lineage, without replicating data. Transformations (map, reduceByKey, join) build new RDDs lazily; actions (count, collect, write) trigger execution, letting Spark pipeline, fuse, and skip unnecessary work. Because RDDs abstract partitioning, placement, and fault tolerance, a single engine supports batch, interactive queries, streaming, machine learning, and graph processing through libraries (Spark SQL, Structured Streaming, MLlib, GraphX) that compose in one program. Spark persists shuffle output to disk so that lost reduce tasks recompute from shuffle files rather than re-running upstream stages. When cached data exceeds memory, blocks spill to disk (or, with MEMORY_ONLY, are evicted and recomputed). This unification reduces the number of systems to operate and lets libraries share optimization.

Número de palabras del resumen: 168

7.2 Respuestas a las cinco preguntas guía

¿Qué extensión del modelo de MapReduce introducen los RDD y qué cargas de trabajo permiten cubrir que antes requerían motores separados? Los RDD introducen colecciones distribuidas en memoria con linaje (no solo map→escribe→map): permiten iterativo (machine learning), interactivo, grafos y streaming, que antes requerían motores separados (Pregel para grafos, frameworks de ML dedicados, sistemas de streaming), ahora en un solo motor.
¿Qué diferencia hay entre una transformación y una acción? ¿Qué ventaja menciona el artículo de que Spark evalúe de forma perezosa? Una transformación construye un nuevo RDD (perezosa, no ejecuta); una acción dispara el cómputo y devuelve un resultado. La evaluación perezosa deja a Spark optimizar todo el plan, pipelinear y fusionar etapas, y no calcular lo que la acción no necesita.
¿Cómo recupera Spark una partición perdida sin replicar los datos? ¿Qué hace con la salida de una operación de mezcla para este fin? Recomputa la partición desde su linaje (los RDDs padres y las transformaciones). Persiste la salida de la mezcla a disco para que una tarea de reducción perdida se recompute desde los archivos de mezcla en vez de volver a correr las etapas anteriores.
El artículo dice que, si los datos persistidos no caben en memoria, Spark los derrama a disco. Contrasten esa afirmación con lo que vieron en la pestaña Storage: ¿qué ocurre con un RDD en MEMORY_ONLY y qué con un DataFrame? En la pestaña Storage, el DataFrame cacheado quedó en MEMORY_ONLY sin derrame (los 1.800.000 registros cabían). Con MEMORY_ONLY, si no cabe, los bloques se evictan (no se derraman a disco) y se recomputan al usarlos; con MEMORY_AND_DISK sí se derraman a disco. En esta corrida no hubo spill.
¿Qué ventaja ofrece que las bibliotecas de nivel superior (SQL, streaming, aprendizaje automático, grafos) corran sobre el mismo motor? Comparten el mismo RDD, particionado y optimizador; se combinan en un solo programa (p. ej., una consulta SQL que alimenta un modelo de ML), optimización unificada, menos sistemas que operar y menos materialización entre bibliotecas.

7.3 Glosario español e inglés (al menos 10 términos, cada uno con un ejemplo del acueducto en la definición si lo desean)

Término en español | Término en inglés
Partición (las 1.800.000 lecturas se parten en 120 archivos) | Partition
Tarea (cada una suma las lecturas de un sector) | Task
Etapa (la de mapa y la de reducción del reduceByKey) | Stage
Mezcla (agrupar las lecturas por (fecha, sector)) | Shuffle
Transformación (map, reduceByKey, perezosa) | Transformation
Acción (count, collect, write, dispara el cómputo) | Action
RDD (conjunto de datos distribuido resistente con linaje) | Resilient Distributed Dataset
Caché (el DataFrame de lecturas se cachea en memoria) | Cache
Ejecución adaptativa (coalesce las 200 particiones en 1) | Adaptive Query Execution (AQE)
Ejecutor (en local[2], el ejecutor es el controlador) | Executor

***
8. Declaración de uso de asistentes de inteligencia artificial

Se utilizó Claude (Kiro) para implementar los generadores de datos, el pipeline de Spark, el orquestador y el cuaderno, y para redactar el registro de decisiones, este documento y el resumen en inglés. Las cifras provienen de la ejecución real del pipeline sobre el perfil del equipo (equipo-2); no se inventó ningún número. Las decisiones de diseño (número de particiones, reduceByKey, caché, parquet, local[2]) fueron tomadas por el equipo y el asistente las implementó.

***
9. Nivel 3 y reto de diseño, si los abordaron (opcional)

Nivel 3 · carga nocturna de la capa cruda de la ampliación (120 CSV pequeños): no se abordó como corrida nocturna separada; los 120 CSV existen en `datalake_equipo/csv_contraste/` y se leyeron como contraste de formato (ADR-4): parquet (1.9 MiB) se eligió sobre CSV (61 MiB) por disco y parseo; 8 particiones de mezcla (ADR-1); caché MEMORY_ONLY sin spill; presupuesto de memoria: memoria del controlador por defecto (~1 GiB), montón del controlador suficiente para los 1.800.000 registros cacheados, un proceso de Python por núcleo en `local[2]`; pico observado sin derrame a disco. Alternativa descartada: leer los 120 CSV directamente en cada corrida (61 MiB y reparseo, ADR-4).
Reto de diseño · dimensionar el procesamiento de 7,8 GB (30 minutos): no se abordó con corrida real. Cálculo de orden: con un ancho de banda B por ejecutor de ~200 MB/s y un factor de expansión k≈3, P = ⌈S/B⌉ ≈ ⌈7.8 GB / 0.2 GB⌉ ≈ 39 particiones (por ejecutor); con E ejecutores y c núcleos (p. ej., 4×4=16 hilos), olas W = ⌈P/(E·c)⌉ ≈ ⌈39/16⌉ = 3 olas; memoria por tarea ~ (7.8 GB × k)/P ≈ 0.6 GB; umbral de escala: si el pico de memoria por tarea supera la memoria del ejecutor, escalar a clúster; postura razonada: a 7.8 GB en 30 min una máquina única con 16 hilos basta (cola de 3 olas), pero la consolidación del sesgo (sector dominante p) recomienda un clúster para distribuir la partición dominante.
