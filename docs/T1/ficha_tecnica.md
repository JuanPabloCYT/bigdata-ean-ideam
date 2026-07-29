# T1 · Ficha técnica de la fuente del proyecto

**Estudiante:** Juan Pablo Castro  
**Asignatura:** Big Data e Ingeniería de Datos  
**Fuente:** Precipitación del IDEAM (`s54a-sgyg`)  
**Fecha de consulta y medición definitiva:** 29 de julio de 2026  
**Equipo de medición:** MacBook Neo · macOS 27.0 · arquitectura `arm64`  
**Convención de unidades:** 1 MB = `1024 ** 2` bytes y 1 GB = `1024 ** 3` bytes.

> **Nota sobre el equipo de medición.** Las cifras definitivas de esta ficha fueron medidas en **macOS, sobre la MacBook Neo**, ejecutando `medicion.ipynb` el 29 de julio de 2026. Sustituyen a la medición anterior, realizada el 28 de julio de 2026 en un equipo con Windows 11. La fuente, el período, el archivo analizado, la clave candidata, la licencia y el método de estimación de \(g\) no cambiaron.

## Resumen

Se analizó un día completo, del 22 de junio de 2026 a las 00:00:00 al 23 de junio de 2026 a las 00:00:00, con el límite final excluido. La consulta devolvió 141.007 registros y produjo un CSV de 21.953.076 bytes. Este \(S_0\) representa una **partición diaria**, no el acumulado histórico. Al cargarla con pandas, el DataFrame ocupó 71.118.728 bytes según `df.memory_usage(deep=True).sum()`, por lo que el factor de expansión fue \(k=3,2395791824\).

La memoria útil disponible inmediatamente antes de la carga fue 1.609.220.096 bytes, es decir \(M=1,498703002930\) GB. La estimación histórica definitiva comparó los conteos de junio de 2025 y junio de 2026 y obtuvo \(g=-0,0478086092\) anual. Una tasa negativa no produce saturación futura en este modelo. En el escenario de sensibilidad de 1 % anual, calculado con los valores medidos en esta MacBook, una partición diaria alcanzaría \(M\) en aproximadamente 313,47 años. La comparación de dos días se conserva solamente como escenario operativo de corto plazo.

## Bloque A. Identidad de la fuente

### A.1 Origen, acceso y licencia

| Elemento | Resultado verificado |
|---|---|
| Entidad responsable | Instituto de Hidrología, Meteorología y Estudios Ambientales (IDEAM), Bogotá D. C. |
| Conjunto | Precipitación |
| Ficha oficial | <https://www.datos.gov.co/Ambiente-y-Desarrollo-Sostenible/Precipitaci-n/s54a-sgyg> |
| API CSV | <https://www.datos.gov.co/resource/s54a-sgyg.csv> |
| Metadatos | <https://www.datos.gov.co/api/views/s54a-sgyg> |
| Formato medido | CSV sin compresión, descargado mediante la API Socrata |
| Licencia declarada | Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0) |
| Términos de licencia | <http://creativecommons.org/licenses/by-sa/4.0/legalcode> |

La licencia permite compartir y adaptar el material con atribución y bajo la misma licencia. Además, la descripción oficial indica que los datos pueden consumirse libremente, pero advierte que corresponden a datos crudos de sensores, pueden presentar retrasos, errores o inconsistencias y no deben utilizarse como evidencia jurídica de fenómenos hidrometeorológicos. El uso y la interpretación posterior quedan bajo responsabilidad de quien consume los datos.

Los metadatos oficiales se conservaron sin reescritura en `evidencia/metadata_dataset.json`.

### A.2 Columnas y mecanismo de descarga

La consulta de descubrimiento fue:

```text
https://www.datos.gov.co/resource/s54a-sgyg.csv?$limit=10
```

Se verificaron 12 nombres internos reales:

```text
codigoestacion, codigosensor, fechaobservacion, valorobservado,
nombreestacion, departamento, municipio, zonahidrografica,
latitud, longitud, descripcionsensor, unidadmedida
```

La descarga principal usó paginación de 50.000 filas y el siguiente conjunto exacto de parámetros:

```text
$where=fechaobservacion >= '2026-06-22T00:00:00'
       AND fechaobservacion < '2026-06-23T00:00:00'
$order=fechaobservacion,codigoestacion,codigosensor,:id
$limit=50000
$offset=0, 50000 y 100000
```

`:id` se usó solamente como desempate interno de Socrata. Las URL completas de la primera y última página, los conteos y los hashes están en `evidencia/consulta_descarga.txt`.

### A.3 Frecuencia declarada y observada

Los metadatos declaran una **actualización diaria**. La descripción del conjunto afirma que contiene registros de lluvia cada diez minutos. En la muestra, después de ordenar por estación, sensor y fecha, la frecuencia observada fue distinta:

| Medición observada | Resultado |
|---|---:|
| Moda | 1 minuto |
| Mediana | 2 minutos |
| Proporción del intervalo modal | 44,164655 % |
| Proporción de intervalos de 10 minutos | 42,955084 % |

Por tanto, no se afirma que todos los registros tengan exactamente diez minutos de separación. La coexistencia de intervalos de 1, 2, 10 minutos y otros valores evidencia una periodicidad irregular en el día analizado.

### A.4 Comparación del esquema

Se compararon los días completos del 21 y 22 de junio de 2026. Los dos archivos presentaron las mismas 12 columnas, en el mismo orden, con los mismos tipos inferidos por pandas. En ambos períodos la proporción de nulos fue 0 para todas las columnas. Esta comparación aporta evidencia puntual, pero no garantiza estabilidad absoluta para toda la historia.

El detalle por columna está en `evidencia/comparacion_esquema.csv`.

### A.5 Clave candidata

Se evaluó:

```text
codigoestacion + codigosensor + fechaobservacion
```

| Verificación | Resultado |
|---|---:|
| Filas | 141.007 |
| Combinaciones únicas | 141.007 |
| Filas en grupos duplicados | 0 |
| Porcentaje de filas duplicadas | 0,000000 % |
| Nulos en `codigoestacion` | 0 |
| Nulos en `codigosensor` | 0 |
| Nulos en `fechaobservacion` | 0 |

La combinación es una clave candidata única y completa en el período medido. No se generaliza este resultado a todo el histórico sin una comprobación adicional.

### A.6 Datos personales

La revisión de nombres y descripciones de columnas no encontró campos de ciudadanos, documentos, teléfonos o correos. Los datos describen estaciones, sensores, fecha, ubicación geográfica y mediciones de precipitación. `nombreestacion` identifica una estación meteorológica, no una persona. No se identificaron datos personales en el alcance revisado.

## Bloque B. Mediciones propias

### B.1 Período y perfil del archivo

| Elemento | Valor |
|---|---:|
| Inicio inclusivo | 2026-06-22 00:00:00 |
| Fin exclusivo | 2026-06-23 00:00:00 |
| Registros | 141.007 |
| Filas del DataFrame | 141.007 |
| Columnas | 12 |
| Columnas de texto inferidas | 7 |
| Proporción de columnas de texto | 58,333333 % |

Los tipos inferidos fueron: `int64` para los códigos de estación y sensor; `float64` para valor, latitud y longitud; y `object` para fecha, nombres geográficos, descripción del sensor y unidad.

### B.2 \(S_0\), memoria del DataFrame y \(k\)

\(S_0\) es el tamaño del archivo correspondiente al 22 de junio de 2026. No representa el tamaño total de la fuente ni del repositorio acumulado.

| Medición | Bytes | MB (`1024 ** 2`) | GB (`1024 ** 3`) |
|---|---:|---:|---:|
| Archivo CSV \(S_0\) | 21.953.076 | 20,936084747 | 0,020445395261 |
| DataFrame con memoria profunda | 71.118.728 | 67,824104309 | 0,066234476864 |

