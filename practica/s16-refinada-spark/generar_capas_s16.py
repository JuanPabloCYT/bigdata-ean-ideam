#!/usr/bin/env python3
"""T16 · Generador de capas de datos del acueducto.

Genera, según --volumen:

  base      datalake/cruda/     (120 CSV, uno por día)
            datalake/refinada/  (capa heredada en Parquet INT64 μs UTC,
                                 particionada por fecha; sin presion_bar —
                                 simula la capa del paquete del curso)
            datalake/consolidada/   (referencia de 480 grupos fecha×sector)
            datalake/refs_refinada/ (referencia de 1440 grupos
                                     fecha×sector×quality_flag)

  ampliacion  datalake_equipo/cruda/     (120 CSV)
              datalake_equipo/refinada/  (capa heredada)
              datalake_equipo/refs_refinada/ (referencia 1440 grupos)
              datalake_equipo/totales_control.csv (480 grupos)

Uso:
  python practica/s16-refinada-spark/generar_capas_s16.py --volumen base
  python practica/s16-refinada-spark/generar_capas_s16.py --volumen ampliacion --equipo equipo-2
"""
import argparse
import os
import sys
from datetime import timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from modelo_s16 import (  # noqa: E402
    SECTORES, N_DIAS, BASE_DATE, MEDIDORES_POR_SECTOR_BASE,
    PERFILES_AMPLIACION, fecha_iso, timestamp_utc, consumo_m3,
    presion_bar, quality_flag, medidores_por_sector,
)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Esquema Arrow para la capa refinada heredada (INT64 μs UTC).
REFINADA_SCHEMA = pa.schema([
    pa.field("meter_id",    pa.int64()),
    pa.field("timestamp",   pa.timestamp("us", tz="UTC")),
    pa.field("sector",      pa.string()),
    pa.field("consumo_m3",  pa.float64()),
    pa.field("presion_bar", pa.float64()),
    pa.field("quality_flag", pa.string()),
])


def build_rows(medidores_range, dia_range):
    """Genera filas para un rango de medidor_id e índices de día."""
    rows = []
    for mid in medidores_range:
        for dia in dia_range:
            ts = timestamp_utc(dia, mid)
            rows.append({
                "meter_id":    mid,
                "timestamp":   ts,
                "fecha":       fecha_iso(dia),
                "sector":      SECTORES[(mid - 1) % len(SECTORES)],
                "consumo_m3":  consumo_m3(mid, dia),
                "presion_bar": presion_bar(mid, dia),
                "quality_flag": quality_flag(mid, dia),
            })
    return rows


def write_cruda_csv(df: pd.DataFrame, out_dir: str):
    """Escribe 120 CSV, uno por día."""
    os.makedirs(out_dir, exist_ok=True)
    for fecha, grp in df.groupby("fecha"):
        path = os.path.join(out_dir, f"lecturas_{fecha}.csv")
        grp.drop(columns=["fecha"]).to_csv(path, index=False)


def write_refinada_parquet(df: pd.DataFrame, out_dir: str):
    """Escribe la capa refinada heredada particionada por fecha (INT64 μs UTC)."""
    import shutil
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    for fecha, grp in df.groupby("fecha"):
        day_dir = os.path.join(out_dir, f"fecha={fecha}")
        os.makedirs(day_dir, exist_ok=True)
        sub = grp.drop(columns=["fecha"]).copy()
        # timestamp como datetime64[us, UTC]
        sub["timestamp"] = pd.to_datetime(sub["timestamp"].apply(
            lambda x: x.astimezone(timezone.utc) if hasattr(x, "astimezone") else x
        )).dt.tz_localize(None).dt.tz_localize("UTC")
        tbl = pa.Table.from_pandas(sub, schema=REFINADA_SCHEMA, preserve_index=False)
        pq.write_table(tbl, os.path.join(day_dir, "part-0.parquet"),
                       use_deprecated_int96_timestamps=False,
                       coerce_timestamps="us")


