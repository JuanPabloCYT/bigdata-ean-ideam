# T15 · Carga distribuida del acueducto — Documentación Nivel 3

Sesión 15 · Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Proyecto integrador: Plataforma de datos del acueducto · carga de `maestro_suscriptores`/lecturas con Spark

**Motor:** PySpark 3.5.3 nativo, Java 21 (OpenJDK), `local[2]` (cambio de entorno documentado: Docker apagado y sin perfil s15; el host solo tiene la librería cliente `libpq`, así que se corre Spark en modo nativo, uno de los entornos permitidos por el enunciado).
**Equipo:** `equipo-2`

| Qué | Dónde |
|---|---|
| Generador de la base común | [`practica/s15-carga-spark/generar_base_s15.py`](../practica/s15-carga-spark/generar_base_s15.py) |
| Generador de la ampliación | [`practica/s15-carga-spark/generar_ampliacion_s15.py`](../practica/s15-carga-spark/generar_ampliacion_s15.py) |
| Pipeline de carga (Spark) | [`pipeline/carga_spark.py`](../pipeline/carga_spark.py) |
| Orquestador (todas las corridas) | [`practica/s15-carga-spark/run_t15.py`](../practica/s15-carga-spark/run_t15.py) |
| Cuaderno | [`practica/s15-carga-spark/control_t15.ipynb`](../practica/s15-carga-spark/control_t15.ipynb) |
| Bitácora | [`practica/s15-carga-spark/resultados/bitacora_carga_spark.jsonl`](../practica/s15-carga-spark/resultados/bitacora_carga_spark.jsonl) |
| Evidencia Nivel 2 | [`practica/s15-carga-spark/resultados/evidencia_nivel2_equipo-2.md`](../practica/s15-carga-spark/resultados/evidencia_nivel2_equipo-2.md) |
| Registro de decisiones (ADR) | [`docs/adr_t15.md`](adr_t15.md) |
| Plantilla de entrega | [`docs/T15_plantilla_entrega.md`](T15_plantilla_entrega.md) |

> Ejecutado el 2026-11-18.

## 1. Modelo de datos

Lecturas de medidores del acueducto: `medidor_id`, `fecha`, `sector`, `consumo` (m³, 2 decimales), `quality_flag` (OK/REVISAR). La carga agrega por `(fecha, sector)` sumando `consumo` redondeado a 6 decimales → 480 filas (8 sectores × 60 días).

- **Base común** (`datalake/`): 1.200 medidores por sector (uniforme) → 9.600 medidores × 60 días = 576.000 lecturas; 1.200 lecturas por (sector, día). Referencia `consolidada/` (480 filas).
- **Ampliación** (`datalake_equipo/`, equipo-2): 30.000 medidores, el sector dominante INDUSTRIAL concentra p=0,4 → 12.000 medidores; los demás ~2.571. Lecturas por (sector, día): min=2.571, max=12.000. Total 1.800.000 lecturas. Referencia `totales_control.csv` (480 filas). Disco: 62,6 MiB (parquet cruda 1,9 MiB + CSV de contraste 61 MiB).

## 2. Carga reejecutable y reconciliación

`pipeline/carga_spark.py` lee la capa cruda, agrega con `reduceByKey` y escribe la consolidada con `coalesce(1).write.mode(overwrite).parquet(...)` (un archivo por corrida; el nombre `part-*.parquet` cambia, el contenido no).

- **Reejecutable:** dos corridas por volumen dejan el mismo número de filas (480), las mismas sumas y el mismo hash (base `35ad5b73ee…`, ampliación `27ef88b0f1…`), `diff_max=0`, 0 duplicados.
- **Reconciliación sin filtro de calidad:** 480 vs 480 en ambos volúmenes, `diff_max=0,0 < 1e-6` → cumple. La línea `build_agg` no lleva `where('quality_flag'='OK')`.
- **Contraste filtrado:** el agregado filtrado por `quality_flag='OK'` (547.200 de 576.000 en base; 1.710.000 de 1.800.000 en ampliación) **no** reconcilia, porque descarta las lecturas REVISAR.

## 3. Bitácora y barrido

