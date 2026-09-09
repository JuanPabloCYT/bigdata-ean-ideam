# Práctica S07 · Taller de decisión de paradigma

Sesión 7 · Juan Pablo Castro

Esta sesión no tiene laboratorio de software: no se levanta ningún contenedor ni se ejecuta ninguna herramienta. La práctica es un **taller de decisión de arquitectura**, y lo que queda producido es texto y tablas.

Este archivo documenta el **Nivel 1 (guiado)**: la asignación de paradigma a los cinco requerimientos del acueducto que plantea la guía del taller. Los niveles 2 y 3 y el reto de negocio se hicieron sobre el proyecto propio y viven en la tarea: [`docs/T7_paradigma.md`](../../docs/T7_paradigma.md).

> **Las cifras de esta página son del caso didáctico del acueducto, no del proyecto.** El acueducto es un caso ficticio del curso, con cifras verosímiles para practicar el criterio. Las únicas cifras medidas de verdad en este repositorio son las de la fuente del IDEAM, y esas se usan en T7, no aquí.

---

## El marco de decisión

Tres criterios. El primero manda; los otros dos afinan.

| Criterio | Qué pregunta |
|---|---|
| 1 · Umbral de frescura exigida | ¿Qué antigüedad del dato tolera el negocio? Segundos → flujo; minutos → casi real; horas o días → lotes |
| 2 · Volumen por ciclo | ¿Cuánto dato llega en cada intervalo? Un volumen enorme puede empujar hacia lotes aunque la frescura tiente al flujo |
| 3 · Costo tolerable | ¿Cuánto está dispuesto a pagar el negocio por esa frescura? Un flujo encendido cuesta más que un lote que se ejecuta y termina |

**La regla de oro:** se parte de la frescura **exigida**, no de la **deseable**. La deseable siempre es máxima y por eso no discrimina nada.

---

## Nivel 1 · Los cinco requerimientos del acueducto

### R1 · Informe mensual de consumo por sector, para planear la facturación

*Resuelto en la guía como ejemplo. Se reproduce para que la tabla quede completa.*

| Criterio | Análisis |
|---|---|
| Frescura exigida | Días. El informe se planea una vez al mes; un dato de ayer sirve igual |
| Volumen por ciclo | Alto, pero se acumula un mes y se procesa de una vez |
| Costo tolerable | Bajo. No se justifica pagar por frescura que nadie usa |
| **Paradigma** | **Lotes** |
| **Justificación** | Un informe mensual no gana nada con frescura de segundos; el lote es más barato y suficiente |

### R2 · Alerta cuando la presión de una tubería sale de rango, para evitar una rotura

| Criterio | Análisis |
|---|---|
| Frescura exigida | Segundos. Entre que la presión se dispara y que la tubería cede pasan segundos o pocos minutos; la alerta tiene que caber dentro de esa ventana |
| Volumen por ciclo | Bajo: del orden de decenas de lecturas por segundo, unos pocos sensores de presión por sector muestreando de forma continua |
| Costo tolerable | Alto, y es el único requerimiento donde lo es. El costo de una rotura —agua perdida, calle inundada, reparación de urgencia— supera con holgura el de mantener un flujo encendido |
| **Paradigma** | **Flujo** |
| **Justificación** | Si la alerta llega con diez minutos de retraso, la tubería ya reventó: el dato tardío no informa una decisión, describe un accidente |

**Por qué el volumen no lo empuja a lotes.** Este es el caso en que los tres criterios apuntan al mismo lado: la frescura exige segundos y el volumen es tan bajo que el flujo sale barato. Cuando eso pasa, la decisión no tiene tensión.

### R3 · Tablero de caudal del centro de control, que el operador mira durante su turno

| Criterio | Análisis |
|---|---|
| Frescura exigida | Minutos. El operador vigila una tendencia, no reacciona a un instante; pero un caudal de hace media hora ya no le sirve para operar |
| Volumen por ciclo | Medio: del orden de cientos de lecturas cada pocos minutos, sumando todos los puntos de medición de la red |
| Costo tolerable | Medio. Se acepta pagar por actualización frecuente, pero no por la infraestructura de baja latencia que exige R2 |
| **Paradigma** | **Casi real** (micro-lotes de pocos minutos) |
| **Justificación** | El operador necesita ver hacia dónde va el caudal, y eso se resuelve con una actualización cada pocos minutos sin montar un flujo continuo |

**Dónde está la confusión que este requerimiento enseña.** Es tentador ponerlo en flujo porque la palabra "tablero" suena a tiempo real. Pero la frescura que el negocio exige aquí es de minutos, no de segundos: el criterio que decide es qué antigüedad tolera quien usa el dato, no qué tan viva se ve la pantalla.

### R4 · Detección de posibles fugas a partir del patrón de consumo de la noche anterior

