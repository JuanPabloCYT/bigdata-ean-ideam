# Proyecto · Precipitación del IDEAM

Proyecto del curso IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean.
Fuente de datos: **Precipitación del IDEAM, conjunto `s54a-sgyg` del Portal de Datos Abiertos de Colombia** (licencia CC BY-SA 4.0).

Estudiante: Juan Pablo Castro.

Este repositorio es donde vive el proyecto del semestre. Contiene el entorno reproducible (T2) y la ficha técnica de la fuente (T1) en `docs/T1/`.

---

## Requisitos previos

Lo que debe estar instalado antes de empezar:

- Git 2.30 o superior
- Docker Desktop (o Docker Engine) 24 o superior, con Docker Compose v2
- 4 GB libres en disco
- Los puertos 8888 y 5432 libres, o cambiarlos en `.env` como explico más abajo

No hace falta instalar Python, pandas ni PostgreSQL. Están dentro de los contenedores; para eso los uso.

**Ruta de infraestructura usada:** A · Docker local

Lo construí y lo probé con Docker Desktop en macOS 27 (arm64). Con esta ruta quedan cubiertas las dos capas de aislamiento de esta sesión: el código con Git y la ejecución con contenedores, más el anclaje de dependencias. La capa de datos se trabaja en S5.

---

## Cómo levantar el entorno

```bash
# 1. Clonar
git clone https://github.com/JuanPabloCYT/bigdata-ean-ideam.git
cd bigdata-ean-ideam

# 2. Configurar variables de entorno
cp .env.example .env
# Abra .env y cambie POSTGRES_PASSWORD por un valor propio.
# Es una base local de desarrollo, no reutilice una contraseña real.

# 3. Levantar
docker compose up
```

La primera vez descarga unos 5,5 GB de imágenes e instala las dependencias. Tarda varios minutos. Después arranca en segundos.

Durante ese primer arranque `docker compose ps` muestra `jupyter` como `unhealthy` y el navegador no responde. Es normal: `pip` está instalando en silencio y el servicio no se declara sano hasta que el servidor escucha. Si prefiere ver el avance en vez de esperar a ciegas, use `docker compose logs -f jupyter`.

Para detenerlo: `docker compose down`.

---

## Cómo saber que quedó bien

- En la terminal, `ideam_db` aparece como `healthy` antes de que arranque Jupyter. El servicio de cuadernos espera a que la base acepte conexiones, no solo a que el contenedor exista.
- Jupyter responde en <http://localhost:8888> sin pedir token ni contraseña.
- En el panel lateral se ven las carpetas `notebooks`, `src`, `data`, `sql` y `docs`.
- El cuaderno `notebooks/00_verificacion.ipynb` corre completo y termina con estas tres líneas:

```
Entorno reproducible verificado: todas las versiones coinciden.
Motor: PostgreSQL 16.4 ...
OK · la restricción de la base reproduce el hallazgo de T1.
```

Si el cuaderno reporta `DISCREPANCIA` o `AUSENTE` en cualquier sección, el entorno no está listo. Vaya a "Si algo falla".

---

## Estructura del proyecto

```
bigdata-ean-ideam/
├── README.md
├── docker-compose.yml     # dos servicios: jupyter y db
├── requirements.txt       # dependencias ancladas con ==
├── .gitignore             # escrito antes del primer commit
├── .env.example           # claves sin valores, como referencia
├── .env                   # valores reales, NO versionado
├── data/
│   ├── raw/               # particiones crudas, NO versionadas
│   └── processed/         # derivados, NO versionados
├── notebooks/
│   └── 00_verificacion.ipynb
├── sql/
│   └── 01_esquema.sql     # la clave candidata de T1 es la clave primaria
├── src/
│   └── config.py
└── docs/
    ├── T1/                # ficha técnica y evidencias de T1
    ├── frontera_contenedor.md
    └── guia_incorporacion.md
```

### Los datos no están en el repositorio

