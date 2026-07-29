-- =============================================================
-- 01_esquema.sql · esquema inicial del proyecto
--
-- Se ejecuta UNA SOLA VEZ, cuando el volumen db_data se crea
-- vacío. Si cambia este archivo y quiere volver a aplicarlo:
--   docker compose down -v && docker compose up
-- (el -v borra el volumen; por eso no se usa a la ligera).
--
-- Las 12 columnas y sus tipos provienen del esquema real medido
-- en T1 sobre el conjunto de precipitación del IDEAM (s54a-sgyg).
-- =============================================================

CREATE TABLE IF NOT EXISTS precipitacion (
    -- Las tres columnas de la clave candidata verificada en T1.
    codigoestacion    BIGINT       NOT NULL,
    codigosensor      BIGINT       NOT NULL,
    fechaobservacion  TIMESTAMP    NOT NULL,

    valorobservado    DOUBLE PRECISION,
    nombreestacion    TEXT,
    departamento      TEXT,
    municipio         TEXT,
    zonahidrografica  TEXT,
    latitud           DOUBLE PRECISION,
    longitud          DOUBLE PRECISION,
    descripcionsensor TEXT,
    unidadmedida      TEXT,

    -- En T1 se comprobó sobre la partición del 22 de junio de 2026
    -- que esta combinación tiene 141.007 filas, 141.007
    -- combinaciones únicas, 0 duplicados y 0 nulos. Aquí esa
    -- comprobación deja de ser un hallazgo y pasa a ser una
    -- restricción que la base hace cumplir en cada inserción.
    CONSTRAINT pk_precipitacion
        PRIMARY KEY (codigoestacion, codigosensor, fechaobservacion)
);

-- La ingesta es incremental por fecha, tal como recomienda la
-- ficha T1. Este índice sirve a ese patrón de consulta.
CREATE INDEX IF NOT EXISTS ix_precipitacion_fecha
    ON precipitacion (fechaobservacion);

-- Registro de cargas: qué partición se ingirió, cuándo y cuántas
-- filas trajo. Sin esto, una ingesta incremental no es auditable.
CREATE TABLE IF NOT EXISTS control_ingesta (
    id             SERIAL PRIMARY KEY,
    particion      DATE        NOT NULL UNIQUE,
    filas_leidas   INTEGER     NOT NULL,
    filas_insertadas INTEGER   NOT NULL,
    sha256_archivo TEXT,
    cargado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);
