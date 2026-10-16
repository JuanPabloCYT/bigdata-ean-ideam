"""Verificación de la ingesta incremental — T12.

Prueba los tres contratos del módulo ingestar_stg:
  Test A  Dos ejecuciones consecutivas para la misma fecha producen
          idéntico número de filas en stg.stg_lecturas.
  Test B  Una brecha de tres horas (dos filas eliminadas) se recupera
          en la siguiente ejecución; la segunda re-ejecución agrega 0 filas;
          la marca de agua permanece sin cambio en ambos casos.
  Test C  La clave única uq_stg_lecturas_clave incluye _fuente, lo que
          permite que el mismo instante coexista con fuentes distintas.

El script limpia sus propias filas sintéticas (codigoestacion 99999*) al
principio y al final para no contaminar datos reales.

Uso:
    python practica/s12-ingesta/verificar_t12.py
    docker exec ideam_jupyter python practica/s12-ingesta/verificar_t12.py
"""

from __future__ import annotations

import sys
import os

# Garantiza que 'src' sea importable cuando se ejecuta desde cualquier ruta.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import psycopg
from datetime import date

from src.config import connection_parameters
from src.ingesta.ingestar_stg import ingest

# ------------------------------------------------------------------ #
# Datos sintéticos de prueba (rango 99999* = convención DEMO del proyecto)
# ------------------------------------------------------------------ #
FECHA_22 = date(2026, 6, 22)   # fecha principal del Test A
FECHA_21 = date(2026, 6, 21)   # fecha con brecha del Test B

SEED_ROWS = [
    # (codigoestacion, codigosensor, fechaobservacion, valorobservado,
    #  nombreestacion, departamento, municipio, zonahidrografica,
    #  latitud, longitud, descripcionsensor, unidadmedida)
    (99999901, 240, "2026-06-21 08:00:00", 1.2,
     "ESTACION DEMO T12 A", "DPTO DEMO", "MUN DEMO", "ZONA DEMO",
     4.60, -74.10, "PRECIPITACION DEMO", "mm"),
    (99999901, 240, "2026-06-21 09:00:00", 2.3,
     "ESTACION DEMO T12 A", "DPTO DEMO", "MUN DEMO", "ZONA DEMO",
     4.60, -74.10, "PRECIPITACION DEMO", "mm"),
    (99999902, 257, "2026-06-21 08:00:00", 0.5,
     "ESTACION DEMO T12 B", "DPTO DEMO", "MUN DEMO", "ZONA DEMO",
     4.70, -74.20, "GPRS - PRECIPITACION DEMO", "mm"),
    (99999901, 240, "2026-06-22 08:00:00", 3.1,
     "ESTACION DEMO T12 A", "DPTO DEMO", "MUN DEMO", "ZONA DEMO",
     4.60, -74.10, "PRECIPITACION DEMO", "mm"),
    (99999902, 257, "2026-06-22 08:00:00", 0.9,
     "ESTACION DEMO T12 B", "DPTO DEMO", "MUN DEMO", "ZONA DEMO",
     4.70, -74.20, "GPRS - PRECIPITACION DEMO", "mm"),
]


def limpiar_demo(conn: psycopg.Connection) -> None:
    """Elimina todas las filas de prueba (99999*) de ambas tablas."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM stg.stg_lecturas WHERE codigoestacion >= 99999000"
        )
        cur.execute(
            "DELETE FROM public.precipitacion WHERE codigoestacion >= 99999000"
        )
        # Reinicia la marca de agua para que los tests sean reproducibles
        cur.execute(
            "UPDATE stg.estado_ingesta SET ultima_marca_agua = NULL, "
            "actualizado_en = now() WHERE nombre_proceso = 'precipitacion_ideam'"
        )
    conn.commit()


def insertar_seed(conn: psycopg.Connection) -> None:
    """Inserta las filas sintéticas en public.precipitacion."""
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO public.precipitacion (
                codigoestacion, codigosensor, fechaobservacion, valorobservado,
                nombreestacion, departamento, municipio, zonahidrografica,
                latitud, longitud, descripcionsensor, unidadmedida
            ) VALUES (%s, %s, %s::timestamp, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            SEED_ROWS,
        )
    conn.commit()


def contar_stg(conn: psycopg.Connection, fecha: date) -> int:
    """Cuenta filas en stg.stg_lecturas para una fecha concreta."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM stg.stg_lecturas "
            "WHERE fechaobservacion::date = %s AND _fuente = 'ideam_socrata'",
            (fecha,),
        )
        return cur.fetchone()[0]


def leer_marca_agua(conn: psycopg.Connection):
    """Devuelve la marca de agua actual del proceso."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ultima_marca_agua FROM stg.estado_ingesta "
            "WHERE nombre_proceso = 'precipitacion_ideam'"
        )
        row = cur.fetchone()
        return row[0] if row else None


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #

def test_a(conn_params: dict) -> bool:
    """Test A: dos ejecuciones consecutivas producen el mismo conteo."""
    print("\n=== TEST A: Idempotencia — dos ejecuciones consecutivas ===")
    try:
        result1 = ingest(conn_params, FECHA_22)
        with psycopg.connect(**conn_params) as conn:
            count_1 = contar_stg(conn, FECHA_22)
            marca_1 = leer_marca_agua(conn)

        result2 = ingest(conn_params, FECHA_22)
        with psycopg.connect(**conn_params) as conn:
            count_2 = contar_stg(conn, FECHA_22)
            marca_2 = leer_marca_agua(conn)

        print(f"  Ejecución 1: filas_procesadas={result1['filas_procesadas']}, "
              f"count stg={count_1}")
        print(f"  Ejecución 2: filas_procesadas={result2['filas_procesadas']}, "
              f"count stg={count_2}")
        print(f"  Marca de agua 1: {marca_1}")
        print(f"  Marca de agua 2: {marca_2}")

        assert count_1 == count_2, (
            f"Los conteos difieren: {count_1} != {count_2}"
        )
        assert marca_1 == marca_2, (
            f"La marca de agua cambió entre ejecuciones: {marca_1} != {marca_2}"
        )
        print("TEST A [PASS]")
        return True
    except AssertionError as e:
        print(f"TEST A [FAIL]: {e}")
        return False
    except Exception as e:
        print(f"TEST A [FAIL]: excepción inesperada: {e}")
        return False


def test_b(conn_params: dict) -> bool:
    """Test B: recuperación de brecha de tres horas."""
    print("\n=== TEST B: Recuperación de brecha (gap recovery) ===")
    try:
        # Ingesta inicial de la fecha 21 — establece la línea base
        ingest(conn_params, FECHA_21)
        with psycopg.connect(**conn_params) as conn:
            baseline = contar_stg(conn, FECHA_21)
            marca_antes = leer_marca_agua(conn)

        print(f"  Línea base (fecha {FECHA_21}): {baseline} filas")
        print(f"  Marca de agua antes de eliminar: {marca_antes}")

        if baseline == 0:
            raise AssertionError(
                "La línea base es 0; revise que las filas seed fueron insertadas"
            )

        # Simula la brecha: elimina 2 filas de la fecha 21
        with psycopg.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM stg.stg_lecturas
                    WHERE ctid IN (
                        SELECT ctid FROM stg.stg_lecturas
                        WHERE fechaobservacion::date = %s
                          AND _fuente = 'ideam_socrata'
                        LIMIT 2
                    )
                    """,
                    (FECHA_21,),
                )
            conn.commit()

        with psycopg.connect(**conn_params) as conn:
            count_tras_delete = contar_stg(conn, FECHA_21)
        print(f"  Tras eliminar 2 filas: {count_tras_delete} filas")

        # Primera re-ingesta: debe restaurar las filas eliminadas
        ingest(conn_params, FECHA_21)
        with psycopg.connect(**conn_params) as conn:
            count_recuperado = contar_stg(conn, FECHA_21)
            marca_despues_1 = leer_marca_agua(conn)

        print(f"  Tras primera re-ingesta: {count_recuperado} filas")
        print(f"  Marca de agua tras re-ingesta 1: {marca_despues_1}")

        assert count_recuperado == baseline, (
            f"No se recuperaron todas las filas: esperado {baseline}, "
            f"obtenido {count_recuperado}"
        )
        assert marca_despues_1 == marca_antes, (
            f"La marca de agua cambió: {marca_antes} -> {marca_despues_1}"
        )

        # Segunda re-ingesta: no debe cambiar nada
        ingest(conn_params, FECHA_21)
        with psycopg.connect(**conn_params) as conn:
            count_segundo = contar_stg(conn, FECHA_21)
            marca_despues_2 = leer_marca_agua(conn)

        print(f"  Tras segunda re-ingesta: {count_segundo} filas")
        print(f"  Marca de agua tras re-ingesta 2: {marca_despues_2}")

        assert count_segundo == baseline, (
            f"La segunda re-ingesta cambió el conteo: {count_segundo} != {baseline}"
        )
        assert marca_despues_2 == marca_antes, (
            f"La marca de agua cambió en la segunda re-ingesta: "
            f"{marca_antes} -> {marca_despues_2}"
        )

        print("TEST B [PASS]")
        return True
    except AssertionError as e:
        print(f"TEST B [FAIL]: {e}")
        return False
    except Exception as e:
        print(f"TEST B [FAIL]: excepción inesperada: {e}")
        return False


