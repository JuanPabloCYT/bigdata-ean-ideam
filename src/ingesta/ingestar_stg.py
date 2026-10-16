"""Ingesta incremental e idempotente de public.precipitacion a stg.stg_lecturas.

Carga las filas de una fecha concreta desde la tabla cruda (public.precipitacion)
a la capa de staging (stg.stg_lecturas) usando un patrón INSERT … ON CONFLICT DO
UPDATE. Toda la operación —lectura de marca de agua, inserción/actualización y
actualización de marca— se ejecuta en una única transacción para garantizar
atomicidad: no existe estado intermedio visible para otras sesiones.

La marca de agua (ultima_marca_agua en stg.estado_ingesta) solo avanza; nunca
retrocede. Re-ejecutar la misma fecha es seguro: las filas ya presentes se
actualizan con los valores de la fuente y el contador devuelto refleja cuántas
filas fueron procesadas, no cuántas fueron nuevas.

Uso:
    python -m src.ingesta.ingestar_stg --date YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

import psycopg

from src.config import connection_parameters


def ingest(conn_params: dict, batch_date: date) -> dict:
    """Ingesta las observaciones de batch_date desde public.precipitacion.

    Parámetros
    ----------
    conn_params:
        Diccionario con los parámetros de conexión (host, port, dbname,
        user, password), tal como devuelve connection_parameters().
    batch_date:
        Fecha de las observaciones a ingestar (se filtra por
        fechaobservacion::date = batch_date).

    Retorno
    -------
    dict con las claves:
        filas_procesadas   — filas leídas de public.precipitacion
        filas_insertadas   — filas nuevas insertadas en stg.stg_lecturas
        filas_actualizadas — filas ya existentes actualizadas (DO UPDATE)
        marca_agua         — valor final de ultima_marca_agua (ISO 8601 o null)

    Distinción insert/update:
        La cláusula RETURNING devuelve xmax por cada fila afectada.
        PostgreSQL asigna xmax = 0 a las filas recién insertadas y
        xmax != 0 a las filas actualizadas por DO UPDATE (el xmax registra
        la transacción que las bloqueó/actualizó por última vez).
    """

    with psycopg.connect(**conn_params) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # (a) Bloquear y leer la marca de agua actual
                cur.execute(
                    "SELECT ultima_marca_agua FROM stg.estado_ingesta "
                    "WHERE nombre_proceso = %s FOR UPDATE",
                    ("precipitacion_ideam",),
                )
                row = cur.fetchone()
                watermark_actual = row[0] if row else None  # noqa: F841

                # (b) Leer las filas de la fuente para la fecha solicitada
                cur.execute(
                    """
                    SELECT codigoestacion, codigosensor, fechaobservacion,
                           valorobservado, nombreestacion, departamento,
                           municipio, zonahidrografica, latitud, longitud,
                           descripcionsensor, unidadmedida
                    FROM public.precipitacion
                    WHERE fechaobservacion::date = %s
                    """,
                    (batch_date,),
                )
                filas = cur.fetchall()

                filas_procesadas = len(filas)

                # (c) Insertar/actualizar con manejo de conflictos y RETURNING xmax.
                # Un único INSERT … SELECT … RETURNING permite usar xmax para
                # distinguir inserciones nuevas de actualizaciones DO UPDATE
                # dentro de la misma transacción:
                #   xmax = 0  → fila recién insertada (no existía antes)
                #   xmax != 0 → fila actualizada por DO UPDATE (existía)
                filas_insertadas = 0
                filas_actualizadas = 0
                new_max = None

                if filas:
                    new_max = max(r[2] for r in filas)  # r[2] es fechaobservacion

                    # Construye la lista de literales VALUES para el INSERT…SELECT
                    # Usar un INSERT con RETURNING en lugar de executemany para
                    # obtener xmax por fila y distinguir insert de update.
                    placeholders = ", ".join(
                        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                        for _ in filas
                    )
                    # Aplana la lista de tuplas para pasar como parámetros
                    params = [val for fila in filas for val in fila]

                    cur.execute(
                        f"""
                        INSERT INTO stg.stg_lecturas (
                            codigoestacion, codigosensor, fechaobservacion,
                            valorobservado, nombreestacion, departamento,
                            municipio, zonahidrografica, latitud, longitud,
                            descripcionsensor, unidadmedida, _fuente
                        )
                        SELECT
                            codigoestacion, codigosensor, fechaobservacion,
                            valorobservado, nombreestacion, departamento,
                            municipio, zonahidrografica, latitud, longitud,
                            descripcionsensor, unidadmedida,
                            'ideam_socrata' AS _fuente
                        FROM (VALUES {placeholders}) AS src(
                            codigoestacion, codigosensor, fechaobservacion,
                            valorobservado, nombreestacion, departamento,
                            municipio, zonahidrografica, latitud, longitud,
                            descripcionsensor, unidadmedida
                        )
                        ON CONFLICT ON CONSTRAINT uq_stg_lecturas_clave DO UPDATE SET
                            valorobservado    = EXCLUDED.valorobservado,
                            nombreestacion    = EXCLUDED.nombreestacion,
                            departamento      = EXCLUDED.departamento,
                            municipio         = EXCLUDED.municipio,
                            zonahidrografica  = EXCLUDED.zonahidrografica,
                            latitud           = EXCLUDED.latitud,
                            longitud          = EXCLUDED.longitud,
                            descripcionsensor = EXCLUDED.descripcionsensor,
                            unidadmedida      = EXCLUDED.unidadmedida,
                            _ingestado_en     = now()
                        RETURNING (xmax = 0)::int AS es_insercion
                        """,
                        params,
                    )
                    # Cuenta filas nuevas (xmax = 0) vs actualizadas (xmax != 0)
                    for (es_insercion,) in cur.fetchall():
                        if es_insercion:
                            filas_insertadas += 1
                        else:
                            filas_actualizadas += 1

                # (d) Actualizar marca de agua solo si avanza
                if new_max is not None:
                    cur.execute(
                        """
                        UPDATE stg.estado_ingesta
                        SET ultima_marca_agua = %s,
                            actualizado_en    = now()
                        WHERE nombre_proceso = 'precipitacion_ideam'
                          AND (ultima_marca_agua IS NULL
                               OR ultima_marca_agua < %s)
                        """,
                        (new_max, new_max),
                    )

                # (e) Leer marca de agua final para reportar
                cur.execute(
                    "SELECT ultima_marca_agua FROM stg.estado_ingesta "
                    "WHERE nombre_proceso = %s",
                    ("precipitacion_ideam",),
                )
                row_final = cur.fetchone()
                marca_agua_final = row_final[0] if row_final else None

    return {
        "filas_procesadas": filas_procesadas,
        "filas_insertadas": filas_insertadas,
        "filas_actualizadas": filas_actualizadas,
        "marca_agua": (
            marca_agua_final.isoformat() if marca_agua_final is not None else None
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingesta incremental de public.precipitacion a stg.stg_lecturas"
    )
    parser.add_argument(
        "--date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Fecha de observación a ingestar",
    )
    args = parser.parse_args()

    batch_date = date.fromisoformat(args.date)
    params = connection_parameters()

    result = ingest(params, batch_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)
