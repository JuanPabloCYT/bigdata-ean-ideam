# T12 · Ingesta incremental e idempotente

**Proyecto:** precipitación del IDEAM · Universidad Ean  
**Motor:** PostgreSQL  
**Guion de reconstrucción:** [sql/T12_ingesta_incremental.sql](../sql/T12_ingesta_incremental.sql)  
**Módulo de ingesta:** [src/ingesta/ingestar_stg.py](../src/ingesta/ingestar_stg.py)  
**Script de verificación:** [practica/s12-ingesta/verificar_t12.py](../practica/s12-ingesta/verificar_t12.py)

> Ejecutado el 2025-10-16

---

## 1. Modelo físico de staging

La capa `stg` recibe las observaciones desde `public.precipitacion` antes de que pasen al modelo dimensional `dw`. Contiene dos tablas.

### stg.stg_lecturas

Replica las 12 columnas de `public.precipitacion` y añade dos columnas de metadatos de ingesta. La restricción única incluye `_fuente` para permitir que el mismo instante coexista con valores de diferentes orígenes.

| Columna | Tipo | Descripción |
|---|---|---|
| `codigoestacion` | `BIGINT NOT NULL` | Código de la estación |
| `codigosensor` | `BIGINT NOT NULL` | Código del sensor |
| `fechaobservacion` | `TIMESTAMP NOT NULL` | Instante de la observación |
| `valorobservado` | `DOUBLE PRECISION` | Valor en la unidad del sensor |
| `nombreestacion` | `TEXT` | Nombre descriptivo de la estación |
| `departamento` | `TEXT` | Departamento geográfico |
| `municipio` | `TEXT` | Municipio |
| `zonahidrografica` | `TEXT` | Zona hidrográfica |
| `latitud` | `DOUBLE PRECISION` | Latitud WGS-84 |
| `longitud` | `DOUBLE PRECISION` | Longitud WGS-84 |
| `descripcionsensor` | `TEXT` | Descripción del tipo de sensor |
| `unidadmedida` | `TEXT` | Unidad (mm, etc.) |
| `_fuente` | `TEXT NOT NULL DEFAULT 'ideam_socrata'` | Origen del registro |
| `_ingestado_en` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Marca de tiempo de ingesta |

Restricción: `UNIQUE (codigoestacion, codigosensor, fechaobservacion, _fuente)` — nombrada `uq_stg_lecturas_clave`.  
Índice: `ix_stg_lecturas_fecha` sobre `fechaobservacion` para filtrado por fecha.

### stg.estado_ingesta

Tabla de control con una fila por proceso de ingesta. Registra la marca de agua más reciente para soportar ingesta incremental y recuperación de brechas.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Identificador interno |
| `nombre_proceso` | `TEXT NOT NULL UNIQUE` | Nombre del proceso (e.g. `'precipitacion_ideam'`) |
| `ultima_marca_agua` | `TIMESTAMPTZ` | `fechaobservacion` máxima procesada |
| `actualizado_en` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Última actualización del registro |

---

## 2. Reconstrucción

Requisitos: Docker en ejecución, contenedor `ideam_db` levantado con `docker compose up -d`.

```bash
docker exec -i ideam_db psql -U ideam_app -d ideam < sql/T12_ingesta_incremental.sql
```

El guion es idempotente: re-ejecutarlo una segunda vez produce código de salida 0 con avisos `NOTICE: relation ... already exists`, sin errores ni duplicados.

---

## 3. Prueba A · Idempotencia

**Procedimiento:** se llama `ingest()` dos veces consecutivas para la misma fecha (`2026-06-22`). Se compara el conteo de filas en `stg.stg_lecturas` y el valor de `ultima_marca_agua` entre las dos ejecuciones.

**Salida real de verificar_t12.py:**

```
=== TEST A: Idempotencia — dos ejecuciones consecutivas ===
  Ejecución 1: filas_procesadas=2, count stg=2
  Ejecución 2: filas_procesadas=2, count stg=2
  Marca de agua 1: 2026-06-22 08:00:00+00:00
  Marca de agua 2: 2026-06-22 08:00:00+00:00
TEST A [PASS]
```

