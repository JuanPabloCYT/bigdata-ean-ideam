# Práctica S16 · Capa refinada con esquema declarado

Sesión 16 · Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Proyecto integrador: Plataforma de datos del acueducto · Hito B

Construye la capa refinada desde los CSV crudos con esquema declarado y
`enforceSchema=true`, escribe particionado por fecha, reconcilia contra las
referencias y mide las tres formas de clasificar `presion_bar`. Registra cada
corrida en `bitacora_refinada_spark.jsonl`.

## Motor de ejecución

**PySpark 3.5.3 nativo, Java 21 (OpenJDK), `local[2]`.** Docker apagado, sin
perfil s16; mismo entorno que T15. Las cifras de la interfaz de Spark se obtienen
vía la API REST (igual que T15).

## Qué hay aquí

| Archivo | Qué es |
|---|---|
| `modelo_s16.py` | Dimensiones, perfiles y funciones compartidas |
| `generar_capas_s16.py` | Genera cruda_t16/, refinada/ y referencias |
| `generar_evidencia_t16.py` | Lee la bitácora y escribe `resultados/evidencia_nivel2_equipo-2.md` |
| `control_t16.ipynb` | Cuaderno |
| `resultados/bitacora_refinada_spark.jsonl` | Bitácora de todas las corridas |
| `resultados/evidencia_nivel2_equipo-2.md` | Evidencia Nivel 2 |
| `resultados/mediciones_nivel1.csv` | Tabla de mediciones del Nivel 1 |

Pipeline: [`pipeline/refinada_spark.py`](../../pipeline/refinada_spark.py)
Reproceso: [`pipeline/reproceso_spark.py`](../../pipeline/reproceso_spark.py)
Verificador: [`pipeline/verificar_etapa.py`](../../pipeline/verificar_etapa.py)
ADR: [`docs/adr_t16.md`](../../docs/adr_t16.md)
Plantilla: [`docs/T16_plantilla_entrega.md`](../../docs/T16_plantilla_entrega.md)
Doc Nivel 3: [`docs/T16_capa_refinada.md`](../../docs/T16_capa_refinada.md)

## Reproducción

```bash
cd /Users/camilorojas/Projects/BigData/bigdata-ean-ideam
source .venv-spark/bin/activate && pip install pyspark==3.5.3 pyarrow pandas
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export PYSPARK_PYTHON=$PWD/.venv-spark/bin/python

# 1) Generar capas (cruda, heredada, referencias)
python practica/s16-refinada-spark/generar_capas_s16.py --volumen base
python practica/s16-refinada-spark/generar_capas_s16.py --volumen ampliacion --equipo equipo-2

# 2) Capa refinada base (dos corridas para verificar reproducibilidad)
python pipeline/refinada_spark.py --equipo equipo-2 --volumen base --modo refinada
python pipeline/refinada_spark.py --equipo equipo-2 --volumen base --modo refinada

# 3) Capa refinada ampliación (dos corridas)
python pipeline/refinada_spark.py --equipo equipo-2 --volumen ampliacion --modo refinada
python pipeline/refinada_spark.py --equipo equipo-2 --volumen ampliacion --modo refinada

# 4) Variantes de clasificación
python pipeline/refinada_spark.py --equipo equipo-2 --volumen ampliacion --modo variantes

# 5) Cierre diario
python pipeline/refinada_spark.py --equipo equipo-2 --volumen ampliacion --modo cierre_diario

# 6) Reproceso
python pipeline/reproceso_spark.py --equipo equipo-2 --sobrescritura estatica
python pipeline/reproceso_spark.py --equipo equipo-2 --sobrescritura dinamica

# 7) Generar evidencia
python practica/s16-refinada-spark/generar_evidencia_t16.py --equipo equipo-2

# 8) Verificar
python pipeline/verificar_etapa.py --etapa t16
```

Resultado esperado del paso 8: `Etapa T16: APROBADA (15 de 15 comprobaciones, 0.4 s)`.
