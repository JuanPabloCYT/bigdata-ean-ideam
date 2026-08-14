# T4 · Una agregación del proyecto en clave map y reduce

**IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean**
Módulo 1 · Sesión 4 · Entrega grupal

**Fuente:** Precipitación del IDEAM (`s54a-sgyg`), la fuente consolidada del equipo en T3.
**Agregación elegida:** precipitación promedio (`valorobservado`) por **departamento**.
**Archivo de entrada:** `precipitacion_2026-06-22.csv` — 141.007 registros, 33 departamentos distintos.

Es la misma estructura del ejemplo del acueducto de la guía (presión promedio por sector), aplicada a la fuente real del equipo: una columna categórica (`departamento`) como clave y una numérica (`valorobservado`) como valor.

---

## Paso 1 · Reescribir la agregación

El código vive en `src/mapreduce/`:

| Archivo | Rol |
|---|---|
| `mapper.py` | Emite `departamento \t valor,1` por cada lectura válida |
| `reducer.py` | Acumula suma y conteo por departamento y promedia solo al cerrar cada grupo |
| `combiner.py` | Reducción parcial local, antes de la mezcla — emite `suma,conteo`, nunca un promedio |

**Diseño clave:** el mapper siempre emite un par `(valor, 1)`, nunca el valor solo. Así el combinador y el reductor final reciben exactamente el mismo formato —dos números separados por coma— sin importar si el combinador corrió cero, una o varias veces. Es el mismo par `(suma_parcial, conteo_parcial)` en todos los casos; solo el reductor final divide, y solo una vez.

```python
# mapper.py, la línea que decide todo
print("{}\t{},1".format(departamento, valor))
```

```python
# combiner.py: agrega, pero NUNCA promedia
print("{}\t{:.6f},{}".format(actual, suma, conteo))
```

```python
# reducer.py: promedia solo al cerrar el grupo, una vez
print("{}\t{:.4f}\t{}".format(actual, suma / conteo, conteo))
```

**Verificación de corrección antes de tocar el clúster.** Se ejecutó la lógica en local (`mapper | sort | reducer`, y `mapper | sort | combiner | sort | reducer`) y se comparó contra una agregación de referencia calculada con `csv.DictReader` y `collections.defaultdict` en Python puro, sin pasar por MapReduce. **Los tres métodos coinciden exactamente en las 33 filas**, y la suma de los conteos por departamento es 141.007 — se contabiliza cada registro exactamente una vez. La comparación está documentada en `docs/T4_ejecucion.md`.

---

## Paso 2 · Estimar el volumen de mezcla

La estimación se calcula con `src/mapreduce/estimacion_mezcla.py`, que mide el esquema real del archivo (no cifras escritas a mano) y aplica las dos referencias de la tarea.

```
python3 src/mapreduce/estimacion_mezcla.py data/raw/precipitacion_2026-06-22.csv 6
```

| Insumo medido | Valor |
|---|---:|
| Registros totales | 141.007 |
| Departamentos distintos | 33 |
| Bytes promedio de la clave (`departamento`) | 8,011 |
| Bytes promedio del valor (`valor,1`) | 3,038 |

**Sin combinador** — un par por registro:

```
pares = 141.007
bytes de mezcla (teórico) ≈ 141.007 × 13,05 ≈ 1.839.937 bytes
```

**Con combinador** — cota superior: un par por clave distinta y por tarea de mapeo. Con 6 tareas de mapeo (ver Paso 3, sección de infraestructura) y 33 departamentos:

```
pares, cota superior = 6 × 33 = 198
bytes de mezcla (teórico), cota superior ≈ 198 × 22,01 ≈ 4.358 bytes
```

**Reducción teórica esperada: ≈ 99,8 %.**

---

## Paso 3 · Contrastar con la realidad

### Infraestructura

Se extendió el clúster HDFS de la sesión 3 con el gestor de recursos (`resourcemanager`, `nodemanager`), en `practica/s04-mapreduce/`. El detalle completo de la infraestructura, incluidos tres fallos reales que costaron tiempo resolver, está en [`docs/T4_ejecucion.md`](T4_ejecucion.md).

