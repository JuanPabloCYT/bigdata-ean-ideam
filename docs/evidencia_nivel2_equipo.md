# Evidencia Nivel 2 — Plantilla de Corridas

> **Nota:** Este archivo es una plantilla. El cuaderno `control_t13.ipynb` lo sobreescribe
> con valores reales tras ejecutar las corridas de control y de equipo.

**Equipo:** `<!-- equipo asignado -->`  
**Fecha de ejecución:** `<!-- YYYY-MM-DD HH:MM UTC -->`

---

## Tabla de corridas

| Corrida | Equipo | `estado_corrida` | `paginas_procesadas` | `registros_insertados` | `registros_actualizados` | `total_en_stg` | `total_registros_informativo` | Conciliación |
|---|---|---|---|---|---|---|---|---|
| Control (1ra vez) | equipo-1 | | | | | | 15 | |
| Control (2da vez) | equipo-1 | | | | | | 15 | |
| Corrida 1 | equipo asignado | | | | | | 15 | |
| Corrida 2 | equipo asignado | | | | | | 15 | |

---

## Validación de `estado_corrida = COMPLETA`

| Corrida | `estado_corrida` | ¿Es COMPLETA? |
|---|---|---|
| Control (1ra vez) | | |
| Control (2da vez) | | |
| Corrida 1 | | |
| Corrida 2 | | |

---

## Conciliación `registros_en_stg` vs `total_registros_informativo`

La conciliación se considera exitosa cuando:

```
registros_insertados + registros_actualizados == total_registros_informativo
```

| Corrida | `registros_en_stg` | `total_registros_informativo` | ¿Coincide? |
|---|---|---|---|
| Control (1ra vez) | | 15 | |
| Control (2da vez) | | 15 | |
| Corrida 1 | | 15 | |
| Corrida 2 | | 15 | |

---

## Notas

- Si `estado_corrida != COMPLETA`, revisar la bitácora en `stg.bitacora_ingesta_api`
  para identificar la página y el tipo de falla.
- El conteo de la 2da corrida de control debe ser idéntico al de la 1ra:
  confirma idempotencia del UPSERT.
- `registros_insertados` en la 2da corrida debe ser 0 y `registros_actualizados`
  debe ser igual a `total_registros_informativo`.

---

*Generado automáticamente por `control_t13.ipynb`*
