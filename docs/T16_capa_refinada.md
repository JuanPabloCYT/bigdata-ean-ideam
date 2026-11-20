# T16 · Capa refinada con esquema declarado — Documentación Nivel 3

Sesión 16 · Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Proyecto integrador: Plataforma de datos del acueducto · Hito B

**Motor:** PySpark 3.5.3 nativo, Java 21, `local[2]` (mismo entorno que T15; Docker apagado).
**Equipo:** `equipo-2` · 30.000 medidores · 3.600.000 lecturas · INDUSTRIAL p=0,40 · 120 días.

| Qué | Dónde |
|---|---|
| Generador de capas | [`practica/s16-refinada-spark/generar_capas_s16.py`](../practica/s16-refinada-spark/generar_capas_s16.py) |
| Pipeline refinada | [`pipeline/refinada_spark.py`](../pipeline/refinada_spark.py) |
| Reproceso | [`pipeline/reproceso_spark.py`](../pipeline/reproceso_spark.py) |
| Verificador | [`pipeline/verificar_etapa.py`](../pipeline/verificar_etapa.py) |
| Cuaderno | [`practica/s16-refinada-spark/control_t16.ipynb`](../practica/s16-refinada-spark/control_t16.ipynb) |
| Bitácora | [`practica/s16-refinada-spark/resultados/bitacora_refinada_spark.jsonl`](../practica/s16-refinada-spark/resultados/bitacora_refinada_spark.jsonl) |
| Evidencia Nivel 2 | [`practica/s16-refinada-spark/resultados/evidencia_nivel2_equipo-2.md`](../practica/s16-refinada-spark/resultados/evidencia_nivel2_equipo-2.md) |
| ADR | [`docs/adr_t16.md`](adr_t16.md) |
| Plantilla diligenciada | [`docs/T16_plantilla_entrega.md`](T16_plantilla_entrega.md) |

## 1. Modelo de datos

6 columnas: `meter_id` (LongType), `timestamp` (TimestampType, INT64 ns UTC), `sector` (StringType), `consumo_m3` (DoubleType), `presion_bar` (DoubleType), `quality_flag` (StringType). La columna `fecha` se deriva en la escritura (`to_date(timestamp)`) y se usa como clave de partición.

Base común: 4.800 medidores × 120 días = 576.000 lecturas. Ampliación equipo-2: 30.000 medidores × 120 días = 3.600.000 lecturas.

## 2. Esquema declarado y calidad de la lectura

`ESQUEMA_CRUDA` en `pipeline/refinada_spark.py` es el contrato versionado. Con `enforceSchema=true` y `mode=DROPMALFORMED`, las filas no conformes se cuentan y se descartan; en base y ampliación `filas_no_conformes = 0` y `nulos_por_columna = 0` en todas las columnas.

## 3. Capa reejecutable y reconciliación

Dos corridas por volumen producen hash idéntico (`1343bc1b…` para la base, `1297856b…` para la ampliación). Reconciliación exacta (`diff_max = 0,0`) contra las referencias de 960 grupos (fecha × sector) y 1.920 grupos (fecha × sector × quality_flag).

## 4. Variantes de clasificación de presión

Tres formas de clasificar `presion_bar` en baja/normal/alta, medidas en dos condiciones (CSV y columna en memoria). Resultado idéntico en las tres (baja=234.960, normal=1.565.520, alta=1.799.520). La nativa y la vectorizada empatan en ambas condiciones; la UDF por fila es 10,8× más lenta en CPU (condición B). Se adopta la nativa. Ver ADR-4 y sección 3.2 de la plantilla.

## 5. Reproceso

Ventana de 6 días (2026-01-01 a 2026-01-06) sobre una copia de la base. Sobrescritura dinámica: 576.000 filas conservadas, 114 particiones intactas, 6 reescritas, 0 perdidas. Sobrescritura estática: 28.800 filas (6 × 4.800), 114 particiones perdidas. Se adopta dinámica.

## 6. Cierre diario

`groupBy("fecha","sector").sum("consumo_m3")` sobre `refinada_spark/`: 2 etapas, 12 tareas, 20.402 bytes de mezcla. Comparable al RDD de T15 (19.703 bytes), ambos en la misma banda. Ver sección 3.4.

## 7. Verificación

```
Etapa T16: APROBADA (15 de 15 comprobaciones, 0.4 s)
```

## 8. Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude (Kiro)** para implementar los generadores, el pipeline, el verificador, el reproceso, el cuaderno y esta documentación. Las cifras provienen de la ejecución real; no se inventó ningún número.
