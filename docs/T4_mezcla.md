# T4 · Estimación y contraste de la mezcla

**IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean**
Equipo: `bigdata-ean-ideam` · Integrantes: Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Fuente del proyecto: Precipitación del IDEAM, conjunto Socrata `s54a-sgyg`, la fuente consolidada del equipo en T3

---

## 1. La pregunta de negocio y la clave

**Pregunta que responde la agregación**
¿Cuál es la precipitación promedio (`valorobservado`) por departamento? Misma estructura que el ejemplo de la guía (presión promedio por sector), aplicada a la fuente real del equipo.

**Clave de agrupación elegida**
`departamento`

**Valor que se agrega y operación**
`valorobservado` (la lectura de precipitación, en mm), operación **promedio**.

**Por qué esta clave responde la pregunta**
`departamento` es, además, la columna categórica de menor cardinalidad entre las disponibles en la fuente (33 valores, frente a 524 estaciones o cientos de municipios), lo que minimiza la mezcla: pocas claves distintas significan pocos grupos que reunir, sin importar cuántos registros tenga cada uno.

---

## 2. Estimación teórica del volumen de la mezcla

Calculada con `src/mapreduce/estimacion_mezcla.py`, que mide el esquema real del archivo (no cifras escritas a mano):

```bash
python3 src/mapreduce/estimacion_mezcla.py data/raw/precipitacion_2026-06-22.csv 6
```

| Magnitud | Valor estimado | Cómo lo estimaron |
|---|---|---|
| Registros de entrada | 141.007 | Conteo exacto del archivo (`csv.DictReader`) |
| Claves distintas | 33 | Departamentos distintos, contados sobre el archivo real |
| Nodos de datos | 1 nodo de cómputo, **6 tareas de mapeo** | El clúster de T4 tiene un solo `nodemanager` (limitación de memoria, ver sección 7); se forzaron 6 tareas de mapeo con `-D mapred.map.tasks=6` para que hubiera más de una, y así poder medir el efecto del combinador entre varias tareas |
| Tamaño medio de un par clave y valor | 13,05 bytes (sin combinador) | Promedio real: 8,011 bytes de clave + 1 tab + 3,038 bytes de `valor,1` + 1 salto de línea |

**Pares que cruzan la mezcla SIN combinador**
141.007 — un par por cada registro de entrada, porque el mapper emite `departamento \t valor,1` por cada lectura sin agregar nada localmente.

**Pares que cruzan la mezcla CON combinador**
Cota superior: 6 (tareas de mapeo) × 33 (claves distintas) = **198** — como máximo, un par por clave distinta y por tarea de mapeo, porque el combinador agrega localmente dentro de cada tarea antes de enviar.

**Bytes estimados sin combinador**
141.007 × 13,05 ≈ **1.839.937 bytes**

**Bytes estimados con combinador**
198 × 22,01 (tamaño del par agregado `departamento \t suma,conteo`) ≈ **4.358 bytes**

---

## 3. Medición real con los contadores

Ejecutado en el clúster HDFS + YARN de `practica/s04-mapreduce/` (comandos exactos en la sección 7).

| Corrida | Reduce shuffle bytes (real) | Registros de salida del map |
|---|---:|---:|
| Sin combinador | **2.398.815** | 141.007 |
| Con combinador | **5.080** | 141.007 |

(Los "registros de salida del map" son los mismos en ambas corridas porque el combinador corre *después* del map, no lo reemplaza. Lo que sí cambia es `Combine output records`: **198**, el valor real, que coincide exacto con la cota superior teórica de la sección 2.)

**Reducción porcentual observada al agregar el combinador**
(2.398.815 − 5.080) / 2.398.815 × 100 = **99,788 %**

---

## 4. Contraste entre lo estimado y lo medido

| Escenario | Estimado (bytes) | Real (bytes) | Comentario del desajuste |
|---|---:|---:|---|
| Sin combinador | 1.839.937 | 2.398.815 | Real es 1,30× el estimado |
| Con combinador | 4.358 | 5.080 | Real es 1,16× el estimado |

**Qué explica la diferencia entre la estimación y la medición**
El contador `Reduce shuffle bytes` de Hadoop mide el tamaño **serializado** de los pares en el formato interno de volcado a disco (con longitudes de campo prefijadas y separadores propios del framework), no el tamaño del texto plano `clave\tvalor\n`. Esa sobrecarga de serialización es real y consistente entre ambas corridas (30 % sin combinador, 16 % con combinador). La estimación sí acertó el **orden de magnitud** en los dos casos —millones de bytes sin combinador, miles con combinador—, que es lo que la tarea pide razonar; el desajuste es de escala fina, no de dirección.

---

## 5. Justificación de la clave

**Por qué esta clave minimiza la mezcla**
`departamento` tiene solo 33 valores distintos sobre 141.007 registros. Cualquier clave con más cardinalidad —`codigoestacion` (524 valores) o `municipio`— generaría más grupos en la mezcla, aunque cada grupo fuera más pequeño. Con combinador, el número de pares que cruzan la mezcla depende directamente del número de claves distintas (`tareas de mapeo × claves`), así que la clave de menor cardinalidad que aún responde la pregunta de negocio es la que minimiza el tráfico.

