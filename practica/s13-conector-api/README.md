# Práctica S13 · Conector de Ingesta API

Sesión 13 · Juan Pablo Castro, Camilo Rojas, Lina Ramírez  
Conector REST paginado con autenticación Bearer, UPSERT idempotente y bitácora append-only.

La documentación completa con tabla de clasificación de códigos HTTP, justificación del backoff y evidencia de logs está en [`docs/T13_conector_api.md`](../../docs/T13_conector_api.md).

## Qué hay aquí

| Archivo | Qué es |
|---|---|
| `api_mock.py` | Servidor Flask que simula la API con 5 perfiles de error configurables por `--equipo` |
| `control_t13.ipynb` | Cuaderno que levanta el mock, ejecuta el conector para equipos 1-3 y genera evidencia |
| `verificar_t13.py` | Script de verificación con cinco tests (idempotencia, append-only, backoff, abort 401, DDL) |
| `README.md` | Este archivo — instrucciones de reproducción |

## Prerrequisitos

- Docker Desktop en ejecución (`docker info` no debe dar error).
- Archivo `.env` configurado en la raíz del proyecto (ver `.env.example`).
- Las variables `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` y `POSTGRES_PASSWORD` deben estar definidas en `.env`.
- Python 3.10+ con `flask`, `psycopg2-binary` y `requests` instalados (ya están en `requirements.txt`).

## Pasos para reproducir

### 1. Levantar el entorno Docker

```bash
cd /Users/camilorojas/Projects/BigData/bigdata-ean-ideam
docker compose up -d
docker compose ps   # esperar hasta que ideam_db muestre (healthy)
```

Salida esperada (fragmento):

```
NAME            STATUS
ideam_db        running (healthy)
ideam_jupyter   running
```

### 2. Aplicar el DDL de T13

```bash
docker exec -i ideam_db psql -U ideam_app -d ideam < sql/T13_conector_api.sql
```

Salida esperada (fragmento):

```
BEGIN
CREATE SCHEMA
CREATE TABLE
CREATE TABLE
COMMIT
   table_name
----------------------
 bitacora_ingesta_api
 estado_ingesta
 stg_estado_medidor
 stg_lecturas
(4 rows)
```

Re-ejecutar el mismo comando debe salir con código 0 — confirma la idempotencia del DDL.

### 3. Levantar la API mock

En una terminal separada (fuera de Docker, en el host):

```bash
python practica/s13-conector-api/api_mock.py --equipo equipo-1 --port 5000
```

### 4. Ejecutar el conector

```bash
docker exec ideam_jupyter python -m src.ingesta.conector_api \
    --url http://host.docker.internal:5000/api/medidores \
    --token demo-token
```

Salida esperada:

```json
{
  "paginas_procesadas": 3,
  "registros_insertados": 15,
  "registros_actualizados": 0,
  "estado_corrida": "COMPLETA"
}
```

Segunda ejecución (mismos datos):

```json
{
  "paginas_procesadas": 3,
  "registros_insertados": 0,
  "registros_actualizados": 15,
  "estado_corrida": "COMPLETA"
}
```

### 5. Ejecutar la verificación completa

```bash
docker exec ideam_jupyter python practica/s13-conector-api/verificar_t13.py
```

Salida esperada (completa):

```
============================================================
Verificación T13 · Conector de Ingesta API
============================================================
[setup] Limpiando filas de prueba previas …

=== TEST E: DDL — existencia de tablas ===
  stg.stg_estado_medidor:  encontrada
  stg.bitacora_ingesta_api: encontrada
TEST E [PASS]

=== TEST A: Idempotencia — dos corridas consecutivas (equipo-1) ===
  Corrida 1: estado=COMPLETA, count=15
  Corrida 2: estado=COMPLETA, count=15
TEST A [PASS]

=== TEST B: Append-only — bitácora acumula filas ===
  Filas antes de corridas: 0
  Filas tras corrida 1:    3
  Filas tras corrida 2:    6
TEST B [PASS]

=== TEST C: Backoff 429 — equipo-2 registra REINTENTO ===
  estado_corrida: COMPLETA
  Registros en bitácora para esta corrida:
    pág=1, intento=1, cod=200, resultado=EXITO
    pág=2, intento=1, cod=200, resultado=EXITO
    pág=3, intento=1, cod=429, resultado=REINTENTO
    pág=3, intento=2, cod=429, resultado=REINTENTO
    pág=3, intento=3, cod=200, resultado=EXITO
TEST C [PASS]

=== TEST D: Abort 401 — equipo-4 aborta corrida ===
  estado_corrida: FALLO_AUTENTICACION
  paginas_procesadas: 1
TEST D [PASS]

[teardown] Limpiando filas de prueba …
============================================================
RESULTADO GLOBAL: PASS — todos los tests pasaron
```

El script sale con código 0 cuando todos los tests pasan, y con código 1 si alguno falla.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude (Kiro)** para implementar el DDL, el módulo conector, el mock, el cuaderno y este documento.

Los comandos se ejecutaron en el entorno real del equipo. Las salidas pegadas en la evidencia provienen de la ejecución real de `verificar_t13.py`, no de estimaciones.
