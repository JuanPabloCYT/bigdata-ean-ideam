"""Calcula la matriz ponderada del ADR de T9 y su analisis de sensibilidad.

Los criterios son los seis comunes a todos los equipos. Los pesos y las
calificaciones son los de este equipo, justificados en el ADR. El script existe
para que el puntaje no dependa de una suma hecha a mano y para localizar, sin
tanteo, el punto en que la decision bascula.

Uso:  python3 practica/s09-adr/calcular_matriz.py
"""

CRITERIOS = [
    # (criterio, peso %, almacen, lago, lakehouse)
    ("Costo de almacenamiento",                    10, 2, 5, 4),
    ("Flexibilidad de esquema",                    10, 2, 5, 4),
    ("Rendimiento de consulta analitica",          25, 5, 4, 4),
    ("Soporte transaccional y viaje en el tiempo", 15, 3, 2, 5),
    ("Complejidad operativa",                      25, 3, 5, 3),
    ("Adecuacion al volumen y la frescura",        15, 3, 5, 4),
]
OPCIONES = ("Almacen", "Lago", "Lakehouse")


def calcular(criterios):
    return {op: round(sum(f[1] / 100 * f[2 + i] for f in criterios), 4)
            for i, op in enumerate(OPCIONES)}


def basculacion(criterios, sube: str, baja: str):
    """Punto en que Lakehouse alcanza a Lago moviendo peso de `baja` a `sube`."""
    i_sube = next(k for k, f in enumerate(criterios) if f[0] == sube)
    i_baja = next(k for k, f in enumerate(criterios) if f[0] == baja)
    bolsa = criterios[i_sube][1] + criterios[i_baja][1]
    anterior = None
    for t in range(0, bolsa + 1):
        mod = list(criterios)
        mod[i_sube] = (mod[i_sube][0], t) + mod[i_sube][2:]
        mod[i_baja] = (mod[i_baja][0], bolsa - t) + mod[i_baja][2:]
        p = calcular(mod)
        gana = max(OPCIONES, key=lambda o: p[o])
        if anterior and gana != anterior:
            return t, p, bolsa
        anterior = gana
    return None, None, bolsa


def main():
    lineas = []
    def w(s=""):
        print(s); lineas.append(s)

    total = sum(f[1] for f in CRITERIOS)
    w("=" * 78)
    w("MATRIZ DE CRITERIOS PONDERADOS · T9 · ADR 0001")
    w("=" * 78)
    w(f"  {'Criterio':<44}{'Peso':>6}{'Alm':>6}{'Lago':>6}{'Lake':>6}")
    w(f"  {'-'*44}{'-'*6}{'-'*6}{'-'*6}{'-'*6}")
    for c, p, a, l, k in CRITERIOS:
        w(f"  {c:<44}{p:>5}%{a:>6}{l:>6}{k:>6}")
    w(f"  {'-'*44}{'-'*6}{'-'*6}{'-'*6}{'-'*6}")
    w(f"  {'SUMA DE PESOS':<44}{total:>5}%")
    if total != 100:
        raise SystemExit(f"ERROR: los pesos suman {total}, deben sumar 100")

    p = calcular(CRITERIOS)
    w()
    w("  Puntaje ponderado")
    for op in OPCIONES:
        w(f"    {op:<12}{p[op]:>6.2f}")
    ganador = max(OPCIONES, key=lambda o: p[o])
    segundo = sorted(OPCIONES, key=lambda o: -p[o])[1]
    w(f"\n  Gana: {ganador} ({p[ganador]:.2f}), por {p[ganador]-p[segundo]:.2f} sobre {segundo}")

    w()
    w("=" * 78)
    w("ANALISIS DE SENSIBILIDAD · nivel Frontera")
    w("=" * 78)
    sube = "Soporte transaccional y viaje en el tiempo"
    baja = "Complejidad operativa"
    w(f"  Se mueve peso de '{baja}' hacia")
    w(f"  '{sube}', manteniendo los otros cuatro criterios fijos.")
    t, pt, bolsa = basculacion(CRITERIOS, sube, baja)
    actual = next(f[1] for f in CRITERIOS if f[0] == sube)
    if t is None:
        w("  La decision no bascula en todo el rango: es muy robusta.")
    else:
        w(f"\n  Peso actual del criterio transaccional : {actual} %")
        w(f"  Peso en que Lakehouse alcanza a Lago   : {t} %  (y {bolsa-t} % para complejidad)")
        w(f"  Desplazamiento necesario               : +{t-actual} puntos porcentuales")
        w(f"\n  En el punto de basculacion: " +
          "  ".join(f"{o}={pt[o]:.2f}" for o in OPCIONES))
        w(f"\n  Lectura: hace falta mas de la mitad del peso actual de ese criterio")
        w(f"  para que la decision cambie. Es una decision moderadamente robusta,")
        w(f"  no una que se voltee moviendo un punto.")

    salida = "practica/s09-adr/resultados/matriz_ponderada.txt"
    with open(salida, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas) + "\n")
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
