# T4 · Cómo reproducir la ejecución

Comandos exactos, en orden, para levantar el clúster de la sesión 4 y reproducir las cifras de [`T4_mezcla.md`](T4_mezcla.md) desde cero.

---

## 1. Requisitos

- Docker Desktop con al menos **3,5 GB** asignados a la VM. Este proyecto se probó con 3,83 GB.
- El repositorio clonado, con `data/raw/precipitacion_2026-06-22.csv` presente (ver el README de la raíz sobre cómo obtenerlo si falta).

## 2. Levantar el clúster

```bash
cd practica/s04-mapreduce
cp ../../data/raw/precipitacion_2026-06-22.csv muestra/
cp ../../src/mapreduce/*.py muestra/
docker compose up -d --build
```

El `--build` es necesario la primera vez: `nodemanager` se construye a partir de [`nodemanager.Dockerfile`](../practica/s04-mapreduce/nodemanager.Dockerfile), que instala Python sobre la imagen oficial (ver la sección 3, fallo 2).

Espere a que HDFS y YARN respondan:

```bash
# Debe reportar 1 nodo de datos vivo
docker compose exec -T namenode hdfs dfsadmin -report | grep "Live datanodes"

# Debe reportar activeNodes: 1
curl -s http://localhost:8088/ws/v1/cluster/metrics
```

Interfaces web: NameNode en `http://localhost:9871`, ResourceManager en `http://localhost:8088`.

## 3. Cargar la fuente a HDFS

```bash
docker compose exec -T namenode hdfs dfs -mkdir -p /entrada
docker compose exec -T namenode hdfs dfs -put -f /muestra/precipitacion_2026-06-22.csv /entrada/
```

## 4. Ejecutar sin combinador

```bash
docker compose exec -T namenode hdfs dfs -rm -r -f /salida_sin_combinador
docker compose exec -T namenode bash -c '
hadoop jar /opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar \
  -D mapreduce.job.name="T4_precipitacion_sin_combinador" \
  -D mapred.map.tasks=6 -D mapred.min.split.size=1 \
  -files /muestra/mapper.py,/muestra/reducer.py \
  -mapper mapper.py -reducer reducer.py \
  -input /entrada/precipitacion_2026-06-22.csv -output /salida_sin_combinador
'
```

## 5. Ejecutar con combinador

```bash
docker compose exec -T namenode hdfs dfs -rm -r -f /salida_con_combinador
docker compose exec -T namenode bash -c '
hadoop jar /opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar \
  -D mapreduce.job.name="T4_precipitacion_con_combinador" \
  -D mapred.map.tasks=6 -D mapred.min.split.size=1 \
  -files /muestra/mapper.py,/muestra/combiner.py,/muestra/reducer.py \
  -mapper mapper.py -combiner combiner.py -reducer reducer.py \
  -input /entrada/precipitacion_2026-06-22.csv -output /salida_con_combinador
'
```

## 6. Leer los contadores y el resultado

```bash
# Los contadores (incluido Reduce shuffle bytes) quedan en el log de la
# consola del propio comando `hadoop jar`, al final de la ejecución.

# El resultado de la agregación:
docker compose exec -T namenode hdfs dfs -cat /salida_sin_combinador/part-00000
```

## 7. Verificar contra la referencia

```bash
# Verdad de referencia, calculada en Python puro sobre el mismo archivo
python3 -c "
import csv
from collections import defaultdict
sumas, conteos = defaultdict(float), defaultdict(int)
with open('data/raw/precipitacion_2026-06-22.csv', encoding='utf-8-sig') as f:
    for fila in csv.DictReader(f):
        d = fila['departamento'].strip()
        try:
            v = float(fila['valorobservado'])
        except ValueError:
            continue
        sumas[d] += v; conteos[d] += 1
for d in sorted(sumas):
    print(f'{d}\t{sumas[d]/conteos[d]:.4f}\t{conteos[d]}')
" > /tmp/verdad_referencia.txt

docker compose exec -T namenode hdfs dfs -cat /salida_sin_combinador/part-00000 | sort > /tmp/salida_cluster.txt
diff /tmp/verdad_referencia.txt /tmp/salida_cluster.txt && echo "COINCIDE EXACTO"
```

## 8. Liberar memoria al terminar

```bash
docker compose down
```

---

## Tres fallos reales, y cómo se resolvieron

