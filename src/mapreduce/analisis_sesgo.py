"""T4 · Nivel Frontera: análisis del sesgo de la clave `departamento`.

Mide, sobre el dato real, si alguna clave concentra tanto trabajo que
un solo reductor se vuelve el cuello de botella, y evalúa una clave
compuesta candidata para redistribuir la carga.

Uso:
    python3 src/mapreduce/analisis_sesgo.py [ruta_csv]
"""
import csv
import sys
from collections import Counter
from pathlib import Path


def main():
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/precipitacion_2026-06-22.csv")

    por_departamento = Counter()
    por_estacion_en_bogota = Counter()
    total = 0

    with open(ruta, encoding="utf-8-sig") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            total += 1
            depto = fila["departamento"].strip()
            por_departamento[depto] += 1
            if depto == "BOGOTÁ":
                por_estacion_en_bogota[fila["codigoestacion"]] += 1

    print("=" * 68)
    print("SESGO DE LA CLAVE ACTUAL: departamento")
    print("=" * 68)
    print(f"  Registros totales      : {total:,}")
    print(f"  Departamentos distintos: {len(por_departamento)}")
    print()
    print(f"  {'Departamento':30s} {'Registros':>10s} {'% del total':>12s}")
    for depto, conteo in por_departamento.most_common(5):
        print(f"  {depto:30s} {conteo:10,d} {conteo/total*100:11.2f}%")

    top_depto, top_conteo = por_departamento.most_common(1)[0]
    print()
    print(f"  El departamento con más carga ({top_depto}) concentra el "
          f"{top_conteo/total*100:.2f} % de los registros.")
    print("  Ese reductor procesaría esa fracción del trabajo total, sin "
          "importar cuántos reductores más se añadan.")

    print()
    print("=" * 68)
    print(f"CLAVE COMPUESTA CANDIDATA: departamento + codigoestacion")
    print(f"(evaluada sobre las estaciones dentro de {top_depto})")
    print("=" * 68)
    n_estaciones = len(por_estacion_en_bogota)
    print(f"  Estaciones distintas dentro de {top_depto}: {n_estaciones}")
    print(f"  Registros promedio por estación: {top_conteo/n_estaciones:.1f}")
    print(f"  Registros de la estación con más carga: "
          f"{por_estacion_en_bogota.most_common(1)[0][1]:,} "
          f"({por_estacion_en_bogota.most_common(1)[0][1]/total*100:.2f} % del total)")
    print()
    print(f"  Con la clave compuesta, el {top_conteo/total*100:.2f} % que hoy va a un "
          f"solo reductor se reparte en {n_estaciones} claves distintas.")


if __name__ == "__main__":
    main()