def test_c(conn_params: dict) -> bool:
    """Test C: la clave única permite _fuente distinta para el mismo instante."""
    print("\n=== TEST C: Clave de deduplicación — caso borde legacy ===")
    try:
        # Verifica que la restricción existe en information_schema
        with psycopg.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'stg'
                      AND table_name   = 'stg_lecturas'
                      AND constraint_type = 'UNIQUE'
                      AND constraint_name = 'uq_stg_lecturas_clave'
                    """
                )
                row = cur.fetchone()

        assert row is not None, (
            "La restricción uq_stg_lecturas_clave no existe en information_schema"
        )
        print(f"  Restricción encontrada: {row[0]}")

        # Verifica que las columnas de la restricción incluyen _fuente
        with psycopg.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT kcu.column_name
                    FROM information_schema.key_column_usage kcu
                    JOIN information_schema.table_constraints tc
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema    = kcu.table_schema
                    WHERE tc.table_schema    = 'stg'
                      AND tc.table_name      = 'stg_lecturas'
                      AND tc.constraint_name = 'uq_stg_lecturas_clave'
                    ORDER BY kcu.ordinal_position
                    """
                )
                columnas = [r[0] for r in cur.fetchall()]

        print(f"  Columnas de la clave única: {columnas}")
        assert "_fuente" in columnas, (
            f"_fuente no está en la clave única: {columnas}"
        )

        # Asegura que exista al menos una fila de ideam_socrata para el instante
        # de prueba (la ingesta del Test A o B pudo haberla insertado)
        with psycopg.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                # Asegura que la fila socrata existe
                cur.execute(
                    """
                    INSERT INTO stg.stg_lecturas (
                        codigoestacion, codigosensor, fechaobservacion,
                        valorobservado, nombreestacion, departamento,
                        municipio, zonahidrografica, latitud, longitud,
                        descripcionsensor, unidadmedida, _fuente
                    ) VALUES (
                        99999901, 240, '2026-06-21 08:00:00',
                        1.2, 'ESTACION DEMO T12 A', 'DPTO DEMO', 'MUN DEMO',
                        'ZONA DEMO', 4.60, -74.10, 'PRECIPITACION DEMO', 'mm',
                        'ideam_socrata'
                    )
                    ON CONFLICT ON CONSTRAINT uq_stg_lecturas_clave DO NOTHING
                    """
                )
                # Inserta la misma combinación (codigoestacion, codigosensor,
                # fechaobservacion) pero con _fuente = 'ideam_legacy'
                cur.execute(
                    """
                    INSERT INTO stg.stg_lecturas (
                        codigoestacion, codigosensor, fechaobservacion,
                        valorobservado, nombreestacion, departamento,
                        municipio, zonahidrografica, latitud, longitud,
                        descripcionsensor, unidadmedida, _fuente
                    ) VALUES (
                        99999901, 240, '2026-06-21 08:00:00',
                        1.2, 'ESTACION DEMO T12 A', 'DPTO DEMO', 'MUN DEMO',
                        'ZONA DEMO', 4.60, -74.10, 'PRECIPITACION DEMO', 'mm',
                        'ideam_legacy'
                    )
                    ON CONFLICT ON CONSTRAINT uq_stg_lecturas_clave DO NOTHING
                    """
                )
            conn.commit()

        # Verifica que hay exactamente 2 filas para ese instante
        with psycopg.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM stg.stg_lecturas
                    WHERE codigoestacion  = 99999901
                      AND codigosensor    = 240
                      AND fechaobservacion = '2026-06-21 08:00:00'
                    """
                )
                total = cur.fetchone()[0]

        print(f"  Filas para el instante de prueba "
              f"(ideam_socrata + ideam_legacy): {total}")
        assert total == 2, (
            f"Se esperaban 2 filas (una por _fuente), se encontraron {total}"
        )

        print("TEST C [PASS]")
        return True
    except AssertionError as e:
        print(f"TEST C [FAIL]: {e}")
        return False
    except Exception as e:
        print(f"TEST C [FAIL]: excepción inesperada: {e}")
        return False


# ------------------------------------------------------------------ #
# Punto de entrada
# ------------------------------------------------------------------ #

def main() -> None:
    print("=" * 60)
    print("Verificación T12 · Ingesta incremental e idempotente")
    print("=" * 60)

    conn_params = connection_parameters()

    # Limpieza inicial
    print("\n[setup] Limpiando filas de prueba previas …")
    with psycopg.connect(**conn_params) as conn:
        limpiar_demo(conn)

    # Insertar datos sintéticos
    print("[setup] Insertando filas sintéticas en public.precipitacion …")
    with psycopg.connect(**conn_params) as conn:
        insertar_seed(conn)

    # Ejecutar los tres tests
    resultado_a = test_a(conn_params)
    resultado_b = test_b(conn_params)
    resultado_c = test_c(conn_params)

    # Limpieza final
    print("\n[teardown] Limpiando filas de prueba …")
    with psycopg.connect(**conn_params) as conn:
        limpiar_demo(conn)

    # Resumen
    print("\n" + "=" * 60)
    todos_ok = resultado_a and resultado_b and resultado_c
    if todos_ok:
        print("RESULTADO GLOBAL: PASS — todos los tests pasaron")
        sys.exit(0)
    else:
        fallidos = [
            nombre
            for nombre, ok in [("A", resultado_a), ("B", resultado_b), ("C", resultado_c)]
            if not ok
        ]
        print(f"RESULTADO GLOBAL: FAIL — tests fallidos: {', '.join(fallidos)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