Documentados porque son exactamente el tipo de hallazgo de infraestructura que este proyecto viene registrando desde la sesión 3, y porque quien reproduzca esto en otro equipo puede toparse con los mismos.

### Fallo 1 · `Could not find or load main class MRAppMaster`

Al primer intento, el maestro de aplicación de YARN fallaba al arrancar con esa excepción, señalando que faltaba `HADOOP_MAPRED_HOME` en el entorno de las tareas. La corrección obvia — añadir las tres propiedades que el propio mensaje de error sugiere (`yarn.app.mapreduce.am.env`, `mapreduce.map.env`, `mapreduce.reduce.env`) a `hadoop.env` — no bastó a la primera.

La causa real: **el cliente que envía el trabajo (`namenode`) construye la configuración del trabajo con su propia copia local de `mapred-site.xml`**, no con la del `resourcemanager` ni la del `nodemanager`. Se había recreado únicamente `resourcemanager` y `nodemanager` tras editar `hadoop.env`, y `namenode` seguía corriendo con la configuración vieja. La corrección fue recrear los cuatro contenedores, no solo los dos que ejecutan YARN.

### Fallo 2 · `subprocess failed with code 127`, luego `code 1`

Con el maestro de aplicación arrancando, las tareas de mapeo fallaban. El código 127 es "comando no encontrado": la imagen oficial `bde2020/hadoop-nodemanager` corre sobre **Debian Stretch, sin Python instalado**. Hadoop Streaming ejecuta el mapper y el reducer como subprocesos del propio contenedor `nodemanager` —no en contenedores aparte—, así que el intérprete tiene que existir ahí.

Instalar Python con `apt-get exec` resolvió el síntoma pero no de forma reproducible: esa instalación vive en la capa editable del contenedor y se pierde en cada recreación. La corrección definitiva fue [`nodemanager.Dockerfile`](../practica/s04-mapreduce/nodemanager.Dockerfile), que extiende la imagen oficial e instala Python 3 en la construcción de la imagen. Stretch salió de soporte, así que sus repositorios habituales devuelven 404; el Dockerfile apunta a `archive.debian.org` con las banderas para aceptar un repositorio archivado.

Resuelto el 127, apareció el código 1: `SyntaxError: invalid syntax` en la línea de un f-string. Python 3.5.3 —la única versión disponible para Stretch— no soporta f-strings, que llegaron en Python 3.6. Los tres scripts (`mapper.py`, `reducer.py`, `combiner.py`) se reescribieron con `.format()`, compatible desde Python 2.7.

### Fallo 3 · `mapred.max.split.size` no producía más tareas de mapeo

Con un archivo de ~21 MB en un solo bloque HDFS de 128 MB, `mapreduce.input.fileinputformat.split.maxsize=4194304` en `mapred-site.xml` no tuvo ningún efecto: el trabajo seguía reportando `number of splits: 2`, incluso bajando el valor a 1 MB.

La causa: **Hadoop Streaming usa la API antigua de MapReduce** (`org.apache.hadoop.mapred.FileInputFormat`), que calcula el tamaño de partición con las propiedades antiguas (`mapred.min.split.size`, `mapred.max.split.size`) y con una pista de número de tareas (`mapred.map.tasks`), no con las propiedades nuevas que se habían configurado. La combinación que sí funcionó, pasada directamente en la línea de comandos para que quede explícita y fácil de ajustar:

```
-D mapred.map.tasks=6 -D mapred.min.split.size=1
```

Con esto el trabajo lanzó las 6 tareas de mapeo reales que sustentan la comparación de `T4_mezcla.md`.

---

## Lo que no se pudo verificar

- **Comportamiento con más de un nodo de cómputo.** Este clúster tiene un solo `nodemanager`, así que la mezcla ocurre entre 6 tareas de mapeo sobre el mismo nodo físico, no entre nodos distintos. El mecanismo de la mezcla —agrupar por clave y mover los pares intermedios— es el mismo; lo que no se observó es la transferencia de red entre máquinas separadas, que sí se demostró para la réplica en la práctica de S03.
- **El rediseño de clave compuesta no se ejecutó en el clúster**, solo se midió sobre el archivo con Python (`src/mapreduce/analisis_sesgo.py`). La propuesta está sustentada en datos reales, pero no en un contador de mezcla real para esa clave.
