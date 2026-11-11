"""Verificación del conector de ingesta API — T13.

Prueba los cinco contratos del conector conector_api:
  Test A  Idempotencia: dos corridas contra equipo-1 producen el mismo
          COUNT(*) en stg.stg_estado_medidor.
  Test B  Append-only: bitacora_ingesta_api acumula filas entre corridas
          (el conteo solo crece, nunca baja).
  Test C  Backoff 429: equipo-2 produce logs REINTENTO en la bitácora para
          la página que da 429, y finalmente EXITO en esa página.
  Test D  Abort 401: equipo-4 resulta en estado FALLO_AUTENTICACION y no
          procesa páginas posteriores a la que devuelve 401.
  Test E  DDL: las tablas stg.stg_estado_medidor y stg.bitacora_ingesta_api
          existen en la base de datos.

El script levanta api_mock.py como subproceso en el puerto 15013.
Limpia filas de prueba al inicio y al final.

Uso:
    python practica/s13-conector-api/verificar_t13.py
    docker exec ideam_jupyter python practica/s13-conector-api/verificar_t13.py
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

# Garantiza que 'src' sea importable cuando se ejecuta desde cualquier ruta.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import psycopg2

from src.config import connection_parameters
from src.ingesta.conector_api import ingestar

# ------------------------------------------------------------------ #
# Configuración del mock
# ------------------------------------------------------------------ #

MOCK_PORT = 15013
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}/api/medidores"
MOCK_TOKEN = "demo-token-t13"
MOCK_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "api_mock.py",
)


def levantar_mock(equipo: str, port: int = MOCK_PORT) -> subprocess.Popen:
    """Levanta api_mock.py como subproceso y espera a que esté listo."""
    proc = subprocess.Popen(
        [sys.executable, MOCK_SCRIPT, "--equipo", equipo, "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)  # dar tiempo a Flask para arrancar
    return proc


def detener_mock(proc: subprocess.Popen) -> None:
    """Detiene el proceso mock."""
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# ------------------------------------------------------------------ #
# Helpers de base de datos
# ------------------------------------------------------------------ #

def contar_medidores(conn) -> int:
    """Cuenta filas en stg.stg_estado_medidor con meter_id de prueba."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM stg.stg_estado_medidor "
            "WHERE meter_id LIKE 'MED-%'"
        )
        return cur.fetchone()[0]


def contar_bitacora(conn) -> int:
    """Cuenta todas las filas en stg.bitacora_ingesta_api."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM stg.bitacora_ingesta_api")
        return cur.fetchone()[0]


def limpiar_prueba(conn) -> None:
    """Elimina filas de prueba de ambas tablas."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM stg.stg_estado_medidor WHERE meter_id LIKE 'MED-%'")
        cur.execute("DELETE FROM stg.bitacora_ingesta_api")
    conn.commit()


