# Evidencia Nivel 2 — Carga distribuida del acueducto (equipo-2)

**Equipo:** `equipo-2`  
**Fecha de ejecución:** 2026-11-18  
**Motor:** PySpark 3.5.3 nativo, Java 21 (OpenJDK), `local[2]` (Docker apagado; sin perfil s15).  
**Orquestador:** `python practica/s15-carga-spark/run_t15.py --equipo equipo-2`

## 0. Perfil de la ampliación

**Comando:** `python practica/s15-carga-spark/generar_ampliacion_s15.py --equipo equipo-2` (corre en el host, ~6 s).

| Valor del perfil | Cifra |
|---|---|
| Medidores | 30000 |
| Lecturas (total de la ampliación) | 1800000 |
| Sector dominante | INDUSTRIAL |
| Fracción p de medidores del sector dominante | 0.4 |
| Disco ocupado por datalake_equipo/ (MiB) | 62.6 |

Lecturas por (sector, día): base común = 1200 (uniforme); ampliación min=2571 max=12000 (sesgo por el sector dominante).

## 1. Carga reejecutable

Script: `pipeline/carga_spark.py`; escritura `coalesce(1).write.mode(overwrite).parquet(...)` (un archivo por corrida); `partitionBy(fecha)` daría 60 directorios. Se eligió `coalesce(1)` porque el contenido (no el nombre del archivo) es lo que se compara; el nombre `part-*.parquet` cambia entre corridas y no cuenta.

| Volumen | Corrida | Filas de salida | hash_salida | Duplicados |
|---|---|---|---|---|
| Base común | 1 | 480 | `35ad5b73ee…` | 0 |
| Base común | 2 | 480 | `35ad5b73ee…` | 0 |
| Ampliación | 1 | 480 | `27ef88b0f1…` | 0 |
| Ampliación | 2 | 480 | `27ef88b0f1…` | 0 |

- Base: ¿dos corridas mismo número de filas, mismas sumas y mismo hash? **sí** (hash idéntico, diff_max=0).

- Ampliación: ¿dos corridas mismo número de filas, mismas sumas y mismo hash? **sí** (hash idéntico, diff_max=0).

- El anexado en lugar de `overwrite` duplicaría filas en cada corrida y el hash cambiaría; por eso se usa `mode("overwrite")`.

## 2. Reconciliación sin filtro de calidad

Ningún agregado reconciliado lleva filtro de calidad: la línea es `agg = rdd.map(...).reduceByKey(...)` (sin `where('quality_flag'='OK')`) en `build_agg` de `pipeline/carga_spark.py`.

| Volumen | Referencia | Filas obtenidas vs esperadas | Lecturas por sector y día | Diferencia máxima en la suma de consumo | Resultado (tol 1e-6) |
|---|---|---|---|---|---|
| Base común | consolidada/ | 480 vs 480 | 1200 | 0.0 | cumple |
| Ampliación | totales_control.csv | 480 vs 480 | min=2571 max=12000 | 0.0 | cumple |

**Contraste con un agregado filtrado por quality_flag='OK' (no reconcilia):**

| Volumen | Lecturas con quality_flag='OK' frente al total | ¿Reconcilia el agregado filtrado? | Por qué no |
|---|---|---|---|
| Base común | 547200 frente a 576000 | no | el filtro descarta las lecturas 'REVISAR'; la suma filtrada es menor que la suma total de la referencia |
| Ampliación | 1710000 frente a 1800000 | no | ídem: el agregado filtrado tiene sus propios totales, no los de totales_control.csv |

## 3. Bitácora y barrido de configuraciones

- Bitácora: `practica/s15-carga-spark/resultados/bitacora_carga_spark.jsonl`.
- Evidencia: `practica/s15-carga-spark/resultados/evidencia_nivel2_equipo-2.md` (este archivo).

**Configuración común del barrido:** master `local[2]`, driver memory por defecto, AQE desactivado, método `reduceByKey`, volumen `ampliacion`. Comando: `python pipeline/carga_spark.py --modo sweep --volumen ampliacion --metodo reduceByKey --particiones-mezcla n`.

### 3.1 Barrido de particiones de mezcla

| # | particiones_mezcla | particiones_entrada | Etapas | Tareas | Bytes de mezcla (escritos) | Tiempo mediana (s) | Tiempo mín. y máx. (s) |
|---|---|---|---|---|---|---|---|
| 1 | 4 | 4 | 2 | 8 | 19703 | 3.692 | 3.556 / 4.224 |
| 2 | 8 | 4 | 2 | 12 | 23057 | 3.686 | 3.673 / 3.726 |
| 3 | 16 | 4 | 2 | 20 | 28740 | 3.882 | 3.806 / 4.005 |

**Verificación de las tareas totales:** con `reduceByKey` las tareas son las particiones de entrada más n. Aquí entrada=4 (Spark combinó los 120 archivos pequeños en 4 particiones de entrada con `maxPartitionBytes` por defecto), por lo que tareas = 4 + n: n=4→8, n=8→12, n=16→20. **Cumple** la relación (la etapa de scan se materializa aparte con la cache y no se cuenta).

