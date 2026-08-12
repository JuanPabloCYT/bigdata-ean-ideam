# T3 · Proyección de almacenamiento y factor de réplica

**IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean**
Módulo 1 · Sesión 3 · Entrega grupal

**Fuente consolidada del equipo:** Precipitación del IDEAM, conjunto `s54a-sgyg` del Portal de Datos Abiertos de Colombia.

> **Pendiente de completar por el equipo.** La consolidación está en curso en [`T3_consolidacion_equipo.md`](T3_consolidacion_equipo.md), y el trabajo que falta, repartido, en [`T3_tareas_pendientes.md`](T3_tareas_pendientes.md). Los nombres de los tres integrantes y el aporte de cada uno van en la sección 10.

---

## 1. Por qué esta fuente

La fuente elegida cumple los cuatro requisitos mínimos que T1 exigía, y los cumple con evidencia medida, no declarada:

| Requisito | Cómo lo cumple | Evidencia |
|---|---|---|
| Volumen conocido | Partición diaria de 21.953.076 bytes, 141.007 registros | Medido con `os.path.getsize()`, hash SHA-256 verificado |
| Licencia clara | CC BY-SA 4.0 | Declarada en los metadatos oficiales de Socrata |
| Tasa de crecimiento conocida | −4,780861 % anual | Conteos de junio 2025 y junio 2026 por API, reconfirmados en vivo |
| Formato declarado | CSV sin comprimir, 12 columnas, esquema estable | Comparado entre dos días completos, 0 nulos, 0 duplicados en la clave |

Dos razones técnicas adicionales para preferirla:

- **Clave candidata verificada.** `codigoestacion + codigosensor + fechaobservacion` identifica unívocamente cada registro: 141.007 filas, 141.007 combinaciones únicas, 0 duplicados y 0 nulos. Eso permite ingesta incremental idempotente sin trabajo previo de limpieza, y ya está implementado como clave primaria en `sql/01_esquema.sql`.
- **Acceso por API con paginación y conteo previo.** La API de Socrata permite consultar `count(*)` antes de descargar, lo que hace verificable cada carga y barata la estimación de crecimiento.

---

## 2. Insumos de entrada

Los dos insumos de la proyección salen de la ficha T1 y **no están escritos a mano en ninguna parte**: el script los lee de `docs/T1/evidencia/resultados_medicion.json`, el archivo que produjo el cuaderno de medición.

| Insumo | Símbolo | Valor | Origen |
|---|---|---:|---|
| Tamaño de la partición diaria | S₀ | 21.953.076 bytes | `os.path.getsize()` sobre el CSV del 22/06/2026 |
| Tasa de crecimiento anual | g | −0,0478086092 | (2.971.298 / 3.120.484) − 1 |
| Tasa mensual equivalente | g_m | −0,0040741135 | (2.971.298 / 3.120.484)^(1/12) − 1 |
| Tamaño de bloque | — | 128 MB | Valor real de HDFS |
| Horizonte | — | 12 meses | Definido por el enunciado |

Condiciones de la medición: macOS 27 (`arm64`), pandas 2.2.3, 29 de julio de 2026. El detalle está en [`T1/ficha_tecnica.md`](T1/ficha_tecnica.md).

---

## 3. Definición del volumen actual

Este paso hay que declararlo, porque el enunciado pide multiplicar un «volumen actual» y **T1 no midió un repositorio acumulado: midió una partición diaria**. La propia ficha lo advierte y deja constancia de que modelar el repositorio completo exigiría un modelo aditivo que allí no se construyó. Aquí se construye.

Se define el volumen actual como **un año de operación al ritmo de hoy**:

```
V₀ = 365 × S₀ = 365 × 21.953.076 = 8.012.872.740 bytes = 7,4626 GB
```

Es la base con la que se dimensiona disco: lo que la fuente genera en doce meses.

---

## 4. Volumen a doce meses · dos modelos

El enunciado da la fórmula `volumen actual × (1 + g_mensual)^meses`. Se aplica tal cual, y además se calcula el acumulado, porque responden preguntas distintas y solo una sirve para comprar disco.

