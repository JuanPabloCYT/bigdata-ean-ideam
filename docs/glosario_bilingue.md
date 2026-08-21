# Glosario técnico bilingüe · acumulativo

Términos técnicos del curso, en español e inglés, con la precisión de uso que aplica en este proyecto. Se amplía en cada sesión.

---

## Sesión 1 · Naturaleza de los datos masivos

| Español | Inglés | Precisión de uso |
|---|---|---|
| Factor de expansión | expansion factor | Cuántas veces crece un archivo al cargarse en memoria. En esta fuente se midió *k* = 3,2396 |
| Memoria útil | available memory | La memoria realmente disponible para el proceso, no la RAM total del equipo. Se mide con `psutil.virtual_memory().available` |
| Umbral del nodo único | single-node threshold | El punto en que un problema de datos deja de resolverse con holgura en una sola máquina |
| Memoria profunda | deep memory usage | Medición que recorre el contenido de las columnas de texto, no solo sus punteros. Requiere `deep=True` |

## Sesión 2 · Reproducibilidad

| Español | Inglés | Precisión de uso |
|---|---|---|
| Anclaje de versiones | version pinning | Fijar la versión exacta de una dependencia con `==`. Sin esto, las demás capas de aislamiento no sirven |
| Imagen | image | Plantilla inmutable a partir de la cual se instancian los contenedores |
| Contenedor | container | Instancia en ejecución de una imagen. Comparte el núcleo del anfitrión, no es una máquina virtual completa |
| Clon limpio | clean clone | Prueba de reproducibilidad: clonar en una carpeta nueva y levantar sin intervención del autor |

## Sesión 3 · Sistemas de archivos distribuidos

| Español | Inglés | Precisión de uso |
|---|---|---|
| Sistema de archivos distribuido | distributed file system | Almacena un archivo repartido **y replicado** entre varias máquinas. Repartir sin replicar no da tolerancia |
| Bloque | block | Fragmento de tamaño fijo en que se corta el archivo. En HDFS, 128 MB típico. Un bloque parcial **no** desperdicia disco |
| Factor de réplica | replication factor | Número de copias de cada bloque. Tolera *R* − 1 fallos simultáneos y cuesta *R* veces el volumen lógico |
| Nodo maestro | master node, NameNode | Guarda el catálogo de bloques y réplicas, no el dato. Es el punto sensible de la arquitectura |
| Nodo de datos | data node, DataNode | Guarda los bloques reales. Su caída es tolerable: el sistema re-replica solo |
| Localidad del dato | data locality | Llevar el cómputo al nodo donde el bloque ya vive, en vez de mover el dato por la red |
| Tolerancia a fallos | fault tolerance | Capacidad de seguir operando pese a la caída de componentes |
| Réplica insuficiente | under-replicated | Un bloque con menos copias que el factor configurado. Estado transitorio: el sistema lo corrige |
| Latido | heartbeat | Señal periódica de cada nodo de datos al maestro. Su ausencia prolongada declara muerto al nodo |
| Conciencia de bastidor | rack awareness | Criterio de colocación que reparte las réplicas en bastidores distintos, para que la falla de uno no las elimine todas |
| Códigos de borrado | erasure coding | Alternativa a la réplica: protección comparable ocupando ~1,5× en vez de 3×, a costa de recuperación más lenta |

## Sesión 4 · El modelo MapReduce

| Español | Inglés | Precisión de uso |
|---|---|---|
| Mapeo | map | Emite pares de clave y valor por cada registro. Corre local, sobre el bloque que el nodo ya tiene |
| Mezcla | shuffle | Agrupa por clave y mueve los valores por la red. Es el cuello de botella y lo ejecuta el sistema |
| Reducción | reduce | Recibe una clave y todos sus valores, y produce el resultado |
| Combinador | combiner | Reducción parcial local, antes de la mezcla, para mover menos. Debe emitir suma y conteo, nunca un promedio |
| Clave de agrupación | grouping key | La clave que decide qué se reúne. Gobierna resultado, paralelismo y costo de la mezcla |
| Sesgo de clave | key skew, data skew | Una clave concentra el trabajo y su reductor se vuelve el cuello de botella. Añadir nodos no lo resuelve |

## Sesión 5 · Almacenamiento de objetos y el lago por capas

| Español | Inglés | Precisión de uso |
|---|---|---|
| Cubo | bucket | Contenedor de nivel superior donde viven los objetos. Uno por capa: `lago-crudo`, `lago-refinado`, `lago-curado` |
| Objeto | object | El archivo completo con sus metadatos, la unidad de almacenamiento. No se edita, se reemplaza |
| Clave | key | El nombre único del objeto dentro del cubo. Incluye el prefijo que finge ser ruta |
| Prefijo | prefix | La parte inicial de la clave que da la apariencia de carpeta y permite listar por grupo. No es un directorio real |
| Espacio de nombres plano | flat namespace | No existen carpetas reales en el almacenamiento de objetos; la jerarquía es una convención de nombres, no una estructura del sistema |
| Inmutabilidad | immutability | Propiedad de que un objeto se reemplaza pero no se edita en el lugar. En `lago-crudo` se hace cumplir con idempotencia por ETag y con versionado |
| Versionado | versioning | Conserva las versiones anteriores de un objeto al sobrescribirlo, en vez de borrarlas. Es la garantía de inmutabilidad que no depende de la disciplina de quien escribe |
| Clase de almacenamiento | storage class | Nivel que cambia el compromiso entre costo y latencia de recuperación. No se observa en el laboratorio local, solo en un despliegue en la nube |
| Lago de datos | data lake | Dato organizado por capas sobre almacenamiento de objetos, navegable en el tiempo. La organización, no la tecnología, es lo que lo distingue de un pantano |

## Sesión 3 · Lectura anclada en inglés · Kleppmann (2017), replicación

> **Pendiente.** Los tres términos de esta sección deben tomarse del extracto de Kleppmann asignado en Canvas, que aún no se ha incorporado al repositorio. Se completa junto con el párrafo en inglés de T3.

| Español | Inglés | Precisión de uso |
|---|---|---|
| *(por definir)* | | |
| *(por definir)* | | |
| *(por definir)* | | |
