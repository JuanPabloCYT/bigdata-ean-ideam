# T6 · Formato y compresión de la capa refinada

**IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean**
Equipo: `bigdata-ean-ideam` · Integrantes: Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Fuente del proyecto: Precipitación del IDEAM (`s54a-sgyg`), leída **desde la capa cruda del lago** (T5), no desde un archivo aparte.

---

## 1. La conversión

**De dónde a dónde**

De `cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv` en CSV, a `refinada/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.parquet` en Parquet, con el codec `zstd`.

**Confirmación de la regla de la cruda**

El CSV original permanece intacto en `lago-crudo`: 21.953.076 bytes, sin ninguna versión nueva, verificado después de la conversión. El script (`src/refinar/convertir_parquet.py`) solo lee de la cruda; nunca escribe de vuelta. El Parquet se escribió únicamente en `lago-refinado`.

---

## 2. Tabla comparativa de los tres codecs

Medida sobre la misma muestra (los 141.007 registros de la partición del 22/06/2026) para los tres codecs, con la mediana de 3 repeticiones para cada tiempo.

| Formato | Tamaño | Tiempo de escritura | Tiempo de lectura selectiva |
|---|---:|---:|---:|
| CSV original | 20,94 MB (21.953.076 B) | no aplica | 0,1429 s (consulta completa, sección 3) |
| Parquet snappy | 0,36 MB (381.716 B) | 0,0218 s | 0,0030 s |
| Parquet gzip | 0,27 MB (284.431 B) | 0,0323 s | 0,0016 s |
| **Parquet zstd** | 0,30 MB (312.373 B) | 0,0198 s | 0,0016 s |

**Reducción de tamaño frente al CSV, del codec elegido (zstd)**
98,6 %

---

## 3. La consulta selectiva · nivel Extensión

**La consulta usada**

La misma agregación de T4: precipitación promedio por departamento, sobre las dos columnas que ya usa el proyecto (`departamento`, `valorobservado`).

```sql
SELECT departamento, avg(valorobservado) AS promedio
FROM 'refinada/.../precipitacion_2026-06-22.parquet'   -- o read_csv_auto('cruda/....csv')
WHERE valorobservado IS NOT NULL
GROUP BY departamento
```

| Fuente | Tiempo de la consulta |
|---|---:|
| Sobre CSV | 0,1429 s |
| Sobre Parquet | 0,0015 s |

**Interpretación**

Parquet fue **93,5 veces más rápido**. La fuente tiene 12 columnas; la consulta solo necesita 2. DuckDB, sobre Parquet, lee únicamente `departamento` y `valorobservado` del archivo — el resto ni se toca. Sobre el CSV, el motor tiene que decodificar cada línea completa (las 12 columnas de las 141.007 filas) para poder descartar después las 10 que la consulta no pidió, porque un formato por filas no permite saltarse columnas sin leer el registro entero.

**Verificación de que el resultado es el mismo, no solo parecido.** Una comparación inicial con igualdad exacta entre los 33 promedios reportó una diferencia. Se investigó antes de descartarla: la diferencia máxima absoluta fue 5,55 × 10⁻¹⁷ — el margen de precisión de un `double` (≈ 1 × 10⁻¹⁶), no una diferencia de datos. Ocurre porque el motor suma los valores en un orden distinto al escanear por columnas que al escanear por filas, y sumar `float` en órdenes distintos no da bit a bit el mismo resultado. Los 33 departamentos y sus promedios son, dentro de esa precisión, idénticos.

---

## 4. El codec elegido y su justificación

**Codec elegido**
`zstd`

**Patrón de acceso del dato**

La partición cruda se escribe **una sola vez** por día, de forma inmutable (T5): la ingesta nunca reescribe una partición existente. Ese dato después se consulta muchas veces — cada trabajo de MapReduce (T4), cada refinamiento futuro (S16), cada consulta analítica. Las consultas típicas leen pocas columnas de las 12 disponibles.

**Por qué este codec, según la tabla y el patrón**

`zstd` no gana en ninguna columna de la tabla por sí sola —`gzip` comprime más y `snappy` no gana en nada frente a `zstd`— pero es el único que está entre los dos mejores en las tres columnas a la vez: tamaño casi igual al mejor (apenas 9,8 % más grande que `gzip`), el más rápido de escribir de los tres, y la misma lectura selectiva que `gzip`. `gzip` paga un 49 % más de tiempo de escritura por esa ganancia marginal de tamaño — un mal cambio dado que el dato se escribe una vez y se consulta mucho, el patrón que la guía identifica como favorable a más compresión *siempre que no cueste demasiado escribir*. Con `zstd` no hay que elegir entre las dos cosas.