**Modelo A — fórmula del enunciado.** Cuánto *producirá* la fuente durante el año siguiente:

```
V₁₂ = V₀ × (1 + g_m)^12
```

**Modelo B — acumulado mes a mes.** Cuánto habrá que *tener guardado* al cabo de doce meses. Un repositorio de particiones diarias crece por suma, no por composición: cada mes añade sus particiones, cuyo tamaño va cambiando según la tasa.

```
V_acum = Σ (días_del_mes × S₀ × (1 + g_m)^mes)   para mes = 0 … 11
```

| Escenario | g anual | Modelo A | Modelo B |
|---|---:|---:|---:|
| Histórico | −4,780861 % | 7,1058 GB | 7,2976 GB |
| Conservador | 0 % | 7,4626 GB | 7,4626 GB |
| Sensibilidad | +1 % | 7,5372 GB | 7,4967 GB |

**Se dimensiona con el Modelo B**, que es el volumen que ocupa disco.

### Por qué tres escenarios y no uno

La tasa histórica medida es **negativa**: junio de 2026 tuvo 149.186 registros menos que junio de 2025. Proyectar doce meses con una tasa negativa da un volumen que *encoge*, y nadie dimensiona infraestructura para un dato que se contrae. Una tasa negativa puede reflejar estaciones fuera de servicio o fallos de transmisión, no una contracción permanente de la fuente.

Por eso se declaran tres escenarios y se dimensiona con el más exigente, **+1 % anual**.

**Hallazgo:** la diferencia entre el escenario más optimista y el más pesimista es de **0,2 GB, menos del 3 %**. Mientras tanto, pasar de R=1 a R=3 triplica la cifra. La elección del factor de réplica pesa mucho más que la de la tasa de crecimiento, y por eso la discusión del equipo debe centrarse ahí.

---

## 5. Tabla de proyección · almacenamiento físico por factor

```
Almacenamiento físico = volumen lógico proyectado × R
Tolerancia a fallos   = R − 1 nodos caídos sin pérdida de dato
```

Escenario de dimensionamiento (+1 % anual, Modelo B, V = 7,4967 GB):

| Factor R | Almacenamiento físico | Nodos que tolera perder | Costo relativo |
|---:|---:|---:|---:|
| 1 | **7,497 GB** | 0 · sin tolerancia | 1× |
| 2 | **14,993 GB** | 1 | 2× |
| 3 | **22,490 GB** | 2 | 3× |

Los tres escenarios completos:

| Escenario | R=1 | R=2 | R=3 |
|---|---:|---:|---:|
| Histórico (−4,78 %) | 7,298 GB | 14,595 GB | 21,893 GB |
| Conservador (0 %) | 7,463 GB | 14,925 GB | 22,388 GB |
| Sensibilidad (+1 %) | 7,497 GB | 14,993 GB | 22,490 GB |

### Verificación experimental de la fórmula

La relación `físico = lógico × R` no se da por buena: se comprobó en el clúster HDFS de la práctica, cargando el mismo archivo con los tres factores y midiendo con `hdfs dfs -du`.

| Archivo | Lógico (bytes) | Físico (bytes) | Factor medido |
|---|---:|---:|---:|
| `muestra_r1.csv` | 10.358.654 | 10.358.654 | 1,0 |
| `muestra_r2.csv` | 10.358.654 | 20.717.308 | 2,0 |
| `muestra_r3.csv` | 10.358.654 | 31.075.962 | 3,0 |

Se cumple **exactamente al byte**. Evidencia en [`../practica/s03-hdfs/resultados/n2_du_bytes.txt`](../practica/s03-hdfs/resultados/n2_du_bytes.txt).

---

## 6. Número de bloques

```
Número de bloques = ⌈ tamaño del archivo / tamaño de bloque ⌉,  bloque = 128 MB
```

| Estrategia de partición | Archivos/año | Bloques/año | Objetos en el maestro |
|---|---:|---:|---:|
| Partición diaria | 365 | 365 | 730 |
| Consolidación mensual | 12 | 60 | 72 |

