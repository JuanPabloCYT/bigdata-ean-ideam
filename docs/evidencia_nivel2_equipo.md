# Evidencia Nivel 2 — Corridas del Conector T13

**Equipo:** `equipo-2`  
**Fecha de ejecución:** `2025-07-10 02:30 UTC`

---

## Tabla de corridas

| Corrida | Equipo | `estado_corrida` | `paginas_procesadas` | `registros_insertados` | `registros_actualizados` | `total_en_stg` | `total_registros_informativo` | Conciliación |
|---|---|---|---|---|---|---|---|---|
| Control (1ra vez) | equipo-1 | `COMPLETA` | 3 | 15 | 0 | 15 | 15 | ✅ OK |
| Control (2da vez) | equipo-1 | `COMPLETA` | 3 | 0 | 15 | 15 | 15 | ✅ OK |
| Corrida 1 | equipo-2 | `COMPLETA` | 3 | 0 | 15 | 15 | 15 | ✅ OK |
| Corrida 2 | equipo-2 | `COMPLETA` | 3 | 0 | 15 | 15 | 15 | ✅ OK |

---

## Validación de `estado_corrida = COMPLETA`

| Corrida | `estado_corrida` | ¿Es COMPLETA? |
|---|---|---|
| Control (1ra vez) | `COMPLETA` | ✅ Validado |
| Control (2da vez) | `COMPLETA` | ✅ Validado |
| Corrida 1 | `COMPLETA` | ✅ Validado |
| Corrida 2 | `COMPLETA` | ✅ Validado |

---

## Conciliación `registros_en_stg` vs `total_registros_informativo`

La conciliación se considera exitosa cuando:

```
registros_insertados + registros_actualizados == total_registros_informativo
```

| Corrida | `registros_en_stg` | `total_registros_informativo` | ¿Coincide? |
|---|---|---|---|
| Control (1ra vez) | 15 | 15 | ✅ OK |
| Control (2da vez) | 15 | 15 | ✅ OK |
| Corrida 1 | 15 | 15 | ✅ OK |
| Corrida 2 | 15 | 15 | ✅ OK |

---

## Salidas completas del conector

### Control (1ra vez) — equipo-1

```json
{
  "paginas_procesadas": 3,
  "registros_insertados": 15,
  "registros_actualizados": 0,
  "estado_corrida": "COMPLETA"
}
```

### Control (2da vez) — equipo-1 (idempotencia)

```json
{
  "paginas_procesadas": 3,
  "registros_insertados": 0,
  "registros_actualizados": 15,
  "estado_corrida": "COMPLETA"
}
```

La segunda corrida de control confirma idempotencia del UPSERT:
`registros_insertados = 0` y `registros_actualizados = 15 = total_registros_informativo`.

### Corrida 1 — equipo-2 (429 → reintento → 200)

```json
{
  "paginas_procesadas": 3,
  "registros_insertados": 0,
  "registros_actualizados": 15,
  "estado_corrida": "COMPLETA"
}
```

### Corrida 2 — equipo-2 (429 → reintento → 200)

```json
{
  "paginas_procesadas": 3,
  "registros_insertados": 0,
  "registros_actualizados": 15,
  "estado_corrida": "COMPLETA"
}
```

---

## Notas

- Las corridas de control (`equipo-1`) tienen `estado_corrida = COMPLETA` en ambas ejecuciones.
- La 2da corrida de control muestra `registros_insertados = 0` y `registros_actualizados = 15`,
  confirmando la idempotencia del `INSERT … ON CONFLICT DO UPDATE`.
- Las corridas de equipo-2 manejan correctamente el perfil 429 (dos reintentos en página 3)
  y terminan con `estado_corrida = COMPLETA`.
- `total_en_stg = 15` al final de todas las corridas confirma que el COUNT de la tabla
  no creció más allá de los 15 medidores únicos (UPSERT idempotente).
- La conciliación `registros_insertados + registros_actualizados == total_registros_informativo`
  se cumple en las cuatro corridas.

---

*Generado con `control_t13.ipynb` y verificado manualmente.  
Entorno: PostgreSQL 17 en Docker (`ideam_db`), mock API Flask en host (`equipo-2`, puerto 15011–15014).  
Fecha: 2025-07-10 02:30 UTC.*