Por la memoria limitada de este equipo (VM de Docker con 3,83 GB, la misma restricción de S03), el clúster de T4 usa **un nodo de datos y un nodo de cómputo**, no tres. Para que el trabajo tuviera más de una tarea de mapeo real —y así poder medir el efecto del combinador entre varias tareas, no solo dentro de una— se forzaron **6 tareas de mapeo** con `-D mapred.map.tasks=6 -D mapred.min.split.size=1`.

### Ejecución sin combinador

```bash
hadoop jar hadoop-streaming-3.2.1.jar \
  -D mapred.map.tasks=6 -D mapred.min.split.size=1 \
  -files mapper.py,reducer.py -mapper mapper.py -reducer reducer.py \
  -input /entrada/precipitacion_2026-06-22.csv -output /salida_sin_combinador
```

| Contador (real, del trabajo) | Valor |
|---|---:|
| Launched map tasks | 6 |
| Map output records | 141.007 |
| Combine input/output records | 0 (no hay combinador) |
| Reduce input groups | 33 |
| **Reduce shuffle bytes** | **2.398.815** |

### Ejecución con combinador

```bash
hadoop jar hadoop-streaming-3.2.1.jar \
  -D mapred.map.tasks=6 -D mapred.min.split.size=1 \
  -files mapper.py,combiner.py,reducer.py \
  -mapper mapper.py -combiner combiner.py -reducer reducer.py \
  -input /entrada/precipitacion_2026-06-22.csv -output /salida_con_combinador
```

| Contador (real, del trabajo) | Valor |
|---|---:|
| Launched map tasks | 6 |
| Map output records | 141.007 |
| Combine input records | 141.007 |
| **Combine output records** | **198** |
| Reduce input groups | 33 |
| **Reduce shuffle bytes** | **5.080** |

**El `Combine output records` real (198) coincide exactamente con la cota superior teórica (6 tareas × 33 claves = 198).** Eso confirma que, con este archivo, cada una de las 6 tareas de mapeo efectivamente vio las 33 claves — no hubo tareas con un subconjunto parcial de departamentos.

### El contraste

| | Sin combinador | Con combinador | Reducción |
|---|---:|---:|---:|
| Bytes de mezcla, **estimación teórica** | ≈ 1.839.937 | ≈ 4.358 (cota superior) | ≈ 99,8 % |
| Bytes de mezcla, **contador real** | **2.398.815** | **5.080** | **99,788 %** |
| Razón real / teórico | 1,30× | 1,16× | — |

La estimación acertó el **orden de magnitud** en ambos casos —millones de bytes sin combinador, miles con combinador—, que es lo que la tarea pide razonar. El contador real es consistentemente **entre 1,2 y 1,3 veces mayor** que la estimación de bytes de texto crudo. La diferencia no es un error de cálculo: el contador de Hadoop mide el tamaño **serializado** de los pares en el formato interno de volcado a disco (`SequenceFile`, con longitudes de campo prefijadas y separadores propios del framework), no el tamaño del texto `clave\tvalor\n` sin más. Esa sobrecarga de serialización es real y consistente entre ambas corridas (30 % sin combinador, 16 % con combinador), y es precisamente el tipo de diferencia que esta tarea pide encontrar al contrastar la estimación con la medición.

**Resultado verificado.** La salida de ambos trabajos (`hdfs dfs -cat .../part-00000`) coincide, campo por campo, con la agregación de referencia calculada en Python puro sobre el mismo archivo. El combinador no alteró el resultado.

---

## Paso 4 · Justificar la clave, y el sesgo

### Por qué `departamento`

Responde directamente la pregunta que un analista del acueducto —o, en este caso, del equipo del proyecto— haría primero: *¿cómo se distribuye la precipitación por región del país?* Es la misma pregunta que el ejemplo de la guía (presión por sector), trasladada a la fuente real. `departamento` es además la columna categórica de menor cardinalidad entre las disponibles (33 valores, frente a 524 estaciones o cientos de municipios), lo que minimiza la mezcla: pocas claves distintas significa pocos grupos que reunir, sin importar cuántos registros tenga cada uno.

### El sesgo, medido, no supuesto

`src/mapreduce/analisis_sesgo.py` mide la distribución real:

