# Bitácora de la práctica S03

Juan Pablo Castro · clúster HDFS de 4 nodos sobre Docker · macOS 27, `arm64`, VM de Docker con 3,83 GB

---

## Nivel 1 · Guiado

### Lo que se observó

Cargué `muestra.csv` (10.358.654 bytes) con bloques de 1 MB. El archivo quedó partido en **10 bloques**: nueve de 1.048.576 bytes y el último de 921.470, que es el residuo. Suman exactamente el tamaño del archivo.

Cada bloque quedó con **`Live_repl=3`**, con una copia en cada uno de los tres nodos de datos, y `fsck` reportó `Status: HEALTHY`. Esta es la réplica hecha visible: no es que el archivo esté tres veces en algún lado, es que *cada bloque por separado* tiene tres copias en tres máquinas distintas.

Al detener `datanode3` y esperar a que el maestro lo diera por muerto, `fsck` pasó a:

```
Status: HEALTHY
 Number of data-nodes:        2
 Under-replicated blocks:     10 (100.0 %)
 Average block replication:   2.0
 Missing blocks:              0
```

El archivo se leyó **completo e íntegro**: 10.358.654 bytes, 320.001 líneas, MD5 `753650fbae01f7bd6e7fa2272ca37526`, idéntico al del archivo original. Ningún bloque se perdió, porque cada uno tenía copias en los otros dos nodos.

Al reintegrar el nodo, la replicación media volvió de 2.0 a 3.0 **en unos 30 segundos, sin que yo hiciera nada**. El sistema detecta que faltan copias y las recrea. Eso es lo que la analogía de las bodegas no captura: una bodega quemada no rehace sus fotocopias sola.

### El hallazgo: la guía dice 30 segundos y son casi nueve minutos

El paso 1.5 de la guía dice «detenga el nodo, espere ~30 segundos, el archivo sigue leyéndose». **En mi clúster no fue así.** A los 30 segundos la lectura falló:

```
-cat: Null exception message
java.nio.channels.UnresolvedAddressException
    at sun.nio.ch.Net.checkAddress(Net.java:101)
exit=255, se leyeron solo 2.097.152 de 10.358.654 bytes
```

La causa: el nodo maestro **todavía creía que el nodo estaba vivo**. Medí cuánto tarda en darlo por muerto con la configuración por defecto: **531 segundos, casi nueve minutos**. Coincide con la fórmula de HDFS, `2 × dfs.namenode.heartbeat.recheck-interval (5 min) + 10 × dfs.heartbeat.interval (3 s)` = 10,5 minutos teóricos. Mientras tanto el maestro sigue entregando ese nodo como ubicación de réplica.

Hay un detalle que agrava esto y que es propio de correr HDFS sobre Docker: al parar el contenedor, Docker **borra su nombre DNS**. El cliente no recibe «conexión rechazada», que sabría reintentar en otra copia, sino `UnresolvedAddressException`, un fallo de resolución de nombre que aborta la lectura. Una máquina real apagada se comportaría distinto: la IP seguiría existiendo y el cliente fallaría más rápido hacia otra réplica.

Pasados los 531 segundos, la misma lectura funcionó perfectamente. **La conclusión de la sesión se sostiene** —con factor 3 el archivo sobrevive a la caída de un nodo—, pero no en la ventana de tiempo que la guía sugiere.

Por eso añadí al `hadoop.env`:

```bash
HDFS_CONF_dfs_namenode_heartbeat_recheck___interval=15000
HDFS_CONF_dfs_heartbeat_interval=3
```

que bajan la detección a `2 × 15 s + 10 × 3 s` = 60 segundos. Lo medí después del cambio y fueron exactamente 60 segundos. Es un ajuste **didáctico**: en producción una detección tan agresiva daría nodos por muertos ante una pausa de red pasajera y dispararía re-replicaciones innecesarias.

### Un error propio que conviene anotar

Al principio concluí que el archivo se había truncado, porque medía con `docker compose exec -T ... | wc -c` y obtenía 2 o 3 MB. Estaba mal: **la tubería de `docker exec` cortaba la salida**, no HDFS. Al redirigir a un archivo dentro del contenedor y contar allí, aparecieron los 10.358.654 bytes completos. La lección es de método: cuando la herramienta de medición se interpone entre uno y el fenómeno, se puede terminar documentando un fallo que no existe.

---

