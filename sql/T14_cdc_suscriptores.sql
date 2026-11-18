-- =============================================================
-- T14 · CDC del maestro de suscriptores · DDL
--
-- Motor de ejecución de esta entrega: DuckDB embebido (versión 2.0.0).
-- Motivo del cambio de motor: el perfil s12 del archivo de servicios
-- (PostgreSQL 17 en el contenedor `ideam_db`) no estaba disponible en la
-- sesión (Docker apagado) y la instalación nativa de PostgreSQL del host
-- es solo la librería cliente `libpq`, sin binario de servidor. DuckDB
-- embebido reproduce sin servidor las mismas semánticas que el prototipo
-- necesita: marca de agua (watermark) con `updated_at`, `INSERT … ON
-- CONFLICT`, funciones de ventana y `greatest()`. La propiedad estructural
-- que se demuestra (las bajas duras nunca son capturadas por una CDC basada
-- en consulta) es independiente del motor, así que la conclusión se traslada
-- a la pila PostgreSQL que usan stg_lecturas (T12) y stg_estado_medidor (T13).
--
-- Las tres tablas se nombran exactamente como exige el enunciado:
--   * maestro_suscriptores         (tabla fuente / maestro operacional)
--   * stg_cambios_suscriptor       (staging de cambios capturados, append-only)
--   * estado_cdc_suscriptores     (checkpoint / marca de agua)
--
-- El guion es idempotente: se puede re-ejecutar sin error.
-- =============================================================

-- Tabla fuente: el maestro operacional de suscriptores del acueducto.
-- `updated_at` es la marca temporal que impulsa la CDC basada en consulta.
CREATE TABLE IF NOT EXISTS maestro_suscriptores (
    subscriber_id   BIGINT   PRIMARY KEY,
    nombre          TEXT,
    direccion       TEXT,
    estado          TEXT,
    updated_at      TIMESTAMP NOT NULL
);

-- Staging de cambios capturados. Es un registro append-only de eventos de
-- cambio (una fila por captura). El prototipo usa un INSERT puro para evidenciar
-- el problema de los duplicados al repetir la corrida con el checkpoint
-- restablecido (sección 2.1); la guarda de idempotencia en producción sería
-- `UNIQUE (subscriber_id, updated_at)` + `ON CONFLICT DO NOTHING`, documentada
-- en el memo y en el párrafo de decisión de la sección 2.1.
CREATE TABLE IF NOT EXISTS stg_cambios_suscriptor (
    subscriber_id   BIGINT   NOT NULL,
    nombre          TEXT,
    direccion       TEXT,
    estado          TEXT,
    tipo_cambio     TEXT     NOT NULL,   -- 'ALTA' | 'MODIFICACION' | 'BAJA'
    updated_at      TIMESTAMP NOT NULL,
    capturado_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Checkpoint / marca de agua del proceso de CDC. Una fila por proceso;
-- el checkpoint solo avanza (monótono) vía greatest().
CREATE TABLE IF NOT EXISTS estado_cdc_suscriptores (
    nombre_proceso  TEXT     PRIMARY KEY,
    checkpoint      TIMESTAMP,
    actualizado_en  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
