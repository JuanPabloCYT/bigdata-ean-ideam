# Dónde vive cada cosa · la frontera del contenedor

**Nivel 3 · Sesión 2 · Juan Pablo Castro**

El proyecto tiene cuatro tipos de cosas. La pregunta no es dónde caben, sino **qué debe ser idéntico entre máquinas y qué puede variar**. Lo que es igual para todos va dentro de la imagen; lo que cambia entre personas o entre ejecuciones se monta o se inyecta.

## La decisión

| Elemento | Dónde vive | Justificación |
|---|---|---|
| **Código de los cuadernos** | Montado como volumen (`./notebooks`, `./src`) | Cambia varias veces por sesión de trabajo. Si viviera dentro de la imagen, cada edición exigiría reconstruirla y el ciclo de trabajo sería inviable. Además, Git ya lo versiona: meterlo en la imagen duplicaría la responsabilidad de versionado en dos lugares que terminarían desincronizados. |
| **Librerías de Python** | Ancladas en `requirements.txt`, instaladas al levantar el servicio | Son idénticas para todos: es justo lo que debe ser reproducible. Se declaran con `==` porque una versión distinta de pandas cambiaría `memory_usage(deep=True)` y haría irreproducible la ficha T1. Se instalan desde `requirements.txt` montado en modo lectura, en vez de congelarse en una imagen propia, para que el anclaje viva en un archivo legible y revisable en el *diff* de un commit. |
| **Datos crudos** | Montados como volumen (`./data`), ignorados por Git | Aquí está la tensión real. No van en la imagen porque la harían enorme y porque cambian con cada partición. No van en Git porque son binarios grandes que degradarían el repositorio de forma permanente. La respuesta es montarlos y **documentar en el README de dónde se obtienen**, con el conteo y el hash esperados para poder verificarlos. Esa separación entre "el entorno" y "el dato" es el tema de S5. |
| **Credenciales de la base** | En `.env`, inyectadas como variables de entorno | Cambian entre personas y no deben existir en ningún archivo versionado: una credencial que entra a la historia de Git queda ahí aunque después se borre el archivo. Se versiona `.env.example`, con las claves pero sin los valores, para que quien llega sepa qué debe definir sin recibir un secreto. |
| **Estado de la base** | Volumen nombrado de Docker (`db_data`) | No es código ni dato de entrada: es estado generado. No pertenece al repositorio ni a la imagen. Se le da un volumen nombrado para que sobreviva a `docker compose down` y se borre solo cuando se pida explícitamente con `-v`. Como se ve más abajo, esta decisión tiene una consecuencia que costó un fallo descubrir. |
| **Esquema SQL** | Versionado (`./sql`), montado en el punto de inicialización | Es código, no estado: define la forma de la base. Debe ser idéntico para todos y quedar en la historia de Git. Se monta en `/docker-entrypoint-initdb.d`, que PostgreSQL ejecuta una sola vez, cuando el volumen está vacío. |

## Qué debe ser idéntico y qué puede variar

**Idéntico entre máquinas:** las versiones de las librerías, la versión del motor de PostgreSQL, el esquema de la base, los puertos *internos* de los contenedores y los nombres de servicio. Si algo de esto varía, los resultados dejan de ser comparables.

**Puede variar legítimamente:** los puertos del anfitrión (por eso son `${JUPYTER_PORT}` y `${POSTGRES_PORT_HOST}`, no literales), la contraseña de la base, la ruta absoluta del repositorio en el disco y el sistema operativo del anfitrión.

Las imágenes se anclan **por digest**, no por etiqueta. `postgres:16.4-alpine` es una etiqueta que su publicador puede reasignar a otra imagen; `postgres@sha256:5660c2…` no puede cambiar. La etiqueta legible se conserva como comentario porque el digest es exacto pero ilegible.

## Reproducción en limpio · qué falló

Se probó de verdad: `docker compose down` sobre el proyecto original, clon del repositorio en otro directorio, sin `.env`, sin datos y sin variables heredadas de la terminal. **Falló dos veces antes de funcionar**, y los dos fallos eran defectos reales.

### Fallo 1 · Sin `.env`, el proyecto no fallaba: fallaba después y mal

Al levantar el clon sin haber copiado `.env`, Compose **no se detuvo**. Sustituyó las tres variables de la base por cadenas vacías y siguió adelante con tres advertencias:

```
warning: The "POSTGRES_PASSWORD" variable is not set. Defaulting to a blank string.
```

