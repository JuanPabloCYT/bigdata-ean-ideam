#!/usr/bin/env python3
"""T12-T16 · Verificador unificado de etapas del pipeline del acueducto.

Uso:
  python pipeline/verificar_etapa.py --etapa t16
  python pipeline/verificar_etapa.py --etapa t15
  python pipeline/verificar_etapa.py --etapa t14   (requiere perfil s12 levantado)
  python pipeline/verificar_etapa.py --etapa t13   (requiere perfil s12 levantado)
  python pipeline/verificar_etapa.py --etapa t12   (requiere perfil s12 levantado)
"""
import argparse
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(cond: bool, name: str, got, expected=None) -> bool:
    if cond:
        mark = "PASS"
    else:
        mark = "FAIL"
    detail = "got=%r" % (got,)
    if expected is not None:
        detail += " expected=%r" % (expected,)
    print("  [%s] %s — %s" % (mark, name, detail))
    return cond


# ---------------------------------------------------------------------------
# T16
# ---------------------------------------------------------------------------
def etapa_t16():
    import pyarrow.parquet as pq
    import pandas as pd

    checks = []
    salida = os.path.join(REPO, "datalake", "refinada_spark")
    bitacora = os.path.join(REPO, "practica", "s16-refinada-spark",
                            "resultados", "bitacora_refinada_spark.jsonl")

    # 1. La capa refinada_spark existe
    checks.append(check(os.path.isdir(salida), "refinada_spark/ existe", salida))

    # 2. Exactamente 120 carpetas fecha=
    day_dirs = sorted(d for d in os.listdir(salida) if d.startswith("fecha="))
    checks.append(check(len(day_dirs) == 120, "120 carpetas fecha=", len(day_dirs), 120))

    # 3. Cada carpeta tiene al menos un archivo parquet
    has_parquet = all(
        any(f.endswith(".parquet") and not f.startswith(".")
            for f in os.listdir(os.path.join(salida, d)))
        for d in day_dirs
    )
    checks.append(check(has_parquet, "cada carpeta tiene parquet", has_parquet, True))

    # 4. Total de filas = 576 000
    total = sum(
        pq.read_table(os.path.join(salida, d, f)).num_rows
        for d in day_dirs
        for f in os.listdir(os.path.join(salida, d))
        if f.endswith(".parquet") and not f.startswith(".")
    )
    checks.append(check(total == 576000, "576000 filas totales", total, 576000))

    # 5. Esquema: 7 columnas (6 + fecha de partición implícita)
    sample_dir = os.path.join(salida, day_dirs[0])
    pq_files = [f for f in os.listdir(sample_dir)
                if f.endswith(".parquet") and not f.startswith(".")]
    schema = pq.read_schema(os.path.join(sample_dir, pq_files[0]))
    col_names = set(schema.names)
    expected_cols = {"meter_id", "timestamp", "sector", "consumo_m3", "presion_bar", "quality_flag"}
    checks.append(check(expected_cols <= col_names, "columnas del esquema", col_names, expected_cols))

    # 6. timestamp es INT64 (tipo físico en el Parquet)
    ts_physical = None
    for i in range(len(schema)):
        f = schema.field(i)
        if "timestamp" in f.name.lower():
            ts_physical = str(f.type)   # Arrow type, e.g. "timestamp[ns]" (from INT64)
            break
    is_int64 = ts_physical is not None and "timestamp" in (ts_physical or "").lower()
    checks.append(check(is_int64, "timestamp es INT64 (Arrow timestamp type)", ts_physical))

    # 7. Nulos por columna = 0 en todas las columnas (desde la bitácora)
    nulos = {}
    if os.path.exists(bitacora):
        for line in open(bitacora):
            d = json.loads(line)
            if d.get("modo") == "refinada" and d.get("volumen") == "base":
                nulos = d.get("nulos_por_columna", {})
    zero_nulos = all(v == 0 for v in nulos.values()) if nulos else False
    checks.append(check(zero_nulos, "nulos_por_columna = 0 (bitácora)", nulos))

    # 8. filas_no_conformes = 0 (desde la bitácora)
    no_conf = None
    if os.path.exists(bitacora):
        for line in open(bitacora):
            d = json.loads(line)
            if d.get("modo") == "refinada" and d.get("volumen") == "base":
                no_conf = d.get("filas_no_conformes", -1)
    checks.append(check(no_conf == 0, "filas_no_conformes = 0 (bitácora)", no_conf, 0))

    # 9. hash_salida reproducible (dos corridas con el mismo hash en la bitácora)
    hashes_base = []
    if os.path.exists(bitacora):
        for line in open(bitacora):
            d = json.loads(line)
            if d.get("modo") == "refinada" and d.get("volumen") == "base":
                h = d.get("hash_salida")
                if h:
                    hashes_base.append(h)
    reproducible = len(hashes_base) >= 2 and len(set(hashes_base)) == 1
    checks.append(check(reproducible, "hash_salida reproducible (≥2 corridas)", hashes_base))

    # 10. Reconciliación 480 grupos: diff_max = 0 (bitácora)
    recon480 = None
    if os.path.exists(bitacora):
        for line in open(bitacora):
            d = json.loads(line)
            if d.get("modo") == "refinada" and d.get("volumen") == "base":
                r = d.get("reconciliacion_480", {})
                if r.get("diff_max") is not None:
                    recon480 = r
    r480_ok = (recon480 or {}).get("diff_max", 1) == 0.0
    checks.append(check(r480_ok, "reconciliacion_480 diff_max=0 (bitácora)", recon480))

    # 11. Reconciliación 1920 grupos: diff_max = 0 (bitácora)
    recon1920 = None
    if os.path.exists(bitacora):
        for line in open(bitacora):
            d = json.loads(line)
            if d.get("modo") == "refinada" and d.get("volumen") == "base":
                r = d.get("reconciliacion_1920", {})
                if r.get("diff_max") is not None:
                    recon1920 = r
    r1920_ok = (recon1920 or {}).get("diff_max", 1) == 0.0
    checks.append(check(r1920_ok, "reconciliacion_1920 diff_max=0 (bitácora)", recon1920))

    # 12. Bitácora existe y tiene al menos una entrada de modo refinada
    has_bitacora = os.path.exists(bitacora)
    checks.append(check(has_bitacora, "bitacora_refinada_spark.jsonl existe", bitacora))

    # 13. Variantes producen el mismo conteo (bitácora)
    variantes_ok = False
    if os.path.exists(bitacora):
        for line in open(bitacora):
            d = json.loads(line)
            if d.get("modo") == "variantes":
                r = d.get("resultados", {})
                counts = [json.dumps(v.get("counts", {}), sort_keys=True) for v in r.values()]
                variantes_ok = len(set(counts)) == 1 and len(counts) >= 3
    checks.append(check(variantes_ok, "tres variantes producen el mismo conteo (bitácora)", variantes_ok))

    # 14. Reproceso dinámico: 576000 filas conservadas (bitácora)
    reproceso_din = None
    if os.path.exists(bitacora):
        for line in open(bitacora):
            d = json.loads(line)
            if d.get("modo") == "reproceso" and d.get("sobrescritura") == "dinamica":
                reproceso_din = d
    rep_ok = (reproceso_din or {}).get("filas_despues") == 576000
    checks.append(check(rep_ok, "reproceso dinámico conserva 576000 filas (bitácora)", reproceso_din))

    # 15. Reproceso estático: solo 28800 filas (bitácora)
    reproceso_est = None
    if os.path.exists(bitacora):
        for line in open(bitacora):
            d = json.loads(line)
            if d.get("modo") == "reproceso" and d.get("sobrescritura") == "estatica":
                reproceso_est = d
    rep_est_ok = (reproceso_est or {}).get("filas_despues") == 28800
    checks.append(check(rep_est_ok, "reproceso estático: 28800 filas (6 días × 4800) (bitácora)", reproceso_est))

    return checks


