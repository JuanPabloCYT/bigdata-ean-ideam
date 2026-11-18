# Evidencia Nivel 2 — CDC del maestro de suscriptores (equipo-2)

**Equipo:** `equipo-2`  
**Fecha de ejecución:** 2026-11-18  
**Motor:** DuckDB embebido 2.0.0  
**Comando:** `python prototipo_cdc_suscriptores.py --equipo equipo-2`

## 0. Perfil de cambios del equipo

**Comando exacto:** `python generar_cambios_suscriptores.py --equipo equipo-2`

| Valor del perfil | Cifra que reporta el generador |
|---|---|
| total_suscriptores | 160 |
| Número de cambios | 42 |
| n_alta | 14 |
| n_modificacion | 18 |
| n_baja | 10 |
| prob_baja_dura | 0.0625 |

## 1. Las tres tablas y la carga inicial

- `maestro_suscriptores` (tabla fuente): confirmado.
- `stg_cambios_suscriptor` (staging de cambios capturados): confirmado.
- `estado_cdc_suscriptores` (checkpoint): confirmado.
- Filas cargadas en `maestro_suscriptores` tras la población inicial: **160**.

## 2. Evidencia cuantitativa del punto ciego

Corrida ANTES del flujo (checkpoint nulo → captura toda la población inicial como ALTAS): capturadas = 160 (altas=160, modif=0, bajas=0). Checkpoint tras la corrida: `2026-11-18 08:00:00` (fecha de la población inicial).

Flujo de cambios aplicado al maestro con `updated_at = T1 = 2026-11-18 12:00:00` (altas + modificaciones + bajas duras).

| Tipo de cambio | Generadas (perfil) | Capturadas por el prototipo |
|---|---:|---:|
| Altas | 14 | 14 |
| Modificaciones | 18 | 18 |
| Bajas duras | 10 | 0 |

Las altas y modificaciones capturadas igualan a las generadas; las **bajas duras capturadas = 0** sin importar cuántas se generaron (aquí 10).

- **Diferencia entre lo que ve el destino y lo que hay en el origen:** el destino, reconstruyendo el maestro con solo lo capturado, ve **174** suscriptores; el maestro real tiene **164**. Diferencia = **10** (= n_baja = 10).

- **Por qué es estructural y no un error del prototipo:** la CDC basada en consulta filtra con `updated_at > checkpoint`. Una baja dura elimina la fila del origen, por lo que esa llave deja de existir y nunca satisface el predicado: no hay `updated_at` que supere el checkpoint porque la fila ya no está. El método no tiene forma de enterarse de algo que dejó de existir. No es un bug de implementación; es la definición del sondeo con marca de agua.

- **Caso de cero bajas por redondeo:** no aplica a este equipo. prob_baja_dura = 0.0625 = 10/160 es exacta (sin redondeo) y produce n_baja = 10 ≠ 0.

### 2.1 Repetición con el checkpoint restablecido

Se restablece el checkpoint a la fecha de la población inicial (`2026-11-18 08:00:00`) y se repite la corrida de captura.

- Filas en `stg_cambios_suscriptor` antes de repetir: 192.
- Re-capturadas: 32 (altas=14, modif=18, bajas=0).
- **Filas duplicadas** en `stg_cambios_suscriptor` tras repetir: **32** (= altas + modificaciones = 14 + 18 = 32).
- **Filas sobrantes por pareja (subscriber_id, tipo_cambio):** **32** (cada pareja del flujo aparece dos veces; las de la población inicial siguen una).
- **Checkpoint tras la repetición:** `2026-11-18 12:00:00` (vuelve a la fecha del flujo de cambios, T1).

**Decisión para evitar los duplicados:** el checkpoint debe avanzar de forma monótona con `greatest(checkpoint_actual, max(updated_at))` (nunca retroceder) y la inserción en el staging debe ser idempotente con `ON CONFLICT (subscriber_id, updated_at) DO NOTHING`, ya que `(subscriber_id, updated_at)` identifica unívocamente un evento de cambio. Así, una re-captura tras un reseteado erróneo es un no-op en vez de un duplicador. Como alternativa más simple, un margen de solapamiento acotado (re-procesar los últimos N segundos) combinado con la misma llave única también elimina los duplicados. El prototipo, para evidenciar el problema, usa un INSERT puro (sin la guarda).

## 3. Funciones de costo y comparación de alternativas

Parámetros del equipo: M = total_suscriptores = 160; T (sondeo) = 60 s; B (reconciliación) = 4/día. La ventana de cambios se modela como un día de actividad → 42 cambios/día.

**Cuatro funciones de costo:**

- `N = 86400 / T` → consultas por día en sondeo = **1440**.
- `K = M × B` → llaves leídas por día en reconciliación (full-scan) = **640**.
- `L_sondeo = T` → latencia máxima de una baja en sondeo = **60 s**.
- `L_recon = 86400 / B` → latencia máxima de una baja en reconciliación = **21600 s**.

**bajas_detectadas por reconciliación sobre la base del equipo:** **10** ids = [19, 20, 21, 22, 23, 24, 25, 26, 27, 28] (= bajas generadas por el perfil = 10).

**Tabla `comparacion`:**

| alternativa | detecta_bajas | intervalo_sondeo_s | barridos_por_dia | consultas_por_dia | llaves_leidas_por_dia | latencia_max_baja_s |
|---|---|---|---|---|---|---|
| Bandera de baja lógica en el origen | sí | 60 | 1440 | 1440 | 42 | 60 |
| Reconciliación periódica de conjunto completo | sí | 21600 | 4 | 4 | 640 | 21600 |
| CDC basada en registro de transacciones | sí | 0 | 0 | 0 | 42 | 0 |

*Nota sobre llaves_leidas_por_dia:* el sondeo con marca de agua lee solo el delta del cambio (no M por barrido), por eso la bandera lógica y la CDC por registro leen 42 llaves/día; la reconciliación sí barre el maestro completo (M×B = 640).

## 4. Decisión (resumen del ADR)

Ver el memo ADR en `docs/memo_adr_t14.md`. Decisión: **estrategia híbrida** (CDC basada en consulta con marca de agua para altas/modificaciones + reconciliación periódica de conjunto completo cada 6 h para las bajas duras).

## 5. Integración con el proyecto integrador

- `stg_lecturas` (T12): append-only (solo agrega filas; nunca actualiza ni borra). La CDC es incremental por marca de agua sobre `fechaobservacion`; **no tiene punto ciego de bajas** porque no hay bajas.
- `stg_estado_medidor` (T13): estado paginado vía API con UPSERT por `meter_id`; el mock no expone bajas. CDC por sondeo de API + UPSERT idempotente; **sin punto ciego de bajas** en el perfil del mock.
- `maestro_suscriptores` (T14): **única** de las tres fuentes con bajas duras reales (prob_baja_dura = 0.0625, 10 bajas). Es la única que requiere la reconciliación/híbrida; su CDC es la más costosa de las tres.

## 6. Reproducción

```bash
cd /Users/camilorojas/Projects/BigData/bigdata-ean-ideam
source .venv/bin/activate && pip install duckdb
python practica/s14-cdc-suscriptores/generar_cambios_suscriptores.py --equipo equipo-2
python practica/s14-cdc-suscriptores/prototipo_cdc_suscriptores.py --equipo equipo-2
```

## 7. Declaración de uso de asistentes de inteligencia artificial

Se utilizó Claude (Kiro) para implementar el generador, el prototipo, el DDL y la redacción del memo y esta evidencia. Las cifras provienen de la ejecución real del prototipo sobre el perfil del equipo; no se inventó ningún número.
