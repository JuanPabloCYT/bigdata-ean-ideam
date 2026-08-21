# T6 · Verificación independiente (Lina Ramírez)

Reproduje el flujo completo en un clon limpio aparte (`git clone` desde `origin/main`, directorio nuevo, Docker y entorno virtual creados desde cero), en Windows con Python 3.12. No modifiqué ningún archivo hasta terminar la comprobación.

Nota sobre el archivo anterior: hubo un commit (`577385b`) que agregó `docs/T6_verificacion_camilo.md` con el nombre de Camilo, pero firmado por la cuenta de Juan Pablo (`Juanext81`), sin evidencia de ejecución real; se retiró después (`f1cb8cb`). Esta es una verificación distinta: ejecutada y firmada por mi propia cuenta, con la salida real de cada comando.

## 1. T5 primero, como exige `convertir_parquet.py`

```bash
python src/ingesta/cargar_cruda.py --date 2026-06-22
```

```
SHA256 · 9a8dc75af1969e21ad7e13bddd9fad0291ebbeba2a0b1418cd4237f81a5155be
```

Mismo hash que T1 y que mi propia verificación de T5.

## 2. Conversión a Parquet

```bash
python src/refinar/convertir_parquet.py --date 2026-06-22
```

```
CARGADO · s3://lago-refinado/refinada/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.parquet
Codec: zstd
Tamaño Parquet: 312,373 bytes
Tamaño CSV original: 21,953,076 bytes
Filas: 141007
```

Coincide byte a byte con lo documentado en `T6_formato.md` sección 1 (312.373 bytes, mismas 141.007 filas).

**Idempotencia**, segunda ejecución con el mismo dato:

```
YA EXISTE · contenido identico · no se sobrescribe
```

**La cruda sigue intacta después de convertir** (leída de vuelta desde `lago-crudo` tras la conversión):

```
CRUDA SHA256 tras conversion T6: 9a8dc75af1969e21ad7e13bddd9fad0291ebbeba2a0b1418cd4237f81a5155be
CRUDA tamano: 21953076
```

Mismo hash y tamaño de antes de correr T6: `convertir_parquet.py` lee la cruda pero nunca la reescribe.

## 3. Medición de los tres codecs

```bash
python src/refinar/medir_codecs.py --date 2026-06-22
```

| Formato | Tamaño (bytes) | Reproducido aquí | Documentado en `T6_formato.md` |
|---|---:|---:|---:|
| CSV | 21.953.076 | igual | igual |
| snappy | 381.716 | igual | igual |
| gzip | 284.431 | igual | igual |
| zstd | 312.373 | igual | igual |

Los **tamaños** son deterministas y coinciden exactos. Los **tiempos** de escritura/lectura varían con la máquina (aquí algo más altos que los documentados, p. ej. zstd escritura 0,1358 s vs 0,0198 s documentado); es la variación esperada de hardware, no una discrepancia del método — ambas corridas usan la mediana de 3 repeticiones sobre la misma muestra, como exige la guía.

## 4. Contraste DuckDB, Parquet(zstd) vs CSV

Reproduje la consulta de la sección 3 de `T6_formato.md` (promedio de `valorobservado` agrupado por `departamento`, con DuckDB, mediana de 3 repeticiones):

```
Parquet(zstd): 0.0098 s | 33 departamentos
CSV:           0.3329 s | 33 departamentos
Speedup: 33.9x
Diferencia maxima absoluta entre promedios: 5.551115123125783e-17
```

- Mismos 33 departamentos en ambos casos.
- La diferencia máxima entre promedios es **exactamente** `5.55 × 10⁻¹⁷`, igual a la que reporta `T6_formato.md` — confirma que es precisión de `double` por orden de suma distinto (columnar vs por filas), no un error de datos.
- El *speedup* absoluto difiere (33,9× aquí contra 93,5× documentado): es la máquina, no el método. Ambas corridas muestran a Parquet leyendo solo 2 de 12 columnas y siendo un orden de magnitud más rápido que el CSV, que es lo que la sección 3 afirma.

## Conclusión

Sin hallazgos nuevos ni correcciones de código. El diseño de `convertir_parquet.py` y `medir_codecs.py` reproduce exacto en un clon limpio de Windows: mismos tamaños de archivo para los tres codecs, misma elección de `zstd` sostenida por la misma medición, cruda verificablemente intacta después de la conversión, e idempotencia confirmada. La única variación observada (tiempos absolutos y el factor de *speedup* de DuckDB) es la esperada entre máquinas distintas y no afecta ninguna conclusión del documento de formato.