def tabla_existe(conn, schema: str, tabla: str) -> bool:
    """Verifica si una tabla existe en information_schema."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema, tabla),
        )
        return cur.fetchone() is not None


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #

def test_e(conn_params: dict) -> bool:
    """Test E: las dos tablas de T13 existen en la base de datos."""
    print("\n=== TEST E: DDL — existencia de tablas ===")
    try:
        with psycopg2.connect(**conn_params) as conn:
            existe_medidor = tabla_existe(conn, "stg", "stg_estado_medidor")
            existe_bitacora = tabla_existe(conn, "stg", "bitacora_ingesta_api")

        print(f"  stg.stg_estado_medidor:  {'encontrada' if existe_medidor else 'NO encontrada'}")
        print(f"  stg.bitacora_ingesta_api: {'encontrada' if existe_bitacora else 'NO encontrada'}")

        assert existe_medidor, "stg.stg_estado_medidor no existe"
        assert existe_bitacora, "stg.bitacora_ingesta_api no existe"

        print("TEST E [PASS]")
        return True
    except AssertionError as e:
        print(f"TEST E [FAIL]: {e}")
        return False
    except Exception as e:
        print(f"TEST E [FAIL]: excepción inesperada: {e}")
        return False


def test_a(conn_params: dict) -> bool:
    """Test A: dos corridas consecutivas (equipo-1) producen el mismo COUNT(*)."""
    print("\n=== TEST A: Idempotencia — dos corridas consecutivas (equipo-1) ===")
    proc = None
    try:
        proc = levantar_mock("equipo-1")

        result1 = ingestar(conn_params, MOCK_URL, MOCK_TOKEN, max_intentos=3, t0=0.05)
        with psycopg2.connect(**conn_params) as conn:
            count_1 = contar_medidores(conn)

        result2 = ingestar(conn_params, MOCK_URL, MOCK_TOKEN, max_intentos=3, t0=0.05)
        with psycopg2.connect(**conn_params) as conn:
            count_2 = contar_medidores(conn)

        print(f"  Corrida 1: estado={result1['estado_corrida']}, count={count_1}")
        print(f"  Corrida 2: estado={result2['estado_corrida']}, count={count_2}")

        assert result1["estado_corrida"] == "COMPLETA", (
            f"Corrida 1 no fue COMPLETA: {result1['estado_corrida']}"
        )
        assert result2["estado_corrida"] == "COMPLETA", (
            f"Corrida 2 no fue COMPLETA: {result2['estado_corrida']}"
        )
        assert count_1 == count_2, (
            f"Los conteos difieren: {count_1} != {count_2}"
        )

        print("TEST A [PASS]")
        return True
    except AssertionError as e:
        print(f"TEST A [FAIL]: {e}")
        return False
    except Exception as e:
        print(f"TEST A [FAIL]: excepción inesperada: {e}")
        return False
    finally:
        detener_mock(proc)


def test_b(conn_params: dict) -> bool:
    """Test B: bitacora_ingesta_api acumula filas entre corridas (append-only)."""
    print("\n=== TEST B: Append-only — bitácora acumula filas ===")
    proc = None
    try:
        proc = levantar_mock("equipo-1")

        with psycopg2.connect(**conn_params) as conn:
            count_antes = contar_bitacora(conn)

        ingestar(conn_params, MOCK_URL, MOCK_TOKEN, max_intentos=3, t0=0.05)
        with psycopg2.connect(**conn_params) as conn:
            count_1 = contar_bitacora(conn)

        ingestar(conn_params, MOCK_URL, MOCK_TOKEN, max_intentos=3, t0=0.05)
        with psycopg2.connect(**conn_params) as conn:
            count_2 = contar_bitacora(conn)

        print(f"  Filas antes de corridas: {count_antes}")
        print(f"  Filas tras corrida 1:    {count_1}")
        print(f"  Filas tras corrida 2:    {count_2}")

        assert count_1 > count_antes, (
            f"La bitácora no creció tras la corrida 1: {count_antes} -> {count_1}"
        )
        assert count_2 > count_1, (
            f"La bitácora no creció tras la corrida 2: {count_1} -> {count_2}"
        )

        print("TEST B [PASS]")
        return True
    except AssertionError as e:
        print(f"TEST B [FAIL]: {e}")
        return False
    except Exception as e:
        print(f"TEST B [FAIL]: excepción inesperada: {e}")
        return False
    finally:
        detener_mock(proc)


def test_c(conn_params: dict) -> bool:
    """Test C: equipo-2 registra REINTENTO en la bitácora para la página con 429."""
    print("\n=== TEST C: Backoff 429 — equipo-2 registra REINTENTO ===")
    proc = None
    try:
        proc = levantar_mock("equipo-2")

        with psycopg2.connect(**conn_params) as conn:
            count_antes = contar_bitacora(conn)

        result = ingestar(
            conn_params, MOCK_URL, MOCK_TOKEN, max_intentos=3, t0=0.05
        )

        with psycopg2.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                # Buscar logs de la página 3 (la que da 429)
                cur.execute(
                    """
                    SELECT pagina, intento, codigo_respuesta, resultado
                    FROM stg.bitacora_ingesta_api
                    WHERE id > %s
                    ORDER BY id
                    """,
                    (count_antes,),
                )
                filas_log = cur.fetchall()

        print(f"  estado_corrida: {result['estado_corrida']}")
        print(f"  Registros en bitácora para esta corrida:")
        for fila in filas_log:
            print(f"    pág={fila[0]}, intento={fila[1]}, "
                  f"cod={fila[2]}, resultado={fila[3]}")

        # Verificar que hay al menos un REINTENTO
        resultados = [f[3] for f in filas_log]
        assert "REINTENTO" in resultados, (
            f"No se encontró ningún REINTENTO en la bitácora: {resultados}"
        )

        # Verificar que la página 3 finalmente tuvo EXITO
        exitos_pag3 = [f for f in filas_log if f[0] == 3 and f[3] == "EXITO"]
        assert len(exitos_pag3) >= 1, (
            f"La página 3 no tuvo EXITO al final: {[f for f in filas_log if f[0] == 3]}"
        )

        print("TEST C [PASS]")
        return True
    except AssertionError as e:
        print(f"TEST C [FAIL]: {e}")
        return False
    except Exception as e:
        print(f"TEST C [FAIL]: excepción inesperada: {e}")
        return False
    finally:
        detener_mock(proc)


def test_d(conn_params: dict) -> bool:
    """Test D: equipo-4 resulta en FALLO_AUTENTICACION y no procesa páginas posteriores."""
    print("\n=== TEST D: Abort 401 — equipo-4 aborta corrida ===")
    proc = None
    try:
        proc = levantar_mock("equipo-4")

        with psycopg2.connect(**conn_params) as conn:
            count_antes = contar_bitacora(conn)

        result = ingestar(
            conn_params, MOCK_URL, MOCK_TOKEN, max_intentos=3, t0=0.05
        )

        with psycopg2.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pagina, intento, codigo_respuesta, resultado
                    FROM stg.bitacora_ingesta_api
                    WHERE id > %s
                    ORDER BY id
                    """,
                    (count_antes,),
                )
                filas_log = cur.fetchall()

        print(f"  estado_corrida: {result['estado_corrida']}")
        print(f"  paginas_procesadas: {result['paginas_procesadas']}")
        print(f"  Logs en bitácora:")
        for fila in filas_log:
            print(f"    pág={fila[0]}, intento={fila[1]}, "
                  f"cod={fila[2]}, resultado={fila[3]}")

        assert result["estado_corrida"] == "FALLO_AUTENTICACION", (
            f"Se esperaba FALLO_AUTENTICACION, se obtuvo: {result['estado_corrida']}"
        )

        # No debe haber logs de página 3 ni posteriores
        paginas_procesadas = {f[0] for f in filas_log}
        assert 3 not in paginas_procesadas, (
            f"La página 3 fue procesada a pesar del 401: {paginas_procesadas}"
        )

        print("TEST D [PASS]")
        return True
    except AssertionError as e:
        print(f"TEST D [FAIL]: {e}")
        return False
    except Exception as e:
        print(f"TEST D [FAIL]: excepción inesperada: {e}")
        return False
    finally:
        detener_mock(proc)


# ------------------------------------------------------------------ #
# Punto de entrada
# ------------------------------------------------------------------ #

def main() -> None:
    print("=" * 60)
    print("Verificación T13 · Conector de Ingesta API")
    print("=" * 60)

    conn_params = connection_parameters()

    # Limpieza inicial
    print("\n[setup] Limpiando filas de prueba previas …")
    with psycopg2.connect(**conn_params) as conn:
        limpiar_prueba(conn)

    # Ejecutar tests (E primero para fallar rápido si el DDL no se aplicó)
    resultado_e = test_e(conn_params)

    if not resultado_e:
        print("\n[ABORT] El DDL no fue aplicado. Ejecute primero:")
        print("  docker exec -i ideam_db psql -U ideam_app -d ideam < sql/T13_conector_api.sql")
        sys.exit(1)

    resultado_a = test_a(conn_params)
    resultado_b = test_b(conn_params)
    resultado_c = test_c(conn_params)
    resultado_d = test_d(conn_params)

    # Limpieza final
    print("\n[teardown] Limpiando filas de prueba …")
    with psycopg2.connect(**conn_params) as conn:
        limpiar_prueba(conn)

    # Resumen
    print("\n" + "=" * 60)
    todos_ok = resultado_a and resultado_b and resultado_c and resultado_d and resultado_e
    if todos_ok:
        print("RESULTADO GLOBAL: PASS — todos los tests pasaron")
        sys.exit(0)
    else:
        fallidos = [
            nombre
            for nombre, ok in [
                ("A", resultado_a),
                ("B", resultado_b),
                ("C", resultado_c),
                ("D", resultado_d),
                ("E", resultado_e),
            ]
            if not ok
        ]
        print(f"RESULTADO GLOBAL: FAIL — tests fallidos: {', '.join(fallidos)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
