# T4 · Verificación independiente (Lina Ramírez)

Reproduje el trabajo completo en un Codespace limpio, sin tocar el codigo original.

## Integridad del archivo de datos
Hash SHA-256 de `precipitacion_2026-06-22.csv`: `9a8dc75af1969e21ad7e13bddd9fad0291ebbeba2a0b1418cd4237f81a5155be` — coincide exacto con el declarado en el README.

## Contadores del cluster (verificados con mi propia ejecucion)
| Contador | Reportado (Juan Pablo) | Reproducido (Lina) |
|---|---|---|
| Reduce shuffle bytes, sin combinador | 2.398.815 | 2.398.815 |
| Reduce shuffle bytes, con combinador | 5.080 | 5.080 |
| Combine output records | 198 | 198 |

## Resultado de la agregacion
La salida del cluster (`hdfs dfs -cat /salida_sin_combinador/part-00000`) coincide exacto, campo por campo, contra la verdad de referencia calculada en Python puro sobre el mismo archivo (`diff` sin diferencias).

**Conclusion: verificado, reproduce igual.**