**Qué habría pasado con una clave alternativa**
Agrupar por `codigoestacion` en vez de por `departamento` multiplicaría las claves distintas de 33 a 524, y por tanto los pares de la mezcla con combinador de 198 a hasta 3.144 (6 × 524) — 16 veces más tráfico, para responder una pregunta más granular que la que pidió la gerencia. La clave se elige por la pregunta que hay que responder, no por la que dé el número más pequeño.

---

## 6. Análisis de sesgo · nivel Frontera

Medido con `src/mapreduce/analisis_sesgo.py`, sobre el archivo real, no supuesto:

```bash
python3 src/mapreduce/analisis_sesgo.py data/raw/precipitacion_2026-06-22.csv
```

**¿Alguna clave concentra la mayoría de los registros?**
**Sí.** `BOGOTÁ` concentra **67.669 registros (47,99 % del total)** — casi tanto como las otras 32 claves juntas. El reductor que recibe esa clave procesa casi la mitad del trabajo total; añadir más reductores no ayuda, porque esos 67.669 registros comparten una sola clave y van, sí o sí, al mismo reductor.

**Si hay sesgo, qué rediseño de clave lo repartiría mejor**
Clave compuesta `departamento + codigoestacion`. Dentro de `BOGOTÁ` hay **67 estaciones distintas**, con un promedio de 1.010 registros cada una (la más cargada, apenas el 0,99 % del total) — el 47,99 % que hoy va a un solo reductor se repartiría en 67 claves.

**El compromiso que introduce:** (1) cambia la granularidad del resultado, de "promedio por departamento" a "promedio por estación", y exige una segunda pasada de agregación para volver al nivel departamental; (2) multiplica las claves distintas en toda la mezcla, de 33 a 524, lo que a esta escala es insignificante pero podría no serlo con una fuente mucho mayor; (3) no corrige el sesgo *entre* departamentos, solo *dentro* de Bogotá.

---

## 7. Reproducibilidad

**Comandos exactos para reproducir estas cifras**

```bash
cd practica/s04-mapreduce
cp ../../data/raw/precipitacion_2026-06-22.csv muestra/
cp ../../src/mapreduce/*.py muestra/
docker compose up -d --build

docker compose exec -T namenode hdfs dfs -mkdir -p /entrada
docker compose exec -T namenode hdfs dfs -put -f /muestra/precipitacion_2026-06-22.csv /entrada/

# Sin combinador
docker compose exec -T namenode bash -c '
hadoop jar /opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar \
  -D mapred.map.tasks=6 -D mapred.min.split.size=1 \
  -files /muestra/mapper.py,/muestra/reducer.py \
  -mapper mapper.py -reducer reducer.py \
  -input /entrada/precipitacion_2026-06-22.csv -output /salida_sin_combinador'

# Con combinador
docker compose exec -T namenode bash -c '
hadoop jar /opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar \
  -D mapred.map.tasks=6 -D mapred.min.split.size=1 \
  -files /muestra/mapper.py,/muestra/combiner.py,/muestra/reducer.py \
  -mapper mapper.py -combiner combiner.py -reducer reducer.py \
  -input /entrada/precipitacion_2026-06-22.csv -output /salida_con_combinador'
```

Los contadores (incluido `Reduce shuffle bytes`) quedan en la consola de cada comando `hadoop jar`, al final de la ejecución. Los tres fallos reales de infraestructura que costó resolver para llegar a esta secuencia —y por qué el clúster tiene un solo nodo de cómputo— están documentados en [`T4_ejecucion.md`](T4_ejecucion.md).

**Declaración**
Confirmamos que otra persona, con un clon limpio del repositorio y estos comandos, obtiene el mismo resultado y las mismas cifras de mezcla. Se verificó dos veces: (1) desde este equipo, con `docker compose down -v`, reconstrucción de la imagen y reejecución completa, obteniendo cifras idénticas al byte; (2) de forma independiente por Lina Ramírez en un Codespace limpio, ajeno a este equipo, documentado en [`T4_verificacion_lina.md`](T4_verificacion_lina.md), con los mismos tres contadores clave reproducidos exactos.

---

## Referencias

Dean, J., y Ghemawat, S. (2008). MapReduce: Simplified data processing on large clusters. *Communications of the ACM, 51*(1), 107-113. https://doi.org/10.1145/1327452.1327492

White, T. (2015). *Hadoop: The definitive guide* (4.ª ed.). O'Reilly Media.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para escribir el mapper, el reductor, el combinador, los scripts de estimación y de análisis de sesgo, extender el clúster con YARN, y redactar este documento.

Cada cifra fue verificada contra ejecución real, no descrita: el resultado de los tres modos de ejecución se contrastó contra una agregación de referencia en Python puro sobre el mismo archivo y coincide exactamente en las 33 filas; los contadores son los que reportó el propio trabajo de Hadoop Streaming, guardados sin editar en `practica/s04-mapreduce/resultados/`; y la reproducibilidad se verificó dos veces, desde este equipo y de forma independiente por otro integrante del equipo.
