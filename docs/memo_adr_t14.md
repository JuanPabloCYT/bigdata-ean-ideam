# ADR · CDC del maestro de suscriptores (T14)

**Estado:** Aceptado · **Fecha:** 2026-11-18 · **Equipo:** `equipo-2`
**Fuente:** `maestro_suscriptores` (maestro operacional de suscriptores del acueducto)
**Motor:** DuckDB embebido 2.0.0 (cambio documentado: el perfil s12 en Docker no estaba disponible y el host solo tiene la librería cliente `libpq`)

---

## Contexto

El equipo de plataforma ya resuelve la CDC de dos fuentes del proyecto
integrador: `stg_lecturas` (T12, append-only por `fechaobservacion`) y
`stg_estado_medidor` (T13, estado paginado vía API con UPSERT). La pregunta que
detona esta decisión es: **¿alcanza una CDC basada en consulta con marca
temporal (`updated_at > checkpoint`) para replicar `maestro_suscriptores`, o el
punto ciego de las bajas duras obliga a otra cosa?**

El maestro mezcla altas, modificaciones y **bajas duras** (borrado físico, sin
tombstone ni bandera). El perfil del equipo es `total_suscriptores = 160`,
`n_alta = 14`, `n_modificacion = 18`, `n_baja = 10`,
`prob_baja_dura = 0.0625` (10/160, sin redondeo), `numero_cambios = 42`.

## Evidencia

El prototipo corre la CDC antes y después del flujo de cambios, sobre el perfil
propio del equipo:

| Tipo de cambio | Generadas | Capturadas |
|---|---:|---:|
| Altas | 14 | 14 |
| Modificaciones | 18 | 18 |
| Bajas duras | 10 | **0** |

- Bajas generadas: **10**. Bajas capturadas: **0**.
- `prob_baja_dura = 0.0625` (6.25 % del maestro).
- Diferencia destino vs origen: el destino reconstruye **174** suscriptores
  contra **164** reales → diferencia **10** (= las 10 bajas no detectadas). Es
  la misma mecánica del ejemplo de clase (99 frente a 94).
- Reconciliación de conjunto completo sobre la base del equipo:
  `bajas_detectadas = 10` (ids 19–28) = bajas generadas.

El resultado **no es un error del prototipo**: una baja dura elimina la fila del
origen, así que esa llave deja de existir y nunca satisface
`updated_at > checkpoint`. El método no puede enterarse de algo que dejó de
existir. Es estructural del sondeo con marca de agua.

## Decisión

**Estrategia híbrida.** Mantener la CDC basada en consulta con marca de agua
(sondeo cada `T = 60 s`, `ON CONFLICT (subscriber_id, updated_at) DO NOTHING`,
checkpoint monótono con `greatest`) para **altas y modificaciones**, y añadir una
**reconciliación periódica de conjunto completo** cada 6 h (`B = 4/día`) para
detectar las **bajas duras**.

## Alternativas descartadas y su costo

| Alternativa | ¿Elegida? | Costo estimado | Beneficio |
|---|---|---|---|
| Bandera de baja lógica en el origen | No | Cambio de esquema y de lógica de borrado en el sistema operacional del acueducto, fuera del control del equipo de plataforma | Detecta bajas con latencia 60 s y costo de lectura bajo (delta) |
| Reconciliación periódica de conjunto completo | **Sí (como barrido complementario)** | `K = M × B = 160 × 4 = 640` llaves/día (trivial a esta escala); un LEFT JOIN periódico | Detecta las 10 bajas; latencia máxima `86400/B = 21600 s` (6 h) |
| CDC basada en registro de transacciones | No | Réplica lógica (slot + `REPLICA IDENTITY`) sobre un origen que el equipo no opera; costo operativo desproporcionado para 160 filas | Detecta bajas en tiempo real |

- **Bandera lógica** se descarta porque exige modificar el origen operacional
  (fuera de alcance) para ganar una latencia de 60 s que un maestro de
  suscriptores no necesita: una baja no es crítica de minuto.
- **CDC por registro** se descarta porque su costo operativo (réplica lógica
  sobre un origen ajeno) es desproporcionado para un maestro de 160 filas. Si se
  hubiera elegido, `REPLICA IDENTITY DEFAULT` alcanzaría: el destino solo necesita
  la llave (`subscriber_id`, PK) para registrar la baja; `FULL` enviaría toda la
  fila vieja sin beneficio.
- **Reconciliación** se elige solo como barrido complementario de bajas, no como
  CDC única: a 640 llaves/día es despreciable para `M = 160` y cierra el punto
  ciego sin tocar el origen.

## Justificación por costo, latencia e impacto sobre el sistema de origen

- **Costo:** el sondeo lee solo el delta (42 cambios/día, no `M` por barrido);
  la reconciliación añade 640 llaves/día. Total despreciable para 160 filas. La
  CDC por registro añadiría el costo de operar un slot de réplica sobre un origen
  ajeno.
- **Latencia:** altas y modificaciones a 60 s (sondeo); bajas a 6 h máximo
  (reconciliación), aceptable para un maestro de suscriptores donde una baja no
  es crítica de minuto. La bandera lógica ganaría 6 h → 60 s en las bajas, pero a
  costa de tocar el origen, lo que no compensa.
- **Impacto sobre el sistema de origen:** **ninguno**. No se modifica el
  esquema ni la lógica de borrado del acueducto (a diferencia de la bandera
  lógica) ni se le exige réplica lógica (a diferencia de la CDC por registro). El
  sondeo y la reconciliación solo leen.

## Intervalo de sondeo y margen de solapamiento

- **Intervalo de sondeo:** `T = 60 s` para altas y modificaciones. Es el mismo
  patrón ya resuelto en T12/T13 y basta para una fuente de baja criticidad
  temporal.
- **Margen de solapamiento:** acotado a los últimos `T` (60 s). El checkpoint
  avanza con `greatest(checkpoint, max(updated_at))` —nunca retrocede— y la
  inserción es idempotente con `ON CONFLICT (subscriber_id, updated_at) DO
  NOTHING`. Si el origen se retrasa o se repite una corrida (sección 2.1), el
  solapamiento re-procesa hasta 60 s de cambios pero la llave única los descarta:
  cero duplicados. La repetición con el checkpoint restablecido, sin esta guarda,
  produjo 32 duplicados (= altas + modificaciones); con la guarda sería 0.
- **Reconciliación:** `B = 4/día` (cada 6 h). Latencia máxima de una baja:
  `86400/B = 21600 s`.

## Datos personales (opcional)

Si el maestro fuera real y contuviera datos personales (nombre, dirección del
suscriptor), la decisión no cambiaría de fondo —la híbrida sigue siendo
adecuada— pero la reconciliación de conjunto completo debería ejecutarse sobre
una proyección mínima (solo `subscriber_id` y `updated_at`, sin columnas
personales) y el `stg_cambios_suscriptor` debería cifrar o seudonimizar las
columnas personales; además, el borrado físico de un suscriptor podría
convertirse en una solicitud de borrado (cumplimiento de protección de datos),
lo que reforzaría la necesidad de registrar la baja explícitamente (bandera
lógica o evento de CDC) en lugar de detectarla por diferencia.
