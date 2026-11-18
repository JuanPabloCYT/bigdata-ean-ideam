# T14 · CDC del maestro de suscriptores — Documentación Nivel 3

Sesión 14 · Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Proyecto integrador: Plataforma de datos del acueducto · fuente `maestro_suscriptores`

**Motor:** DuckDB embebido 2.0.0 (cambio documentado frente al perfil s12 en Docker)
**Generador:** [practica/s14-cdc-suscriptores/generar_cambios_suscriptores.py](../practica/s14-cdc-suscriptores/generar_cambios_suscriptores.py)
**Prototipo:** [practica/s14-cdc-suscriptores/prototipo_cdc_suscriptores.py](../practica/s14-cdc-suscriptores/prototipo_cdc_suscriptores.py)
**Cuaderno:** [practica/s14-cdc-suscriptores/control_t14.ipynb](../practica/s14-cdc-suscriptores/control_t14.ipynb)
**DDL:** [sql/T14_cdc_suscriptores.sql](../sql/T14_cdc_suscriptores.sql)
**Memo ADR:** [docs/memo_adr_t14.md](memo_adr_t14.md)
**Evidencia Nivel 2:** [practica/s14-cdc-suscriptores/resultados/evidencia_nivel2_equipo-2.md](../practica/s14-cdc-suscriptores/resultados/evidencia_nivel2_equipo-2.md)

> Ejecutado el 2026-11-18 · Equipo `equipo-2`

---

## 0. Perfil de cambios del equipo

Comando exacto: `python practica/s14-cdc-suscriptores/generar_cambios_suscriptores.py --equipo equipo-2`

| Valor del perfil | Cifra que reporta el generador |
|---|---|
| total_suscriptores | 160 |
| Número de cambios | 42 |
| n_alta | 14 |
| n_modificacion | 18 |
| n_baja | 10 |
| prob_baja_dura | 0.0625 |

`prob_baja_dura = n_baja / total_suscriptores = 10/160 = 0.0625`, sin redondeo.
El perfil es el conjunto completo de valores; dos equipos pueden coincidir en
un indicador aislado (equipo-1, equipo-5 y equipo-6 comparten `n_baja = 6`) sin
repetir el perfil completo.

## 1. Las tres tablas y su nomenclatura

Las tablas se nombran exactamente como exige el enunciado (DDL en
`sql/T14_cdc_suscriptores.sql`):

- **`maestro_suscriptores`** — tabla fuente / maestro operacional. Llave
  `subscriber_id`; columna `updated_at TIMESTAMP` que impulsa la CDC.
- **`stg_cambios_suscriptor`** — staging de cambios capturados, append-only.
  Una fila por evento de cambio, con `tipo_cambio` ∈ {ALTA, MODIFICACION, BAJA},
  `updated_at` (del origen) y `capturado_en` (de la captura).
- **`estado_cdc_suscriptores`** — checkpoint / marca de agua, una fila por
  proceso (`nombre_proceso` PK), `checkpoint TIMESTAMP` que solo avanza.

Población inicial: **160 filas** cargadas en `maestro_suscriptores`.

## 2. Evidencia cuantitativa del punto ciego

El prototipo corre la CDC basada en consulta
(`INSERT INTO stg_cambios_suscriptor SELECT … FROM maestro_suscriptores WHERE updated_at > checkpoint`)
antes y después del flujo de cambios. La clasificación ALTAS/MODIFICACIONES
compara la llave contra la membresía del maestro **a la fecha del checkpoint**
(instantánea puntual), determinística por evento y estable ante una repetición.

| Tipo de cambio | Generadas (perfil) | Capturadas por el prototipo |
|---|---:|---:|
| Altas | 14 | 14 |
| Modificaciones | 18 | 18 |
| Bajas duras | 10 | 0 |

- **Corrida ANTES** (checkpoint nulo → captura toda la población inicial como
  ALTAS): 160 capturadas; checkpoint = `2026-11-18 08:00:00`.
- **Flujo de cambios** con `updated_at = T1 = 2026-11-18 12:00:00`:
  14 altas + 18 modificaciones + 10 bajas duras. Maestro real tras el flujo:
  164 filas.
- **Corrida DESPUÉS** (checkpoint = T0): 32 capturadas (14 altas + 18 modif,
  **0 bajas**); checkpoint = T1.

