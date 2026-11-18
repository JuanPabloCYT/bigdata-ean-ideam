#!/usr/bin/env python3
"""T14 · Generador del perfil de cambios del maestro de suscriptores.

Uso:

    python generar_cambios_suscriptores.py --equipo equipo-2

Produce un perfil de cambios **determinístico por equipo** (total_suscriptores,
n_alta, n_modificacion, n_baja, prob_baja_dura) y el plan de cambios exacto
que el prototipo de CDC aplica después de la población inicial.

El perfil se identifica por el CONJUNTO completo de sus valores, no por uno
solo: dos equipos pueden coincidir en un indicador aislado (por ejemplo, el
mismo número de bajas) sin que eso signifique nada. Aquí ``prob_baja_dura`` se
deriva como ``n_baja / total_suscriptores`` (la tasa realizada de bajas duras),
de modo que la probabilidad y el conteo son siempre consistentes entre sí.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from typing import Dict, List

# ---------------------------------------------------------------------------
# Perfil base por equipo.
#
# Cada equipo recibe un total_suscriptores, un número de altas, un número de
# modificaciones y un número de bajas duras distintos. prob_baja_dura se calcula
# como n_baja / total_suscriptores, así que el conteo y la probabilidad coinciden
# sin redondeo. El conjunto completo (total, altas, modif, bajas, prob) es único
# por equipo; dos equipos pueden empatar en UN indicador aislado (equipo-1,
# equipo-5 y equipo-6 comparten n_baja=6) sin repetir el perfil completo.
# ---------------------------------------------------------------------------
PERFILES: Dict[str, Dict[str, int]] = {
    "equipo-1": dict(total_suscriptores=120, n_alta=8,  n_modificacion=13, n_baja=6),
    "equipo-2": dict(total_suscriptores=160, n_alta=14, n_modificacion=18, n_baja=10),
    "equipo-3": dict(total_suscriptores=200, n_alta=10, n_modificacion=20, n_baja=8),
    "equipo-4": dict(total_suscriptores=90,  n_alta=6,  n_modificacion=9,  n_baja=7),
    "equipo-5": dict(total_suscriptores=130, n_alta=11, n_modificacion=14, n_baja=6),
    "equipo-6": dict(total_suscriptores=110, n_alta=7,  n_modificacion=11, n_baja=6),
}


@dataclass
class Perfil:
    equipo: str
    total_suscriptores: int
    n_alta: int
    n_modificacion: int
    n_baja: int
    prob_baja_dura: float
    numero_cambios: int
    # Plan de cambios determinista (subscriber_id por cambiar):
    altas: List[int]            # ids NUEVOS: total+1 .. total+n_alta
    modificaciones: List[int]   # ids existentes a modificar: 1 .. n_modificacion
    bajas: List[int]            # ids existentes a borrar (duras): n_mod+1 .. n_mod+n_baja


def generar_perfil(equipo: str) -> Perfil:
    base = PERFILES[equipo]
    total = base["total_suscriptores"]
    n_alta = base["n_alta"]
    n_mod = base["n_modificacion"]
    n_baja = base["n_baja"]
    prob = round(n_baja / total, 4)
    # Plan determinista, sin solapamiento entre modificaciones y bajas:
    altas = list(range(total + 1, total + 1 + n_alta))
    modificaciones = list(range(1, 1 + n_mod))
    bajas = list(range(1 + n_mod, 1 + n_mod + n_baja))
    return Perfil(
        equipo=equipo,
        total_suscriptores=total,
        n_alta=n_alta,
        n_modificacion=n_mod,
        n_baja=n_baja,
        prob_baja_dura=prob,
        numero_cambios=n_alta + n_mod + n_baja,
        altas=altas,
        modificaciones=modificaciones,
        bajas=bajas,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--equipo", required=True, choices=sorted(PERFILES))
    ap.add_argument(
        "--out",
        default=None,
        help="Ruta del JSON a escribir (por defecto: perfil_<equipo>.json).",
    )
    args = ap.parse_args()

    perfil = generar_perfil(args.equipo)
    # Reporte que consume el resto de la entrega:
    print(f"equipo={perfil.equipo}")
    print(f"total_suscriptores={perfil.total_suscriptores}")
    print(f"numero_cambios={perfil.numero_cambios}")
    print(f"n_alta={perfil.n_alta}")
    print(f"n_modificacion={perfil.n_modificacion}")
    print(f"n_baja={perfil.n_baja}")
    print(f"prob_baja_dura={perfil.prob_baja_dura}")

    out = args.out or f"perfil_{args.equipo}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(asdict(perfil), f, indent=2, ensure_ascii=False)
    print(f"perfil_escrito={out}")


if __name__ == "__main__":
    main()
