"""T3 · Proyección de almacenamiento y factor de réplica.

Calcula el volumen a doce meses y el almacenamiento físico para los
factores de réplica 1, 2 y 3, sobre la fuente consolidada del equipo.

Reproducibilidad: los insumos NO están escritos a mano. Se leen de
`docs/T1/evidencia/resultados_medicion.json`, el archivo que produjo el
cuaderno de medición de T1. Otra persona con esa ficha corre este script
y obtiene exactamente las mismas cifras.

Uso:
    python3 src/proyeccion_almacenamiento.py
"""

import json
import math
from pathlib import Path

# --- Constantes de la sesión 3 -------------------------------------------
GB = 1024 ** 3
MB = 1024 ** 2
BLOQUE_HDFS = 128 * MB      # valor real de HDFS, no el didáctico de 1 MB
DIAS_ANIO = 365
MESES_HORIZONTE = 12
FACTORES = (1, 2, 3)

RAIZ = Path(__file__).resolve().parents[1]
FICHA = RAIZ / "docs" / "T1" / "evidencia" / "resultados_medicion.json"


def cargar_insumos():
    """Lee de la ficha T1 los dos insumos de la proyección: S0 y g."""
    datos = json.loads(FICHA.read_text(encoding="utf-8"))
    return {
        "S0_bytes": datos["disco"]["S0_bytes"],
        "S0_alcance": datos["disco"]["alcance_S0"],
        "g_anual": datos["crecimiento"]["g_historico_anual"],
        "g_mensual": datos["crecimiento"]["g_historico_mensual_equivalente"],
        "registros_dia": datos["periodos_medicion"]["conteo_principal"],
        "equipo": datos["entorno"]["sistema_operativo"],
    }


def volumen_actual_anual(S0_bytes):
    """Volumen lógico que la fuente produce en un año al ritmo de hoy.

    T1 midió S0 sobre UNA partición diaria, no sobre el repositorio
    acumulado. Para aplicar la fórmula del enunciado hace falta un
    'volumen actual', y el que tiene sentido para dimensionar disco es
    lo que la fuente genera en un año: 365 particiones diarias.
    """
    return DIAS_ANIO * S0_bytes


def proyeccion_compuesta(volumen_inicial, tasa_mensual, meses=MESES_HORIZONTE):
    """Fórmula del enunciado: V * (1 + g_mensual) ** meses.

    Responde: ¿cuánto producirá la fuente durante el año SIGUIENTE?
    """
    return volumen_inicial * (1 + tasa_mensual) ** meses


def proyeccion_acumulada(S0_bytes, tasa_mensual, meses=MESES_HORIZONTE):
    """Volumen acumulado tras `meses` de operación, mes a mes.

    Un repositorio de particiones diarias crece por SUMA: cada mes añade
    sus particiones, cuyo tamaño cambia según la tasa. Esta es la cifra
    que dimensiona el disco a comprar. T1 advirtió que este modelo
    aditivo hacía falta y no se había construido; aquí se construye.
    """
    dias_por_mes = DIAS_ANIO / meses
    return sum(
        dias_por_mes * S0_bytes * (1 + tasa_mensual) ** mes
        for mes in range(meses)
    )


def bloques(tamano_bytes, tamano_bloque=BLOQUE_HDFS):
    """Número de bloques: tamaño entre tamaño de bloque, hacia arriba."""
    return math.ceil(tamano_bytes / tamano_bloque)


def tasa_mensual_desde_anual(g_anual):
    """Convierte una tasa anual a su equivalente mensual compuesta."""
    return (1 + g_anual) ** (1 / 12) - 1