El código ejecutado fue:

```python
S0_bytes = os.path.getsize(MAIN_PATH)
df = pd.read_csv(MAIN_PATH, low_memory=False)
memory_dataframe_bytes = df.memory_usage(deep=True).sum()
k = memory_dataframe_bytes / S0_bytes
```

La sustitución de \(k\) fue:

```text
k = 71.118.728 / 21.953.076
k = 3,239579182434389
```

**Por qué \(S_0\), la memoria del DataFrame y \(k\) coinciden con la medición anterior.** Las tres cifras se remidieron en macOS y resultaron idénticas a las obtenidas en Windows. No es una omisión: es el resultado esperado y verificable.

- \(S_0\) es el tamaño del mismo archivo. Se comprobó que el CSV conserva el hash SHA-256 `9a8dc75af1969e21ad7e13bddd9fad0291ebbeba2a0b1418cd4237f81a5155be`, por lo que es byte a byte el mismo archivo del 22 de junio de 2026 y `os.path.getsize()` devuelve necesariamente el mismo valor. El archivo no se volvió a descargar, precisamente para no alterar \(S_0\).
- `df.memory_usage(deep=True).sum()` es determinista dados los mismos datos y la misma versión de pandas. Ambas mediciones usaron **pandas 2.2.3**, y en las dos plataformas los tipos son de 64 bits, de modo que enteros, flotantes y punteros a objeto ocupan lo mismo. Los tipos inferidos fueron idénticos en las dos ejecuciones.
- \(k\) es el cociente de dos cantidades idénticas, así que también coincide.

La única magnitud de esta ficha que depende realmente de la máquina es \(M\), y esa sí cambió. Se fijó deliberadamente pandas 2.2.3 en macOS para que la plataforma fuera la única variable; usar una versión mayor distinta de pandas habría alterado \(k\) por un cambio de semántica de la librería y no por un cambio de equipo.

### B.3 Memoria útil \(M\)

La medición se ejecutó inmediatamente antes de `pd.read_csv`:

```python
vm_before = psutil.virtual_memory()
M_bytes = vm_before.available
```

| Condición | Valor |
|---|---:|
| Equipo | MacBook Neo · macOS 27.0 · `arm64` |
| Fecha y hora local | 2026-07-29 15:17:10, UTC-05:00 |
| RAM total observada por el sistema | 8.589.934.592 bytes |
| Memoria disponible \(M\) | 1.609.220.096 bytes |
| Memoria disponible en GB (`1024 ** 3`) | 1,498703002930 GB |
| Uso de memoria | 81,3 % |

Esta es la diferencia sustantiva entre las dos mediciones: el equipo Windows anterior reportaba 17.042.010.112 bytes de RAM total, mientras que esta MacBook reporta 8.589.934.592 bytes. Con 81,3 % de uso en el momento de la medición, la memoria realmente disponible para el proceso fue de 1,50 GB, no los 8 GB de la etiqueta. **\(M\) es lo que queda, no lo que dice la etiqueta.**

Entre los procesos con mayor memoria RSS al momento de medir estaban el cliente de escritorio de Claude y sus procesos auxiliares, varios procesos `claude` de línea de comandos y el propio intérprete `python3.12` que ejecutaba el cuaderno. Solo se registraron nombre, PID y RSS; no se consultaron líneas de comandos ni datos privados, y no se cerró ningún programa. El detalle está en `evidencia/procesos_memoria.csv`.

En macOS, `psutil` devuelve `memory_info = None` para los procesos que el usuario no tiene permiso de inspeccionar. El cuaderno los omite de ese inventario en lugar de interrumpirse. Esa restricción afecta únicamente la tabla de procesos, que es evidencia de contexto; no afecta a \(M\), que proviene de `psutil.virtual_memory().available` y se mide antes de recorrer los procesos.