El arranque terminaba fallando después, dentro de PostgreSQL, con un error que no mencionaba `.env` en ninguna parte. Quien llegara nuevo al proyecto habría depurado el síntoma equivocado.

Se corrigió declarando las variables como obligatorias, con la sintaxis `${VARIABLE:?mensaje}`. Ahora el fallo ocurre de inmediato y dice qué hacer:

```
error while interpolating services.jupyter.environment.POSTGRES_PASSWORD:
required variable POSTGRES_PASSWORD is missing a value:
falta en .env, ejecute 'cp .env.example .env'
```

Al aplicar el arreglo apareció, de paso, una confirmación de que en YAML la puntuación es sintaxis: el mensaje de error original contenía `: `, y eso por sí solo rompió el análisis del archivo con `mapping values are not allowed in this context`. Hubo que entrecomillar el valor.

### Fallo 2 · El "clon limpio" no era limpio, y esto fue lo más instructivo

El clon levantó bien, pero el cuaderno no pudo conectarse a la base:

```
FATAL: password authentication failed for user "ideam_app"
```

La contraseña del `.env` del clon era nueva y correcta. El problema era otro: **Compose deriva el nombre del proyecto del nombre del directorio**, y el clon estaba en un directorio con el mismo nombre que el original. Por eso el volumen `proyecto-ideam-precipitacion_db_data` **no se creó: se reutilizó**. La base ya venía inicializada de la ejecución anterior, con la contraseña anterior.

Y `POSTGRES_PASSWORD` solo se aplica cuando PostgreSQL inicializa un directorio de datos vacío. Con un volumen preexistente, la variable se ignora en silencio.

Es decir: había **estado fuera del repositorio** sobreviviendo entre dos proyectos que yo creía independientes. Exactamente lo que la prueba del clon existe para atrapar. Con `docker compose down -v` para destruir el volumen, el clon levantó desde cero y el cuaderno pasó las tres verificaciones sin errores.

La consecuencia práctica quedó documentada en el README: cambiar `sql/` o la contraseña no tiene efecto sobre un volumen que ya existe, y `-v` borra los datos.

### Decisiones tomadas para evitar fallos que sí anticipé

Dos cosas se diseñaron desde el principio para no fallar, y conviene decir que **no llegaron a fallar porque se previnieron, no porque el problema no exista**:

- **Carrera de arranque.** `depends_on` a secas solo espera a que el contenedor *exista*, no a que el servicio acepte conexiones. Se añadió un `healthcheck` con `pg_isready` y `condition: service_healthy`. En los registros se observa `Container ideam_db Waiting` → `Healthy` → `ideam_jupyter Starting`, que es la secuencia buscada. Sin esto el fallo sería intermitente, y en una máquina rápida podría no aparecer nunca.
- **Comando de arranque de Jupyter.** La guía de la sesión usa `start-notebook.sh` y `--NotebookApp.token`, que corresponden a versiones anteriores de las imágenes. La imagen anclada aquí expone `start-notebook.py` y `--IdentityProvider.token`, que es la forma que este repositorio usa y la que se verificó funcionando.

### Una observación menor, para no ocultarla

La imagen de Jupyter emite en su arranque un error interno al instanciar el gestor de extensiones (`TypeError: AsyncClient.__init__() got an unexpected keyword argument 'proxies'`) y cae a un gestor de solo lectura. Viene de dentro de la imagen, no de esta configuración, y no afecta a la ejecución de cuadernos ni a ninguna verificación. Se anota porque una limitación declarada es honestidad de ingeniería y una limitación oculta es el problema que esta sesión combate.

## Lo que no se pudo verificar

- **Otro sistema operativo u otra arquitectura.** Todo se probó en macOS 27 sobre `arm64`. Las dos imágenes publican manifiestos para `amd64` y `arm64`, así que hay base razonable para esperar que funcione en un equipo Intel o en Linux, pero esperar no es haber verificado. Queda pendiente para la prueba entre compañeros.
- **Dos instancias simultáneas.** Los servicios usan `container_name` fijo (`ideam_jupyter`, `ideam_db`), de modo que dos copias del proyecto no pueden correr a la vez aunque se les cambien los puertos. Por eso la prueba del clon exigió detener antes el entorno original. Es una consecuencia asumida: nombres fijos hacen los comandos de diagnóstico más legibles para quien recién llega, a cambio de no poder levantar dos copias en paralelo.
- **La ingesta de datos.** El esquema existe y la clave primaria replica el hallazgo de T1, pero todavía no se cargan las particiones en PostgreSQL. Eso llega con las sesiones siguientes; hoy el alcance es el entorno.