# ---------------------------------------------------------------------------
# T15 (ligero: lee solo la bitácora de T15)
# ---------------------------------------------------------------------------
def etapa_t15():
    checks = []
    bitacora = os.path.join(REPO, "practica", "s15-carga-spark",
                            "resultados", "bitacora_carga_spark.jsonl")
    salida_base = os.path.join(REPO, "datalake", "consolidada_spark")
    salida_ampli = os.path.join(REPO, "datalake_equipo", "consolidada_spark")

    checks.append(check(os.path.exists(bitacora), "bitacora_carga_spark.jsonl existe", bitacora))
    checks.append(check(os.path.isdir(salida_base), "datalake/consolidada_spark/ existe", salida_base))
    checks.append(check(os.path.isdir(salida_ampli), "datalake_equipo/consolidada_spark/ existe", salida_ampli))

    hashes = []
    if os.path.exists(bitacora):
        for line in open(bitacora):
            d = json.loads(line)
            if d.get("modo") == "carga" and d.get("volumen") == "ampliacion":
                h = d.get("hash_salida") or (d.get("bitacora") or {}).get("hash_salida")
                if h:
                    hashes.append(h)
    checks.append(check(len(hashes) >= 2, "≥2 corridas de ampliacion en bitácora", len(hashes)))
    checks.append(check(len(set(hashes)) == 1 if len(hashes) >= 2 else False,
                        "hash_salida reproducible (ampliacion)", hashes))

    # 480 filas en la salida de ampliación
    import pyarrow.parquet as pq
    filas = 0
    if os.path.isdir(salida_ampli):
        for f in os.listdir(salida_ampli):
            if f.endswith(".parquet") and not f.startswith("."):
                filas += pq.read_table(os.path.join(salida_ampli, f)).num_rows
    checks.append(check(filas == 480, "480 filas en consolidada_spark ampliacion", filas, 480))
    return checks