A diferencia de la entrega anterior, la sensibilidad **no usa una línea base fijada aparte**: emplea directamente la \(M\) medida en esta ejecución, junto con la \(k\) y el \(S_0\) medidos sobre el mismo archivo.

## Bloque C. Crecimiento y umbral

### C.1 Método y tasa histórica \(g\)

La estimación definitiva usa el mismo mes calendario en años consecutivos. Los conteos se obtuvieron con `$select=count(*)`; no fue necesario descargar ambos meses completos.

| Valor | Junio de 2025 | Junio de 2026 |
|---|---:|---:|
| Inicio inclusivo | 2025-06-01 | 2026-06-01 |
| Fin exclusivo | 2025-07-01 | 2026-07-01 |
| Registros | 3.120.484 | 2.971.298 |

Transcurrió un período anual, equivalente a 12 meses. La tasa anual fue:

```text
g_anual = (2.971.298 / 3.120.484) ** (1 / 1) - 1
g_anual = -0,04780860917729424
g_anual = -4,780860917729 %
```

La tasa mensual equivalente fue:

```text
g_mensual = (2.971.298 / 3.120.484) ** (1 / 12) - 1
g_mensual = -0,00407411349065856
g_mensual = -0,407411349066 %
```

La tasa histórica medida es negativa: el mismo mes tuvo menos registros en 2026. Esto puede reflejar disponibilidad de estaciones, transmisión o cobertura y no necesariamente una contracción permanente de la fuente.

La variación entre los días 21 y 22 de junio de 2026 (`0,876398878044 %` por día basada en tamaño) se conserva únicamente como escenario operativo de corto plazo, no como tendencia histórica.

### C.2 Horizonte histórico y sensibilidad

La fórmula para una tasa positiva es:

```python
t_umbral = math.log(M / (k * S0)) / math.log(1 + g)
```

Con \(g_{\text{histórico}}=-0,0478086092\), no existe un horizonte futuro de saturación: mantener esa tasa reduciría el tamaño de la partición representativa. Por ello no se fuerza la fórmula con la tasa negativa.

Como escenario explícito de referencia se usó un crecimiento de 1 % anual, calculado con los valores medidos en esta MacBook: \(M=1,498703002930\) GB, \(k=3,239579182434\), \(S_0=0,020445395261\) GB y \(g=0,01\). \(M\) y \(S_0\) están en la misma unidad, \(k\) es adimensional y el resultado está en años:

```text
t_umbral_1% =
log(1,498703002930 / (3,239579182434 × 0,020445395261))
---------------------------------------------------------
log(1 + 0,01)

t_umbral_1% = 313,4724129716826 años
```

| Escenario anual | Horizonte de una partición diaria |
|---:|---:|
| Histórico: −4,780861 % | No existe horizonte futuro |
| 1 % | 313,472413 años |
| 2 % | 157,512141 años |
| 5 % | 63,929980 años |
| 10 % | 32,726349 años |

El horizonte se acortó respecto de la medición anterior en Windows, que arrojaba 474,390960 años con 1 % anual. La causa es única y verificable: \(k\) y \(S_0\) son idénticos en las dos mediciones, de modo que toda la diferencia proviene de \(M\), que pasó de 7,431983948 GB a 1,498703002930 GB. Es exactamente lo que la fórmula predice, y refuerza la tesis de la sesión 1: el umbral no es una propiedad del dato, sino del binomio dato–equipo.

El escenario diario de corto plazo arroja 357,463084 días con la memoria medida en esta ejecución, pero no se interpreta como tendencia histórica.

### C.3 Interpretación y limitaciones

La muestra ocupa alrededor de 67,82 MB en pandas frente a 1,50 GB disponibles en esta ejecución, por lo que el día medido se procesa con margen en esta MacBook: la partición expandida consume cerca del 4,4 % de la memoria útil. El margen es menor que en el equipo Windows anterior, pero sigue siendo amplio para una partición diaria. La recomendación inmediata es una ingesta incremental por `fechaobservacion`, con comprobaciones de conteo, esquema y unicidad.

