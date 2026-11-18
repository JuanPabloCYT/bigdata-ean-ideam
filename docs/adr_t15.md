# T15 · Registro de decisiones de arquitectura (ADR)

**Equipo:** `equipo-2` · **Fecha:** 2026-11-18
**Volumen de la ampliación:** 30.000 medidores, 1.800.000 lecturas, sector dominante INDUSTRIAL (p=0,4), 8 sectores × 60 días = 480 grupos.
**Motor:** PySpark 3.5.3 nativo, Java 21, `local[2]`.
**Evidencia:** [`practica/s15-carga-spark/resultados/evidencia_nivel2_equipo-2.md`](../practica/s15-carga-spark/resultados/evidencia_nivel2_equipo-2.md)

Formato: Nygard (2011). Cada decisión justificada declara una alternativa descartada con su costo. Capturas: no se usan; las cifras vienen de la interfaz de Spark (pestaña Stages / Storage) leídas por la bitácora `bitacora_carga_spark.jsonl`.

---

## ADR-1 · Número de particiones (obligatoria)

**Estado:** aceptada
**Contexto:** se decide `spark.sql.shuffle.partitions` (particiones de mezcla) para el `reduceByKey` sobre la ampliación. La pregunta: con 480 grupos y un sector dominante (p=0,4), ¿cuántas particiones de reducción conviene?
**Opciones:** n=4, n=8, n=16 (barrido de la sección 3.1, tres corridas cada una).
**Evidencia (Stages, ampliación):**

| n | particiones_entrada | Tareas | Bytes de mezcla | Tiempo mediana (s) |
|---|---|---|---|---|
| 4 | 4 | 8 | 19.703 | 3,692 |
| 8 | 4 | 12 | 23.057 | 3,686 |
| 16 | 4 | 20 | 28.740 | 3,882 |

Las tareas = entrada (4) + n (verificado: 8, 12, 20). Los bytes de mezcla crecen con n; el tiempo es estable hasta n=16 (+5 %).
**Decisión:** **n=8**. Reparte los 480 grupos en 8 particiones, limita el tamaño de la partición del sector dominante (que recibe 4,7× los bytes de las demás) y evita el sobrecosto de n=16 (más tareas y más shuffle sin ganar en tiempo).
**Alternativa descartada y su costo:** n=16 — 28.740 bytes de mezcla (+25 % sobre n=8) y 20 tareas (+67 %), con +5 % de tiempo y sin beneficio a esta escala.
**Consecuencias:** se gana una partición por sector dominante acotada; se arriesga a que con muy pocos grupos la sobrecarga de 8 particiones no se amortice.
**Cifra que obligaría a revisarla:** si el volumen crece hasta que los bytes de mezcla por partición superen la memoria, o si la fracción p del sector dominante crece (más sesgo), revisar n al alza (más particiones) o cambiar de particionador.

## ADR-2 · Operación de agregación

**Estado:** aceptada
**Contexto:** se decide entre `reduceByKey` y `groupByKey` para sumar `consumo` por (fecha, sector). La pregunta: ¿vale la pena el combine del lado del mapa?
**Opciones:** `reduceByKey` (combine map-side) frente a `groupByKey` (transfiere todos los valores).
**Evidencia (Stages, bytes por tarea, sección 3.2):** con `groupByKey` por sector (8 particiones), la tarea del sector dominante INDUSTRIAL lee **640.932 bytes** (shuffle read); las demás leen ~138.000 (razón 4,7). `reduceByKey` combina del lado del mapa y transfiere solo la suma parcial, no la lista completa de valores.
**Decisión:** **`reduceByKey`**. La suma es asociativa y conmutativa, así que el combine map-side reduce los bytes de mezcla y la tarea del sector dominante transfiere menos.
**Alternativa descartada y su costo:** `groupByKey` — la tarea dominante transfiere 640.932 bytes (la lista de valores, no la suma); más red y más memoria por tarea.
**Consecuencias:** menos mezcla y menos memoria; se arriesga a que, si la agregación no fuera asociativa, el combine daría resultados erróneos.
**Cifra que obligaría a revisarla:** si la agregación deja de ser asociativa/conmutativa (p. ej., mediana o recolección de los valores), volver a `groupByKey`.

