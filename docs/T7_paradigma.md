# T7 · Decisión de paradigma del proyecto

**Equipo:** `bigdata-ean-ideam`
**Integrantes:** Juan Pablo Castro, Camilo Rojas, Lina Ramírez
**Proyecto:** Precipitación del IDEAM (`s54a-sgyg`, Portal de Datos Abiertos de Colombia)
**Fecha:** 2026-09-07

> Este documento es el primer ladrillo del documento de arquitectura del hito de la sesión 8. Verificación por criterio de aceptación, no por rúbrica.

---

## 0. Supuestos declarados

- **El pipeline medido hasta T6 es enteramente por lotes** (ingesta diaria a `lago-crudo`, refinado a Parquet, curación de agregados). Esta tarea no cambia esa arquitectura ya construida: añade, sobre el papel, un requisito de negocio nuevo —alerta temprana— que hoy el proyecto no implementa, para poder mostrar una asignación de paradigma que no caiga en el "todo por lotes porque es lo que ya tenemos".
- **El requisito de alerta se apoya en un canal de telemetría de estación, no en la API histórica de Socrata medida en T1.** Los metadatos oficiales del conjunto (`docs/T1/evidencia/resultados_medicion.json`, campo `frecuencia_actualizacion: "Diaria"`) declaran que el histórico consolidado se publica una vez al día. La misma descripción oficial, sin embargo, dice textualmente que el dato "puede ser útil para... apoyar sistemas de alerta temprana" y advierte que "es posible que los datos aquí dispuestos tengan cierto retraso en el tiempo debido a las frecuencias de envío de datos de los sensores y los medios de transmisión utilizados". Se supone que un requisito real de alerta se conectaría a la telemetría de estación (el mismo IDEAM u otro proveedor), no al extracto diario que hoy consume el proyecto. Se declara así para no fingir una cifra de frescura que la fuente medida no ofrece.
- **El número de estaciones activas a nivel nacional (orden de un centenar) se deriva por aritmética de cifras medidas en T1**, no es una cifra nueva medida: 141.007 registros/día ÷ 1.440 minutos/día ≈ 98 registros/minuto en promedio; con la moda observada de 1 lectura/minuto/estación (44,16 % de los intervalos), eso implica del orden de 100 a 200 estaciones activas simultáneamente el día medido.
- **"Cuenca urbana priorizada" es un caso de uso hipotético** para esta tarea (el proyecto no ha seleccionado una cuenca específica). Se supone un conjunto de ~10 estaciones en esa cuenca, como orden de magnitud razonable frente al total nacional, no como cifra medida.

---

## Parte A · Tabla de asignación de paradigma

| Requisito | Frescura exigida | Volumen por ciclo | Paradigma | Justificación en una frase |
|---|---|---|---|---|
| Alerta automática de creciente súbita por lluvia intensa puntual, para activar el protocolo de gestión del riesgo | Segundos (≤ 30-60 s entre la lectura del sensor y la evaluación del umbral) | Decenas de registros por minuto en la cuenca priorizada (≈10 estaciones × 1 lectura/min, según la moda medida en T1) | Flujo | El tiempo de concentración de una cuenca urbana de alta pendiente es de minutos; un retraso de un solo minuto ya reduce la ventana de evacuación |
| Panel operativo de precipitación para el operador de turno de gestión del riesgo | Minutos (actualización cada 2-5 min) | Del orden de cientos de registros cada 5 minutos a nivel nacional (≈98 registros/min medidos × 5) | Casi real | El operador necesita ver la tendencia de la lluvia, no reaccionar al segundo; una demora de un par de minutos no cambia su decisión |
| Ingesta diaria de la partición cruda al lago de datos (`lago-crudo` → `lago-refinado`, T5-T6) | Horas (disponible a la mañana siguiente es suficiente) | ≈141.000 registros, ≈22 MB por día (medido en T1, `S0=21.953.076` bytes) | Lotes | La fuente de Socrata solo publica una vez al día; consultar más seguido no trae dato nuevo, solo cuesta cómputo |
| Reporte mensual de precipitación promedio por departamento, para planeación e informes de gerencia | Días (se calcula sobre el mes ya cerrado) | ≈4,2 millones de registros de entrada por mes (141.007 × ~30 días); salida agregada de unas pocas decenas de filas por departamento | Lotes | Es una agregación estadística sobre un período cerrado: calcularla con un día de rezago no cambia el resultado |

**Paradigma del proyecto en conjunto:** **Híbrido**. La columna dominante es lotes (ingesta, refinado, curación, reportes), que es lo que hoy sostiene todo el pipeline de T5-T6. El único requisito que exige flujo real es la alerta de creciente súbita, y el panel operativo se resuelve con casi real (micro-lotes de pocos minutos), sin necesitar la misma infraestructura de baja latencia que la alerta. El híbrido no es indecisión: nace de que un mismo proyecto de precipitación sirve tanto a la analítica de largo plazo (lotes) como a la gestión del riesgo (flujo/casi real), y esas dos necesidades tienen frescuras que difieren en varios órdenes de magnitud.

---

## Parte B · Compromiso del teorema CAP

