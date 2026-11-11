"""Conector de ingesta desde API REST paginada a stg.stg_estado_medidor.

Consume una API de medidores con autenticación Bearer, itera páginas
usando while hay_siguiente == True, aplica UPSERT idempotente en
stg.stg_estado_medidor y registra cada intento HTTP en
stg.bitacora_ingesta_api (append-only, sin ON CONFLICT).

Manejo de errores:
  200           → UPSERT datos + log EXITO
  401           → log FALLO_AUTENTICACION + abortar corrida
  429 / 5xx / Timeout → reintentar con backoff exponencial;
                        log REINTENTO por cada intento fallido,
                        AGOTADO si se agotan los intentos
  otros 4xx     → log ERROR_PERMANENTE, continúa a la siguiente página

Backoff antes del intento k ≥ 2:
    sleep = min(t0 * 2**(k-2), tmax) + random.uniform(0, 1)

Uso:
    python -m src.ingesta.conector_api --url URL --token TOKEN
    python -m src.ingesta.conector_api --url URL --token TOKEN \\
        --max-intentos 5 --t0 2.0 --tmax 120.0
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import os
from typing import Optional

import psycopg2
import requests

# Garantiza que 'src' sea importable cuando se ejecuta como script directo.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.config import connection_parameters


# ------------------------------------------------------------------ #
# Persistencia en bitácora (append-only)
# ------------------------------------------------------------------ #

def _log_bitacora(
    cur,
    pagina: int,
    intento: int,
    codigo_respuesta: Optional[int],
    duracion: float,
    resultado: str,
) -> None:
    """Inserta una fila en stg.bitacora_ingesta_api (puro INSERT, sin ON CONFLICT)."""
    cur.execute(
        """
        INSERT INTO stg.bitacora_ingesta_api
            (pagina, intento, codigo_respuesta, duracion, resultado)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (pagina, intento, codigo_respuesta, duracion, resultado),
    )


# ------------------------------------------------------------------ #
# UPSERT de medidores
# ------------------------------------------------------------------ #

def _upsert_medidores(cur, registros: list[dict]) -> tuple[int, int]:
    """Aplica INSERT … ON CONFLICT DO UPDATE a stg.stg_estado_medidor.

    Retorna (insertados, actualizados) usando xmax para distinguirlos.
    """
    if not registros:
        return 0, 0

    insertados = 0
    actualizados = 0

    for rec in registros:
        cur.execute(
            """
            INSERT INTO stg.stg_estado_medidor
                (meter_id, estado, ultimo_valor, unidad, timestamp_lectura)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (meter_id) DO UPDATE SET
                estado            = EXCLUDED.estado,
                ultimo_valor      = EXCLUDED.ultimo_valor,
                unidad            = EXCLUDED.unidad,
                timestamp_lectura = EXCLUDED.timestamp_lectura,
                _ingestado_en     = now()
            RETURNING (xmax = 0)::int AS es_insercion
            """,
            (
                rec.get("meter_id"),
                rec.get("estado"),
                rec.get("ultimo_valor"),
                rec.get("unidad"),
                rec.get("timestamp_lectura"),
            ),
        )
        row = cur.fetchone()
        if row and row[0]:
            insertados += 1
        else:
            actualizados += 1

    return insertados, actualizados


# ------------------------------------------------------------------ #
# Lógica principal
# ------------------------------------------------------------------ #