## ADR-3 · Uso de caché

**Estado:** aceptada
**Contexto:** se decide si cachear la capa cruda leída. La pregunta: ¿se relee el parquet en cada corrida del barrido o se cachea?
**Opciones:** cachear (MEMORY_ONLY) frente a releer el parquet en cada acción.
**Evidencia (Storage, sección caché):** primera lectura (fría) **0,6004 s**; segunda lectura (cacheada) **0,0604 s** (**~9,9×** más rápida); los 1.800.000 registros caben en memoria (MEMORY_ONLY, sin derrame a disco).
**Decisión:** **cachear el DataFrame de entrada** (MEMORY_ONLY) cuando se van a hacer varias pasadas (barrido, ADR), porque la segunda lectura es ~10× más rápida y los datos caben en memoria.
**Alternativa descartada y su costo:** no cachear — releer el parquet cuesta 0,6 s por acción; en un barrido de 9 corridas son ~5,4 s de más.
**Consecuencias:** se gana velocidad en pasadas repetidas; se arriesga a OOM si los datos no caben (aquí caben).
**Cifra que obligaría a revisarla:** si el volumen supera la memoria del controlador (spill a disco), pasar a MEMORY_AND_DISK o no cachear.

## ADR-4 · Formato de entrada

**Estado:** aceptada
**Contexto:** se decide el formato de la capa cruda: parquet o CSV. La pregunta: ¿conviene leer parquet columnar o CSV de texto?
**Opciones:** parquet (`datalake_equipo/cruda/`) frente a CSV (`datalake_equipo/csv_contraste/`), mismo `reduceByKey` n=8.
**Evidencia (Stages + disco):** la capa cruda parquet ocupa **1,9 MiB**; el CSV equivalente **61 MiB** (~32× más). El tiempo de reloj es similar (parquet 3,69 s, CSV 3,48 s; dentro del ruido de reloj del enunciado), porque a 1,8 M filas la agregación domina y el parseo es rápido, pero parquet evita reparsear y es 32× más pequeño en disco.
**Decisión:** **parquet** (columnar, comprimido, con esquema). Para cargas repetidas escala mejor: menos disco, menos parseo, tipos preservados.
**Alternativa descartada y su costo:** CSV — 61 MiB (~32×) y se reparsea en cada lectura; útil para intercambio, costoso para lectura repetida.
**Consecuencias:** menos disco y menos CPU de parseo; se arriesga a que, si la fuente solo entrega CSV, haya que convertir.
**Cifra que obligaría a revisarla:** si la fuente deja de entregar parquet y solo CSV, aceptar CSV o convertir una sola vez a parquet.

## ADR-5 · Tamaño de ejecutores y núcleos (en local: local[N] y memoria del controlador)

**Estado:** aceptada
**Contexto:** se decide el `master` (`local[N]`) y la memoria del controlador para correr en el host (Docker apagado). La pregunta: ¿cuántos núcleos y cuánta memoria?
**Opciones:** `local[1]`, `local[2]`, `local[*]`; memoria del controlador por defecto (~1 GiB).
**Evidencia (pestaña Executors):** en `local[2]` hay un único ejecutor (el controlador) con 2 núcleos; los 1,8 M registros y la caché caben en la memoria por defecto (sin spill).
**Decisión:** **`local[2]`** con memoria por defecto. 2 núcleos dan paralelismo suficiente para 1,8 M filas (la etapa de reducción de n=8 corre en 2 núcleos) sin saturar el portátil; la caché cabe.
**Alternativa descartada y su costo:** `local[1]` — sin paralelismo (las tareas de reducción corren en serie, más lento); `local[*]` — todos los núcleos, pero compite con el sistema operativo del host.
**Consecuencias:** paralelismo moderado y reproducible; se arriesga a que con más núcleos el controlador se quede sin memoria.
**Cifra que obligaría a revisarla:** si el volumen o la caché superan la memoria del controlador (OOM/spill), reducir el cacheo o pasar a un clúster con ejecutores separados.

---

**Decisiones justificadas en total:** 5 (mínimo 3, una de ellas la ADR-1). Todas con cifras de la interfaz sobre la ampliación del equipo.