Una partición diaria pesa 20,94 MB, es decir el **16,4 %** de un bloque de 128 MB.

### Una precisión que cambia la conclusión

Es habitual afirmar que un archivo pequeño «desperdicia» el resto del bloque. **En HDFS eso no ocurre.** Un bloque es una construcción lógica; el nodo de datos lo almacena como un archivo normal del sistema operativo. Una partición de 20,94 MB ocupa 20,94 MB en disco, no 128 MB. No se pierden los 107 MB restantes.

El costo real de los archivos pequeños es la **memoria del nodo maestro**, que guarda metadatos por cada archivo y cada bloque, del orden de 150 bytes por objeto:

| Estrategia | Objetos | Memoria del maestro |
|---|---:|---:|
| Partición diaria | 730 | 0,104 MB al año |
| Consolidación mensual | 72 | 0,010 MB al año |

**A esta escala el problema de los archivos pequeños no existe.** 0,1 MB de memoria al año no es una restricción para ningún clúster. El problema se vuelve real con millones de archivos, no con 365. Afirmar lo contrario sería repetir una advertencia de manual sin mirar las cifras propias.

**Decisión sobre el bloque:** mantener 128 MB, que es el valor por defecto y no hay evidencia medida para moverlo. Bajarlo para «ajustarlo» a los 20,94 MB de la partición sería el error contrario: multiplicaría los bloques sin ganar nada, porque el disco no se estaba desperdiciando. Se recomienda **consolidar las particiones diarias en archivos mensuales** una vez cerrado el mes: reduce los objetos un 90,1 % y baja de 365 a 60 bloques, lo que además favorece el paralelismo en el procesamiento distribuido de la sesión 4.

---

## 7. Recomendación de factor de réplica

**Factor 3 para el dato crudo de mediciones. Factor 2 para el dato derivado.**

### El argumento, por el valor del dato

El dato de precipitación del IDEAM es **telemetría de sensores en el tiempo**. Si se pierde la partición del 22 de junio de 2026, no hay forma de volver a capturarla: ese instante ya pasó. Es cierto que la API de Socrata permite volver a descargarla mientras el IDEAM conserve el histórico, pero eso significa **depender de un tercero sobre el que el equipo no tiene control ni acuerdo de nivel de servicio**. Un dato del que se depende y que no se puede regenerar por medios propios es, a efectos de riesgo, irrecuperable.

Los datos **derivados** —agregados por estación, consolidados mensuales, tablas de resumen— sí se regeneran ejecutando de nuevo el proceso sobre el dato crudo. Para ellos, factor 2 es suficiente: tolera una caída, y una pérdida total solo cuesta tiempo de cómputo.

### El argumento, por el costo

Lo que compra el factor 3 sobre el factor 2 es tolerar **dos caídas simultáneas en vez de una**, a cambio de **7,5 GB adicionales al año**.

A esta escala, el costo absoluto es despreciable. Se habla de decenas de gigabytes, no de terabytes. **Discutir la tercera copia para ahorrar cuesta más en horas de reunión que en disco.** La conversación sería completamente distinta si la fuente pesara 50 TB: ahí cada copia sería una línea visible del presupuesto y habría que justificarla al detalle.

El escenario que el factor 3 cubre y el 2 no es concreto y frecuente: **que falle un nodo mientras otro está en mantenimiento programado**. Con factor 2 esa combinación deja el dato inaccesible.

### La evidencia experimental que sostiene la recomendación

No es un argumento teórico. En la práctica de la sesión se detuvo un nodo que alojaba bloques y se compararon dos archivos idénticos con distinto factor:

| | `muestra_r1.csv` (R=1) | `muestra_r3.csv` (R=3) |
|---|---|---|
| Estado según `fsck` | **`CORRUPT`** | `HEALTHY` |
| Bloques perdidos | **4 de 10** | 0 |
| Replicación media | 0,6 | 2,0 |
| Lectura | **`exit=1`, 0 bytes leídos** | `exit=0`, 10.358.654 bytes |
| Integridad | — | MD5 idéntico al original |

