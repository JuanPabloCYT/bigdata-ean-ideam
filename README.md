# Proyecto de curso · Precipitación del IDEAM

**Estudiante:** Juan Pablo Castro
**Asignatura:** IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean
**Fuente de datos:** Precipitación del IDEAM · conjunto `s54a-sgyg` del Portal de Datos Abiertos
**Licencia de los datos:** CC BY-SA 4.0

Este repositorio aloja el proyecto acumulativo de la asignatura. Contiene el entorno reproducible (T2) y la ficha técnica de la fuente (T1) versionada dentro de `docs/`.

> Este README es un **contrato de ejecución**, no una descripción. Si un paso no está aquí, no existe. Si sigue estos pasos y algo no ocurre como está escrito, el fallo es del repositorio y debe reportarse.

---

## 1. Qué necesita antes de empezar

| Requisito | Versión mínima | Cómo comprobarlo |
|---|---|---|
| Git | 2.30 | `git --version` |
| Docker Desktop (o Docker Engine) | 24 | `docker --version` |
| Docker Compose | v2 | `docker compose version` |
| Espacio libre en disco | 4 GB | — |
| Puertos libres en el anfitrión | 8888 y 5432 | ver paso 5 si están ocupados |

No necesita instalar Python, ni pandas, ni PostgreSQL en su equipo. Todo eso vive dentro de los contenedores. Esa es la razón de ser de este montaje.

---

## 2. Cómo se levanta

```bash
git clone <URL-DEL-REPOSITORIO> && cd proyecto-ideam-precipitacion
```

```bash
cp .env.example .env
```

Abra `.env` y cambie `POSTGRES_PASSWORD` por un valor propio. Es un entorno local de desarrollo; no reutilice contraseñas reales.

```bash
docker compose up
```

La primera vez descarga las imágenes e instala las dependencias ancladas: toma varios minutos. Las siguientes veces arranca en segundos.

---

## 3. Qué debe ver si quedó bien

1. En la terminal, la línea `ideam_db ... healthy` antes de que arranque Jupyter. El servicio de cuadernos espera deliberadamente a que la base acepte conexiones.
2. En el navegador, **<http://localhost:8888>** abre JupyterLab **sin pedir contraseña ni token**.
3. En el panel lateral, las carpetas `notebooks`, `src`, `data`, `sql` y `docs`.
4. Abra `notebooks/00_verificacion.ipynb` y ejecute todas las celdas. Debe terminar con:

```
Entorno reproducible verificado: todas las versiones coinciden.
...
Motor: PostgreSQL 16.4 ...
Tablas creadas por sql/01_esquema.sql: ['control_ingesta', 'precipitacion']
...
OK · la restricción de la base reproduce el hallazgo de T1.
```

Si el cuaderno reporta `DISCREPANCIA` o `AUSENTE` en cualquier sección, el entorno **no** está listo. Vaya a la sección 7.

Para detenerlo:

```bash
docker compose down
```

---

## 4. Los datos no están en este repositorio

Y es deliberado. Cada partición diaria del IDEAM pesa cerca de 21 MB; Git no está diseñado para archivos grandes ni binarios, y subirlos degradaría el repositorio de forma permanente. `data/raw/` está en `.gitignore`.

**En un clon limpio, `data/raw/` está vacío. Eso es lo correcto, no un error.**

Para obtener las particiones que usa la ficha T1, ejecute el cuaderno `docs/T1/medicion.ipynb`: descarga los dos días desde la API de Socrata con paginación y verifica el conteo contra la API antes de guardar. También puede descargarlas manualmente:

```
https://www.datos.gov.co/resource/s54a-sgyg.csv?$where=fechaobservacion >= '2026-06-22T00:00:00' AND fechaobservacion < '2026-06-23T00:00:00'&$order=fechaobservacion,codigoestacion,codigosensor,:id&$limit=50000&$offset=0
```

Colóquelas en `data/raw/` con los nombres `precipitacion_AAAA-MM-DD.csv`. La partición del 22 de junio de 2026 debe tener 141.007 filas y el hash SHA-256 `9a8dc75af1969e21ad7e13bddd9fad0291ebbeba2a0b1418cd4237f81a5155be`.

---

## 5. Si un puerto está ocupado

`docker compose up` falla con un error de puerto en uso cuando algo más usa el 8888 o el 5432. No cambie el `docker-compose.yml`: cambie su `.env`.

```
JUPYTER_PORT=8889
POSTGRES_PORT_HOST=5433
```

