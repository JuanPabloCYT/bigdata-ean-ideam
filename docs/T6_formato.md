# T6 · El dato en Parquet, con el codec que la medición justifica

**IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean**
Equipo: `bigdata-ean-ideam` · Integrantes: Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Fuente: Precipitación del IDEAM (`s54a-sgyg`), leída **desde la capa cruda del lago** (T5), no desde un archivo aparte.

> **La regla que no se negocia:** el CSV original permanece intacto en `lago-crudo`. `src/refinar/convertir_parquet.py` solo lee de ahí; nunca escribe de vuelta. Verificado en la sección 6.

---

## 1. La conversión

**Script:** [`src/refinar/convertir_parquet.py`](../src/refinar/convertir_parquet.py)

Lee el CSV de `lago-crudo`, lo convierte a Parquet con el codec elegido (justificado en la sección 4) y lo escribe en `lago-refinado`, bajo la misma convención de partición por fecha que ya documentó T5:

```text
refinada/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.parquet
```

Es idempotente por el mismo criterio que la ingesta de T5: si el objeto ya existe con el mismo contenido, no lo reemplaza; si existe con contenido distinto, falla en vez de sobrescribir en silencio.

```bash
python3 src/refinar/convertir_parquet.py --date 2026-06-22
```

```text
CARGADO · s3://lago-refinado/refinada/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.parquet
Codec: zstd
Tamaño Parquet: 312,373 bytes
Tamaño CSV original: 21,953,076 bytes
Filas: 141007
```

---

## 2. Tabla comparativa de codecs

**Script:** [`src/refinar/medir_codecs.py`](../src/refinar/medir_codecs.py) — mide sobre la **misma muestra** para los tres codecs (los 141.007 registros de la partición del 22/06/2026), y cada tiempo es la **mediana de 3 repeticiones**, no una sola medición, para no dejar que la primera lectura sin caché infle el número.

```bash
python3 src/refinar/medir_codecs.py --date 2026-06-22
```

| Formato | Tamaño (bytes) | Escritura (s) | Lectura selectiva (s) | Reducción vs CSV |
|---|---:|---:|---:|---:|
| CSV | 21.953.076 | — | — | — |
| **snappy** | 381.716 | 0,0218 | 0,0030 | 98,3 % |
| **gzip** | 284.431 | 0,0323 | 0,0016 | 98,7 % |
| **zstd** | 312.373 | 0,0198 | 0,0016 | 98,6 % |

La lectura selectiva mide las mismas dos columnas que ya usa el proyecto en la agregación de T4: `departamento` y `valorobservado` — un patrón de consulta real, no arbitrario. Evidencia completa, sin editar, en [`practica/s06-parquet/resultados/tabla_comparativa.txt`](../practica/s06-parquet/resultados/tabla_comparativa.txt).

**Lectura de la tabla:** `gzip` da el archivo más pequeño, pero es el más lento de escribir (49 % más que `zstd`). `zstd` casi iguala a `gzip` en tamaño (apenas 9,8 % más grande) y es el más rápido en escritura de los tres, con la misma velocidad de lectura selectiva que `gzip`. `snappy` es el más grande de los tres (22 % más que `zstd`) sin ser notablemente más rápido de escribir que `zstd` en esta muestra.

---

## 3. Contraste: consulta selectiva sobre Parquet contra CSV

**Nivel Extensión.** Se ejecutó la misma consulta —promedio de `valorobservado` agrupado por `departamento`, la agregación de T4— sobre el Parquet en `zstd` y sobre el CSV crudo, con DuckDB, mediana de 3 repeticiones cada una. Evidencia completa en [`practica/s06-parquet/resultados/consulta_duckdb.txt`](../practica/s06-parquet/resultados/consulta_duckdb.txt).

| | Parquet (zstd) | CSV |
|---|---:|---:|
| Tiempo de la consulta (mediana de 3) | **0,0015 s** | 0,1429 s |
| Resultado | 33 departamentos | 33 departamentos |

**Parquet fue 93,5× más rápido** en esta consulta.