\(S_0\) describe una partición diaria. El horizonte pregunta cuándo **una partición diaria representativa**, expandida en pandas, alcanzaría \(M\) si aumentara a una tasa positiva. No modela cuándo se llenará el repositorio completo.

Un pipeline incremental incorpora nuevas particiones y su almacenamiento total crece principalmente por suma acumulativa. Modelar el repositorio completo exigiría medir su tamaño acumulado, política de retención y crecimiento del número y tamaño de las particiones; esos datos no forman parte de esta medición. No se afirma que el repositorio completo crezca exponencialmente.

Aunque la tasa histórica usa meses comparables, solo incluye dos observaciones anuales y puede verse afectada por cobertura y transmisión. Los horizontes positivos son sensibilidad, no predicciones. La unicidad de la clave y la estabilidad del esquema se comprobaron únicamente en los períodos indicados.

\(M\) es una medición instantánea y depende de la carga del equipo en ese momento. Con 81,3 % de memoria en uso, un equipo más descargado habría arrojado una \(M\) mayor y por tanto un horizonte más largo. Por eso se reportan la fecha, la hora y los procesos con mayor RSS: la cifra solo es interpretable junto con las condiciones en que se tomó.

## Entorno de la medición definitiva

| Elemento | Valor |
|---|---|
| Equipo | MacBook Neo |
| Sistema operativo | `macOS-27.0-arm64-arm-64bit` |
| Python | 3.12.8 |
| pandas | 2.2.3 |
| psutil | 7.2.2 |
| requests | 2.32.5 |
| Fecha y hora de ejecución | 2026-07-29 15:17:07, UTC-05:00 |

La versión de pandas se fijó deliberadamente en 2.2.3, la misma de la medición anterior, para que el cambio de equipo fuera la única variable. La versión de Python difiere (3.12.8 en macOS frente a 3.13.3 en Windows) y se declara por transparencia; no afecta a `memory_usage(deep=True)`, cuyo resultado depende de los datos y de la versión de pandas.

## Procedimiento de reproducción

1. Ejecutar `medicion.ipynb` con Python 3.12 o superior y las dependencias registradas, fijando `pandas==2.2.3`.
2. Consultar los conteos de ambos días antes de descargar.
3. Descargar por páginas usando `$where`, `$order`, `$limit` y `$offset`. Si el CSV ya existe y su conteo coincide con el de la API, el cuaderno lo reutiliza y no vuelve a descargarlo, de modo que \(S_0\) se conserva.
4. Verificar que el total descargado coincida con el conteo de la API.
5. Medir \(S_0\) con `os.path.getsize`.
6. Medir \(M\) con `psutil.virtual_memory().available`, inmediatamente antes de cargar el CSV.
7. Cargar el CSV principal y medir memoria con `df.memory_usage(deep=True).sum()`.
8. Consultar por API los conteos de junio de 2025 y junio de 2026.
9. Recalcular \(k\), \(g\) y los escenarios de \(t_{\text{umbral}}\) con las fórmulas mostradas.

## Declaración de uso de inteligencia artificial

> Para la estructuración metodológica, generación inicial de código y revisión de redacción se utilizaron Codex de OpenAI y ChatGPT. Para la remedición en macOS del 29 de julio de 2026 se utilizó Claude Code, que adaptó el cuaderno a la plataforma —reutilización del CSV ya descargado y manejo de los procesos que `psutil` no puede inspeccionar en macOS—, lo ejecutó y actualizó esta ficha. Todas las cifras reportadas fueron obtenidas mediante código ejecutado en el equipo del estudiante y verificadas contra las salidas visibles del cuaderno `medicion.ipynb`. Ninguna cifra fue proporcionada por un asistente sin haber sido medida.
