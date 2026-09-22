"""Mide, contra la fuente real, las cardinalidades que sostienen el modelo de T10.

El modelo dimensional de T10 se justifica con cifras (cuantas filas tendria cada
dimension, si una jerarquia es realmente jerarquica, si un nombre sirve de clave).
Este script las mide en vez de estimarlas, para que cualquiera pueda rehacerlas.

Uso:
    python3 src/modelo/medir_cardinalidades.py [--date AAAA-MM-DD]
"""

import argparse
import json
import urllib.parse
import urllib.request
from datetime import date, timedelta

BASE = "https://www.datos.gov.co/resource/s54a-sgyg.json"
FECHA_POR_DEFECTO = "2026-06-22"
LIMITE = 50000  # muy por encima de cualquier cardinalidad esperada; evita truncar


def _consulta(params: dict) -> list:
    url = BASE + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def _where(dia: date) -> str:
    sig = dia + timedelta(days=1)
    return (f"fechaobservacion >= '{dia.isoformat()}T00:00:00' "
            f"AND fechaobservacion < '{sig.isoformat()}T00:00:00'")


def distintos(where: str, campo: str) -> int:
    """Cuantos valores distintos toma el campo en la particion."""
    filas = _consulta({"$select": f"{campo}", "$where": where,
                       "$group": campo, "$limit": LIMITE})
    if len(filas) >= LIMITE:
        raise RuntimeError(f"{campo}: la consulta alcanzo el limite {LIMITE}; "
                           "la cifra estaria truncada")
    return len(filas)


def cruces(where: str, campo: str, contra: str) -> list:
    """Valores de `campo` que aparecen bajo mas de un valor de `contra`."""
    filas = _consulta({"$select": f"{campo}, count(distinct {contra}) as n",
                       "$where": where, "$group": campo, "$limit": LIMITE})
    if len(filas) >= LIMITE:
        raise RuntimeError(f"{campo}: consulta truncada en {LIMITE}")
    return sorted([f for f in filas if int(f["n"]) > 1],
                  key=lambda f: (-int(f["n"]), f[campo] or ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=FECHA_POR_DEFECTO)
    dia = date.fromisoformat(ap.parse_args().date)
    where = _where(dia)

    campos = ["codigoestacion", "codigosensor", "fechaobservacion", "nombreestacion",
              "departamento", "municipio", "zonahidrografica", "descripcionsensor",
              "unidadmedida"]

    lineas = []
    def w(s=""):
        print(s)
        lineas.append(s)

    w("=" * 68)
    w(f"CARDINALIDADES DE LA FUENTE · particion {dia.isoformat()} · s54a-sgyg")
    w("=" * 68)
    w()
    w(f"  {'campo':<22}{'valores distintos':>18}")
    w(f"  {'-'*22}{'-'*18}")
    for c in campos:
        w(f"  {c:<22}{distintos(where, c):>18,}")

    w()
    w("=" * 68)
    w("EL NOMBRE DE LA ESTACION NO SIRVE COMO CLAVE NATURAL")
    w("=" * 68)
    rep = cruces(where, "nombreestacion", "codigoestacion")
    w(f"  Nombres usados por mas de un codigo de estacion: {len(rep)}")
    for f in rep:
        w(f"    {f['nombreestacion'][:44]:<46}{f['n']} codigos")

    w()
    w("=" * 68)
    w("LA ZONA HIDROGRAFICA NO ES UN NIVEL BAJO EL DEPARTAMENTO")
    w("=" * 68)
    zc = cruces(where, "zonahidrografica", "departamento")
    total_z = distintos(where, "zonahidrografica")
    w(f"  Zonas hidrograficas: {total_z} · cruzan mas de un departamento: {len(zc)}")
    for f in zc:
        w(f"    {f['zonahidrografica'][:44]:<46}{f['n']} departamentos")

    w()
    w("=" * 68)
    w("EL NOMBRE DEL MUNICIPIO TAMPOCO IDENTIFICA POR SI SOLO")
    w("=" * 68)
    mc = cruces(where, "municipio", "departamento")
    pares = len(_consulta({"$select": "departamento, municipio", "$where": where,
                           "$group": "departamento, municipio", "$limit": LIMITE}))
    w(f"  Nombres de municipio en mas de un departamento: {len(mc)}")
    for f in mc:
        w(f"    {f['municipio'][:44]:<46}{f['n']} departamentos")
    w(f"  Pares (departamento, municipio) distintos: {pares}")

    salida = "practica/s10-dimensional/resultados/cardinalidades.txt"
    with open(salida, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas) + "\n")
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