**Verificación de que el resultado es el mismo, no solo parecido.** Una primera comparación con `==` exacto entre los 33 promedios reportó una diferencia. Se investigó antes de descartarla: la diferencia máxima absoluta entre cualquier par de promedios fue **5,55 × 10⁻¹⁷** — el margen de precisión de un `double` (≈ 1 × 10⁻¹⁶), no una diferencia de datos. Ocurre porque el motor suma los valores en un orden distinto al escanear por columnas (Parquet) que al escanear por filas (CSV), y sumar `float` en órdenes distintos no da bit a bit el mismo resultado. Los 33 departamentos y sus promedios son, dentro de esa precisión, idénticos.

**Por qué Parquet fue más rápido, en términos de lectura por columnas:** la fuente tiene 12 columnas; la consulta solo necesita 2. DuckDB, sobre Parquet, lee únicamente `departamento` y `valorobservado` del archivo — el resto de columnas ni se tocan. Sobre el CSV, el motor tiene que decodificar cada línea completa (las 12 columnas de cada uno de los 141.007 registros) para poder descartar las 10 que no pidió la consulta, porque el formato por filas no permite saltarse columnas sin leer el registro entero.

---

## 4. Justificación del codec

**Codec elegido: `zstd`.**

**Contra la medición propia (sección 2).** `zstd` no es el que más comprime (`gzip` lo supera por 9,8 %) ni el más rápido de escribir por mucho margen sobre `snappy`, pero es el único que está entre los dos mejores en las tres columnas de la tabla a la vez: tamaño casi igual al mejor, escritura más rápida que los otros dos, lectura empatada con el mejor. `gzip` gana en tamaño pero paga un 49 % más de tiempo de escritura por una ganancia de apenas 27.942 bytes (9,8 %) — un mal cambio dado el patrón de acceso de este proyecto (ver abajo). `snappy` no gana en ninguna columna frente a `zstd`.

**Contra el patrón de acceso real del proyecto.** La partición cruda se escribe **una sola vez** por día, de forma inmutable (T5): la ingesta nunca reescribe una partición existente. Ese dato después se consulta muchas veces — cada trabajo de MapReduce (T4), cada refinamiento futuro (S16), cada consulta analítica. Es exactamente el patrón que la guía identifica como el que inclina hacia más compresión, aunque escribir cueste: *"¿el dato se escribe una vez y se consulta mucho?"* La respuesta aquí es sí, y `zstd` da la mayor compresión disponible sin pagar el peor tiempo de escritura por ella.

**Una precisión honesta, para no sobrevalorar la diferencia entre codecs.** A esta escala (141.007 filas, ~22 MB de CSV), las diferencias absolutas entre los tres codecs son de milisegundos y de unos pocos cientos de kilobytes — insignificantes frente a la reducción que ya logra el formato columnar por sí solo (98 %+ contra el CSV, para los tres codecs por igual). La elección de codec aquí es un afinamiento fino sobre una decisión que ya está tomada por cambiar de CSV a Parquet, no la decisión principal. Con una fuente varios órdenes de magnitud más grande, la diferencia entre `zstd` y `gzip` en tiempo de escritura sí sería una decisión de peso; a este volumen, es una preferencia razonada, no una necesidad urgente.

---

## 5. Nivel Frontera · análisis de costo y beneficio

Ver el documento dedicado para gerencia: [`T6_reto_negocio.md`](T6_reto_negocio.md).

---

## 6. Reproducibilidad

Comandos exactos, contraste de fallos y verificación de que la cruda queda intacta: [`T6_ejecucion.md`](T6_ejecucion.md).

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para escribir los scripts de conversión y medición, ejecutar el flujo completo y redactar este documento.

Cada cifra fue verificada contra ejecución real, no descrita: la tabla comparativa y la comparación DuckDB salen de las evidencias guardadas sin editar en `practica/s06-parquet/resultados/`; la discrepancia numérica entre Parquet y CSV se investigó hasta confirmar que era precisión de punto flotante y no un error de datos, en vez de descartarse o esconderse; y la integridad de la capa cruda se comprobó después de la conversión, no se asumió.