La bitácora (`bitacora_carga_spark.jsonl`) se llena desde la interfaz REST de Spark (pestaña Stages: `numTasks`, `shuffleWriteBytes`, `shuffleReadBytes`; pestaña Storage: memoria del RDD cacheado). El detalle y las hipótesis/conclusiones están en la evidencia Nivel 2.

- **Barrido de particiones** (3.1): n=4/8/16, tres corridas cada uno. `tareas = entrada + n` (entrada=4, Spark combinó los 120 archivos en 4 particiones). Los bytes de mezcla crecen con n (19.703 → 23.057 → 28.740); el tiempo es estable (~3,7 s) hasta n=16.
- **Tarea que lee más bytes** (3.2): `groupByKey` por sector con 8 particiones (una por sector). La tarea INDUSTRIAL lee 640.932 bytes (4,7× las demás), el sesgo del perfil.
- **AQE** (3.3): con AQE activa, la etapa de reducción coalesce de 200 a 1 tarea; con AQE desactivada, 200 tareas. Lo que se configura (200) no es lo que se ejecuta con AQE.
- **Caché** (ADR-3): 0,6004 s (fría) → 0,0604 s (cacheada), ~9,9×; MEMORY_ONLY sin derrame.

## 4. Decisiones

Ver [`docs/adr_t15.md`](adr_t15.md). Cinco ADR, todos justificados con cifras de la interfaz sobre la ampliación del equipo (ADR-1 número de particiones = n=8; ADR-2 `reduceByKey`; ADR-3 caché; ADR-4 parquet; ADR-5 `local[2]`).

## 5. Contraste con la solución de referencia (T14)

| Decisión del memo (T14) | En la referencia | Qué mantenemos / coincide | Qué cambiaríamos |
|---|---|---|---|
| Nomenclatura de las tablas | `maestro_suscriptores`, `stg_cambios_suscriptor`, `estado_cdc_suscriptores` | coincide: nombres predecibles para que las etapas siguientes los consuman | nada |
| Punto de control (checkpoint) | el mayor `updated_at` leído, con centinela antiguo en la primera corrida | coincide | nada |
| Frontera de la transacción | cambios y punto de control en una sola transacción | coincide | nada |
| Método de captura | consulta por marca temporal + reconciliación periódica para las bajas | coincide | nada |
| Punto ciego de las bajas duras | se mide (bajas generadas frente a capturadas) | coincide | nada |

El memo de T14 ya coincide con la solución de referencia en las cinco filas; se mantienen. T15 no las cambia: trabaja sobre otra fuente (lecturas de medidores) y otra operación (carga distribuida con Spark), no sobre el maestro de suscriptores.

## 6. Reproducción

```bash
cd /Users/camilorojas/Projects/BigData/bigdata-ean-ideam
# 1) Entorno: venv de Python 3.11 con PySpark 3.5.3 y Java 21
source .venv-spark/bin/activate   # o: python3.11 -m venv .venv-spark && pip install pyspark==3.5.3 pyarrow pandas
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export PYSPARK_PYTHON=$PWD/.venv-spark/bin/python
# 2) Regenerar datalake_equipo/ (y la base común)
python practica/s15-carga-spark/generar_base_s15.py
python practica/s15-carga-spark/generar_ampliacion_s15.py --equipo equipo-2
# 3) Correr la carga (base y ampliación) y el barrido completo
python practica/s15-carga-spark/run_t15.py --equipo equipo-2
```

Salida esperada: perfil `medidores=30000 lecturas=1800000 dominante=INDUSTRIAL p=0.4`; carga reejecutable (480 filas, hash estable, `diff_max=0`); barrido `tareas=4+n` (8/12/20 para n=4/8/16); bytes por tarea INDUSTRIAL=640.932 (4,7×); AQE on→1 / off→200; caché 0,60→0,06 s. Las cifras se leen en `practica/s15-carga-spark/resultados/bitacora_carga_spark.jsonl` y en `evidencia_nivel2_equipo-2.md`.

## 7. Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude (Kiro)** para implementar los generadores, el pipeline de Spark, el orquestador, el cuaderno y esta documentación, y para redactar el registro de decisiones y el resumen en inglés. Las cifras provienen de la ejecución real del pipeline sobre el perfil del equipo; no se inventó ningún número.
