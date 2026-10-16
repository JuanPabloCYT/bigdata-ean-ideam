# Práctica S12 · Ingesta incremental e idempotente

Sesión 12 · Juan Pablo Castro, Camilo Rojas, Lina Ramírez  
Dataset: IDEAM precipitación · [s54a-sgyg](https://www.datos.gov.co/resource/s54a-sgyg.json)

Esta sesión implementa una capa de staging (`stg`) con ingesta incremental e idempotente. El patrón `INSERT … ON CONFLICT DO UPDATE` garantiza que re-ejecutar la misma fecha no duplica filas. La marca de agua persiste en `stg.estado_ingesta` y solo avanza; nunca retrocede.

La evidencia completa con salidas reales, análisis de costo evitado y criterios de aceptación está en [`docs/T12_ingesta_incremental.md`](../../docs/T12_ingesta_incremental.md).

## Qué hay aquí

| Archivo | Qué es |
|---|---|
| `verificar_t12.py` | Script de verificación con tres pruebas (idempotencia, recuperación de brecha, clave de deduplicación) |
| `README.md` | Este archivo — instrucciones de reproducción |

## Prerrequisitos

- Docker Desktop en ejecución (`docker info` no debe dar error).
- Archivo `.env` configurado en la raíz del proyecto (ver `.env.example`).
- Las variables `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` y `POSTGRES_PASSWORD` deben estar definidas en `.env`.

## Reproducción paso a paso

### 1. Levantar el entorno

```bash
cd /Users/camilorojas/Projects/BigData/bigdata-ean-ideam
docker compose up -d
docker compose ps   # esperar hasta que ideam_db muestre (healthy)
```

Salida esperada (fragmento):

```
NAME            STATUS
ideam_db        running (healthy)
ideam_jupyter   running
```

### 2. Aplicar el DDL de staging

```bash
docker exec -i ideam_db psql -U ideam_app -d ideam < sql/T12_ingesta_incremental.sql
```

Salida esperada:

```
BEGIN
CREATE SCHEMA
CREATE TABLE
CREATE INDEX
CREATE TABLE
INSERT 0 0
COMMIT
   table_name
-----------------
 estado_ingesta
 stg_lecturas
(2 rows)

 nombre_proceso    | ultima_marca_agua
-------------------+------------------
 precipitacion_ideam |
(1 row)
```

Re-ejecutar el mismo comando debe salir con código 0 y mostrar `NOTICE: relation ... already exists` — eso confirma la idempotencia del DDL.

### 3. Probar el CLI de ingesta

```bash
docker exec ideam_jupyter python -m src.ingesta.ingestar_stg --date 2026-06-22
```

Salida esperada con tabla fuente vacía:

```json
{
  "filas_procesadas": 0,
  "filas_insertadas": 0,
  "filas_actualizadas": 0,
  "marca_agua": null
}
```

### 4. Ejecutar la verificación completa

```bash
docker exec ideam_jupyter python practica/s12-ingesta/verificar_t12.py
```

Salida esperada (completa):

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

El script sale con código 0 cuando todos los tests pasan, y con código 1 si alguno falla.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude (Kiro)** para implementar el DDL, el módulo de ingesta y este documento.

Los comandos se ejecutaron en el entorno real del equipo. Las salidas pegadas en la evidencia provienen de la ejecución real de `verificar_t12.py`, no de estimaciones.
