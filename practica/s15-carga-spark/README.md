# Práctica S15 · Carga distribuida del acueducto

Sesión 15 · Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Proyecto integrador: Plataforma de datos del acueducto · carga de lecturas con Spark

Carga distribuida y reejecutable de las lecturas de medidores: agrega `consumo`
por `(fecha, sector)` con `reduceByKey`, reconcilia contra la referencia y hace
un barrido de configuraciones con la bitácora leída de la interfaz de Spark.

## Motor de ejecución

**PySpark 3.5.3 nativo, Java 21 (OpenJDK), `local[2]`.** Docker estaba apagado y
no había perfil s15; el host solo tiene la librería cliente `libpq`, sin servidor
de PostgreSQL. Se documenta el cambio a PySpark nativo (entorno permitido por el
enunciado). Las cifras de la interfaz de Spark se obtienen vía la API REST de la
UI (`/api/v1/applications/{id}/stages`, `?details=true` para tareas).

## Qué hay aquí

| Archivo | Qué es |
|---|---|
| `generar_base_s15.py` | Genera la base común (datalake/, 576.000 lecturas, 480 grupos, 1.200/sector/día) |
| `generar_ampliacion_s15.py` | Genera la ampliación por `--equipo` (datalake_equipo/, 120 parquet + 120 CSV + totales_control.csv) |
| `modelo_s15.py` | Dimensiones y perfil por equipo (compartido) |
| `run_t15.py` | Orquestador: corre las 18 corridas y genera la evidencia |
| `generar_evidencia_t15.py` | Lee la bitácora y escribe `resultados/evidencia_nivel2_equipo-2.md` |
| `control_t15.ipynb` | Cuaderno |
| `resultados/bitacora_carga_spark.jsonl` | Bitácora (tareas, bytes de mezcla, tiempo por configuración) |
| `resultados/evidencia_nivel2_equipo-2.md` | Evidencia Nivel 2 |
| `resultados/run_results.jsonl` | Resultado (RESULT) de cada corrida |
| `resultados/logs/` | Logs de cada corrida (no se versionan) |

Pipeline: [`pipeline/carga_spark.py`](../../pipeline/carga_spark.py)
Documentación Nivel 3: [`docs/T15_carga_spark.md`](../../docs/T15_carga_spark.md)
Registro de decisiones: [`docs/adr_t15.md`](../../docs/adr_t15.md)
Plantilla de entrega: [`docs/T15_plantilla_entrega.md`](../../docs/T15_plantilla_entrega.md)

## Reproducción

```bash
cd /Users/camilorojas/Projects/BigData/bigdata-ean-ideam
# 1) Entorno de Spark (Python 3.11 + Java 21)
python3.11 -m venv .venv-spark && .venv-spark/bin/pip install pyspark==3.5.3 pyarrow pandas
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export PYSPARK_PYTHON=$PWD/.venv-spark/bin/python
# 2) Datos
python practica/s15-carga-spark/generar_base_s15.py
python practica/s15-carga-spark/generar_ampliacion_s15.py --equipo equipo-2
# 3) Todo (carga + barrido + bytes/AQE/caché/CSV) y evidencia
python practica/s15-carga-spark/run_t15.py --equipo equipo-2
```

Salida esperada (equipo-2): perfil `medidores=30000 lecturas=1800000 dominante=INDUSTRIAL p=0.4`;
carga reejecutable (480 filas, hash estable, `diff_max=0`); barrido `tareas=4+n`
(8/12/20 para n=4/8/16); bytes por tarea INDUSTRIAL=640932 (4,7×); AQE on→1 /
off→200; caché 0,60→0,06 s. Las cifras se leen en `resultados/bitacora_carga_spark.jsonl`
y `resultados/evidencia_nivel2_equipo-2.md`.

## Qué se versiona

Sí: `consolidada_spark/` (base y ampliación), `consolidada/` y `totales_control.csv`
(referencias), la bitácora y la evidencia, el código. No: `cruda/`, `csv_contraste/`
y `resultados/logs/` (en `.gitignore`); ningún `.zip`.