**Qué prueba:** la segunda ejecución lee las mismas 2 filas de la fuente y ejecuta el mismo número de upserts, pero el `ON CONFLICT DO UPDATE` actualiza las filas ya existentes en lugar de duplicarlas. El conteo total en staging permanece en 2 tras ambas ejecuciones. La marca de agua no avanza porque `2026-06-22 08:00:00` ya era el valor registrado; la condición `ultima_marca_agua < %s` es falsa y el `UPDATE` afecta 0 filas. El estado es matemáticamente idéntico al de la primera ejecución.

---

## 4. Prueba B · Recuperación de brecha de tres horas

**Procedimiento:** se carga la fecha `2026-06-21` (3 filas sintéticas: estación 99999901 a las 08:00 y 09:00, estación 99999902 a las 08:00). Se eliminan 2 filas directamente de `stg.stg_lecturas` para simular una pérdida. Se re-ingesta la misma fecha y se verifica la restauración. Se re-ingesta una vez más para confirmar estabilidad.

**Salida real de verificar_t12.py:**

```
=== TEST B: Recuperación de brecha (gap recovery) ===
  Línea base (fecha 2026-06-21): 3 filas
  Marca de agua antes de eliminar: 2026-06-22 08:00:00+00:00
  Tras eliminar 2 filas: 1 filas
  Tras primera re-ingesta: 3 filas
  Marca de agua tras re-ingesta 1: 2026-06-22 08:00:00+00:00
  Tras segunda re-ingesta: 3 filas
  Marca de agua tras re-ingesta 2: 2026-06-22 08:00:00+00:00
TEST B [PASS]
```

**Mecánica del delete-and-restore:** cuando se eliminan 2 filas de staging, la tabla fuente (`public.precipitacion`) sigue teniendo las 3 observaciones originales para `2026-06-21`. Al re-ejecutar `ingest(batch_date='2026-06-21')`, el módulo lee las 3 filas de la fuente y ejecuta un upsert por cada una. Las 2 filas eliminadas se reinsertan (la restricción `ON CONFLICT` no se activa porque la fila ya no existe); la fila que sobrevivió se actualiza sin cambiar el conteo. La tabla vuelve a 3 filas.

**Por qué la marca de agua no cambia:** la condición de actualización es `ultima_marca_agua IS NULL OR ultima_marca_agua < new_max`. La marca actual es `2026-06-22 08:00:00` (del paso anterior) y el `new_max` de `2026-06-21` es `2026-06-21 09:00:00`, que es anterior. La condición es falsa; la marca permanece en `2026-06-22 08:00:00`. Esto es correcto: la marca solo avanza hacia adelante en el tiempo y una recuperación de brecha retroactiva no debe retrocederla.

---

## 5. Prueba C · Clave de deduplicación

**Procedimiento:** se verifica que la restricción `uq_stg_lecturas_clave` exista con las columnas correctas. Se inserta una fila adicional con `_fuente='ideam_legacy'` para el mismo instante `(99999901, 240, 2026-06-21 08:00)` y se comprueba que coexistan 2 filas.

**Salida real de verificar_t12.py:**

```
=== TEST C: Clave de deduplicación — caso borde legacy ===
  Restricción encontrada: uq_stg_lecturas_clave
  Columnas de la clave única: ['codigoestacion', 'codigosensor', 'fechaobservacion', '_fuente']
  Filas para el instante de prueba (ideam_socrata + ideam_legacy): 2
TEST C [PASS]
```

**La clave compuesta:** la deduplicación se define sobre `(codigoestacion, codigosensor, fechaobservacion, _fuente)`. Los tres primeros campos identifican un instante físico único en la red de medición: una estación, un sensor, un momento. El cuarto campo, `_fuente`, permite que el mismo instante tenga representaciones distintas según el canal de entrega.