**Diferencia destino vs origen:** el destino, reconstruyendo el maestro con
solo lo capturado, ve **174** suscriptores; el maestro real tiene **164**.
Diferencia = **10** (= `n_baja`). Es el mismo mecanismo del ejemplo de clase
(99 frente a 94, diferencia 5).

**Por qué es estructural y no un error del prototipo:** la CDC filtra con
`updated_at > checkpoint`. Una baja dura elimina la fila del origen, así que
esa llave deja de existir y nunca satisface el predicado: no hay `updated_at`
que supere el checkpoint porque la fila ya no está. El método no tiene forma de
enterarse de algo que dejó de existir. No es un bug de implementación; es la
definición misma del sondeo con marca de agua.

**Caso de cero bajas por redondeo:** no aplica a este equipo. `prob_baja_dura =
0.0625` es exacta y produce `n_baja = 10 ≠ 0`.

### 2.1 Repetición con el checkpoint restablecido

Se restablece el checkpoint a la fecha de la población inicial (T0) y se repite
la corrida de captura (sin la guarda de idempotencia, para evidenciar el
problema):

- Filas en `stg_cambios_suscriptor` antes de repetir: **192** (160 de la
  población + 32 del flujo).
- Re-capturadas: **32** (14 altas + 18 modif + 0 bajas).
- **Filas duplicadas** tras repetir: **32** (= altas + modificaciones = 14 + 18).
- **Filas sobrantes por pareja (subscriber_id, tipo_cambio):** **32** (cada
  pareja del flujo aparece dos veces; las de la población inicial siguen una).
- Checkpoint tras la repetición: `2026-11-18 12:00:00` (vuelve a T1).

**Decisión para evitar los duplicados:** el checkpoint debe avanzar de forma
monótona con `greatest(checkpoint_actual, max(updated_at))` (nunca retroceder) y
la inserción en el staging debe ser idempotente con
`ON CONFLICT (subscriber_id, updated_at) DO NOTHING`, porque
`(subscriber_id, updated_at)` identifica unívocamente un evento de cambio. Una
re-captura tras un reseteado erróneo es entonces un no-op. Como alternativa más
simple, un margen de solapamiento acotado (re-procesar los últimos N segundos)
con la misma llave única también elimina los duplicados. El prototipo usa un
INSERT puro (sin la guarda) para evidenciar el problema.

## 3. Decisión de mitigación del Nivel 3

Las cuatro funciones de costo, con `M = total_suscriptores = 160`,
`T = 60 s` (sondeo) y `B = 4/día` (reconciliación cada 6 h):

- `N = 86400 / T = 1440` consultas por día (sondeo).
- `K = M × B = 640` llaves leídas por día (reconciliación full-scan).
- `L_sondeo = T = 60 s`.
- `L_recon = 86400 / B = 21600 s` (6 h).

`bajas_detectadas` por reconciliación sobre la base del equipo: **10** ids
(19, 20, …, 28) = bajas generadas por el perfil.

Tabla `comparacion`:

| alternativa | detecta_bajas | intervalo_sondeo_s | barridos_por_dia | consultas_por_dia | llaves_leidas_por_dia | latencia_max_baja_s |
|---|---|---|---|---|---|---|
| Bandera de baja lógica en el origen | sí | 60 | 1440 | 1440 | 42 | 60 |
| Reconciliación periódica de conjunto completo | sí | 21600 | 4 | 4 | 640 | 21600 |
| CDC basada en registro de transacciones | sí | 0 | 0 | 0 | 42 | 0 |

> El sondeo con marca de agua lee solo el delta del cambio (no `M` por barrido);
> por eso la bandera lógica y la CDC por registro leen 42 llaves/día, mientras
> que la reconciliación barre el maestro completo (`M × B = 640`).

### Justificación de la alternativa elegida

**Decisión: estrategia híbrida** (CDC basada en consulta con marca de agua para
altas/modificaciones + reconciliación periódica de conjunto completo cada 6 h
para las bajas duras).

`prob_baja_dura = 0.0625` y `n_baja = 10` (6.25 % del maestro) hacen que el
punto ciego sea material: el destino se queda con 10 suscriptores fantasma
(diferencia 174 vs 164). No se puede aceptar el statu quo. Pero el maestro es
operacional y externo al equipo de plataforma, así que:

- **Bandera de baja lógica en el origen (descartada):** detectaría las bajas con
  latencia 60 s y costo de lectura bajo (delta), pero exige modificar el esquema
  y la lógica de borrado del sistema operacional del acueducto, que no está bajo
  el control del equipo de plataforma. Costo: cambio en el origen, fuera de
  alcance. Beneficio descartado: latencia baja que aquí no se necesita (una baja
  de suscriptor no es crítica de minuto).
- **Reconciliación periódica de conjunto completo (elegida, como barrido
  complementario):** sin tocar el origen, barre los 160 suscriptores 4 veces/día
  (`K = 640` llaves/día, despreciable para `M = 160`) y detecta las 10 bajas con
  latencia máxima 6 h. Costo: 640 lecturas/día (trivial a esta escala) y un
  LEFT JOIN periódico. Beneficio: cierra el punto ciego sin alterar el origen.
- **CDC basada en registro de transacciones (descartada):** detectaría las bajas
  en tiempo real, pero exige réplica lógica (slot, `REPLICA IDENTITY`) sobre un
  origen que el equipo no opera, con un costo operativo desproporcionado para un
  maestro de 160 filas. Si se hubiera elegido, `REPLICA IDENTITY DEFAULT`
  alcanzaría: el destino solo necesita la llave (`subscriber_id`, PK) para
  registrar la baja; `FULL` enviaría toda la fila vieja sin beneficio adicional.

La híbrida conserva el sondeo barato y de baja latencia (60 s) para altas y
modificaciones —el mismo patrón ya resuelto en T12 y T13— y añade el barrido de
reconciliación barato (640 llaves/día) solo para las bajas, que pueden tolerar
6 h de latencia en un maestro de suscriptores.

## 4. Memo de decisión ADR

Ver [docs/memo_adr_t14.md](memo_adr_t14.md). Decisión explícita: **estrategia
hibrida**, justificada por costo (640 llaves/día), latencia (6 h máxima para
bajas, 60 s para altas/modificaciones) e impacto sobre el sistema de origen
(ninguno: no se modifica el origen operacional).

## 5. Integración con el proyecto integrador

- `stg_lecturas` (T12): append-only (solo agrega filas; nunca actualiza ni
  borra). CDC incremental por marca de agua sobre `fechaobservacion`. **Sin
  punto ciego de bajas** porque no hay bajas.
- `stg_estado_medidor` (T13): estado paginado vía API con UPSERT por `meter_id`;
  el mock no expone bajas. CDC por sondeo de API + UPSERT idempotente. **Sin
  punto ciego de bajas** en el perfil del mock.
- `maestro_suscriptores` (T14): **única** de las tres fuentes con bajas duras
  reales (`prob_baja_dura = 0.0625`, 10 bajas). Es la única que requiere la
  reconciliación/híbrida; su CDC es la más costosa de las tres.

El memo no descalifica la decisión del equipo por diferir de la de referencia:
está justificada por los números propios del perfil (0.0625, 10 bajas, M = 160)
y por el costo/latencia/impacto propios, no por coincidir con un caso de
referencia.

## 6. Reproducción

```bash
cd /Users/camilorojas/Projects/BigData/bigdata-ean-ideam
source .venv/bin/activate && pip install duckdb
python practica/s14-cdc-suscriptores/generar_cambios_suscriptores.py --equipo equipo-2
python practica/s14-cdc-suscriptores/prototipo_cdc_suscriptores.py --equipo equipo-2
```

Salida esperada (resumen): perfil `total_suscriptores=160, numero_cambios=42,
n_alta=14, n_modificacion=18, n_baja=10, prob_baja_dura=0.0625`; bajas
capturadas = 0; diferencia 174 frente a 164; filas duplicadas = 32;
`bajas_detectadas` = 10; `N=1440, K=640, L_sondeo=60, L_recon=21600`.

## 7. Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude (Kiro)** para implementar el generador, el prototipo, el
DDL, el cuaderno y la redacción del memo y esta documentación. Las cifras
provienen de la ejecución real del prototipo sobre el perfil del equipo; no se
inventó ningún número. Las decisiones de diseño (marca de agua monótona con
`greatest`, llave única `(subscriber_id, updated_at)`, clasificación por
instantánea del checkpoint, híbrida sondeo + reconciliación) fueron tomadas por
el equipo y el asistente las implementó.