En T1 medí que una partición diaria pesa 21.953.076 bytes. Con esa cifra la decisión es fácil: `data/raw/` va en `.gitignore`, porque Git no sirve para archivos grandes y subirlos degradaría el repositorio para siempre.

**En un clon limpio `data/raw/` está vacío. Eso está bien, no es un error.**

Para obtener las particiones, ejecute `docs/T1/medicion.ipynb`, que las descarga de la API de Socrata por páginas y verifica el conteo contra la API antes de guardar. También puede descargarlas a mano:

```
https://www.datos.gov.co/resource/s54a-sgyg.csv?$where=fechaobservacion >= '2026-06-22T00:00:00' AND fechaobservacion < '2026-06-23T00:00:00'&$order=fechaobservacion,codigoestacion,codigosensor,:id&$limit=50000&$offset=0
```

Guárdelas en `data/raw/` como `precipitacion_AAAA-MM-DD.csv`. La del 22 de junio de 2026 debe tener 141.007 filas y hash SHA-256 `9a8dc75af1969e21ad7e13bddd9fad0291ebbeba2a0b1418cd4237f81a5155be`.

### Cómo se conecta con T1

T2 no reemplaza a T1: es lo que la vuelve verificable.

- **La ficha entra al repositorio.** Está en `docs/T1/`, dentro de la historia de Git, no como un adjunto aparte.
- **Anclé `pandas==2.2.3` por T1.** Es la versión con la que medí el factor de expansión *k*. `memory_usage(deep=True)` da el mismo resultado con los mismos datos y la misma versión de pandas, así que cambiar la versión mayor movería *k* por un cambio de la librería y no del dato. Ese `==` es lo que mantiene reproducible la cifra.
- **La clave candidata pasó a ser una restricción.** En T1 comprobé que `codigoestacion + codigosensor + fechaobservacion` era única: 141.007 filas, 141.007 combinaciones, 0 duplicados y 0 nulos. En `sql/01_esquema.sql` es la clave primaria que PostgreSQL exige en cada inserción, y el cuaderno lo verifica contra `information_schema`.
- **La ingesta incremental se volvió estructura.** T1 recomendaba ingerir por `fechaobservacion`. De ahí salen el índice sobre esa columna y la tabla `control_ingesta`, que registra qué partición se cargó, cuándo, con cuántas filas y con qué hash.

Las cifras de T1 las medí en macOS, en esta MacBook. Al rehacer la medición, *k* y S₀ salieron iguales que en la medición anterior en Windows, porque el archivo y la versión de pandas eran los mismos. Lo que cambió fue *M*, la memoria útil: pasó de 7,43 GB a 1,50 GB, y el horizonte de saturación de 474 a 313 años. El umbral depende del equipo tanto como del dato, y por eso hay que declarar y congelar el equipo. Eso es lo que hace este repositorio.

El detalle de qué vive dentro de la imagen, qué se monta y qué se inyecta está en [`docs/frontera_contenedor.md`](docs/frontera_contenedor.md).

---

## Si algo falla

| Problema | Solución |
|---|---|
| `docker compose up` no encuentra el comando | Tiene Compose v1: use `docker-compose up`, con guion |
| Puerto ocupado (`port is already allocated`) | Cambie `JUPYTER_PORT` y `POSTGRES_PORT_HOST` en `.env`, por ejemplo a 8889 y 5433, y abra `localhost:8889`. No toque el compose: los puertos del anfitrión varían entre personas, los internos no |
| `jupyter` sigue `unhealthy` y el navegador no responde | Si es el primer arranque, está instalando dependencias. Espere y siga el avance con `docker compose logs -f jupyter` |
| El navegador pide un token | El parámetro de token no se aplicó. Revise la indentación del bloque `command` en el YAML: ahí la indentación es sintaxis, no adorno |
| `required variable POSTGRES_PASSWORD is missing a value` | No copió `.env.example` a `.env` |
| `password authentication failed for user "ideam_app"` | El volumen de la base ya existía, creado con otra contraseña. `POSTGRES_PASSWORD` solo se aplica cuando PostgreSQL inicializa un directorio vacío; sobre un volumen que ya existe se ignora sin avisar. Use `docker compose down -v && docker compose up`. **El `-v` borra los datos de la base** |
| `Tablas creadas: (ninguna)` | Los scripts de `sql/` solo corren cuando el volumen se crea vacío. Si ya existía, editar el SQL no tiene efecto. Misma solución: `docker compose down -v && docker compose up` |
| El cuaderno no alcanza la base | Está apuntando a `localhost`. Dentro de la red de Compose el host es el nombre del servicio: `db` |
| `git status` muestra CSV de datos | El `.gitignore` se escribió tarde. `git rm --cached <archivo>` y revise el orden |

