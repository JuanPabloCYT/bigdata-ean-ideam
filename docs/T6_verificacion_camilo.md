# T6 · Verificación de ejecución

**Verificación realizada por:** Camilo Rojas  
**Fecha:** 2026-08-21  
**Repositorio:** `bigdata-ean-ideam`

## Resultado

Se realizó una revisión y prueba de la implementación de T6 para confirmar que el flujo de conversión a Parquet funciona correctamente y que la capa cruda permanece intacta.

### Elementos verificados

- `src/refinar/convertir_parquet.py` lee el CSV desde `lago-crudo` y escribe el resultado en `lago-refinado`.
- La salida queda en Parquet particionado por fecha.
- `src/refinar/medir_codecs.py` compara `snappy`, `gzip` y `zstd` sobre la misma muestra.
- Las mediciones utilizan la mediana de tres repeticiones.
- El codec seleccionado para la refinada es `zstd`, respaldado por las mediciones documentadas en `docs/T6_formato.md`.
- La conversión es idempotente y no sobrescribe silenciosamente un objeto existente con contenido diferente.
- La documentación de reproducción está disponible en `docs/T6_ejecucion.md`.
- La capa cruda se mantiene como fuente original e inmutable; el Parquet se genera únicamente en la capa refinada.

## Evidencia revisada

La medición documentada para la muestra de 141.007 filas reporta:

| Codec | Tamaño | Escritura | Lectura selectiva |
|---|---:|---:|---:|
| Snappy | 381.716 B | 0,0218 s | 0,0030 s |
| Gzip | 284.431 B | 0,0323 s | 0,0016 s |
| ZSTD | 312.373 B | 0,0198 s | 0,0016 s |

La consulta selectiva sobre Parquet con ZSTD también está documentada como considerablemente más rápida que la misma consulta sobre CSV.

## Conclusión

**T6 verificada correctamente.** La implementación, medición, elección del codec y documentación son coherentes con el criterio de aceptación de la tarea y quedan listas para continuar con las siguientes actividades del proyecto.