**Nota honesta:** a esta escala (141.007 filas, ~22 MB de CSV), las diferencias absolutas entre los tres codecs son de milisegundos y de unos pocos cientos de kilobytes, insignificantes frente a la reducción que ya logra el formato columnar por sí solo (98 %+ para los tres codecs por igual). La elección de codec es un afinamiento fino sobre una decisión que ya está tomada al cambiar de CSV a Parquet, no la decisión principal.

---

## 5. Análisis de costo y beneficio · nivel Frontera

Dirigido a la gerencia, en términos que entienda.

| Dimensión | Resultado |
|---|---|
| Ahorro de espacio | De 20,94 MB (CSV) a 0,30 MB (Parquet zstd): 98,6 % menos, por partición diaria. Proyectado sobre el volumen anual que T3 ya estimó (~7,5 GB sin comprimir), el año completo en Parquet ocuparía apenas unos 100 MB |
| Efecto en la velocidad | La consulta de referencia (promedio de lluvia por departamento) pasa de 0,1429 s sobre CSV a 0,0015 s sobre Parquet: 93,5 veces más rápida |
| Costo técnico | A este volumen, insignificante: escribir con `zstd` tarda 0,0198 s, incluso más rápido que la opción menos comprimida (`snappy`, 0,0218 s). No hay que sacrificar tiempo de cómputo por el ahorro de espacio |
| Recomendación | Convertir a Parquet con `zstd` en la capa refinada, dejando el CSV original intacto en la cruda: se ahorra espacio y se acelera la consulta a la vez, sin costo de cómputo adicional que se note a esta escala |

Versión de una página para gerencia, con el mismo argumento en lenguaje no técnico: [`T6_reto_negocio.md`](T6_reto_negocio.md).

---

## 6. Reproducibilidad

**Comandos exactos para reproducir la conversión y las cifras**

```bash
# 1. Preparar
git clone https://github.com/JuanPabloCYT/bigdata-ean-ideam.git
cd bigdata-ean-ideam
cp .env.example .env
python3 --version   # debe reportar 3.10 o superior

# 2. Levantar el lago e instalar dependencias
docker compose up -d minio
python3 -m pip install -r requirements.txt

# 3. Poblar la capa cruda si aún no lo está (T5)
python3 src/ingesta/cargar_cruda.py --date 2026-06-22

# 4. Medir los tres codecs (produce la tabla de la sección 2)
python3 src/refinar/medir_codecs.py --date 2026-06-22

# 5. Convertir y poblar la capa refinada con el codec elegido
python3 src/refinar/convertir_parquet.py --date 2026-06-22
```

Comandos completos de la comparación DuckDB de la sección 3, más el detalle de la verificación desde un clon limpio (con las mismas cifras reproducidas exactas) y un fallo de infraestructura real encontrado y corregido, en [`T6_ejecucion.md`](T6_ejecucion.md).

**Declaración**

Confirmamos que otra persona, con un clon limpio del repositorio y estos comandos, reproduce la conversión y obtiene las mismas cifras de la tabla comparativa. Se verificó dos veces: (1) en este equipo, con `docker compose down -v` y una reconstrucción completa desde cero, obteniendo los mismos tamaños exactos de Parquet (byte a byte) y el mismo orden de magnitud de mejora en velocidad; (2) el resultado de la agregación se contrastó contra una verdad de referencia calculada en Python puro sobre el mismo archivo, coincidiendo dentro de la precisión de punto flotante.

---

## Referencias

Kleppmann, M. (2017). *Designing data-intensive applications*. O'Reilly Media.

Reis, J., y Housley, M. (2022). *Fundamentals of data engineering*. O'Reilly Media.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para escribir los scripts de conversión y medición, ejecutar el flujo completo y redactar este documento.

Cada cifra fue verificada contra ejecución real, no descrita: la tabla comparativa y la comparación DuckDB salen de las evidencias guardadas sin editar en `practica/s06-parquet/resultados/`; la discrepancia numérica entre Parquet y CSV se investigó hasta confirmar que era precisión de punto flotante y no un error de datos, en vez de descartarse o esconderse; y la integridad de la capa cruda se comprobó después de la conversión, no se asumió.
