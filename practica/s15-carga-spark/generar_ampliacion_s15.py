#!/usr/bin/env python3
"""T15 · Generador de la ampliación (datalake_equipo/).

Construye, por equipo, una capa cruda de 120 archivos parquet (entrada del
pipeline), una capa CSV de contraste (120 archivos, para ADR-4 y para la carga
nocturna del Nivel 3) y la referencia `totales_control.csv` (480 filas, suma de
consumo por (fecha, sector) redondeada a 6 decimales). El sector dominante
concentra una fracción p de los medidores, lo que sesga las lecturas por
(sector, día): ese sesgo es lo que la celda de bytes por tarea evidencia.

Uso:  python practica/s15-carga-spark/generar_ampliacion_s15.py --equipo equipo-2
"""
import argparse
import os
import sys

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from modelo_s15 import (  # noqa: E402
    SECTORES, N_DIAS, PERFILES_AMPLIACION, fecha_iso, consumo, quality_flag,
)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
N_ARCHIVOS = 120


def medidores_por_sector(medidores, p, dom_idx):
    """Distribuye `medidores` entre los 12 sectores: el dominante recibe
    round(p*M) y el resto se reparte exacto entre los otros 11, de modo que
    la suma siempre es exactamente M (sin desfase por redondeo)."""
    dom = int(round(p * medidores))
    other = medidores - dom
    otros = len(SECTORES) - 1
    base = other // otros
    resto = other % otros
    counts = [0] * len(SECTORES)
    j = 0
    for i in range(len(SECTORES)):
        if i == dom_idx:
            continue
        counts[i] = base + (1 if j < resto else 0)
        j += 1
    counts[dom_idx] = dom
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equipo", required=True, choices=sorted(PERFILES_AMPLIACION))
    args = ap.parse_args()
    perfil = PERFILES_AMPLIACION[args.equipo]
    M = perfil["medidores"]
    p = perfil["p"]
    dom = perfil["dominante"]
    dom_idx = SECTORES.index(dom)
    counts = medidores_por_sector(M, p, dom_idx)

    base_dir = os.path.join(REPO, "datalake_equipo")
    cruda = os.path.join(base_dir, "cruda")
    csvc = os.path.join(base_dir, "csv_contraste")
    for d in (cruda, csvc):
        os.makedirs(d, exist_ok=True)

    frames = []
    mid = 0
    for s_idx, sec in enumerate(SECTORES):
        rows = []
        for _ in range(counts[s_idx]):
            mid += 1
            for dia in range(N_DIAS):
                rows.append((mid, fecha_iso(dia), sec, consumo(mid, dia), quality_flag(mid, dia)))
        frames.append(pd.DataFrame(rows, columns=["medidor_id", "fecha", "sector", "consumo", "quality_flag"]))
    df = pd.concat(frames, ignore_index=True)

    # Capa cruda: 120 parquet (uno por ~M*40/120 filas).
    chunk = len(df) // N_ARCHIVOS
    for i in range(N_ARCHIVOS):
        a = i * chunk
        b = (i + 1) * chunk if i < N_ARCHIVOS - 1 else len(df)
        sub = df.iloc[a:b]
        pq.write_table(pa.Table.from_pandas(sub, preserve_index=False),
                       os.path.join(cruda, f"lecturas_{i:03d}.parquet"))
        sub.to_csv(os.path.join(csvc, f"lecturas_{i:03d}.csv"), index=False)

    # Referencia: suma por (fecha, sector) redondeada a 6 decimales.
    ref = df.groupby(["fecha", "sector"], as_index=False)["consumo"].sum()
    ref["consumo"] = ref["consumo"].round(6)
    ref = ref.sort_values(["fecha", "sector"]).reset_index(drop=True)
    ref.to_csv(os.path.join(base_dir, "totales_control.csv"), index=False)

    # Disco ocupado por datalake_equipo/ (MiB).
    total = 0
    for root, _, files in os.walk(base_dir):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    disk_mib = total / (1024 * 1024)

    lecturas_por_dia = counts  # 1 lectura/medidor/día
    print(f"ampliacion equipo={args.equipo} medidores={M} lecturas={len(df)} "
          f"sector_dominante={dom} p={p} grupos={len(ref)} (esperado 480) "
          f"lecturas_por_sector_dia_min={min(lecturas_por_dia)} "
          f"max={max(lecturas_por_dia)} disk_MiB={disk_mib:.1f}")


if __name__ == "__main__":
    main()
