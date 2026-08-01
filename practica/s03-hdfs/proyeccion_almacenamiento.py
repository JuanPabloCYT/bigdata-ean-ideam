"""Nivel 3 · Proyección de almacenamiento a 12 meses.

Toma S0 de la ficha T1 (partición diaria medida) y proyecta el
almacenamiento acumulado para los factores de réplica 1, 2 y 3.

Reproducible: lee las cifras de docs/T1/evidencia/resultados_medicion.json
en lugar de tenerlas escritas a mano, así que otra persona con la misma
ficha obtiene exactamente los mismos números.
"""
import json
import math
from pathlib import Path

GB = 1024 ** 3
MB = 1024 ** 2
BLOQUE_HDFS = 128 * MB          # valor real de HDFS, no el didáctico de 1 MB
DIAS_ANIO = 365
MESES = 12

RAIZ = Path(__file__).resolve().parents[2]
FICHA = RAIZ / "docs" / "T1" / "evidencia" / "resultados_medicion.json"

datos = json.loads(FICHA.read_text(encoding="utf-8"))
S0_bytes = datos["disco"]["S0_bytes"]
g_anual = datos["crecimiento"]["g_historico_anual"]
g_mensual = datos["crecimiento"]["g_historico_mensual_equivalente"]

print("=" * 66)
print("INSUMOS TOMADOS DE LA FICHA T1")
print("=" * 66)
print(f"  S0 (partición diaria)  : {S0_bytes:,} bytes = {S0_bytes/MB:.2f} MB")
print(f"  g histórico anual      : {g_anual:.10f}  ({g_anual*100:.6f} %)")
print(f"  g mensual equivalente  : {g_mensual:.10f}  ({g_mensual*100:.6f} %)")


def acumulado_12_meses(tasa_mensual):
    """Volumen lógico acumulado en 12 meses.

    Cada mes aporta sus particiones diarias; el tamaño de la partición
    cambia mes a mes según la tasa. Con tasa 0 se reduce a 365 * S0.
    """
    dias_por_mes = DIAS_ANIO / MESES
    total = 0.0
    for mes in range(MESES):
        total += dias_por_mes * S0_bytes * (1 + tasa_mensual) ** mes
    return total


escenarios = {
    "Histórico (g = -4,780861 % anual)": g_mensual,
    "Conservador (g = 0 %)": 0.0,
    "Sensibilidad (g = +1 % anual)": (1.01) ** (1 / 12) - 1,
}

print()
print("=" * 66)
print("VOLUMEN LÓGICO ACUMULADO A 12 MESES")
print("=" * 66)
volumenes = {}
for nombre, tasa in escenarios.items():
    v = acumulado_12_meses(tasa)
    volumenes[nombre] = v
    print(f"  {nombre:38s} {v/GB:8.4f} GB")

print()
print("=" * 66)
print("ALMACENAMIENTO FÍSICO POR FACTOR DE RÉPLICA")
print("=" * 66)
print(f"  {'Escenario':38s} {'R=1':>10s} {'R=2':>10s} {'R=3':>10s}")
for nombre, v in volumenes.items():
    print(
        f"  {nombre:38s} "
        f"{v/GB:9.3f}G {2*v/GB:9.3f}G {3*v/GB:9.3f}G"
    )

print()
print("  Tolerancia: R=1 -> 0 nodos | R=2 -> 1 nodo | R=3 -> 2 nodos")

print()
print("=" * 66)
print("TAMAÑO DE BLOQUE · PARTICIÓN DIARIA CONTRA BLOQUE DE 128 MB")
print("=" * 66)
bloques_particion = math.ceil(S0_bytes / BLOQUE_HDFS)
print(f"  Partición diaria         : {S0_bytes/MB:.2f} MB")
print(f"  Bloque HDFS              : {BLOQUE_HDFS/MB:.0f} MB")
print(f"  Bloques por partición    : {bloques_particion}")
print(f"  Ocupación del bloque     : {S0_bytes/BLOQUE_HDFS*100:.1f} %")

archivos_anio = DIAS_ANIO
bloques_anio = DIAS_ANIO * bloques_particion
objetos = archivos_anio + bloques_anio
heap_por_objeto = 150  # bytes, valor de referencia habitual en HDFS
print()
print(f"  Con partición DIARIA     : {archivos_anio} archivos + {bloques_anio} bloques")
print(f"    objetos en el maestro  : {objetos:,}")
print(f"    memoria del maestro    : {objetos*heap_por_objeto/MB:.3f} MB al año")

v_base = volumenes["Conservador (g = 0 %)"]
bloques_consolidado = math.ceil(v_base / BLOQUE_HDFS)
objetos_consolidado = 12 + bloques_consolidado
print()
print(f"  Con consolidación MENSUAL: 12 archivos + {bloques_consolidado} bloques")
print(f"    objetos en el maestro  : {objetos_consolidado:,}")
print(f"    memoria del maestro    : {objetos_consolidado*heap_por_objeto/MB:.3f} MB al año")
print(f"    reducción de objetos   : {(1-objetos_consolidado/objetos)*100:.1f} %")

print()
print("  Nota: HDFS NO desperdicia disco en bloques parciales. Una")
print("  partición de 20,94 MB ocupa 20,94 MB, no 128 MB. El costo de")
print("  los archivos pequeños es la memoria del nodo maestro y el")
print("  exceso de tareas en el procesamiento, no el espacio en disco.")