def ingestar(
    conn_params: dict,
    api_url: str,
    token: str,
    max_intentos: int = 3,
    t0: float = 1.0,
    tmax: float = 60.0,
) -> dict:
    """Ingesta completa desde la API paginada al staging.

    Parámetros
    ----------
    conn_params:
        Diccionario de conexión a PostgreSQL (host, port, dbname, user, password).
    api_url:
        URL base del endpoint, p.ej. http://localhost:5000/api/medidores.
    token:
        Token Bearer para Authorization.
    max_intentos:
        Número máximo de intentos por página (incluye el primero).
    t0:
        Tiempo base del backoff en segundos.
    tmax:
        Tiempo máximo de espera por intervalo en segundos.

    Retorno
    -------
    dict con:
        paginas_procesadas     — páginas con resultado EXITO o ERROR_PERMANENTE
        registros_insertados   — filas nuevas en stg_estado_medidor
        registros_actualizados — filas actualizadas en stg_estado_medidor
        estado_corrida         — COMPLETA | FALLO_AUTENTICACION | AGOTADO_REINTENTOS
    """
    paginas_procesadas = 0
    registros_insertados = 0
    registros_actualizados = 0
    estado_corrida = "COMPLETA"

    headers = {"Authorization": f"Bearer {token}"}
    pagina = 1
    hay_siguiente = True

    conn = psycopg2.connect(**conn_params)
    conn.autocommit = False

    try:
        while hay_siguiente is True:
            intento = 1
            exito_pagina = False

            while intento <= max_intentos:
                # Backoff antes del intento k ≥ 2
                if intento >= 2:
                    espera = min(t0 * 2 ** (intento - 2), tmax) + random.uniform(0, 1)
                    time.sleep(espera)

                t_inicio = time.monotonic()
                codigo_respuesta = None
                resultado_log = None

                try:
                    response = requests.get(
                        api_url,
                        params={"pagina": pagina},
                        headers=headers,
                        timeout=30,
                    )
                    duracion = time.monotonic() - t_inicio
                    codigo_respuesta = response.status_code

                    if codigo_respuesta == 200:
                        payload = response.json()
                        datos = payload.get("datos", [])
                        hay_siguiente = payload.get("hay_siguiente", False)

                        cur = conn.cursor()
                        ins, act = _upsert_medidores(cur, datos)
                        registros_insertados += ins
                        registros_actualizados += act
                        resultado_log = "EXITO"
                        _log_bitacora(cur, pagina, intento, codigo_respuesta, duracion, resultado_log)
                        conn.commit()

                        paginas_procesadas += 1
                        exito_pagina = True
                        break  # página completada

                    elif codigo_respuesta == 401:
                        resultado_log = "FALLO_AUTENTICACION"
                        cur = conn.cursor()
                        _log_bitacora(cur, pagina, intento, codigo_respuesta, duracion, resultado_log)
                        conn.commit()
                        estado_corrida = "FALLO_AUTENTICACION"
                        hay_siguiente = False  # abortar corrida
                        exito_pagina = True    # romper el loop interno
                        break

                    elif codigo_respuesta == 429 or (500 <= codigo_respuesta <= 599):
                        if intento < max_intentos:
                            resultado_log = "REINTENTO"
                        else:
                            resultado_log = "AGOTADO"
                        cur = conn.cursor()
                        _log_bitacora(cur, pagina, intento, codigo_respuesta, duracion, resultado_log)
                        conn.commit()

                        if intento >= max_intentos:
                            estado_corrida = "AGOTADO_REINTENTOS"
                            exito_pagina = True  # salir del loop interno
                            hay_siguiente = False  # abortar corrida
                            break
                        intento += 1
                        continue

                    else:
                        # Otros 4xx: error permanente, no reintentar
                        resultado_log = "ERROR_PERMANENTE"
                        cur = conn.cursor()
                        _log_bitacora(cur, pagina, intento, codigo_respuesta, duracion, resultado_log)
                        conn.commit()
                        paginas_procesadas += 1
                        exito_pagina = True
                        # Avanzar de página: hay_siguiente ya tiene el valor anterior
                        # Como no obtuvimos payload, no sabemos si hay más páginas;
                        # consideramos que sí las hay si la página anterior lo indicó
                        # pero forzamos avance usando el último hay_siguiente conocido.
                        break

                except requests.exceptions.Timeout:
                    duracion = time.monotonic() - t_inicio
                    if intento < max_intentos:
                        resultado_log = "REINTENTO"
                    else:
                        resultado_log = "AGOTADO"
                    cur = conn.cursor()
                    _log_bitacora(cur, pagina, intento, None, duracion, resultado_log)
                    conn.commit()

                    if intento >= max_intentos:
                        estado_corrida = "AGOTADO_REINTENTOS"
                        hay_siguiente = False
                        exito_pagina = True
                        break
                    intento += 1
                    continue

                except requests.exceptions.RequestException as exc:
                    duracion = time.monotonic() - t_inicio
                    resultado_log = "ERROR_PERMANENTE"
                    cur = conn.cursor()
                    _log_bitacora(cur, pagina, intento, None, duracion, resultado_log)
                    conn.commit()
                    paginas_procesadas += 1
                    exito_pagina = True
                    break

            # Verificar si debemos abortar antes de avanzar de página
            if estado_corrida in ("FALLO_AUTENTICACION", "AGOTADO_REINTENTOS"):
                break

            pagina += 1

    finally:
        conn.close()

    return {
        "paginas_procesadas": paginas_procesadas,
        "registros_insertados": registros_insertados,
        "registros_actualizados": registros_actualizados,
        "estado_corrida": estado_corrida,
    }


# ------------------------------------------------------------------ #
# Punto de entrada CLI
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conector de ingesta desde API REST paginada a stg.stg_estado_medidor"
    )
    parser.add_argument("--url", required=True, help="URL del endpoint de la API")
    parser.add_argument("--token", required=True, help="Token Bearer para Authorization")
    parser.add_argument(
        "--max-intentos",
        type=int,
        default=3,
        dest="max_intentos",
        help="Máximo de intentos por página (default: 3)",
    )
    parser.add_argument(
        "--t0",
        type=float,
        default=1.0,
        help="Tiempo base de backoff en segundos (default: 1.0)",
    )
    parser.add_argument(
        "--tmax",
        type=float,
        default=60.0,
        help="Tiempo máximo de espera por intervalo en segundos (default: 60.0)",
    )
    args = parser.parse_args()

    conn_params = connection_parameters()

    result = ingestar(
        conn_params=conn_params,
        api_url=args.url,
        token=args.token,
        max_intentos=args.max_intentos,
        t0=args.t0,
        tmax=args.tmax,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
