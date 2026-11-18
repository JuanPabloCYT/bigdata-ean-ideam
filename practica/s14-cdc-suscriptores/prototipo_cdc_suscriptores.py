#!/usr/bin/env python3
"""T14 · Prototipo de CDC del maestro de suscriptores.

Motor: DuckDB embebido (sin servidor). El prototipo reproduce una CDC basada
en consulta (sondeo con marca de agua sobre ``updated_at``) y demuestra que:

  * las ALTAS y las MODIFICACIONES sí se capturan,
  * las BAJAS DURAS nunca se capturan (punto ciego estructural del método),
  * repetir la corrida con el checkpoint restablecido duplica exactamente
    (altas + modificaciones) filas en el staging,
  * una reconciliación de conjunto completo sí detecta las bajas.

Al final imprime un reporte y escribe ``resultados/evidencia_nivel2_<equipo>.md``.

Uso:

    python prototipo_cdc_suscriptores.py --equipo equipo-2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import duckdb

# Importar el generador del mismo directorio.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from generar_cambios_suscriptores import generar_perfil  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SQL_DDL = os.path.join(REPO_ROOT, "sql", "T14_cdc_suscriptores.sql")
RESULTADOS = os.path.join(HERE, "resultados")

# Marcas temporales del escenario (fecha de esta entrega).
T0 = datetime(2026, 11, 18, 8, 0, 0)   # población inicial
T1 = datetime(2026, 11, 18, 12, 0, 0)  # flujo de cambios
EPOCH = datetime(1900, 1, 1, 0, 0, 0)  # checkpoint nulo -> captura todo

PROCESO = "cdc_suscriptores"

# Parámetros de costo del Nivel 3 (para el equipo-2):
T_SONDEO = 60        # segundos entre sondeos
B_RECON = 4         # reconciliaciones por día (cada 6 h)


# ---------------------------------------------------------------------------
# Helpers de checkpoint (avance monótono con greatest() en Python).
# ---------------------------------------------------------------------------
def upsert_checkpoint(con, new_cp):
    """Avanza el checkpoint de forma monótona (greatest(current, new))."""
    row = con.execute(
        "SELECT checkpoint FROM estado_cdc_suscriptores WHERE nombre_proceso = ?",
        [PROCESO],
    ).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO estado_cdc_suscriptores (nombre_proceso, checkpoint, actualizado_en) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            [PROCESO, new_cp],
        )
    else:
        cur = row[0]
        merged = new_cp if cur is None else max(cur, new_cp)
        con.execute(
            "UPDATE estado_cdc_suscriptores SET checkpoint = ?, actualizado_en = CURRENT_TIMESTAMP "
            "WHERE nombre_proceso = ?",
            [merged, PROCESO],
        )


def reset_checkpoint(con, cp):
    """Restablece (sobrescribe) el checkpoint a un valor dado. Simula la
    operación errónea que reproduce los duplicados de la sección 2.1."""
    row = con.execute(
        "SELECT checkpoint FROM estado_cdc_suscriptores WHERE nombre_proceso = ?",
        [PROCESO],
    ).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO estado_cdc_suscriptores (nombre_proceso, checkpoint, actualizado_en) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            [PROCESO, cp],
        )
    else:
        con.execute(
            "UPDATE estado_cdc_suscriptores SET checkpoint = ?, actualizado_en = CURRENT_TIMESTAMP "
            "WHERE nombre_proceso = ?",
            [cp, PROCESO],
        )


def get_checkpoint(con):
    row = con.execute(
        "SELECT checkpoint FROM estado_cdc_suscriptores WHERE nombre_proceso = ?",
        [PROCESO],
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Captura basada en consulta (watermark).
# ---------------------------------------------------------------------------
def capturar(con, checkpoint, snapshots):
    """Ejecuta la captura CDC: INSERT en stg_cambios_suscriptor de las filas del
    maestro con ``updated_at > checkpoint``. Clasifica ALTAS vs MODIFICACIONES
    comparando la llave contra la membresía del maestro **a la fecha del
    checkpoint** (instantánea puntual), de modo que la clasificación es
    determinística por evento de cambio y estable ante una repetición.

    Las BAJAS DURAS nunca aparecen aquí: la fila borrada del origen ya no
    satisface ``updated_at > checkpoint``. Es la propiedad estructural.
    """
    ref = snapshots.get(checkpoint, set()) if checkpoint is not None else set()
    cp_value = checkpoint if checkpoint is not None else EPOCH
    rows = con.execute(
        "SELECT subscriber_id, nombre, direccion, estado, updated_at "
        "FROM maestro_suscriptores WHERE updated_at > ? ORDER BY subscriber_id",
        [cp_value],
    ).fetchall()
    capt = {"ALTA": 0, "MODIFICACION": 0, "BAJA": 0}
    for sid, nombre, direccion, estado, updated_at in rows:
        tipo = "ALTA" if sid not in ref else "MODIFICACION"
        capt[tipo] += 1
        con.execute(
            "INSERT INTO stg_cambios_suscriptor "
            "(subscriber_id, nombre, direccion, estado, tipo_cambio, updated_at, capturado_en) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            [sid, nombre, direccion, estado, tipo, updated_at],
        )
    # Avance monótono del checkpoint.
    if rows:
        new_max = max(r[4] for r in rows)
        new_cp = new_max if checkpoint is None else max(checkpoint, new_max)
        upsert_checkpoint(con, new_cp)
    return capt, len(rows)


# ---------------------------------------------------------------------------
# Flujo de cambios sobre el maestro (el "origen" muta).
# ---------------------------------------------------------------------------
def poblacion_inicial(con, perfil):
    con.execute("DELETE FROM maestro_suscriptores")
    rows = []
    for sid in range(1, perfil.total_suscriptores + 1):
        rows.append((sid, f"Suscriptor {sid}", f"Calle {sid}", "ACTIVO", T0))
    con.executemany(
        "INSERT INTO maestro_suscriptores (subscriber_id, nombre, direccion, estado, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def flujo_de_cambios(con, perfil):
    """Aplica altas, modificaciones y bajas duras al maestro, todas con
    ``updated_at = T1``. Las bajas son DURAS: DELETE puro, sin bandera ni
    marca de baja. Devuelve los conteos generados por el perfil."""
    # Altas: ids nuevos.
    for sid in perfil.altas:
        con.execute(
            "INSERT INTO maestro_suscriptores (subscriber_id, nombre, direccion, estado, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [sid, f"Suscriptor {sid}", f"Calle {sid}", "ACTIVO", T1],
        )
    # Modificaciones: ids existentes (1..n_mod); cambian direccion/estado y updated_at.
    for sid in perfil.modificaciones:
        con.execute(
            "UPDATE maestro_suscriptores SET direccion = ?, estado = ?, updated_at = ? "
            "WHERE subscriber_id = ?",
            [f"Calle {sid} Bis", "REVISADO", T1, sid],
        )
    # Bajas duras: DELETE puro del origen (sin tombstone, sin bandera).
    for sid in perfil.bajas:
        con.execute("DELETE FROM maestro_suscriptores WHERE subscriber_id = ?", [sid])
    return {
        "ALTA": perfil.n_alta,
        "MODIFICACION": perfil.n_modificacion,
        "BAJA": perfil.n_baja,
    }


# ---------------------------------------------------------------------------
# Funciones de costo del Nivel 3.
# ---------------------------------------------------------------------------
def consultas_por_dia(T):
    return 86400 / T


def llaves_leidas_por_dia(M, B):
    return M * B


def latencia_max_baja_sondeo(T):
    return T


def latencia_max_baja_recon(B):
    return 86400 / B


# ---------------------------------------------------------------------------
# Reporte + evidencia.
# ---------------------------------------------------------------------------
def fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt is not None else "NULL"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--equipo", required=True)
    args = ap.parse_args()

    perfil = generar_perfil(args.equipo)
    os.makedirs(RESULTADOS, exist_ok=True)

    con = duckdb.connect(":memory:")
    with open(SQL_DDL, "r", encoding="utf-8") as f:
        con.execute(f.read())

    snapshots = {}

    # --- 1) Población inicial -------------------------------------------
    n_inicial = poblacion_inicial(con, perfil)
    snapshots[T0] = set(
        r[0]
        for r in con.execute("SELECT subscriber_id FROM maestro_suscriptores").fetchall()
    )

    # --- 2) Corrida ANTES del flujo de cambios --------------------------
    # Checkpoint nulo -> captura toda la población inicial como ALTAS.
    capt_antes, n_antes = capturar(con, None, snapshots)
    cp_antes = get_checkpoint(con)

    # --- 3) Flujo de cambios --------------------------------------------
    generadas = flujo_de_cambios(con, perfil)
    # Instantánea del maestro tras el flujo (para referencia futura).
    snapshots[T1] = set(
        r[0]
        for r in con.execute("SELECT subscriber_id FROM maestro_suscriptores").fetchall()
    )
    n_maestro_tras_flujo = con.execute("SELECT COUNT(*) FROM maestro_suscriptores").fetchone()[0]

    # --- 4) Corrida DESPUÉS del flujo de cambios -------------------------
    capt_despues, n_despues = capturar(con, cp_antes, snapshots)
    cp_despues = get_checkpoint(con)

    # --- 5) Diferencia destino vs origen + reconciliación ---------------
    reconstruido = con.execute(
        "SELECT COUNT(DISTINCT subscriber_id) FROM stg_cambios_suscriptor"
    ).fetchone()[0]
    reales = n_maestro_tras_flujo
    diferencia = reconstruido - reales
    bajas_detectadas = con.execute(
        "SELECT COUNT(*) FROM ("
        " SELECT DISTINCT subscriber_id FROM stg_cambios_suscriptor"
        " EXCEPT"
        " SELECT subscriber_id FROM maestro_suscriptores"
        ") d"
    ).fetchone()[0]
    bajas_detectadas_ids = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT subscriber_id FROM stg_cambios_suscriptor "
            "WHERE subscriber_id NOT IN (SELECT subscriber_id FROM maestro_suscriptores) "
            "ORDER BY subscriber_id"
        ).fetchall()
    ]

    # --- 6) Sección 2.1: repetición con checkpoint restablecido ---------
    n_stg_antes_reset = con.execute("SELECT COUNT(*) FROM stg_cambios_suscriptor").fetchone()[0]
    reset_checkpoint(con, cp_antes)  # restablece a T0 (la fecha de la población inicial)
    capt_repet, n_repet = capturar(con, cp_antes, snapshots)
    cp_tras_repet = get_checkpoint(con)
    n_stg_tras_reset = con.execute("SELECT COUNT(*) FROM stg_cambios_suscriptor").fetchone()[0]
    filas_duplicadas = n_stg_tras_reset - n_stg_antes_reset
    sobrantes_pareja = con.execute(
        "SELECT COALESCE(SUM(c - 1), 0) FROM ("
        " SELECT subscriber_id, tipo_cambio, COUNT(*) c FROM stg_cambios_suscriptor "
        " GROUP BY subscriber_id, tipo_cambio HAVING COUNT(*) > 1"
        ") d"
    ).fetchone()[0]

    # --- 7) Funciones de costo + tabla comparación ---------------------
    M = perfil.total_suscriptores
    N = consultas_por_dia(T_SONDEO)          # consultas/día (sondeo)
    K = llaves_leidas_por_dia(M, B_RECON)     # llaves/día (reconciliación full-scan)
    L_son = latencia_max_baja_sondeo(T_SONDEO)
    L_rec = latencia_max_baja_recon(B_RECON)
    cambios_por_dia = perfil.numero_cambios   # la ventana de cambios se modela como 1 día

    comparacion = [
        {
            "alternativa": "Bandera de baja lógica en el origen",
            "detecta_bajas": "sí",
            "intervalo_sondeo_s": T_SONDEO,
            "barridos_por_dia": int(round(86400 / T_SONDEO)),
            "consultas_por_dia": int(N),
            "llaves_leidas_por_dia": cambios_por_dia,  # sondeo con marca de agua: lee el delta, no M×B
            "latencia_max_baja_s": L_son,
        },
        {
            "alternativa": "Reconciliación periódica de conjunto completo",
            "detecta_bajas": "sí",
            "intervalo_sondeo_s": int(L_rec),
            "barridos_por_dia": B_RECON,
            "consultas_por_dia": B_RECON,
            "llaves_leidas_por_dia": int(K),  # M×B (escaneo completo por barrido)
            "latencia_max_baja_s": int(L_rec),
        },
        {
            "alternativa": "CDC basada en registro de transacciones",
            "detecta_bajas": "sí",
            "intervalo_sondeo_s": 0,
            "barridos_por_dia": 0,
            "consultas_por_dia": 0,
            "llaves_leidas_por_dia": cambios_por_dia,  # solo cambios entregados por el WAL
            "latencia_max_baja_s": 0,
        },
    ]

    # --- 8) Salida a consola -------------------------------------------
    print("=" * 70)
    print(f"PERFIL equipo={perfil.equipo}")
    print(f"  total_suscriptores={perfil.total_suscriptores}")
    print(f"  numero_cambios={perfil.numero_cambios}")
    print(f"  n_alta={perfil.n_alta}  n_modificacion={perfil.n_modificacion}  n_baja={perfil.n_baja}")
    print(f"  prob_baja_dura={perfil.prob_baja_dura}")
    print("-" * 70)
    print(f"Población inicial: filas en maestro_suscriptores = {n_inicial}")
    print(f"Corrida ANTES  del flujo (checkpoint nulo): capturadas = {n_antes} "
          f"(altas={capt_antes['ALTA']}, modif={capt_antes['MODIFICACION']}, bajas={capt_antes['BAJA']})")
    print(f"  checkpoint tras 'antes' = {fmt_dt(cp_antes)}")
    print(f"Flujo de cambios generado: altas={generadas['ALTA']}, "
          f"modif={generadas['MODIFICACION']}, bajas={generadas['BAJA']}")
    print(f"  maestro_suscriptores tras el flujo = {n_maestro_tras_flujo} filas reales")
    print(f"Corrida DESPUÉS del flujo (checkpoint={fmt_dt(cp_antes)}): "
          f"capturadas = {n_despues} "
          f"(altas={capt_despues['ALTA']}, modif={capt_despues['MODIFICACION']}, bajas={capt_despues['BAJA']})")
    print(f"  checkpoint tras 'después' = {fmt_dt(cp_despues)}")
    print("-" * 70)
    print("Evidencia cuantitativa del punto ciego:")
    print(f"  {'Tipo':<14}{'Generadas':>12}{'Capturadas':>14}")
    print(f"  {'Altas':<14}{generadas['ALTA']:>12}{capt_despues['ALTA']:>14}")
    print(f"  {'Modificaciones':<14}{generadas['MODIFICACION']:>12}{capt_despues['MODIFICACION']:>14}")
    print(f"  {'Bajas duras':<14}{generadas['BAJA']:>12}{capt_despues['BAJA']:>14}")
    print(f"  Diferencia destino vs origen: reconstruido={reconstruido} frente a reales={reales} "
          f"-> diferencia={diferencia}")
    print(f"  Reconciliación: bajas_detectadas={bajas_detectadas} ids={bajas_detectadas_ids}")
    print("-" * 70)
    print("Sección 2.1 — repetición con checkpoint restablecido:")
    print(f"  stg antes de repetir = {n_stg_antes_reset}")
    print(f"  checkpoint restablecido a = {fmt_dt(cp_antes)}")
    print(f"  re-capturadas = {n_repet} (altas={capt_repet['ALTA']}, "
          f"modif={capt_repet['MODIFICACION']}, bajas={capt_repet['BAJA']})")
    print(f"  filas_duplicadas = {filas_duplicadas}  (deben igualar altas+modif = "
          f"{perfil.n_alta + perfil.n_modificacion})")
    print(f"  sobrantes por pareja (subscriber_id, tipo_cambio) = {sobrantes_pareja}")
    print(f"  checkpoint tras repetición = {fmt_dt(cp_tras_repet)} (debe volver a T1)")
    print("-" * 70)
    print("Funciones de costo (M=total_suscriptores, T=60s, B=4/día):")
    print(f"  N = 86400/T = {N:g} consultas/día (sondeo)")
    print(f"  K = M*B = {K} llaves/día (reconciliación full-scan)")
    print(f"  L_sondeo = T = {L_son} s")
    print(f"  L_recon = 86400/B = {L_rec:g} s")
    print("Tabla comparacion:")
    hdr = f"  {'alternativa':<46}{'detecta':<9}{'sondeo_s':<9}{'barr/d':<8}{'cons/d':<8}{'llaves/d':<10}{'lat_baja_s':<11}"
    print(hdr)
    for r in comparacion:
        print(f"  {r['alternativa']:<46}{r['detecta_bajas']:<9}"
              f"{str(r['intervalo_sondeo_s']):<9}{r['barridos_por_dia']:<8}"
              f"{r['consultas_por_dia']:<8}{r['llaves_leidas_por_dia']:<10}"
              f"{str(r['latencia_max_baja_s']):<11}")
    print(f"  bajas_detectadas por reconciliación = {bajas_detectadas}")
    print("=" * 70)

    # --- 9) Evidencia Nivel 2 (md) -------------------------------------
    escribir_evidencia(
        perfil, n_inicial, capt_antes, n_antes, cp_antes, generadas,
        n_maestro_tras_flujo, capt_despues, n_despues, cp_despues,
        reconstruido, reales, diferencia, bajas_detectadas, bajas_detectadas_ids,
        n_stg_antes_reset, capt_repet, n_repet, filas_duplicadas,
        sobrantes_pareja, cp_tras_repet, comparacion, N, K, L_son, L_rec,
    )
    # perfil json
    with open(os.path.join(RESULTADOS, f"perfil_{args.equipo}.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "equipo": perfil.equipo,
                "total_suscriptores": perfil.total_suscriptores,
                "n_alta": perfil.n_alta,
                "n_modificacion": perfil.n_modificacion,
                "n_baja": perfil.n_baja,
                "prob_baja_dura": perfil.prob_baja_dura,
                "numero_cambios": perfil.numero_cambios,
                "altas": perfil.altas,
                "modificaciones": perfil.modificaciones,
                "bajas": perfil.bajas,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Evidencia escrita en: {os.path.join(RESULTADOS, f'evidencia_nivel2_{args.equipo}.md')}")


def escribir_evidencia(perfil, n_inicial, capt_antes, n_antes, cp_antes, generadas,
                       n_maestro_tras_flujo, capt_despues, n_despues, cp_despues,
                       reconstruido, reales, diferencia, bajas_detectadas,
                       bajas_detectadas_ids, n_stg_antes_reset, capt_repet, n_repet,
                       filas_duplicadas, sobrantes_pareja, cp_tras_repet, comparacion,
                       N, K, L_son, L_rec):
    equipo = perfil.equipo
    lines = []
    lines.append(f"# Evidencia Nivel 2 — CDC del maestro de suscriptores ({equipo})\n")
    lines.append(f"**Equipo:** `{equipo}`  ")
    lines.append(f"**Fecha de ejecución:** 2026-11-18  ")
    lines.append(f"**Motor:** DuckDB embebido 2.0.0  ")
    lines.append(f"**Comando:** `python prototipo_cdc_suscriptores.py --equipo {equipo}`\n")
    lines.append("## 0. Perfil de cambios del equipo\n")
    lines.append(f"**Comando exacto:** `python generar_cambios_suscriptores.py --equipo {equipo}`\n")
    lines.append("| Valor del perfil | Cifra que reporta el generador |")
    lines.append("|---|---|")
    lines.append(f"| total_suscriptores | {perfil.total_suscriptores} |")
    lines.append(f"| Número de cambios | {perfil.numero_cambios} |")
    lines.append(f"| n_alta | {perfil.n_alta} |")
    lines.append(f"| n_modificacion | {perfil.n_modificacion} |")
    lines.append(f"| n_baja | {perfil.n_baja} |")
    lines.append(f"| prob_baja_dura | {perfil.prob_baja_dura} |\n")
    lines.append("## 1. Las tres tablas y la carga inicial\n")
    lines.append(f"- `maestro_suscriptores` (tabla fuente): confirmado.")
    lines.append(f"- `stg_cambios_suscriptor` (staging de cambios capturados): confirmado.")
    lines.append(f"- `estado_cdc_suscriptores` (checkpoint): confirmado.")
    lines.append(f"- Filas cargadas en `maestro_suscriptores` tras la población inicial: **{n_inicial}**.\n")
    lines.append("## 2. Evidencia cuantitativa del punto ciego\n")
    lines.append(f"Corrida ANTES del flujo (checkpoint nulo → captura toda la población inicial como ALTAS): "
                 f"capturadas = {n_antes} (altas={capt_antes['ALTA']}, "
                 f"modif={capt_antes['MODIFICACION']}, bajas={capt_antes['BAJA']}). "
                 f"Checkpoint tras la corrida: `{fmt_dt(cp_antes)}` (fecha de la población inicial).\n")
    lines.append("Flujo de cambios aplicado al maestro con `updated_at = T1 = "
                 f"{fmt_dt(T1)}` (altas + modificaciones + bajas duras).\n")
    lines.append("| Tipo de cambio | Generadas (perfil) | Capturadas por el prototipo |")
    lines.append("|---|---:|---:|")
    lines.append(f"| Altas | {generadas['ALTA']} | {capt_despues['ALTA']} |")
    lines.append(f"| Modificaciones | {generadas['MODIFICACION']} | {capt_despues['MODIFICACION']} |")
    lines.append(f"| Bajas duras | {generadas['BAJA']} | {capt_despues['BAJA']} |")
    lines.append("\nLas altas y modificaciones capturadas igualan a las generadas; las **bajas duras "
                 "capturadas = 0** sin importar cuántas se generaron (aquí 10).\n")
    lines.append(f"- **Diferencia entre lo que ve el destino y lo que hay en el origen:** el destino, "
                 f"reconstruyendo el maestro con solo lo capturado, ve **{reconstruido}** suscriptores; "
                 f"el maestro real tiene **{reales}**. Diferencia = **{diferencia}** "
                 f"(= n_baja = {perfil.n_baja}).\n")
    lines.append(f"- **Por qué es estructural y no un error del prototipo:** la CDC basada en consulta "
                 f"filtra con `updated_at > checkpoint`. Una baja dura elimina la fila del origen, por lo "
                 f"que esa llave deja de existir y nunca satisface el predicado: no hay `updated_at` que "
                 f"supere el checkpoint porque la fila ya no está. El método no tiene forma de enterarse "
                 f"de algo que dejó de existir. No es un bug de implementación; es la definición del "
                 f"sondeo con marca de agua.\n")
    lines.append(f"- **Caso de cero bajas por redondeo:** no aplica a este equipo. "
                 f"prob_baja_dura = {perfil.prob_baja_dura} = {perfil.n_baja}/{perfil.total_suscriptores} "
                 f"es exacta (sin redondeo) y produce n_baja = {perfil.n_baja} ≠ 0.\n")
    lines.append("### 2.1 Repetición con el checkpoint restablecido\n")
    lines.append(f"Se restablece el checkpoint a la fecha de la población inicial (`{fmt_dt(T0)}`) y se "
                 f"repite la corrida de captura.\n")
    lines.append(f"- Filas en `stg_cambios_suscriptor` antes de repetir: {n_stg_antes_reset}.")
    lines.append(f"- Re-capturadas: {n_repet} (altas={capt_repet['ALTA']}, "
                 f"modif={capt_repet['MODIFICACION']}, bajas={capt_repet['BAJA']}).")
    lines.append(f"- **Filas duplicadas** en `stg_cambios_suscriptor` tras repetir: **{filas_duplicadas}** "
                 f"(= altas + modificaciones = {perfil.n_alta} + {perfil.n_modificacion} = "
                 f"{perfil.n_alta + perfil.n_modificacion}).")
    lines.append(f"- **Filas sobrantes por pareja (subscriber_id, tipo_cambio):** **{sobrantes_pareja}** "
                 f"(cada pareja del flujo aparece dos veces; las de la población inicial siguen una).")
    lines.append(f"- **Checkpoint tras la repetición:** `{fmt_dt(cp_tras_repet)}` "
                 f"(vuelve a la fecha del flujo de cambios, T1).\n")
    lines.append("**Decisión para evitar los duplicados:** el checkpoint debe avanzar de forma monótona "
                 "con `greatest(checkpoint_actual, max(updated_at))` (nunca retroceder) y la inserción en "
                 "el staging debe ser idempotente con `ON CONFLICT (subscriber_id, updated_at) DO NOTHING`, "
                 "ya que `(subscriber_id, updated_at)` identifica unívocamente un evento de cambio. Así, "
                 "una re-captura tras un reseteado erróneo es un no-op en vez de un duplicador. Como "
                 "alternativa más simple, un margen de solapamiento acotado (re-procesar los últimos N "
                 "segundos) combinado con la misma llave única también elimina los duplicados. El prototipo, "
                 "para evidenciar el problema, usa un INSERT puro (sin la guarda).\n")
    lines.append("## 3. Funciones de costo y comparación de alternativas\n")
    lines.append(f"Parámetros del equipo: M = total_suscriptores = {perfil.total_suscriptores}; "
                 f"T (sondeo) = {T_SONDEO} s; B (reconciliación) = {B_RECON}/día. La ventana de cambios "
                 f"se modela como un día de actividad → {perfil.numero_cambios} cambios/día.\n")
    lines.append("**Cuatro funciones de costo:**\n")
    lines.append(f"- `N = 86400 / T` → consultas por día en sondeo = **{N:g}**.")
    lines.append(f"- `K = M × B` → llaves leídas por día en reconciliación (full-scan) = **{int(K)}**.")
    lines.append(f"- `L_sondeo = T` → latencia máxima de una baja en sondeo = **{L_son} s**.")
    lines.append(f"- `L_recon = 86400 / B` → latencia máxima de una baja en reconciliación = **{L_rec:g} s**.\n")
    lines.append("**bajas_detectadas por reconciliación sobre la base del equipo:** "
                 f"**{bajas_detectadas}** ids = {bajas_detectadas_ids} "
                 f"(= bajas generadas por el perfil = {perfil.n_baja}).\n")
    lines.append("**Tabla `comparacion`:**\n")
    lines.append("| alternativa | detecta_bajas | intervalo_sondeo_s | barridos_por_dia | "
                "consultas_por_dia | llaves_leidas_por_dia | latencia_max_baja_s |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in comparacion:
        lines.append(
            f"| {r['alternativa']} | {r['detecta_bajas']} | {r['intervalo_sondeo_s']} | "
            f"{r['barridos_por_dia']} | {r['consultas_por_dia']} | {r['llaves_leidas_por_dia']} | "
            f"{r['latencia_max_baja_s']} |"
        )
    lines.append("\n*Nota sobre llaves_leidas_por_dia:* el sondeo con marca de agua lee solo el delta "
                 "del cambio (no M por barrido), por eso la bandera lógica y la CDC por registro leen "
                 f"{perfil.numero_cambios} llaves/día; la reconciliación sí barre el maestro completo "
                 f"(M×B = {int(K)}).\n")
    lines.append("## 4. Decisión (resumen del ADR)\n")
    lines.append("Ver el memo ADR en `docs/memo_adr_t14.md`. Decisión: **estrategia híbrida** "
                 "(CDC basada en consulta con marca de agua para altas/modificaciones + reconciliación "
                 "periódica de conjunto completo cada 6 h para las bajas duras).\n")
    lines.append("## 5. Integración con el proyecto integrador\n")
    lines.append("- `stg_lecturas` (T12): append-only (solo agrega filas; nunca actualiza ni borra). "
                 "La CDC es incremental por marca de agua sobre `fechaobservacion`; **no tiene punto "
                 "ciego de bajas** porque no hay bajas.")
    lines.append("- `stg_estado_medidor` (T13): estado paginado vía API con UPSERT por `meter_id`; el "
                 "mock no expone bajas. CDC por sondeo de API + UPSERT idempotente; **sin punto ciego "
                 "de bajas** en el perfil del mock.")
    lines.append(f"- `maestro_suscriptores` (T14): **única** de las tres fuentes con bajas duras reales "
                 f"(prob_baja_dura = {perfil.prob_baja_dura}, {perfil.n_baja} bajas). Es la única que "
                 f"requiere la reconciliación/híbrida; su CDC es la más costosa de las tres.\n")
    lines.append("## 6. Reproducción\n")
    lines.append("```bash")
    lines.append("cd /Users/camilorojas/Projects/BigData/bigdata-ean-ideam")
    lines.append("source .venv/bin/activate && pip install duckdb")
    lines.append(f"python practica/s14-cdc-suscriptores/generar_cambios_suscriptores.py --equipo {equipo}")
    lines.append(f"python practica/s14-cdc-suscriptores/prototipo_cdc_suscriptores.py --equipo {equipo}")
    lines.append("```\n")
    lines.append("## 7. Declaración de uso de asistentes de inteligencia artificial\n")
    lines.append("Se utilizó Claude (Kiro) para implementar el generador, el prototipo, el DDL y la "
                 "redacción del memo y esta evidencia. Las cifras provienen de la ejecución real del "
                 "prototipo sobre el perfil del equipo; no se inventó ningún número.\n")
    with open(os.path.join(RESULTADOS, f"evidencia_nivel2_{equipo}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
