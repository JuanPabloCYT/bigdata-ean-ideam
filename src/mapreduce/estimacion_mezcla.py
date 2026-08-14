"""T4 · Estimación teórica del volumen de mezcla.

Calcula, a partir del esquema real del dato (no de cifras escritas a
mano), cuántos bytes deberían atravesar la mezcla al agregar
`valorobservado` por `departamento`, con y sin combinador. La cifra no
busca acertar el número exacto del contador real -eso lo hace la
mezcla del framework, con su propio formato de serialización- sino
razonar el orden de magnitud antes de ejecutar.

Uso:
    python3 src/mapreduce/estimacion_mezcla.py [ruta_csv] [num_splits]
"""
import csv
import sys
from pathlib import Path

COL_VALOR = "valorobservado"
COL_CLAVE = "departamento"


def medir_esquema(ruta_csv):
    """Recorre el CSV una vez y mide lo que la estimación necesita."""
    total = 0
    key_bytes = 0
    val_bytes = 0
    claves = set()
    with open(ruta_csv, encoding="utf-8-sig") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            clave = fila[COL_CLAVE].strip()
            valor = fila[COL_VALOR]
            total += 1
            key_bytes += len(clave.encode("utf-8"))
            val_bytes += len(valor.encode("utf-8"))
            claves.add(clave)
    return {
        "total_registros": total,
        "avg_key_bytes": key_bytes / total,
        "avg_val_bytes": val_bytes / total,
        "claves_distintas": len(claves),
    }


def main():
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/precipitacion_2026-06-22.csv")
    n_splits = int(sys.argv[2]) if len(sys.argv) > 2 else 6

    esquema = medir_esquema(ruta)
    n = esquema["total_registros"]
    avg_key = esquema["avg_key_bytes"]
    avg_val = esquema["avg_val_bytes"]
    n_claves = esquema["claves_distintas"]

    # Sin combinador: un par (clave, valor,1) por registro de entrada.
    avg_pair_sin = avg_key + 1 + len(str(round(avg_val))) + 3 + 1  # \t + "valor,1" + \n, aprox
    # Aproximacion mas fiel: promedio real de "valor,1" en texto.
    avg_val_texto = avg_val + 2  # ",1" añadido por el mapper
    avg_pair_sin = avg_key + 1 + avg_val_texto + 1
    teorico_sin = n * avg_pair_sin

    # Con combinador: como maximo, un par por clave distinta y por
    # tarea de mapeo (division). El valor real sera menor o igual,
    # porque no todas las claves aparecen en todas las divisiones.
    avg_pair_con = avg_key + 1 + 12 + 1  # "suma,conteo" en texto, ~12 caracteres
    cota_superior_con = n_splits * n_claves * avg_pair_con
    pares_cota_superior = n_splits * n_claves

    print("=" * 68)
    print("ESQUEMA MEDIDO SOBRE EL DATO REAL")
    print("=" * 68)
    print(f"  Registros totales          : {n:,}")
    print(f"  Departamentos distintos    : {n_claves}")
    print(f"  Bytes promedio de la clave : {avg_key:.3f}")
    print(f"  Bytes promedio del valor   : {avg_val:.3f}")

    print()
    print("=" * 68)
    print("ESTIMACION SIN COMBINADOR")
    print("=" * 68)
    print(f"  Pares emitidos (= registros): {n:,}")
    print(f"  Bytes por par (aprox)       : {avg_pair_sin:.2f}")
    print(f"  Bytes de mezcla (teorico)   : {teorico_sin:,.0f}")

    print()
    print("=" * 68)
    print(f"ESTIMACION CON COMBINADOR ({n_splits} tareas de mapeo)")
    print("=" * 68)
    print(f"  Pares, cota superior (splits x claves): {n_splits} x {n_claves} = {pares_cota_superior}")
    print(f"  Bytes por par agregado (aprox)         : {avg_pair_con:.2f}")
    print(f"  Bytes de mezcla, cota superior (teorico): {cota_superior_con:,.0f}")

    print()
    print(f"  Reduccion teorica esperada: {(1 - cota_superior_con/teorico_sin)*100:.1f} %")


if __name__ == "__main__":
    main()
