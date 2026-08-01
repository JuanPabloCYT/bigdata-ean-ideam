# Práctica S03 · Clúster HDFS

Sesión 3 · Sistemas de archivos distribuidos · Juan Pablo Castro

Clúster HDFS de cuatro nodos (un maestro y tres nodos de datos) para ver la réplica funcionando y medir el costo de cada factor. Vive aparte del entorno de T2: tiene su propio `docker-compose.yml` y no toca el de la raíz.

**Ruta de infraestructura: A · clúster de 4 nodos**, con dos ajustes que documento abajo porque el equipo no cumple lo que la guía supone.

---

## Cómo levantarlo

```bash
cd practica/s03-hdfs
python3 genera_muestra.py     # crea muestra/muestra.csv, semilla fija
docker compose up -d
```

Espere a que los tres nodos de datos se registren y a que el maestro salga de modo seguro:

```bash
docker compose exec namenode hdfs dfsadmin -report | grep "Live datanodes"
docker compose exec namenode hdfs dfsadmin -safemode get
```

Interfaz web del maestro: <http://localhost:9870>, pestaña **Datanodes**.

Al terminar:

```bash
docker compose down       # conserva los datos en los volúmenes
docker compose down -v    # elimina también los datos del clúster
```

---

## Dos cambios respecto del compose de la guía

**1. `platform: linux/amd64` en los cuatro servicios.** Las imágenes `bde2020/hadoop-*` publican manifiesto solo para `amd64`. Este equipo es `arm64` (Apple Silicon), así que los contenedores corren emulados. Lo verifiqué antes de empezar:

```
bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8 -> arquitectura: amd64
bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8 -> arquitectura: amd64
```

**2. Límites de memoria por servicio.** La VM de Docker de este equipo tiene 3,83 GB, no los 16 GB de la sala. Se acota el heap de Hadoop (512 MB el maestro, 256 MB cada nodo de datos) y se pone `mem_limit` para que los cuatro nodos quepan. Con estos límites la ruta A funcionó completa; no hizo falta bajar a la ruta B.

También agregué al `hadoop.env` una detección de nodos caídos más rápida. La razón está en la bitácora del nivel 1: por defecto HDFS tarda minutos en declarar muerto un nodo, y eso hace la práctica impracticable en una sesión.

---

## Qué hay en `resultados/`

| Archivo | Qué contiene |
|---|---|
| `n1_fsck_antes_de_la_caida.txt` | Los 10 bloques con sus 3 réplicas y en qué nodo quedó cada una |
| `n1_fsck_con_nodo_caido.txt` | El mismo archivo con un nodo abajo: réplica insuficiente |
| `n1_error_lectura_a_los_30s.txt` | El error real al leer antes de que el maestro detecte la caída |
| `n2_du_por_factor.txt`, `n2_du_bytes.txt` | Almacenamiento físico medido para los factores 1, 2 y 3 |
| `n2_fsck_r1.txt` | Ubicación de los bloques con factor 1, sin copias |
| `n2_fsck_muestra_r1_nodo_caido.txt` | Factor 1 con un nodo caído: `CORRUPT` |
| `n2_fsck_muestra_r3_nodo_caido.txt` | Factor 3 con el mismo nodo caído: `HEALTHY` |
| `n3_proyeccion.txt` | Salida de `proyeccion_almacenamiento.py` |

Las observaciones están en [`bitacora.md`](bitacora.md) y la recomendación a gerencia en [`reto_negocio.md`](reto_negocio.md).

La muestra (`muestra/muestra.csv`) no se versiona: se regenera con `genera_muestra.py`, que usa semilla fija, así que cualquiera obtiene el mismo archivo.