Con factor 1 el archivo no quedó degradado: quedó **inservible**. No se recuperó un solo byte, pese a que sus 10 bloques estaban perfectamente repartidos entre tres máquinas. Repartir sin copiar no es tolerancia a fallos.

También se observó la **re-replicación automática**: al reintegrar el nodo, la replicación media volvió de 2,0 a 3,0 en unos 30 segundos, sin intervención manual.

### Alternativa de menor costo, y cuándo mirarla

Cuando el volumen crezca lo suficiente para que el almacenamiento pese en el presupuesto, conviene evaluar los **códigos de borrado** (*erasure coding*), que ofrecen una protección comparable a la triple copia ocupando alrededor de 1,5 veces el volumen original en lugar de 3. El precio es una recuperación más lenta y con más cómputo tras una falla.

No se propone hoy porque a 22,5 GB el ahorro no compensa la complejidad añadida. El umbral razonable para reevaluarlo es cuando el almacenamiento alcance el orden de los terabytes.

---

## 8. Cómo reproducir estas cifras

Requisito de la entrega: otra persona, con la ficha del equipo, debe llegar a los mismos números.

```bash
git clone https://github.com/JuanPabloCYT/bigdata-ean-ideam.git
cd bigdata-ean-ideam
python3 src/proyeccion_almacenamiento.py
```

No requiere dependencias externas ni levantar el entorno: solo Python 3. El script lee `docs/T1/evidencia/resultados_medicion.json` y vuelve a calcular todo, de modo que **las cifras de este documento no pueden desincronizarse de la ficha**. Si alguien corrige la ficha T1, la proyección cambia sola.

La salida completa está guardada en [`../practica/s03-hdfs/resultados/n3_proyeccion.txt`](../practica/s03-hdfs/resultados/n3_proyeccion.txt).

### Trazabilidad del cálculo

| Cifra | Fórmula | Sustitución |
|---|---|---|
| V₀ | 365 × S₀ | 365 × 21.953.076 = 8.012.872.740 B |
| V₁₂ acumulado, +1 % | Σ (30,4167 × S₀ × (1+g_m)^m) | = 8.049.464.… B = 7,4967 GB |
| Físico R=3 | V × 3 | 7,4967 × 3 = 22,490 GB |
| Bloques, consolidado | ⌈V / 128 MB⌉ | ⌈7,4967 GB / 128 MB⌉ = 60 |
| Tolerancia R=3 | R − 1 | 2 nodos |

---

## 9. Evidencia de la lectura en inglés

> **Pendiente.** Falta el extracto de Kleppmann (2017) asignado en Canvas. El párrafo de 80 a 120 palabras y los tres términos del glosario deben redactarse a partir de esa lectura. El glosario bilingüe acumulativo del repositorio está en [`glosario_bilingue.md`](glosario_bilingue.md), con los términos de las sesiones 3 y 4 ya incorporados y el espacio reservado para los tres de la lectura.

---

## 10. Integrantes y aportes

> **Pendiente de completar por el equipo.**

| Integrante | Aporte |
|---|---|
| Juan Pablo Castro | Fuente, ficha técnica T1, entorno reproducible T2, práctica del clúster HDFS y proyección |
| *(por definir)* | |
| *(por definir)* | |

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para el desarrollo del script de proyección, la estructura de este documento y su redacción.

Cada cifra fue verificada contra ejecución real:

- Los insumos S₀ y g provienen del cuaderno `docs/T1/medicion.ipynb`, ejecutado en el equipo del estudiante, no de una estimación generada.
- La relación `físico = lógico × R` se comprobó en un clúster HDFS de cuatro nodos levantado para la práctica, midiendo con `hdfs dfs -du`, y se cumple exactamente al byte.
- El contraste entre factor 1 y factor 3 ante la caída de un nodo se ejecutó y se conservaron las salidas de `fsck` en `practica/s03-hdfs/resultados/`.
- La proyección es reejecutable con un solo comando y lee sus entradas de la ficha, de modo que cualquiera puede rehacerla.

Ninguna cifra de este documento proviene de una descripción generada sin medición que la respalde.
