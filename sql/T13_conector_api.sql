-- T13 · Conector de Ingesta API — DDL idempotente
-- Ejecutar: docker exec -i ideam_db psql -U ideam_app -d ideam < sql/T13_conector_api.sql
-- Requiere el schema stg (creado por sql/T12_ingesta_incremental.sql).
-- Idempotente: se puede ejecutar varias veces sin error ni duplicados.

BEGIN;

-- ----------------------------------------------------------------
-- Esquema de staging (idempotente, ya podría existir de T12)
-- ----------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS stg;

-- ----------------------------------------------------------------
-- Tabla de staging de medidores: idempotente con ON CONFLICT (meter_id).
-- meter_id es la clave primaria; re-ejecutar el mismo lote no duplica filas.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.stg_estado_medidor (
    meter_id          TEXT             NOT NULL,
    estado            TEXT,
    ultimo_valor      DOUBLE PRECISION,
    unidad            TEXT,
    timestamp_lectura TIMESTAMPTZ,
    _fuente           TEXT             NOT NULL DEFAULT 'api_ideam',
    _ingestado_en     TIMESTAMPTZ      NOT NULL DEFAULT now(),
    CONSTRAINT pk_stg_estado_medidor PRIMARY KEY (meter_id)
);

-- ----------------------------------------------------------------
-- Bitácora de ingesta API: append-only, una fila por intento HTTP.
-- Sin ON CONFLICT: nunca se actualiza ni se deduplica.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.bitacora_ingesta_api (
    id               BIGSERIAL        PRIMARY KEY,
    ejecutado_en     TIMESTAMPTZ      NOT NULL DEFAULT now(),
    pagina           INTEGER          NOT NULL,
    intento          INTEGER          NOT NULL,
    codigo_respuesta INTEGER,
    duracion         DOUBLE PRECISION,
    resultado        TEXT             NOT NULL
);

COMMIT;

-- ----------------------------------------------------------------
-- Verificación inmediata (fuera de transacción)
-- ----------------------------------------------------------------
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'stg'
ORDER BY table_name;

SELECT
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'stg'
  AND table_name   = 'stg_estado_medidor'
ORDER BY ordinal_position;

SELECT
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'stg'
  AND table_name   = 'bitacora_ingesta_api'
ORDER BY ordinal_position;