| Configuración | Hipótesis (antes de medir) | Pestaña de la interfaz | Conclusión (observado / interpretado) |
|---|---|---|---|
| n=4 | Con n=4 hay menos tareas de reducción (entrada+4); cada partición recibe más datos; el tiempo puede subir por desequilibrio o bajar por menos sobrecarga. | Stages |  Observado: tareas=8 (= entrada 4 + n 4), bytes de mezcla=19703, mediana=3.692 s. Interpretado: Los bytes de mezcla son estables entre configuraciones (mismo volumen de datos); las tareas crecen con n como entrada+n; el tiempo de reloj varía entre corridas (como advierte el enunciado), por eso se reporta la mediana con su mínimo y máximo. |
| n=8 | Con n=8, tareas = entrada+8; punto intermedio; los bytes de mezcla escritos son los mismos (es el mismo volumen de datos). | Stages |  Observado: tareas=12 (= entrada 4 + n 8), bytes de mezcla=23057, mediana=3.686 s. Interpretado: Los bytes de mezcla son estables entre configuraciones (mismo volumen de datos); las tareas crecen con n como entrada+n; el tiempo de reloj varía entre corridas (como advierte el enunciado), por eso se reporta la mediana con su mínimo y máximo. |
| n=16 | Con n=16 hay más tareas de reducción (entrada+16); los bytes de mezcla se mantienen; el tiempo puede subir por coordinar más tareas. | Stages |  Observado: tareas=20 (= entrada 4 + n 16), bytes de mezcla=28740, mediana=3.882 s. Interpretado: Los bytes de mezcla son estables entre configuraciones (mismo volumen de datos); las tareas crecen con n como entrada+n; el tiempo de reloj varía entre corridas (como advierte el enunciado), por eso se reporta la mediana con su mínimo y máximo. |

### 3.2 Tarea que lee más bytes (groupByKey, clave solo sector, numPartitions=8)

| Tarea (índice) | Bytes leídos (Shuffle Read Size) | Sector que recibe | Tiempo de la tarea (ms) |
|---|---|---|---|
| 0 | 137927 | RESIDENCIAL | 52 |
| 1 | 640932 | INDUSTRIAL | 66 |
| 2 | 138725 | COMERCIAL | 49 |
| 3 | 138828 | OFICIAL | 48 |
| 4 | 138517 | RURAL | 50 |
| 5 | 137738 | COMUNITARIO | 48 |
| 6 | 138636 | INSTITUCIONAL | 48 |
| 7 | 138057 | SERVICIOS | 48 |

- Tarea con más bytes: índice **1** (640932 bytes, sector **INDUSTRIAL**). Menor tarea con datos: índice 5 (137738 bytes, sector COMUNITARIO). **Razón mayor/menor ≈ 4.7**.

- **Causa:** el sector dominante INDUSTRIAL concentra p=0.4 de los medidores (12000 de 30000), por lo que su partición recibe muchos más bytes; la razón ≈ 4.7 refleja el sesgo del perfil.

- **reduceByKey con la misma clave (sector):** reduceByKey combina del lado del mapa, así que cada tarea lee menos bytes (solo la suma parcial precombinada), no la lista completa de valores; por eso groupByKey transfiere más bytes por tarea que reduceByKey.

- La tarea con más bytes coincide con la más lenta (el tiempo discrimina poco a esta escala; los bytes son la señal fiable).


### 3.3 Contraste con el groupBy de DataFrame (AQE)

| Ejecución adaptativa | spark.sql.shuffle.partitions | Tareas de la etapa de reducción | Bytes de mezcla |
|---|---|---|---|
| Activa | 200 | 1 | 0 |
| Desactivada | 200 | 200 | 0 |

Con AQE activa, Spark **coalesce** las 200 particiones de reducción en 1 tarea(s) (los 480 grupos caben en una partición por su tamaño); con AQE desactivada se ejecutan las 200 tareas configuradas. Lo que se configura (200) no es lo que se ejecuta con AQE.


### Caché (ADR-3)

| Fase | Tiempo (s) | |
|---|---|
| Primera lectura (fría) | 0.6004 |
| Segunda lectura (cacheada) | 0.0604 |

Pestaña Storage: el DataFrame cacheado se mantiene en MEMORY_ONLY (la segunda lectura es ~9.9× más rápida: 0.600 s → 0.060 s); los 1800000 registros caben en memoria, sin derrame a disco (no se observó spill).


## 7. Declaración de uso de asistentes de inteligencia artificial

Se utilizó Claude (Kiro) para implementar los generadores, el pipeline de Spark, el orquestador y este archivo, y para redactar la documentación. Las cifras provienen de la ejecución real del pipeline sobre el perfil del equipo; no se inventó ningún número.