## Nivel 2 · Aplicado

### Almacenamiento físico por factor

Cargué el mismo archivo tres veces, con factores 1, 2 y 3, y medí con `hdfs dfs -du`:

| Archivo | Lógico (bytes) | Físico (bytes) | Factor medido |
|---|---:|---:|---:|
| `muestra_r1.csv` | 10.358.654 | 10.358.654 | 1,0 |
| `muestra_r2.csv` | 10.358.654 | 20.717.308 | 2,0 |
| `muestra_r3.csv` | 10.358.654 | 31.075.962 | 3,0 |

La relación **físico = lógico × R** se cumple exactamente, al byte. No hay réplica gratuita ni descuento por compresión: cada copia cuesta el tamaño completo.

### El contraste que importa: factor 1 contra factor 3

Detuve `datanode3`, que alojaba 4 de los 10 bloques de `muestra_r1.csv` sin ninguna copia. Con el mismo nodo caído, los dos archivos se comportaron de forma opuesta:

| | `muestra_r1.csv` (R=1) | `muestra_r3.csv` (R=3) |
|---|---|---|
| `fsck` | **`Status: CORRUPT`** | `Status: HEALTHY` |
| Bloques perdidos | **4 de 10** | 0 |
| Replicación media | 0,6 | 2,0 |
| Lectura | **`exit=1`, 0 bytes**, «Could not obtain block» | `exit=0`, 10.358.654 bytes |
| MD5 | — | `753650…` correcto |

Con factor 1 el archivo no está degradado: **está roto**. No se leyó ni un byte, porque le faltan bloques y un archivo con un hueco no sirve para nada. Con factor 3, el mismo fallo en el mismo momento no tuvo ninguna consecuencia.

Esto responde la pregunta 1 de la autoevaluación de forma tangible: repartir sin copiar no es tolerancia a fallos. Los 10 bloques de `muestra_r1.csv` estaban perfectamente repartidos entre tres máquinas, y aun así bastó apagar una para perder el archivo entero.

### Relación entre factor y tolerancia

| Factor R | Físico | Nodos que puede perder | Comprobado |
|---:|---:|---:|---|
| 1 | 1× | 0 | Sí: cayó un nodo y el archivo quedó `CORRUPT` |
| 2 | 2× | 1 | Por construcción; con 3 nodos no se probó el segundo fallo |
| 3 | 3× | 2 | Se probó 1 fallo: `HEALTHY`. El segundo no se probó porque solo hay 3 nodos |

**Lo que no pude verificar:** la tolerancia a dos caídas simultáneas con factor 3. Con solo tres nodos de datos, apagar dos deja uno solo, y el clúster no puede sostener el factor. Haría falta un clúster de al menos cuatro nodos de datos para observarlo, y la memoria de este equipo no da.

---

## Nivel 3 · Autónomo

Las cifras salen de `proyeccion_almacenamiento.py`, que lee los valores directamente de la ficha T1 en lugar de tenerlos escritos a mano. Otra persona con la misma ficha obtiene los mismos números.

### El problema de proyectar con crecimiento negativo

La ficha T1 mide **g = −4,780861 % anual**: el mismo mes tuvo menos registros en 2026 que en 2025. Proyectar 12 meses con una tasa negativa da un volumen que *encoge*, lo cual no sirve para dimensionar disco: nadie compra almacenamiento para un dato que se contrae. Es el mismo problema que ya apareció en T1 con el horizonte de saturación.

Por eso proyecto **tres escenarios declarados**, y dimensiono con el más exigente:

| Escenario | Lógico a 12 meses | R=1 | R=2 | R=3 |
|---|---:|---:|---:|---:|
| Histórico, g = −4,78 % | 7,298 GB | 7,30 GB | 14,59 GB | 21,89 GB |
| Conservador, g = 0 % | 7,463 GB | 7,46 GB | 14,93 GB | 22,39 GB |
| Sensibilidad, g = +1 % | 7,497 GB | 7,50 GB | 14,99 GB | 22,49 GB |

La diferencia entre los tres escenarios es de apenas 0,2 GB, menos del 3 %. **La elección de la tasa es casi irrelevante para esta decisión**, y eso también es un hallazgo: no vale la pena discutir la proyección de crecimiento cuando el factor de réplica mueve la cifra el triple. Dimensiono con el escenario de sensibilidad, **22,49 GB con factor 3**.

