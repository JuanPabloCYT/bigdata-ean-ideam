# Plantilla de entrega · T12 · Ingesta incremental e idempotente

## Datos del equipo

| Campo | Valor |
|---|---|
| **Integrantes** | Juan Pablo Castro, Camilo Rojas, Lina Ramírez |
| **Dataset** | IDEAM precipitación · [s54a-sgyg](https://www.datos.gov.co/resource/s54a-sgyg.json) |
| **Sesión** | S12 · Ingesta incremental |
| **Fecha de entrega** | 2025-10-16 |

---

## Archivos entregados

| Archivo | Ruta en el repositorio | Descripción |
|---|---|---|
| DDL de staging | `sql/T12_ingesta_incremental.sql` | Crea `stg.stg_lecturas` y `stg.estado_ingesta`; idempotente |
| Módulo de ingesta | `src/ingesta/ingestar_stg.py` | Ingesta incremental con `ON CONFLICT DO UPDATE` en una transacción |
| Script de verificación | `practica/s12-ingesta/verificar_t12.py` | Tres pruebas automatizadas (idempotencia, brecha, deduplicación) |
| Evidencia técnica | `docs/T12_ingesta_incremental.md` | Modelo físico, salidas reales, análisis de costo evitado |
| README de práctica | `practica/s12-ingesta/README.md` | Instrucciones de reproducción paso a paso |
| Esta plantilla | `docs/T12_plantilla_entrega.md` | Resumen ejecutivo del entregable |

---

## Comando de reproducción

Desde la raíz del repositorio (`/Users/camilorojas/Projects/BigData/bigdata-ean-ideam`), ejecutar en orden:

```bash
# 1. Levantar el entorno
docker compose up -d
docker compose ps   # esperar hasta que ideam_db muestre (healthy)

# 2. Aplicar DDL (primera vez y re-ejecución idempotente)
docker exec -i ideam_db psql -U ideam_app -d ideam < sql/T12_ingesta_incremental.sql

# 3. Probar el CLI de ingesta
docker exec ideam_jupyter python -m src.ingesta.ingestar_stg --date 2026-06-22

# 4. Ejecutar verificación completa
docker exec ideam_jupyter python practica/s12-ingesta/verificar_t12.py
```

El paso 4 debe terminar con código de salida 0 y la línea `RESULTADO GLOBAL: PASS — todos los tests pasaron`.

---

## Resultados reales de la ejecución

### Salida completa de verificar_t12.py

```
============================================================
Verificación T12 · Ingesta incremental e idempotente
============================================================
[setup] Limpiando filas de prueba previas …
[setup] Insertando filas sintéticas en public.precipitacion …
=== TEST A: Idempotencia — dos ejecuciones consecutivas ===
  Ejecución 1: filas_procesadas=2, count stg=2
  Ejecución 2: filas_procesadas=2, count stg=2
  Marca de agua 1: 2026-06-22 08:00:00+00:00
  Marca de agua 2: 2026-06-22 08:00:00+00:00
TEST A [PASS]
=== TEST B: Recuperación de brecha (gap recovery) ===
  Línea base (fecha 2026-06-21): 3 filas
  Marca de agua antes de eliminar: 2026-06-22 08:00:00+00:00
  Tras eliminar 2 filas: 1 filas
  Tras primera re-ingesta: 3 filas
  Marca de agua tras re-ingesta 1: 2026-06-22 08:00:00+00:00
  Tras segunda re-ingesta: 3 filas
  Marca de agua tras re-ingesta 2: 2026-06-22 08:00:00+00:00
TEST B [PASS]
=== TEST C: Clave de deduplicación — caso borde legacy ===
  Restricción encontrada: uq_stg_lecturas_clave
  Columnas de la clave única: ['codigoestacion', 'codigosensor', 'fechaobservacion', '_fuente']
  Filas para el instante de prueba (ideam_socrata + ideam_legacy): 2
TEST C [PASS]
[teardown] Limpiando filas de prueba …
============================================================
RESULTADO GLOBAL: PASS — todos los tests pasaron
```

### Conteos por prueba

| Prueba | Métrica | Valor |
|---|---|---|
| Test A · Idempotencia (fecha 2026-06-22) | Filas en stg ejecución 1 | 2 |
| Test A · Idempotencia (fecha 2026-06-22) | Filas en stg ejecución 2 | 2 |
| Test A · Idempotencia | Marca de agua ejecución 1 | `2026-06-22 08:00:00+00:00` |
| Test A · Idempotencia | Marca de agua ejecución 2 | `2026-06-22 08:00:00+00:00` |
| Test B · Recuperación (fecha 2026-06-21) | Línea base | 3 filas |
| Test B · Recuperación | Tras eliminar 2 filas | 1 fila |
| Test B · Recuperación | Tras primera re-ingesta | 3 filas |
| Test B · Recuperación | Tras segunda re-ingesta | 3 filas |
| Test B · Recuperación | Marca de agua tras re-ingesta 1 | `2026-06-22 08:00:00+00:00` |
| Test B · Recuperación | Marca de agua tras re-ingesta 2 | `2026-06-22 08:00:00+00:00` |
| Test C · Deduplicación | Filas coexistiendo para mismo instante con distinta _fuente | 2 |

---

## Limitaciones conocidas

- `public.precipitacion` está vacía en el entorno local (la API del IDEAM no se consume en esta práctica). `verificar_t12.py` usa datos sintéticos con `codigoestacion` en el rango `99999*` (convención DEMO del proyecto). Los conteos de 2 y 3 filas reflejan esa muestra sintética.
- A escala real la tabla fuente contiene 141.007 filas/día (medido en T1). El mecanismo de ingesta incremental es idéntico; solo cambia el volumen.
- La recuperación de brecha retroactiva (Test B) no retrocede la marca de agua. Si se necesita recargar una fecha anterior a la marca actual, se debe invocar `ingest()` directamente con esa fecha; el módulo la procesará correctamente aunque la marca no cambie.
- El riesgo residual de la clave de deduplicación (dos entregas del mismo instante con la misma `_fuente`) produce una sobreescritura silenciosa, que propaga correcciones pero no conserva historial de cambios. Documentado en `docs/T12_ingesta_incremental.md`, sección 5.
