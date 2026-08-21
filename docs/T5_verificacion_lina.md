# T5 · Verificación independiente (Lina Ramírez)

Reproduje la ingesta completa en un clon limpio aparte (`git clone` desde `origin/main`, directorio nuevo, nada preinstalado), en Windows, sin tocar el código original hasta terminar la comprobación. No encontré errores nuevos en `src/ingesta/cargar_cruda.py` ni en `docker-compose.yml`: las dos correcciones que documentó Juan Pablo en `T5_verificacion.md` (imagen de MinIO anclada por digest, CSV byte a byte sin reserializar) siguen sosteniéndose en una máquina y un sistema operativo distintos a los suyos.

## Un fallo real de entorno, no del proyecto

`pip install -r requirements.txt` falló en la instalación inicial:

```
ERROR: Could not find a version that satisfies the requirement pandas==2.2.3
...
ERROR: Could not find C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe
```

La causa: el `python` que resuelve por defecto en esta máquina es 3.14, y `pandas==2.2.3` no publica *wheel* precompilado para `cp314` en Windows — pip intenta compilarlo desde el código fuente y necesita Visual Studio Build Tools, que no están instalados. Es el mismo tipo de problema que ya describe la sección final de `T5_ejecucion.md` (ahí con Python 3.9 en macOS por la ruta contraria: muy viejo), pero en el sentido opuesto: aquí el intérprete por defecto es **más nuevo** de lo que el `requirements.txt` anticipa, no más viejo.

**Verificación, no corrección de código:** T5 solo depende de `boto3` y `requests` (ver la sección "T5 · almacenamiento de objetos" de `requirements.txt`); no necesita `pandas`. Con un entorno virtual creado explícitamente sobre Python 3.12 (`py -3.12 -m venv .venv`), `pip install -r requirements.txt` completo — pandas incluido — instaló sin problema, y la ingesta corrió igual. No cambié ninguna versión anclada del proyecto: el `requirements.txt` funciona correctamente con el intérprete que pide (`3.10` o superior, pero no *cualquiera* por encima de eso). Dejo esto documentado como un límite superior no escrito de la guía, para quien reproduzca en una máquina Windows con Python 3.14+ instalado por defecto.

## Resto de la verificación, sin hallazgos

| Prueba | Resultado |
|---|---|
| `docker compose up -d minio` con la imagen anclada por digest | Descarga y arranca sin error; healthcheck `healthy` |
| Los tres buckets se crean (`lago-crudo`, `lago-refinado`, `lago-curado`) | Correcto |
| Versionado habilitado en `lago-crudo` | `Status: Enabled` |
| Ingesta normal (`cargar_cruda.py --date 2026-06-22`) | `CARGADO` con `SHA256 · 9a8dc75af1969e21ad7e13bddd9fad0291ebbeba2a0b1418cd4237f81a5155be` — coincide exacto con el hash que T1 documentó para esa misma partición |
| Ruta particionada | `cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv`, predecible sin preguntar |
| Segunda ejecución con el mismo dato | `YA EXISTE · contenido identico · no se sobrescribe` |
| `--demo-versioning` | `VERSION NUEVA` + dos IDs en `VERSIONES RECUPERABLES`; `VERSION ANTERIOR RECUPERADA` con `SHA256 VERSION ANTERIOR` igual al original |

## Conclusión

Un clon limpio en Windows, con el intérprete correcto, reproduce el lago completo sin intervención manual: los mismos tres buckets, la misma ruta, el mismo contenido byte a byte (mismo SHA-256 que T1 y que la verificación de Juan Pablo) y el versionado activo y demostrado. El diseño de `cargar_cruda.py` no cambió; el único hallazgo es de entorno (versión de Python en Windows) y queda documentado arriba para el próximo que reproduzca, no como una corrección al código.