Otra advertencia que hereda de T1: S₀ es una **partición diaria**, no el acumulado. La ficha decía explícitamente que modelar el repositorio completo exigiría un modelo aditivo que no se había hecho. Ese modelo aditivo es justamente lo que hace el script: suma las particiones diarias mes a mes.

### Decisión 1 · Factor de réplica: 3 para el dato crudo

El dato de precipitación del IDEAM es **telemetría de sensores en el tiempo**. Si se pierde la partición del 22 de junio de 2026, no hay forma de volver a capturarla: ese instante ya pasó. La API de Socrata permite volver a descargar mientras el IDEAM conserve el histórico, pero eso es depender de un tercero sobre el que no tenemos control ni acuerdo de servicio.

Lo que compra el factor 3 sobre el factor 2 es tolerar **dos** caídas simultáneas en vez de una, por 7,5 GB adicionales al año. Con volúmenes de esta escala el costo absoluto es despreciable: hablamos de decenas de gigabytes, no de terabytes. **A este tamaño, discutir el factor por ahorro de disco no tiene sentido.** La discusión sería otra si la fuente pesara 50 TB.

Para datos derivados —agregados, tablas de resumen, resultados intermedios del pipeline— el factor 2 basta, porque se regeneran ejecutando el proceso de nuevo.

### Decisión 2 · Tamaño de bloque: 128 MB, pero consolidando particiones

Aquí hay que nombrar las dos tensiones, no solo una.

Una partición diaria pesa 20,94 MB, es decir el **16,4 % de un bloque de 128 MB**. A un año son 365 archivos y 365 bloques.

**Primero, una precisión que la pista 2 de la guía deja ambigua:** HDFS **no desperdicia disco** en bloques parciales. Un bloque es una construcción lógica; el nodo de datos lo guarda como un archivo normal del sistema operativo. Una partición de 20,94 MB ocupa 20,94 MB en disco, no 128 MB. No se pierden los 107 MB restantes.

El costo real de los archivos pequeños es el que el propio enunciado del nivel 3 sí describe bien: **la memoria del nodo maestro**, que guarda metadatos por cada archivo y cada bloque, del orden de 150 bytes por objeto. Y, de cara a la sesión 4, el exceso de tareas: un bloque suele ser una tarea de lectura, y 365 tareas diminutas rinden peor que 60 tareas llenas.

Ahora, la parte honesta: **a esta escala el problema no existe todavía**.

| Estrategia | Objetos en el maestro | Memoria del maestro |
|---|---:|---:|
| Partición diaria | 730 | 0,104 MB al año |
| Consolidación mensual | 72 | 0,010 MB al año |

0,1 MB de memoria al año no es una restricción para nadie. El problema de los archivos pequeños se vuelve real con millones de archivos, no con 365. Decir lo contrario sería repetir una advertencia de libro sin mirar las cifras propias.

**Decisión:** mantener bloque de 128 MB, que es el valor por defecto y no hay razón medida para moverlo, y **consolidar las particiones diarias en archivos mensuales** una vez cerrado el mes. Reduce los objetos en un 90,1 % y baja de 365 a 60 bloques al año, lo que ayuda al procesamiento de la sesión 4. La ingesta diaria se conserva porque la recomendación de T1 era ingesta incremental por `fechaobservacion`; consolidar es un paso posterior, no un reemplazo.

Bajar el tamaño de bloque para «ajustarlo» a los 20,94 MB de la partición sería el error contrario: multiplicaría los bloques sin ganar nada, porque el disco no se estaba desperdiciando.

---

## Lo que no se pudo verificar

- **Tolerancia a dos caídas simultáneas con factor 3.** Requiere al menos cuatro nodos de datos; la memoria de este equipo no alcanza.
- **Comportamiento ante una caída real de máquina.** Aquí se detuvo un contenedor, y Docker elimina el nombre DNS, lo que produce un modo de fallo distinto (`UnresolvedAddressException`) al de un servidor apagado, cuya IP seguiría existiendo.
- **El clúster corre emulado** (`amd64` sobre `arm64`), así que los tiempos observados no son representativos del rendimiento real. Las cifras de tamaño y réplica sí lo son, porque no dependen de la velocidad.
- **Códigos de borrado.** El `fsck` muestra la sección `Erasure Coded Block Groups` en cero. No se probaron; quedan mencionados en el reto de negocio como alternativa.