def main():
    ins = cargar_insumos()
    S0 = ins["S0_bytes"]
    V0 = volumen_actual_anual(S0)

    print("=" * 72)
    print("T3 · PROYECCIÓN DE ALMACENAMIENTO · Precipitación del IDEAM")
    print("=" * 72)

    print("\n1. INSUMOS (leídos de docs/T1/evidencia/resultados_medicion.json)")
    print("-" * 72)
    print(f"  S0, partición diaria     : {S0:,} bytes = {S0/MB:.2f} MB")
    print(f"  Registros de esa partición: {ins['registros_dia']:,}")
    print(f"  Alcance de S0            : {ins['S0_alcance']}")
    print(f"  g histórico anual        : {ins['g_anual']:.10f} = {ins['g_anual']*100:.6f} %")
    print(f"  g mensual equivalente    : {ins['g_mensual']:.10f} = {ins['g_mensual']*100:.6f} %")
    print(f"  Equipo de la medición    : {ins['equipo']}")

    print("\n2. VOLUMEN ACTUAL")
    print("-" * 72)
    print("  T1 midió una partición diaria, no el repositorio acumulado.")
    print("  Se define el volumen actual como un año de operación al ritmo")
    print("  de hoy, que es la base con la que se dimensiona el disco:")
    print(f"    V0 = 365 x {S0:,} = {V0:,} bytes = {V0/GB:.4f} GB")

    escenarios = {
        "Histórico (g = -4,780861 % anual)": ins["g_mensual"],
        "Conservador (g = 0 % anual)": 0.0,
        "Sensibilidad (g = +1 % anual)": tasa_mensual_desde_anual(0.01),
    }

    print("\n3. VOLUMEN A DOCE MESES · DOS MODELOS")
    print("-" * 72)
    print("  Modelo A, fórmula del enunciado: V0 x (1 + g_mensual) ^ 12")
    print("    -> lo que la fuente PRODUCIRÁ durante el año siguiente.")
    print("  Modelo B, acumulado mes a mes: suma de las particiones.")
    print("    -> lo que habrá que TENER GUARDADO al cabo de 12 meses.")
    print()
    print(f"  {'Escenario':36s} {'Modelo A':>12s} {'Modelo B':>12s}")
    resultados = {}
    for nombre, g_m in escenarios.items():
        va = proyeccion_compuesta(V0, g_m)
        vb = proyeccion_acumulada(S0, g_m)
        resultados[nombre] = {"A": va, "B": vb}
        print(f"  {nombre:36s} {va/GB:9.4f} GB {vb/GB:9.4f} GB")

    print("\n4. ALMACENAMIENTO FÍSICO POR FACTOR DE RÉPLICA")
    print("-" * 72)
    print("  Físico = volumen lógico x R. Se usa el Modelo B, que es el que")
    print("  dimensiona el disco. Tolerancia: R = 1 -> 0 nodos; R = 2 -> 1; R = 3 -> 2.")
    print()
    print(f"  {'Escenario':36s} {'R=1':>10s} {'R=2':>10s} {'R=3':>10s}")
    for nombre, vals in resultados.items():
        v = vals["B"]
        fila = "".join(f" {v*R/GB:9.3f}" for R in FACTORES)
        print(f"  {nombre:36s}{fila}")

    print("\n  Escenario de dimensionamiento (el más exigente, +1 % anual):")
    v_dim = resultados["Sensibilidad (g = +1 % anual)"]["B"]
    for R in FACTORES:
        print(
            f"    R={R}: {v_dim*R/GB:7.3f} GB   "
            f"tolera {R-1} nodo(s) caído(s)   costo {R}x"
        )

    print("\n5. NÚMERO DE BLOQUES (bloque real de HDFS = 128 MB)")
    print("-" * 72)
    b_particion = bloques(S0)
    print(f"  Partición diaria de {S0/MB:.2f} MB -> {b_particion} bloque")
    print(f"    ocupa el {S0/BLOQUE_HDFS*100:.1f} % de un bloque de 128 MB")
    print(f"  Un año en particiones diarias -> {DIAS_ANIO} archivos, "
          f"{DIAS_ANIO*b_particion} bloques")
    b_consolidado = bloques(v_dim)
    print(f"  Un año consolidado por mes    -> 12 archivos, "
          f"{b_consolidado} bloques")

    heap = 150  # bytes por objeto en el nodo maestro, valor de referencia
    obj_diario = DIAS_ANIO + DIAS_ANIO * b_particion
    obj_mensual = 12 + b_consolidado
    print(f"\n  Metadatos en el nodo maestro (~{heap} B por objeto):")
    print(f"    particiones diarias : {obj_diario:,} objetos = {obj_diario*heap/MB:.3f} MB")
    print(f"    consolidado mensual : {obj_mensual:,} objetos = {obj_mensual*heap/MB:.3f} MB")
    print(f"    reducción de objetos: {(1-obj_mensual/obj_diario)*100:.1f} %")

    print("\n" + "=" * 72)


if __name__ == "__main__":
    main()