Y abra `http://localhost:8889`. Los puertos del anfitrión son configurables porque varían entre personas; los puertos internos no, porque son iguales para todos.

---

## 6. Estructura y por qué cada cosa está donde está

```
proyecto-ideam-precipitacion/
├── docker-compose.yml     # la "cocina": servicios, puertos, volúmenes
├── requirements.txt       # dependencias ancladas con ==
├── .env.example           # plantilla de credenciales (SÍ se versiona)
├── .env                   # credenciales reales (NUNCA se versiona)
├── .gitignore             # escrito antes del primer commit
├── data/
│   ├── raw/               # particiones crudas, ignoradas por Git
│   └── processed/         # derivados, ignorados por Git
├── notebooks/
│   └── 00_verificacion.ipynb
├── sql/
│   └── 01_esquema.sql     # esquema inicial; la clave de T1 es la PK
├── src/                   # código reutilizable (crece desde S3)
└── docs/
    ├── T1/                # ficha técnica y evidencias de T1
    ├── frontera_contenedor.md
    └── guia_incorporacion.md
```

El razonamiento completo sobre qué vive dentro de la imagen, qué se monta y qué se inyecta está en [`docs/frontera_contenedor.md`](docs/frontera_contenedor.md).

---

## 7. Si algo falla

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `docker compose up` no encuentra el comando | Docker Compose v1 | Pruebe `docker-compose up`, con guion |
| Error de puerto en uso | Otro proceso usa 8888 o 5432 | Cambie los puertos en `.env` (sección 5) |
| El navegador pide un token | El parámetro de token no se aplicó | Revise la indentación del bloque `command` en el YAML: en YAML la indentación es sintaxis |
| `required variable POSTGRES_PASSWORD is missing a value` | No copió `.env.example` a `.env` | `cp .env.example .env` y `docker compose up` de nuevo |
| El cuaderno no alcanza la base | Usó `localhost` en vez de `db` | Dentro de la red de Compose el host es el nombre del servicio: `db` |
| `password authentication failed for user "ideam_app"` | El volumen de la base ya existía, inicializado con otra contraseña. `POSTGRES_PASSWORD` solo se aplica cuando PostgreSQL crea un directorio de datos vacío: sobre un volumen preexistente se ignora en silencio | `docker compose down -v && docker compose up`. **El `-v` borra los datos de la base** |
| `Tablas creadas: (ninguna)` | Los scripts de `sql/` solo corren cuando el volumen se crea vacío; si ya existía, editar el SQL no tiene efecto | `docker compose down -v && docker compose up`. **El `-v` borra los datos de la base** |
| `git status` muestra CSV de datos | El `.gitignore` se escribió tarde | `git rm --cached <archivo>` y verifique el orden |
| Docker no se puede instalar en su equipo | Permisos o virtualización | Use GitHub Codespaces (ruta B). Si tampoco, `venv` + `requirements.txt` (ruta C), y declare que la capa de ejecución quedó sin aislar |

> **Sobre los volúmenes y el nombre del proyecto.** Compose deriva el nombre del proyecto del nombre de la carpeta, y el volumen de la base se llama `<nombre-de-carpeta>_db_data`. Si clona el repositorio en un directorio con el mismo nombre que otra copia suya, **ambas compartirán el mismo volumen de base de datos**. Eso hace que un "clon limpio" no sea limpio en la capa de datos. Para partir realmente de cero, use `docker compose down -v`, o clone en una carpeta con otro nombre.

Si un paso falla y no está en esta tabla, es un defecto del contrato: repórtelo abriendo un *issue* en el repositorio, indicando su sistema operativo, la salida completa del error y el paso exacto en que ocurrió.

---

## 8. Entregas de la asignatura

| Entrega | Contenido | Ubicación |
|---|---|---|
| T1 | Ficha técnica de la fuente y cuaderno de medición | [`docs/T1/`](docs/T1/) |
| T2 | Este entorno reproducible | raíz del repositorio |

Las cifras de T1 (S₀, memoria del DataFrame, k, M, g y el horizonte de saturación) están en [`docs/T1/ficha_tecnica.md`](docs/T1/ficha_tecnica.md), con las condiciones y el equipo en que se midieron.

---

## Declaración de uso de inteligencia artificial

> Se utilizó Claude Code para construir la estructura de este repositorio, redactar el `docker-compose.yml`, el `.gitignore`, el cuaderno de verificación y esta documentación. El entorno se levantó y se verificó ejecutándolo; las salidas reportadas en la sección 3 provienen de esa ejecución y no de una descripción generada. La ficha T1 declara por separado el uso de asistentes en su propia medición.
