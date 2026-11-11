# T13 · Conector de Ingesta API — Documentación Nivel 3

Sesión 13 · Juan Pablo Castro, Camilo Rojas, Lina Ramírez

## 1. Descripción y arquitectura

El conector `src/ingesta/conector_api.py` consume una API REST paginada de medidores y persiste los datos en la capa de staging de PostgreSQL. Su función de entrada es:

```
ingestar(conn_params, api_url, token, max_intentos=3, t0=1.0, tmax=60.0)
```

El flujo por página es:

```
while hay_siguiente == True
  └─ para cada página: intentar hasta max_intentos
       ├─ 200  → UPSERT en stg_estado_medidor + log EXITO → hay_siguiente del payload
       ├─ 401  → log FALLO_AUTENTICACION → abortar corrida
       ├─ 429/5xx/Timeout → log REINTENTO/AGOTADO → backoff exponencial
       └─ otros 4xx → log ERROR_PERMANENTE → avanzar de página
```

**Idempotencia:** `stg_estado_medidor` usa `INSERT … ON CONFLICT (meter_id) DO UPDATE`. Re-ejecutar el mismo lote no duplica filas; el `COUNT(*)` queda idéntico.

**Append-only:** `bitacora_ingesta_api` recibe un `INSERT` puro por cada intento HTTP, sin `ON CONFLICT`. Nunca se modifica ni se elimina una fila de bitácora.

---

## 2. Clasificación de códigos HTTP

| Código | Categoría | Acción del conector | Resultado en bitácora |
|---|---|---|---|
| 200 | Éxito | UPSERT en `stg_estado_medidor`; leer `hay_siguiente` del payload | `EXITO` |
| 401 | Error de autenticación | Abortar corrida inmediatamente; no reintentar | `FALLO_AUTENTICACION` |
| 429 | Límite de tasa (transitorio) | Backoff exponencial; reintentar hasta `max_intentos` | `REINTENTO` (intentos k < max) / `AGOTADO` (intento k = max) |
| 500–503 | Error del servidor (transitorio) | Backoff exponencial; reintentar hasta `max_intentos` | `REINTENTO` / `AGOTADO` |
| 404 / otros 4xx | Error permanente del cliente | Loguear y avanzar a la siguiente página; no reintentar | `ERROR_PERMANENTE` |
| Timeout | Red / servidor lento (transitorio) | Igual que 429/5xx: backoff y reintento | `REINTENTO` / `AGOTADO` |

---

## 3. Backoff exponencial — fórmula y justificación de parámetros

Antes del intento **k ≥ 2** el conector espera:

```
sleep(k) = min(t0 · 2^(k-2), tmax) + jitter
```

donde `jitter = random.uniform(0, 1)` evita que múltiples clientes que fallan al mismo tiempo envíen sus reintentos de forma sincronizada.

### 3.1 Probabilidad de fallo tras N intentos

Sea `p` la probabilidad de que un intento individual resulte en 429 o 5xx.  
Para el perfil **equipo-2** (dos páginas de 15 dan 429), `p ≈ 0.3`.

La probabilidad de que los N intentos fallen todos es:

```
P(todos fallan) = p^N
```

### 3.2 Espera máxima acumulada

La espera acumulada antes de los intentos 2 a N es:

```
W(N) = Σ_{k=1}^{N-1} min(t0 · 2^(k-1), tmax)
```

(El jitter no se incluye aquí; en promedio suma `0.5·(N-1)` segundos adicionales.)

### 3.3 Tabla de parámetros (t0 = 1 s, tmax = 60 s, p = 0.3)

| N (max_intentos) | p^N | Espera máx. acumulada (sin jitter) |
|---|---|---|
| 3 | 0.027 | 1 + 2 = 3 s |
| 4 | 0.0081 | 1 + 2 + 4 = 7 s |
| 5 | 0.00243 | 1 + 2 + 4 + 8 = 15 s |

Con `max_intentos = 3` la probabilidad de que los 3 intentos fallen todos es 2.7 %, y la espera máxima acumulada es 3 segundos. Para escenarios de alta inestabilidad se puede aumentar N a 5 (probabilidad de fallo total: 0.24 %, espera máxima: 15 s).

---

## 4. Comandos exactos

### Levantar el entorno Docker

```bash
docker compose up -d
```

### Aplicar el DDL

```bash
docker exec -i ideam_db psql -U ideam_app -d ideam < sql/T13_conector_api.sql
```

### Levantar la API mock (en el host, terminal separada)

```bash
# Perfil de control
python practica/s13-conector-api/api_mock.py --equipo equipo-1 --port 5000

# Perfil con 429
python practica/s13-conector-api/api_mock.py --equipo equipo-2 --port 5000

# Perfil con 500 (agotado)
python practica/s13-conector-api/api_mock.py --equipo equipo-3 --port 5000

# Perfil con 401 (aborta)
python practica/s13-conector-api/api_mock.py --equipo equipo-4 --port 5000

# Perfil con 404 (error permanente)
python practica/s13-conector-api/api_mock.py --equipo equipo-5 --port 5000
```

### Ejecutar el conector (desde Docker)

```bash
# Corrida normal
docker exec ideam_jupyter python -m src.ingesta.conector_api \
    --url http://host.docker.internal:5000/api/medidores \
    --token demo-token

# Con parámetros de backoff personalizados
docker exec ideam_jupyter python -m src.ingesta.conector_api \
    --url http://host.docker.internal:5000/api/medidores \
    --token demo-token \
    --max-intentos 5 \
    --t0 2.0 \
    --tmax 120.0
```

### Ejecutar la verificación completa

```bash
docker exec ideam_jupyter python practica/s13-conector-api/verificar_t13.py
```

---

## 5. Evidencia de logs por perfil

### equipo-1 (control — 200 siempre)

Salida esperada de `bitacora_ingesta_api` tras una corrida:

```
 pagina | intento | codigo_respuesta | resultado
--------+---------+-----------------+-----------
      1 |       1 |             200 | EXITO
      2 |       1 |             200 | EXITO
      3 |       1 |             200 | EXITO
(3 rows)
```

### equipo-2 (429 en página 3, dos veces)

```
 pagina | intento | codigo_respuesta | resultado
--------+---------+-----------------+-----------
      1 |       1 |             200 | EXITO
      2 |       1 |             200 | EXITO
      3 |       1 |             429 | REINTENTO
      3 |       2 |             429 | REINTENTO
      3 |       3 |             200 | EXITO
(5 rows)
```

### equipo-3 (500 en página 2 — agotado)

```
 pagina | intento | codigo_respuesta | resultado
--------+---------+-----------------+-----------
      1 |       1 |             200 | EXITO
      2 |       1 |             500 | REINTENTO
      2 |       2 |             500 | REINTENTO
      2 |       3 |             500 | AGOTADO
(4 rows)
```

`estado_corrida = AGOTADO_REINTENTOS`; página 3 no se procesa.

### equipo-4 (401 en página 2)

```
 pagina | intento | codigo_respuesta | resultado
--------+---------+-----------------+-----------
      1 |       1 |             200 | EXITO
      2 |       1 |             401 | FALLO_AUTENTICACION
(2 rows)
```

`estado_corrida = FALLO_AUTENTICACION`; corrida abortada.

### equipo-5 (404 en página 2 — error permanente)

```
 pagina | intento | codigo_respuesta | resultado
--------+---------+-----------------+-----------
      1 |       1 |             200 | EXITO
      2 |       1 |             404 | ERROR_PERMANENTE
      3 |       1 |             200 | EXITO
(3 rows)
```

`estado_corrida = COMPLETA`; la página con 404 se salta y se continúa.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude (Kiro)** para implementar el DDL, el módulo conector, el mock, el cuaderno y este documento.

Los cálculos de backoff y las tablas de probabilidad fueron revisados manualmente por el equipo para verificar su corrección.
