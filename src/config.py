"""Parámetros de conexión, leídos del entorno.

Centralizar esto evita que cada cuaderno repita las credenciales y
garantiza que todos alcancen la base por el NOMBRE DEL SERVICIO
definido en docker-compose.yml, no por una dirección fija.
"""
import os


def connection_parameters():
    """Devuelve los parámetros de conexión a PostgreSQL.

    Los valores provienen de variables de entorno inyectadas desde
    .env por Compose. Falla de forma explícita si falta alguna, en
    lugar de intentar un valor por defecto que escondería el error.
    """
    required = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Faltan variables de entorno: "
            + ", ".join(missing)
            + ". ¿Copió .env.example a .env antes de levantar el entorno?"
        )
    return {
        "host": os.environ["POSTGRES_HOST"],
        "port": os.environ["POSTGRES_PORT"],
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }
