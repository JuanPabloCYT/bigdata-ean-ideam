# Dónde vive cada cosa · la frontera del contenedor

**Nivel 3 · Sesión 2 · Juan Pablo Castro**

El proyecto tiene cuatro tipos de cosas. La pregunta no es dónde caben, sino **qué debe ser idéntico entre máquinas y qué puede variar**. Lo que es igual para todos va dentro de la imagen; lo que cambia entre personas o entre ejecuciones se monta o se inyecta.

## La decisión

| Elemento | Dónde vive | Justificación |
|---|---|---|
| **Código de los cuadernos** | Montado como volumen (`./notebooks`, `./src`) | Cambia varias veces por sesión de trabajo. Si viviera dentro de la imagen, cada edición exigiría reconstruirla y el ciclo de trabajo sería inviable. Además, Git ya lo versiona: meterlo en la imagen duplicaría la responsabilidad de versionado en dos lugares que se desincronizarían. |
| **Librerías de Python** | Ancladas en `requirements.txt`, instaladas al levantar el servicio | Son idénticas para todos: es justo lo que debe ser reproducible. Se declaran con `==` porque una versión distinta de pandas cambiaría `memory_usage(deep=True)` y haría irreproducible la ficha T1. Se instalan desde `requirements.txt` montado en modo lectura, y no se congelan en una imagen propia, para que el anclaje viva en un archivo legible y revisable en el *diff* de un commit. |
| **Datos crudos** | Montados como volumen (`./data`), ignorados por Git | Aquí está la tensión real. No van en la imagen porque la harían enorme y porque cambian con cada partición. No van en Git porque son binarios grandes que degradarían el repositorio de forma permanente. La respuesta es montarlos y **documentar en el README de dónde se obtienen**, con el conteo y el hash esperados para poder verificarlos. Esa separación entre "el entorno" y "el dato" es el tema de S5. |
| **Credenciales de la base** | En `.env`, inyectadas como variables de entorno | Cambian entre personas y entre despliegues, y no deben existir en ningún archivo versionado: una credencial que entra a la historia de Git queda ahí aunque después se borre el archivo. Se versiona `.env.example`, con las claves pero sin los valores, para que quien llega sepa qué debe definir sin recibir un secreto. |
| **Estado de la base** | Volumen nombrado de Docker (`db_data`) | No es código ni dato de entrada: es estado generado. No pertenece al repositorio ni a la imagen. Se le da un volumen nombrado para que sobreviva a `docker compose down` y se borre solo cuando se pida explícitamente con `-v`. |
| **Esquema SQL** | Versionado (`./sql`), montado en el punto de inicialización | Es código, no estado: define la forma de la base. Debe ser idéntico para todos y quedar en la historia de Git. Se monta en `/docker-entrypoint-initdb.d`, que PostgreSQL ejecuta una sola vez cuando el volumen está vacío. |

## Qué debe ser idéntico y qué puede variar

**Idéntico entre máquinas:** las versiones de las librerías, la versión del motor de PostgreSQL, el esquema de la base, los puertos *internos* de los contenedores y los nombres de servicio. Si algo de esto varía, los resultados dejan de ser comparables.

**Puede variar legítimamente:** los puertos del anfitrión (por eso son `${JUPYTER_PORT}` y no literales), la contraseña de la base, la ruta absoluta del repositorio en el disco y el sistema operativo del anfitrión. Todo esto está parametrizado o es irrelevante por construcción.

## Reproducción en limpio · qué falló

Se probó levantando el proyecto desde cero: `docker compose down -v`, borrado de las imágenes descargadas y un clon limpio en un directorio distinto, sin variables heredadas de la terminal.

**Falló en el primer intento, y así se corrigió:**

1. **El cuaderno no encontraba la base.** El servicio de Jupyter arrancaba antes de que PostgreSQL aceptara conexiones. `depends_on` a secas solo espera a que el contenedor *exista*, no a que el servicio esté *listo*. Se corrigió con un `healthcheck` sobre `pg_isready` y `condition: service_healthy`. Es una condición de carrera: aparece de forma intermitente, y en una máquina rápida puede no manifestarse nunca — razón de más para no confiar en que "funcionó una vez".

2. **`start-notebook.sh` no existe en la imagen actual.** El comando de la guía corresponde a una versión anterior de las imágenes de Jupyter. En la imagen anclada el script es `start-notebook.py`, y el parámetro de token cambió de `--NotebookApp.token` a `--IdentityProvider.token`. Es exactamente el problema que esta sesión combate: una instrucción que funcionaba en un entorno y dejó de funcionar sin que nadie lo anotara.

3. **El esquema no se aplicaba al cambiar `sql/`.** Los scripts de `/docker-entrypoint-initdb.d` solo corren cuando el volumen se crea vacío. Con un volumen preexistente, editar el SQL no tiene ningún efecto y la base queda silenciosamente desactualizada. Se documentó en el README que hace falta `docker compose down -v`, advirtiendo que ese comando borra los datos.

Los tres fallos tienen la misma forma: **algo que funcionaba en la máquina donde se construyó y dependía de estado que no estaba declarado**. Esa es la definición del problema que esta sesión ataca. Si al reproducir en limpio no hubiera fallado nada, la conclusión razonable no sería que el montaje es perfecto, sino que la prueba no partió realmente de cero.

## Lo que no se pudo verificar

El entorno se reprodujo en limpio en la misma máquina (macOS, `arm64`). **No se probó en un sistema operativo ni en una arquitectura distintos.** Las imágenes ancladas publican manifiestos para `amd64` y `arm64`, de modo que hay base razonable para esperar que funcione en un equipo Intel o en Linux, pero esperar no es haber verificado. Queda pendiente para la prueba entre compañeros.