def write_refs(df: pd.DataFrame, ref_dir: str, totales_path: str = None):
    """Escribe referencias de reconciliación."""
    os.makedirs(ref_dir, exist_ok=True)
    # 1440 grupos fecha × sector × quality_flag
    r3 = df.groupby(["fecha", "sector", "quality_flag"], as_index=False).agg(
        filas=("meter_id", "count"),
        suma_consumo=("consumo_m3", "sum"),
        ts_min=("timestamp", "min"),
        ts_max=("timestamp", "max"),
    )
    r3["suma_consumo"] = r3["suma_consumo"].round(6)
    r3.to_csv(os.path.join(ref_dir, "refs_3clave.csv"), index=False)
    # 480 grupos fecha × sector
    r2 = df.groupby(["fecha", "sector"], as_index=False)["consumo_m3"].sum()
    r2["consumo_m3"] = r2["consumo_m3"].round(6)
    if totales_path:
        r2.to_csv(totales_path, index=False)
    r2.to_csv(os.path.join(ref_dir, "totales_480.csv"), index=False)
    return len(r3), len(r2)


def gen_base():
    total_m = MEDIDORES_POR_SECTOR_BASE * len(SECTORES)
    all_rows = []
    for s_idx, sec in enumerate(SECTORES):
        base_m = s_idx * MEDIDORES_POR_SECTOR_BASE + 1
        for m in range(MEDIDORES_POR_SECTOR_BASE):
            mid = base_m + m
            for dia in range(N_DIAS):
                ts = timestamp_utc(dia, mid)
                all_rows.append({
                    "meter_id": mid, "timestamp": ts,
                    "fecha": fecha_iso(dia), "sector": sec,
                    "consumo_m3": consumo_m3(mid, dia),
                    "presion_bar": presion_bar(mid, dia),
                    "quality_flag": quality_flag(mid, dia),
                })
    df = pd.DataFrame(all_rows)
    cruda = os.path.join(REPO, "datalake", "cruda_t16")
    ref_dir = os.path.join(REPO, "datalake", "refs_refinada")
    refinada = os.path.join(REPO, "datalake", "refinada")
    write_cruda_csv(df, cruda)
    write_refinada_parquet(df, refinada)
    g3, g2 = write_refs(df, ref_dir)
    disk = sum(
        os.path.getsize(os.path.join(r, f))
        for r, _, files in os.walk(cruda) for f in files
    ) / (1024 * 1024)
    print(f"base: medidores={total_m} lecturas={len(df)} dias={N_DIAS} "
          f"grupos_480={g2} grupos_1440={g3} "
          f"cruda_csv={cruda} refinada={refinada} disk_MiB={disk:.1f}")


def gen_ampliacion(equipo: str):
    perfil = PERFILES_AMPLIACION[equipo]
    M = perfil["medidores"]
    p = perfil["p"]
    dom = perfil["dominante"]
    dom_idx = SECTORES.index(dom)
    counts = medidores_por_sector(M, p, dom_idx)
    all_rows = []
    mid = 0
    for s_idx, sec in enumerate(SECTORES):
        for _ in range(counts[s_idx]):
            mid += 1
            for dia in range(N_DIAS):
                ts = timestamp_utc(dia, mid)
                all_rows.append({
                    "meter_id": mid, "timestamp": ts,
                    "fecha": fecha_iso(dia), "sector": sec,
                    "consumo_m3": consumo_m3(mid, dia),
                    "presion_bar": presion_bar(mid, dia),
                    "quality_flag": quality_flag(mid, dia),
                })
    df = pd.DataFrame(all_rows)
    base_dir = os.path.join(REPO, "datalake_equipo")
    cruda = os.path.join(base_dir, "cruda_t16")
    refinada = os.path.join(base_dir, "refinada")
    ref_dir = os.path.join(base_dir, "refs_refinada")
    totales = os.path.join(base_dir, "totales_control_t16.csv")
    write_cruda_csv(df, cruda)
    write_refinada_parquet(df, refinada)
    g3, g2 = write_refs(df, ref_dir, totales)
    disk = sum(
        os.path.getsize(os.path.join(r, f))
        for r, _, files in os.walk(base_dir) for f in files
    ) / (1024 * 1024)
    print(f"ampliacion equipo={equipo} medidores={M} lecturas={len(df)} "
          f"dominante={dom} p={p} grupos_480={g2} grupos_1440={g3} disk_MiB={disk:.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--volumen", required=True, choices=["base", "ampliacion"])
    ap.add_argument("--equipo", default="equipo-2")
    args = ap.parse_args()
    if args.volumen == "base":
        gen_base()
    else:
        gen_ampliacion(args.equipo)


if __name__ == "__main__":
    main()
