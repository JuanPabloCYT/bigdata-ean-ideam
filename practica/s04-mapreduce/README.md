# Práctica S04 · Clúster HDFS + YARN, y la tarea T4

Sesión 4 · El modelo MapReduce · Juan Pablo Castro

Extiende el clúster HDFS de `practica/s03-hdfs/` con el gestor de recursos (YARN), en un compose aparte para no tocar lo ya entregado en S03. Aquí corrió la ejecución real de T4: la agregación de precipitación promedio por departamento, en clave map y reduce, con y sin combinador.

El informe de T4 está en [`docs/T4_mezcla.md`](../../docs/T4_mezcla.md); los comandos exactos de reproducción y los tres fallos de infraestructura que costó resolver, en [`docs/T4_ejecucion.md`](../../docs/T4_ejecucion.md).

---

## Por qué este clúster es más chico que el de S03

Un solo nodo de datos y un solo nodo de cómputo, no tres. La VM de Docker de este equipo tiene 3,83 GB en total, y S03 ya mostró que 4 contenedores de Hadoop la dejan al límite. Sumar `resourcemanager` + `nodemanager` (que además lanza JVM hijas por cada tarea) no cabría manteniendo los tres nodos de datos. La réplica no es el objeto de esta sesión —lo fue en S03—, así que se reduce sin perder lo que S04 sí necesita: mapeo, mezcla y reducción reales, con contadores reales.

## `nodemanager.Dockerfile`

La imagen oficial `bde2020/hadoop-nodemanager` corre sobre Debian Stretch sin Python instalado, y Hadoop Streaming ejecuta el mapper y el reducer como subprocesos de ese mismo contenedor. Este Dockerfile instala Python 3 en la construcción de la imagen, para que cualquiera que clone el repositorio lo tenga sin pasos manuales. Detalle completo del porqué en `docs/T4_ejecucion.md`.

## Qué hay en `resultados/`

| Archivo | Contenido |
|---|---|
| `log_sin_combinador.txt` | Consola completa del trabajo sin combinador, con sus contadores |
| `log_con_combinador.txt` | Ídem, con combinador |
| `resultado_sin_combinador.txt`, `resultado_con_combinador.txt` | La agregación en sí: precipitación promedio por departamento |
| `estimacion_teorica.txt` | Salida de `src/mapreduce/estimacion_mezcla.py` |
| `analisis_sesgo.txt` | Salida de `src/mapreduce/analisis_sesgo.py` |

## Cómo levantarlo

```bash
cd practica/s04-mapreduce
cp ../../data/raw/precipitacion_2026-06-22.csv muestra/
cp ../../src/mapreduce/*.py muestra/
docker compose up -d --build
```

Los pasos completos, con verificación, están en [`docs/T4_ejecucion.md`](../../docs/T4_ejecucion.md).

Al terminar: `docker compose down` para liberar memoria.
