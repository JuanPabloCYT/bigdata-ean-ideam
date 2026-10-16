-- T12 · Ingesta incremental a la capa staging
-- Ejecutar: docker exec -i ideam_db psql -U ideam_app -d ideam < sql/T12_ingesta_incremental.sql
-- Requiere public.precipitacion (creada por sql/01_esquema.sql).
-- Idempotente: se puede ejecutar varias veces sin error ni duplicados.

BEGIN;

-- ----------------------------------------------------------------
-- Esquema de staging
-- ----------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS stg;

-- ----------------------------------------------------------------
-- Tabla de staging: replica columnas de public.precipitacion
-- más metadatos de ingesta (_fuente, _ingestado_en).
-- La clave única incluye _fuente para permitir convivencia de
-- registros del mismo instante provenientes de distintas fuentes
-- (ej. ideam_socrata vs ideam_legacy).
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.stg_lecturas (
    codigoestacion   BIGINT            NOT NULL,
    codigosensor     BIGINT            NOT NULL,
    fechaobservacion TIMESTAMP         NOT NULL,
    valorobservado   DOUBLE PRECISION,
    nombreestacion   TEXT,
    departamento     TEXT,
    municipio        TEXT,
    zonahidrografica TEXT,
    latitud          DOUBLE PRECISION,
    longitud         DOUBLE PRECISION,
    descripcionsensor TEXT,
    unidadmedida     TEXT,
    _fuente          TEXT              NOT NULL DEFAULT 'ideam_socrata',
    _ingestado_en    TIMESTAMPTZ       NOT NULL DEFAULT now(),
    CONSTRAINT uq_stg_lecturas_clave
        UNIQUE (codigoestacion, codigosensor, fechaobservacion, _fuente)
);

CREATE INDEX IF NOT EXISTS ix_stg_lecturas_fecha
    ON stg.stg_lecturas (fechaobservacion);

-- ----------------------------------------------------------------
-- Tabla de control de ingesta: almacena la marca de agua por proceso.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.estado_ingesta (
    id               SERIAL        PRIMARY KEY,
    nombre_proceso   TEXT          NOT NULL UNIQUE,
    ultima_marca_agua TIMESTAMPTZ,
    actualizado_en   TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- Registro inicial del proceso de precipitación (idempotente).
INSERT INTO stg.estado_ingesta (nombre_proceso)
VALUES ('precipitacion_ideam')
ON CONFLICT DO NOTHING;

COMMIT;

-- Verificación inmediata (fuera de transacción para que siempre se ejecute)
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'stg'
ORDER BY table_name;

SELECT nombre_proceso, ultima_marca_agua
FROM stg.estado_ingesta;
