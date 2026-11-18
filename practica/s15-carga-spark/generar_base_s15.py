#!/usr/bin/env python3
"""T15 · Generador de la base común (datalake/).

Construye la capa cruda (12 archivos parquet, uno por sector) y la referencia
`consolidada/` (480 filas, suma de consumo por (fecha, sector) redondeada a
6 decimales) que el pipeline de Spark debe reproducir.

Uso:  python practica/s15-carga-spark/generar_base_s15.py
"""
import os
import sys

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from modelo_s15 import (  # noqa: E402
    SECTORES, N_DIAS, MEDIDORES_POR_SECTOR_BASE, fecha_iso, consumo, quality_flag,
)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    cruda = os.path.join(REPO, "datalake", "cruda")
    ref = os.path.join(REPO, "datalake", "consolidada")
    for d in (cruda, ref):
        os.makedirs(d, exist_ok=True)

    frames = []
    for s_idx, sec in enumerate(SECTORES):
        base_m = s_idx * MEDIDORES_POR_SECTOR_BASE + 1
        rows = []
        for m in range(MEDIDORES_POR_SECTOR_BASE):
            mid = base_m + m
            for dia in range(N_DIAS):
                rows.append((mid, fecha_iso(dia), sec, consumo(mid, dia), quality_flag(mid, dia)))
        sub = pd.DataFrame(rows, columns=["medidor_id", "fecha", "sector", "consumo", "quality_flag"])
        pq.write_table(pa.Table.from_pandas(sub, preserve_index=False),
                       os.path.join(cruda, f"lecturas_{s_idx:02d}_{sec}.parquet"))
        frames.append(sub)
    df = pd.concat(frames, ignore_index=True)

    ref_df = df.groupby(["fecha", "sector"], as_index=False)["consumo"].sum()
    ref_df["consumo"] = ref_df["consumo"].round(6)
    ref_df = ref_df.sort_values(["fecha", "sector"]).reset_index(drop=True)
    pq.write_table(pa.Table.from_pandas(ref_df, preserve_index=False),
                   os.path.join(ref, "consolidada.parquet"))
    ref_df.to_csv(os.path.join(ref, "consolidada.csv"), index=False)

    total_medidores = MEDIDORES_POR_SECTOR_BASE * len(SECTORES)
    print(f"base: medidores={total_medidores} lecturas={len(df)} grupos={len(ref_df)} "
          f"(esperado 480) lecturas_por_sector_dia={MEDIDORES_POR_SECTOR_BASE} "
          f"(esperado 1200) cruda={cruda} referencia={ref}")


if __name__ == "__main__":
    main()
