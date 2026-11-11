"""API Mock para T13 · Conector de Ingesta API.

Simula una API REST de medidores con paginación y comportamientos
de error configurables por equipo.

Perfiles de respuesta:
  equipo-1 (control): 200 siempre, 3 páginas de 5 registros cada una.
  equipo-2: páginas 1-2 → 200, página 3 → 429 dos veces luego 200.
  equipo-3: página 1 → 200, página 2 → 500 tres veces (agotado), página 3 → 200.
  equipo-4: página 1 → 200, página 2 → 401 (aborta corrida).
  equipo-5: página 1 → 200, página 2 → 404 (error permanente), página 3 → 200.

Uso:
    python practica/s13-conector-api/api_mock.py --equipo equipo-1 --port 5000
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any

from flask import Flask, jsonify, request

app = Flask(__name__)

# Contador de intentos por página (en memoria, se reinicia al relanzar el mock).
# Clave: pagina (int) → número de veces que fue llamada esa página.
_contadores: dict[int, int] = defaultdict(int)

# Perfil activo (configurado en main via argparse, almacenado globalmente).
_equipo: str = "equipo-1"


# ------------------------------------------------------------------ #
# Generadores de datos
# ------------------------------------------------------------------ #

def _registros_pagina(pagina: int, cantidad: int = 5) -> list[dict[str, Any]]:
    """Genera `cantidad` registros de medidores para la página dada."""
    base = (pagina - 1) * cantidad
    return [
        {
            "meter_id": f"MED-{base + i + 1:04d}",
            "estado": "ACTIVO",
            "ultimo_valor": round(100.0 + (base + i) * 0.5, 2),
            "unidad": "kWh",
            "timestamp_lectura": f"2026-06-22T{8 + (base + i) % 12:02d}:00:00+00:00",
        }
        for i in range(cantidad)
    ]


# ------------------------------------------------------------------ #
# Lógica de respuesta por perfil
# ------------------------------------------------------------------ #

def _responder_equipo1(pagina: int):
    """Equipo 1 — control: siempre 200, 3 páginas de 5 registros."""
    if pagina > 3:
        return jsonify({
            "datos": [],
            "hay_siguiente": False,
            "total_registros_informativo": 15,
        }), 200
    return jsonify({
        "datos": _registros_pagina(pagina),
        "hay_siguiente": pagina < 3,
        "total_registros_informativo": 15,
    }), 200


def _responder_equipo2(pagina: int):
    """Equipo 2: páginas 1-2 → 200; página 3 → 429 las primeras 2 llamadas, luego 200."""
    if pagina <= 2:
        return jsonify({
            "datos": _registros_pagina(pagina),
            "hay_siguiente": True,
            "total_registros_informativo": 15,
        }), 200

    if pagina == 3:
        intento = _contadores[pagina]
        if intento < 2:
            return jsonify({"error": "Too Many Requests"}), 429
        return jsonify({
            "datos": _registros_pagina(pagina),
            "hay_siguiente": False,
            "total_registros_informativo": 15,
        }), 200

    return jsonify({
        "datos": [],
        "hay_siguiente": False,
        "total_registros_informativo": 15,
    }), 200


def _responder_equipo3(pagina: int):
    """Equipo 3: página 1 → 200; página 2 → 500 siempre (agotado); página 3 → 200."""
    if pagina == 1:
        return jsonify({
            "datos": _registros_pagina(pagina),
            "hay_siguiente": True,
            "total_registros_informativo": 15,
        }), 200

    if pagina == 2:
        # Siempre devuelve 500; el conector agotará sus reintentos.
        return jsonify({"error": "Internal Server Error"}), 500

    if pagina == 3:
        return jsonify({
            "datos": _registros_pagina(pagina),
            "hay_siguiente": False,
            "total_registros_informativo": 15,
        }), 200

    return jsonify({
        "datos": [],
        "hay_siguiente": False,
        "total_registros_informativo": 15,
    }), 200


def _responder_equipo4(pagina: int):
    """Equipo 4: página 1 → 200; página 2 → 401 (abortar corrida)."""
    if pagina == 1:
        return jsonify({
            "datos": _registros_pagina(pagina),
            "hay_siguiente": True,
            "total_registros_informativo": 15,
        }), 200

    # Cualquier página posterior devuelve 401
    return jsonify({"error": "Unauthorized"}), 401


def _responder_equipo5(pagina: int):
    """Equipo 5: página 1 → 200; página 2 → 404 (error permanente); página 3 → 200."""
    if pagina == 1:
        return jsonify({
            "datos": _registros_pagina(pagina),
            "hay_siguiente": True,
            "total_registros_informativo": 15,
        }), 200

    if pagina == 2:
        return jsonify({"error": "Not Found"}), 404

    if pagina == 3:
        return jsonify({
            "datos": _registros_pagina(pagina),
            "hay_siguiente": False,
            "total_registros_informativo": 15,
        }), 200

    return jsonify({
        "datos": [],
        "hay_siguiente": False,
        "total_registros_informativo": 15,
    }), 200


# ------------------------------------------------------------------ #
# Endpoint principal
# ------------------------------------------------------------------ #

@app.route("/api/medidores")
def get_medidores():
    """GET /api/medidores?pagina=N

    Verifica header Authorization: Bearer <token>.
    Delega la respuesta al perfil del equipo configurado.
    """
    # Verificación de autenticación (cualquier token no-vacío pasa)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or len(auth) <= len("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        pagina = int(request.args.get("pagina", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "parámetro pagina debe ser entero"}), 400

    # Incrementar el contador de intentos para esta página
    _contadores[pagina] += 1

    _PERFILES = {
        "equipo-1": _responder_equipo1,
        "equipo-2": _responder_equipo2,
        "equipo-3": _responder_equipo3,
        "equipo-4": _responder_equipo4,
        "equipo-5": _responder_equipo5,
    }

    handler = _PERFILES.get(_equipo, _responder_equipo1)
    return handler(pagina)


# ------------------------------------------------------------------ #
# Punto de entrada
# ------------------------------------------------------------------ #

def main():
    global _equipo, _contadores

    parser = argparse.ArgumentParser(
        description="API Mock para T13 · Conector de Ingesta API"
    )
    parser.add_argument(
        "--equipo",
        default="equipo-1",
        help="Perfil de respuestas: equipo-1 .. equipo-5 (default: equipo-1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Puerto en que escucha el servidor (default: 5000)",
    )
    args = parser.parse_args()

    _equipo = args.equipo
    _contadores = defaultdict(int)  # reiniciar contadores al arrancar

    print(f"[api_mock] Equipo: {_equipo} | Puerto: {args.port}")
    app.run(host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