> **Este es el requerimiento ambiguo del taller, y la guía pide declarar el supuesto.**
>
> **Supuesto que tomamos:** el negocio se conforma con enterarse a la mañana siguiente. Lo suponemos porque el propio requerimiento define el patrón sobre *la noche anterior completa*: una fuga se detecta porque el consumo nocturno no baja como debería, y ese contraste solo existe cuando la noche terminó. Evaluar a media noche compararía contra una línea base incompleta y produciría falsos positivos.
>
> **Cuándo cambiaría la asignación:** si el negocio decidiera que quiere detectar la fuga durante la misma noche —para cerrar una válvula antes del amanecer y no perder seis horas de agua—, el requerimiento sube a **casi real**, con ventanas móviles de una o dos horas contra el patrón histórico. Es una decisión de negocio, no técnica.

| Criterio | Análisis |
|---|---|
| Frescura exigida | Horas, bajo el supuesto declarado. El resultado se necesita a primera hora de la mañana |
| Volumen por ciclo | Del orden de miles de lecturas por noche, todas las de la ventana nocturna de la red |
| Costo tolerable | Bajo. Un lote nocturno se ejecuta cuando el sistema está descargado y termina |
| **Paradigma** | **Lotes** (nocturno) |
| **Justificación** | El patrón se define sobre la noche completa, así que el lote nocturno no es una limitación: es la unidad natural del análisis |

### R5 · Carga del histórico de lecturas para el análisis de tendencias del último año

| Criterio | Análisis |
|---|---|
| Frescura exigida | Días. Es un análisis de tendencia anual; un dato de la semana pasada no cambia la conclusión |
| Volumen por ciclo | Muy alto: del orden de millones de lecturas en la carga inicial, y grandes bloques periódicos después |
| Costo tolerable | Bajo por registro. Es exactamente el terreno donde el lote es más eficiente |
| **Paradigma** | **Lotes** |
| **Justificación** | Los dos primeros criterios apuntan al mismo lado —frescura de días y volumen enorme—, así que no hay tensión que resolver |

---

## Salida esperada · verificación

La guía fija dos condiciones de salida para el Nivel 1:

| Condición | Estado |
|---|---|
| Los cinco requerimientos con paradigma y una frase de justificación | ✅ R1 a R5, tabla completa |
| Al menos uno en flujo y al menos tres en lotes o casi real | ✅ Flujo: R2 (1). Lotes o casi real: R1, R3, R4, R5 (4) |

**No caímos en la trampa del tiempo real.** De cinco requerimientos, uno solo justifica el flujo. La guía advierte que la respuesta fácil es ponerlo todo en flujo porque suena mejor; el reparto que sale del marco es el contrario.

### Resumen

| # | Requerimiento | Frescura exigida | Paradigma |
|---|---|---|---|
| R1 | Informe mensual de consumo por sector | Días | Lotes |
| R2 | Alerta de presión fuera de rango | Segundos | **Flujo** |
| R3 | Tablero de caudal del centro de control | Minutos | Casi real |
| R4 | Detección de fugas por el patrón nocturno | Horas *(supuesto declarado)* | Lotes |
| R5 | Carga del histórico anual | Días | Lotes |

---

## Cómo se conecta con la entrega

La §6 de la guía del taller lista cuatro elementos producidos. Dónde vive cada uno:

| Elemento de la guía | Dónde está |
|---|---|
| Los cinco requerimientos del acueducto asignados | Este archivo, Nivel 1 |
| Los requisitos del proyecto con sus cifras de frescura y volumen | [`docs/T7_paradigma.md`](../../docs/T7_paradigma.md) · Parte A (Nivel 2) |
| El paradigma del proyecto, con un compromiso CAP nombrado | [`docs/T7_paradigma.md`](../../docs/T7_paradigma.md) · Partes A y B (Nivel 3) |
| La defensa ante la gerencia (reto de negocio) | [`docs/T7_paradigma.md`](../../docs/T7_paradigma.md) · Parte C |

Los términos de la sesión están en [`docs/glosario_bilingue.md`](../../docs/glosario_bilingue.md), sección de la sesión 7.

---

## Referencias

Brewer, E. A. (2012). CAP twelve years later: How the "rules" have changed. *Computer, 45*(2), 23-29. https://doi.org/10.1109/MC.2012.37

Kleppmann, M. (2017). *Designing data-intensive applications*. O'Reilly Media.

Reis, J., y Housley, M. (2022). *Fundamentals of data engineering*. O'Reilly Media.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para estructurar y redactar este documento del taller.

El razonamiento de cada asignación se hizo con el marco de tres criterios de la guía, no copiando una tabla de referencia. Las cifras de volumen son órdenes de magnitud del caso ficticio del acueducto y están declaradas como tales al comienzo del documento, para no confundirlas con las cifras medidas de la fuente real del IDEAM que sustentan T1 a T7. El supuesto de R4 —el requerimiento que la guía deja ambiguo a propósito— se declara de forma explícita, junto con la condición bajo la cual la asignación cambiaría.