```bash
python3 src/mapreduce/analisis_sesgo.py data/raw/precipitacion_2026-06-22.csv
```

| Departamento | Registros | % del total |
|---|---:|---:|
| **BOGOTÁ** | **67.669** | **47,99 %** |
| Antioquia | 9.230 | 6,55 % |
| Boyacá | 7.146 | 5,07 % |
| Cundinamarca | 6.343 | 4,50 % |
| Santander | 4.785 | 3,39 % |

**Hay sesgo real y severo.** El reductor que recibe la clave `BOGOTÁ` procesa casi la mitad de los 141.007 registros — más que las 32 claves restantes juntas casi en su totalidad. Añadir más reductores no acelera nada: esos 67.669 registros comparten una sola clave y van, sí o sí, al mismo reductor. El trabajo completo tarda lo que tarda ese reductor, no el promedio de los 33.

### Rediseño propuesto: `departamento + codigoestacion`

Dentro de `BOGOTÁ` hay **67 estaciones distintas**, con un promedio de 1.010 registros cada una (la más cargada tiene 1.402, apenas el 0,99 % del total). Una clave compuesta `departamento_codigoestacion` reparte esos 67.669 registros en 67 claves en vez de una:

```bash
$ python3 src/mapreduce/analisis_sesgo.py data/raw/precipitacion_2026-06-22.csv
...
Con la clave compuesta, el 47.99 % que hoy va a un solo reductor
se reparte en 67 claves distintas.
```

### El compromiso que introduce

El rediseño no es gratis, y hay que decirlo con la misma honestidad con que se mide el sesgo:

1. **Cambia la granularidad del resultado.** La salida deja de ser "promedio por departamento" y pasa a ser "promedio por estación". Para recuperar el promedio departamental hace falta una **segunda pasada de agregación** (un segundo trabajo map-reduce, o una agregación final fuera del clúster) que vuelva a agrupar las 524 salidas por estación en 33 salidas por departamento. Se paga con una etapa adicional lo que se gana en paralelismo.
2. **Multiplica el número de claves distintas en la mezcla:** de 33 a 524 en todo el archivo (67 solo dentro de Bogotá). Eso aumenta la cantidad de grupos que la mezcla debe reunir, aunque cada grupo individual sea mucho más pequeño. Para este archivo (141.007 registros) el costo es insignificante; en una fuente con millones de estaciones podría no serlo.
3. **No corrige el sesgo entre departamentos, solo dentro de uno.** Bogotá seguirá siendo, en conjunto, el mayor contribuyente de dato; lo que cambia es que ya no lo procesa un solo reductor, sino hasta 67 en paralelo.

**Conclusión:** para la pregunta actual del proyecto ("promedio por departamento"), `departamento` sigue siendo la clave correcta — es la que responde la pregunta con la mezcla mínima. El rediseño a clave compuesta se reserva para el momento en que el sesgo de Bogotá se vuelva el cuello de botella real del pipeline (con la fuente completa, no la muestra de un día), que es exactamente donde la sesión 24 retoma este análisis.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para escribir el mapper, el reductor, el combinador, los scripts de estimación y de análisis de sesgo, extender el clúster con YARN, y redactar este documento.

Cada cifra fue verificada contra ejecución real, no descrita:

- El resultado de los tres modos de ejecución (mapper+reductor, mapper+combinador+reductor, y el trabajo real en el clúster) se contrastó contra una agregación de referencia en Python puro sobre el mismo archivo, y coincide exactamente en las 33 filas.
- Los contadores `Reduce shuffle bytes`, `Combine input/output records` y `Launched map tasks` son los que reportó el propio trabajo de Hadoop Streaming, guardados sin editar en `practica/s04-mapreduce/resultados/`.
- La cifra de sesgo (47,99 % en Bogotá) y la del rediseño (67 estaciones) salen de recorrer el archivo real, no de una estimación.
- Se encontraron y corrigieron tres fallos reales de infraestructura durante la ejecución (documentados en `docs/T4_ejecucion.md`), incluida una incompatibilidad de Python 3.5 que habría hecho fallar el trabajo en silencio si no se hubiera revisado el `stderr` de la tarea.