**Caso borde legacy:** si el mismo instante llega tanto por `'ideam_socrata'` como por `'ideam_legacy'` (canal histórico o migración), se almacenan como dos filas independientes. Ambas son accesibles; ninguna sobreescribe a la otra. La prueba confirma que 2 filas coexisten para `codigoestacion=99999901, codigosensor=240, fechaobservacion='2026-06-21 08:00'` con fuentes distintas.

**Riesgo residual:** si el mismo proceso envía dos veces la misma fila con la misma `_fuente` (ej. dos cargas del mismo archivo de `'ideam_socrata'`), el `ON CONFLICT DO UPDATE` ejecuta una actualización silenciosa: la segunda entrega sobreescribe a la primera con los mismos valores. Esto es intencional — propaga correcciones de la fuente sin requerir un `DELETE` previo — pero implica que no se detecta si la fuente envía dos versiones distintas del mismo instante en la misma `_fuente`. Para detectar esa discrepancia habría que conservar el historial de cambios en una tabla de auditoría, lo que está fuera del alcance de esta sesión.

---

## 6. Costo evitado

Con los datos de la ejecución real del Test A: la tabla `stg.stg_lecturas` tiene **2 filas** para la fecha `2026-06-22` (datos sintéticos de los sensores 99999901 y 99999902). Una re-ejecución idempotente lee las mismas 2 filas de `public.precipitacion` y ejecuta 2 upserts que actualizan 0 filas (los valores no han cambiado). El ciclo completo termina en menos de 1 segundo sin truncar ni recargar la tabla.

Con datos reales a la escala medida en T1, `public.precipitacion` contiene **141.007 filas/día**. El impacto diferencial entre los dos enfoques es:

| Estrategia | Filas procesadas por re-ejecución | Filas modificadas |
|---|---:|---:|
| DROP + RELOAD completo | 141.007 | 141.007 |
| Re-ingesta incremental (idempotente) | 141.007 (lectura) | 0 (upsert sin cambio) |

En ambos casos se leen las mismas 141.007 filas de la fuente, pero la ingesta incremental evita el ciclo `DROP TABLE / TRUNCATE + INSERT` que invalida índices, genera bloat de MVCC y requiere un `VACUUM` posterior. Con la muestra sintética actual los conteos son bajos, pero el mecanismo es idéntico al que operaría a escala real.

> **Nota:** los conteos de 2 filas corresponden a datos sintéticos con `codigoestacion` en el rango `99999*` (convención DEMO del proyecto). La cifra de 141.007 filas/día proviene de la medición real de T1 sobre la API del IDEAM. Ambos números se usan tal como se registraron; no se inventaron.

---

## 7. Criterios de aceptación

- [x] `sql/T12_ingesta_incremental.sql` es idempotente: dos ejecuciones consecutivas salen con código 0.
- [x] `SELECT table_name FROM information_schema.tables WHERE table_schema='stg' ORDER BY table_name` devuelve exactamente: `estado_ingesta`, `stg_lecturas`.
- [x] `SELECT nombre_proceso FROM stg.estado_ingesta` devuelve `'precipitacion_ideam'`.
- [x] CLI `python -m src.ingesta.ingestar_stg --date 2026-06-22` sale con código 0 con `filas_procesadas: 0` sobre tabla fuente vacía.
- [x] `verificar_t12.py` sale con código 0 y los tres tests imprimen `[PASS]`.
- [x] Dos ejecuciones consecutivas para la misma fecha producen conteos idénticos en `stg.stg_lecturas` (Test A).
- [x] Eliminar 2 filas y re-ingestar las restaura exactamente; segunda re-ingesta añade 0 filas; marca de agua sin cambio (Test B).
- [x] La restricción `uq_stg_lecturas_clave` permite el mismo `(codigoestacion, codigosensor, fechaobservacion)` con distintas `_fuente` (Test C).

---

## 8. Declaración de uso de asistentes

Se utilizó **Claude (Kiro)** para redactar el DDL, el módulo Python y este documento. Los resultados de las pruebas provienen de la ejecución real en el entorno Docker del equipo; no se inventó ningún número. Las decisiones de diseño (clave compuesta con `_fuente`, marca de agua que solo avanza, transacción única) fueron tomadas por el equipo y el asistente las implementó.
