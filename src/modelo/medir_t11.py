"""Measure T11 analytical queries in PostgreSQL.

Run from the repository root after loading sql/T11_modelo_fisico.sql:
    python -m src.modelo.medir_t11

Reads the same POSTGRES_* environment variables as src.config. Each query is
executed seven times; the first run is a warm-up and the median of the next
six runs is reported. Results are measurements from the active database, not
hard-coded estimates.
"""
from __future__ import annotations

import statistics
import time

import psycopg

from src.config import connection_parameters


QUERIES = {
    "Q1_promedio_departamento": """
        SELECT e.departamento, avg(h.valor_precipitacion_mm) AS promedio_mm
        FROM dw.hechos_precipitacion h
        JOIN dw.dim_estacion e USING (sk_estacion)
        GROUP BY e.departamento
        ORDER BY promedio_mm DESC NULLS LAST
    """,
    "Q2_evolucion_mensual": """
        SELECT f.anio, f.mes, e.departamento,
               avg(h.valor_precipitacion_mm) AS promedio_mm
        FROM dw.hechos_precipitacion h
        JOIN dw.dim_fecha f USING (sk_fecha)
        JOIN dw.dim_estacion e USING (sk_estacion)
        GROUP BY f.anio, f.mes, e.departamento
        ORDER BY f.anio, f.mes, e.departamento
    """,
    "Q3_franja_horaria": """
        SELECT dh.franja, avg(h.valor_precipitacion_mm) AS promedio_mm,
               count(*) AS observaciones
        FROM dw.hechos_precipitacion h
        JOIN dw.dim_hora_del_dia dh USING (sk_hora_del_dia)
        GROUP BY dh.franja
        ORDER BY promedio_mm DESC NULLS LAST
    """,
    "Q4_top_estaciones": """
        SELECT e.codigoestacion, e.nombre_estacion, e.departamento,
               avg(h.valor_precipitacion_mm) AS promedio_mm,
               count(*) AS observaciones
        FROM dw.hechos_precipitacion h
        JOIN dw.dim_estacion e USING (sk_estacion)
        GROUP BY e.codigoestacion, e.nombre_estacion, e.departamento
        ORDER BY promedio_mm DESC NULLS LAST
        LIMIT 10
    """,
    "Q5_sensor_mes": """
        SELECT f.anio, f.mes, s.codigosensor, s.descripcion_sensor,
               sum(h.valor_precipitacion_mm) AS suma_mm, count(*) AS observaciones
        FROM dw.hechos_precipitacion h
        JOIN dw.dim_fecha f USING (sk_fecha)
        JOIN dw.dim_sensor s USING (sk_sensor)
        GROUP BY f.anio, f.mes, s.codigosensor, s.descripcion_sensor
        ORDER BY f.anio, f.mes, s.codigosensor
    """,
}


def measure(cursor, label: str, sql: str, repetitions: int = 7) -> tuple[float, int]:
    """Return median milliseconds after one warm-up and result row count."""
    times_ms: list[float] = []
    row_count = 0
    for run in range(repetitions):
        started = time.perf_counter()
        cursor.execute(sql)
        rows = cursor.fetchall()
        elapsed_ms = (time.perf_counter() - started) * 1000
        row_count = len(rows)
        if run > 0:  # first execution is a warm-up
            times_ms.append(elapsed_ms)
    median_ms = statistics.median(times_ms)
    print(f"{label}\tmedian_ms={median_ms:.3f}\trows={row_count}\truns={len(times_ms)}")
    return median_ms, row_count


def main() -> None:
    with psycopg.connect(**connection_parameters()) as conn:
        with conn.cursor() as cur:
            print("T11 PostgreSQL benchmark; times include fetching result rows.")
            for label, sql in QUERIES.items():
                measure(cur, label, sql)

            # Compare the fine-grain Q2 with an aggregate at the same output grain.
            cur.execute("""
                CREATE TEMP TABLE t11_agg_precipitacion_mes_departamento AS
                SELECT f.anio, f.mes, e.departamento,
                       avg(h.valor_precipitacion_mm) AS promedio_mm
                FROM dw.hechos_precipitacion h
                JOIN dw.dim_fecha f USING (sk_fecha)
                JOIN dw.dim_estacion e USING (sk_estacion)
                GROUP BY f.anio, f.mes, e.departamento
            """)
            cur.execute("ANALYZE t11_agg_precipitacion_mes_departamento")
            before_ms, _ = measure(cur, "Q2_antes_grano_fino", QUERIES["Q2_evolucion_mensual"])
            after_sql = """
                SELECT anio, mes, departamento, promedio_mm
                FROM t11_agg_precipitacion_mes_departamento
                ORDER BY anio, mes, departamento
            """
            after_ms, _ = measure(cur, "Q2_despues_agregada", after_sql)
            if after_ms > 0:
                print(f"Q2_speedup={before_ms / after_ms:.2f}x")
            else:
                print("Q2_speedup=not_calculated (measured aggregate time was zero)")
            print("Note: the aggregate is TEMP for the benchmark. Persist it only if the measured gain justifies maintenance cost.")


if __name__ == "__main__":
    main()