Un detalle que me costó una hora entender: Compose saca el nombre del proyecto del nombre de la carpeta, y el volumen de la base se llama `<carpeta>_db_data`. Si clona el repositorio en una carpeta con el mismo nombre que otra copia suya, las dos comparten el mismo volumen y el "clon limpio" no queda limpio en la capa de datos. Para partir de cero de verdad, use `docker compose down -v` o clone en una carpeta con otro nombre.

Si el problema no está en esta tabla, el que falla es este README. Abra un *issue* con su sistema operativo, el paso exacto donde se quedó y el error completo.

Contacto del responsable del repositorio: Juan Pablo Castro · juanpablopug@gmail.com · [@JuanPabloCYT](https://github.com/JuanPabloCYT)

---

## Guía de incorporación

Está en [`docs/guia_incorporacion.md`](docs/guia_incorporacion.md): una página para que alguien que llega nuevo tenga el proyecto corriendo el primer día, sin depender de nadie del equipo. Va dirigida a una persona sin contexto, así que explica qué instalar, los pasos en orden, qué debe ver en pantalla y a quién escribir si algo falla.

---

## Declaración de uso de asistentes de inteligencia artificial

- **Herramienta usada:** Claude Code. En T1 usé además Codex y ChatGPT, declarado en `docs/T1/ficha_tecnica.md`.
- **En qué parte:** estructura del repositorio, `docker-compose.yml`, `.gitignore`, `requirements.txt`, `sql/01_esquema.sql`, el cuaderno de verificación y la redacción de este README y de los documentos de `docs/`.
- **Qué verifiqué contra ejecución real:** todo lo que este README afirma. Levanté el entorno, ejecuté el cuaderno dentro del contenedor y comprobé las salidas. Hice la prueba del clon limpio desde la URL pública, en una carpeta con otro nombre y con volumen nuevo: los dos servicios quedaron `healthy`, Jupyter respondió HTTP 200 sin token y el cuaderno corrió completo con 0 errores. Las tres fallas que encontré en el camino están documentadas en `docs/frontera_contenedor.md` con lo que hice para resolverlas. Ninguna cifra ni ninguna salida de este repositorio viene de una descripción generada.

---

## Lista de verificación antes de entregar

- [x] `.gitignore` escrito antes del primer commit; no hay datos ni credenciales en la historia
- [x] `requirements.txt` con todas las versiones ancladas con doble igual
- [x] `docker-compose.yml` con dos servicios y versiones ancladas
- [x] Cuaderno de verificación ejecutado, con salidas visibles
- [x] Ficha T1 versionada en `docs/`
- [x] Varios commits con mensajes que explican qué cambió
- [x] **Prueba del clon limpio:** cloné en una carpeta nueva y levantó sin que yo tocara nada
- [x] Repositorio público o compartido con la cuenta docente

Verificaciones adicionales que hice: las dos imágenes están ancladas por digest y no por etiqueta, porque una etiqueta la puede reasignar quien la publica; revisé la historia completa de Git y confirmé que `.env` nunca se versionó, que no hay CSV crudos en ningún commit y que la contraseña real no aparece en ninguna revisión.

---

*IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean.*