- **Requisito sobre el que se decide:** alerta automática de creciente súbita por lluvia intensa puntual.
- **Bajo una partición de red, elegimos:** disponibilidad (seguir respondiendo con el último valor conocido, que puede estar desactualizado).
- **Por qué en este requisito:** si el servicio de alerta elige consistencia y deja de responder mientras dura la partición, el resultado no es "un dato viejo pero seguro": es silencio total durante justo la ventana en la que una creciente puede estar formándose. Un falso negativo por apagón del sistema es más peligroso para la gestión del riesgo que una lectura con algunos segundos o minutos de rezago, porque el operador puede descartar un dato marcado como desactualizado, pero no puede reaccionar a una alerta que nunca llegó. Esto además es coherente con lo que la propia fuente ya advierte en sus metadatos: que los datos "pueden tener cierto retraso" por la transmisión de los sensores, así que un sistema construido sobre esta fuente ya tiene que tolerar cierta obsolescencia, no fingir que puede eliminarla deteniéndose.

---

## Parte C · Defensa ante la gerencia

**El requisito crítico.** La alerta de creciente súbita por lluvia intensa puntual es el único requisito del proyecto que exige frescura de segundos. Lo exige porque, en una cuenca urbana de alta pendiente, el tiempo de concentración —el tiempo entre que empieza a llover fuerte y el agua llega al punto crítico aguas abajo— se mide en minutos, no en horas. Si el sistema tarda en evaluar el umbral lo mismo que tarda el agua en llegar, la alerta deja de ser una alerta: es un registro histórico de algo que ya pasó.

**El costo de no tenerla.** Si ese dato llega con el mismo rezago que el resto del pipeline (horas, como la ingesta diaria), la alerta se dispararía después de que la creciente ya ocurrió. No es una degradación de calidad de servicio: es la diferencia entre dar tiempo para evacuar una zona y no darlo. Ese es un costo que no se mide en gigabytes ni en pesos de infraestructura, y por eso no compite en la misma escala que el ahorro de poner todo por lotes.

**El resto por lotes.** Los otros tres requisitos —el panel operativo, la ingesta diaria al lago y el reporte mensual por departamento— no tienen esa urgencia. La fuente de Socrata que alimenta la ingesta solo se actualiza una vez al día (`frecuencia_actualizacion: "Diaria"`, medido en T1), así que consultarla en flujo no traería un solo dato nuevo, solo cómputo corriendo en vano. El reporte mensual se calcula sobre un mes ya cerrado: da exactamente el mismo número si se ejecuta el día 1 o el día 3 del mes siguiente. Manteniendo estos tres por lotes, el equipo evita pagar por infraestructura de streaming (colas, procesamiento continuo, monitoreo de baja latencia) donde el negocio nunca la va a usar: se ahorra el costo de operar en tiempo real sobre el 99 % del volumen del proyecto (los ≈141.000 registros diarios y los ≈4,2 millones mensuales), reservando esa inversión solo para la porción de datos —decenas de registros por minuto en una cuenca priorizada— donde de verdad se necesita.

**La conclusión.** Poner todo por flujo costaría operar infraestructura de baja latencia para reportes mensuales y para una ingesta que la propia fuente solo entrega una vez al día: se pagaría por una frescura que nadie va a consumir. Poner todo por lotes, en cambio, no ahorra dinero de forma segura: traslada el riesgo de una creciente no advertida a la comunidad, que es un costo que no aparece en la factura de la nube pero sí en el balance real del proyecto. El híbrido paga la infraestructura de flujo solo donde el tiempo de reacción tiene consecuencias irreversibles, y usa lotes —más barato y más simple de operar— en todo lo demás, que es la mayor parte del volumen del proyecto.

---

## Autoverificación antes de entregar

- [x] Hay al menos tres requisitos, cada uno con paradigma y una frase de justificación.
- [x] Cada requisito tiene sus dos cifras: frescura exigida y volumen por ciclo, sin celdas vacías.
- [x] La frescura declarada es la exigida por el negocio, no la deseable. No todo quedó en segundos sin razón.
- [x] Se nombra un compromiso CAP concreto, aplicado a un requisito real, con su porqué.
- [x] La defensa sostiene la decisión con qué se rompe sin la frescura crítica, no con la novedad del tiempo real.
- [x] Los supuestos que se tomaron están declarados en la sección 0.

---

## Referencias

Brewer, E. A. (2012). CAP twelve years later: How the "rules" have changed. *Computer, 45*(2), 23-29. https://doi.org/10.1109/MC.2012.37

Kleppmann, M. (2017). *Designing data-intensive applications*. O'Reilly Media.

Reis, J., y Housley, M. (2022). *Fundamentals of data engineering*. O'Reilly Media.

Instituto de Hidrología, Meteorología y Estudios Ambientales (IDEAM). Metadatos del conjunto Precipitación (`s54a-sgyg`), Portal de Datos Abiertos de Colombia. Consultado y conservado en `docs/T1/evidencia/metadata_dataset.json` y `docs/T1/evidencia/resultados_medicion.json`.

---

## Declaración de uso de asistentes de inteligencia artificial

- **Herramienta usada:** Claude Code.
- **En qué parte:** estructura y redacción de este documento, y el cálculo aritmético de las cifras derivadas (registros por minuto, número de estaciones estimado, volumen mensual agregado) a partir de las mediciones ya existentes en `docs/T1/evidencia/resultados_medicion.json`.
- **Qué se verificó:** las cifras de volumen y frecuencia citadas (141.007 registros/día, `S0=21.953.076` bytes, moda de intervalo de 1 minuto, `frecuencia_actualizacion: "Diaria"`) provienen directamente de la ficha T1 ya medida y verificada por el equipo, no de una estimación nueva. Las cifras del requisito de alerta (segundos de frescura, ~10 estaciones en una cuenca priorizada) son un supuesto de diseño declarado explícitamente en la sección 0, no una medición: el proyecto no opera hoy un canal de telemetría en tiempo real.