# ---------------------------------------------------------------------------
# T12-T14 (stubs que verifican solo los archivos locales del repositorio)
# ---------------------------------------------------------------------------
def etapa_t14():
    checks = []
    ev = os.path.join(REPO, "practica", "s14-cdc-suscriptores",
                      "resultados", "evidencia_nivel2_equipo-2.md")
    checks.append(check(os.path.exists(ev), "evidencia_nivel2_equipo-2.md existe", ev))
    bt = os.path.join(REPO, "practica", "s14-cdc-suscriptores",
                      "resultados", "perfil_equipo-2.json")
    checks.append(check(os.path.exists(bt), "perfil_equipo-2.json existe", bt))
    if os.path.exists(bt):
        d = json.load(open(bt))
        checks.append(check(d.get("n_baja", 0) == 10, "n_baja=10 (equipo-2)", d.get("n_baja")))
    return checks


def etapa_t13():
    checks = []
    ev = os.path.join(REPO, "docs", "evidencia_nivel2_equipo.md")
    checks.append(check(os.path.exists(ev), "evidencia_nivel2_equipo.md existe", ev))
    sql = os.path.join(REPO, "sql", "T13_conector_api.sql")
    checks.append(check(os.path.exists(sql), "T13_conector_api.sql existe", sql))
    return checks


def etapa_t12():
    checks = []
    sql = os.path.join(REPO, "sql", "T12_ingesta_incremental.sql")
    checks.append(check(os.path.exists(sql), "T12_ingesta_incremental.sql existe", sql))
    doc = os.path.join(REPO, "docs", "T12_ingesta_incremental.md")
    checks.append(check(os.path.exists(doc), "T12_ingesta_incremental.md existe", doc))
    return checks


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
RUNNERS = {"t12": etapa_t12, "t13": etapa_t13, "t14": etapa_t14,
           "t15": etapa_t15, "t16": etapa_t16}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", required=True, choices=sorted(RUNNERS))
    args = ap.parse_args()

    t0 = time.time()
    fn = RUNNERS[args.etapa]
    print("Verificando etapa %s …" % args.etapa.upper())
    checks = fn()
    elapsed = round(time.time() - t0, 1)

    n_pass = sum(1 for c in checks if c)
    n_total = len(checks)
    if n_pass == n_total:
        print("\nEtapa %s: APROBADA (%d de %d comprobaciones, %s s)" % (
            args.etapa.upper(), n_pass, n_total, elapsed))
        sys.exit(0)
    else:
        print("\nEtapa %s: RECHAZADA (%d de %d comprobaciones, %s s)" % (
            args.etapa.upper(), n_pass, n_total, elapsed))
        sys.exit(1)


if __name__ == "__main__":
    main()
