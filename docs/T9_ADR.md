# T9 · ADR-001 — Arquitectura híbrida de procesamiento

**Proyecto:** Precipitación del IDEAM (`s54a-sgyg`)  
**Curso:** IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean  
**Estado:** Aceptado  
**Fecha:** 2026-09-09

## 1. Contexto

En T7 se identificaron cuatro requisitos con necesidades de frescura diferentes: una alerta de precipitación que requiere respuesta en segundos, un panel operativo que puede actualizarse cada 2–5 minutos, la ingesta diaria de la fuente histórica y el cálculo mensual de promedios por departamento.

La fuente histórica utilizada por el proyecto se publica mediante una API de datos abiertos con actualización diaria. En T1 se midió una partición de 141.007 registros y 21.953.076 bytes. Por tanto, el problema arquitectónico no está dominado por volumen sino por la diferencia entre los requisitos de frescura.

T8 consolidó la arquitectura de referencia: una vía principal por lotes y un componente de flujo acotado para el requisito de alerta.

## 2. Problema / decisión a tomar

Se debe decidir qué paradigma y arquitectura de procesamiento utilizar para atender simultáneamente el histórico y los requisitos operativos, evitando introducir infraestructura distribuida o duplicación de lógica que no esté justificada por las necesidades reales del proyecto.

La decisión debe ser trazable a las mediciones de T1–T7 y debe distinguir entre lo que actualmente está implementado y lo que queda diseñado para una futura fuente de telemetría.

## 3. Alternativas consideradas

### Alternativa A — Arquitectura principalmente batch

Mantener todo el procesamiento sobre la vía histórica por lotes.

**Ventajas:** simplicidad, bajo costo operativo, reutilización de los componentes existentes y buena trazabilidad del histórico.

**Desventaja:** no cumple por sí sola el requisito de alerta con frescura de segundos.

**Resultado:** descartada como arquitectura completa.

### Alternativa B — Lambda

Mantener una vía batch y agregar una vía de velocidad que replique parte de la lógica para producir resultados rápidos.

**Ventajas:** permite combinar resultados de batch y velocidad cuando ambos representan vistas del mismo dato y necesitan reconciliación.

**Desventajas:** duplica lógica, aumenta la infraestructura y agrega complejidad de operación.

**Resultado:** descartada porque la alerta no es una versión rápida del mismo resultado histórico. Es un cálculo distinto, sobre telemetría distinta y para una decisión operacional distinta.

### Alternativa C — Kappa

Convertir el procesamiento en una arquitectura orientada completamente a eventos, manteniendo el flujo como fuente principal.

**Ventajas:** un solo camino de procesamiento y buena adaptación a datos que llegan continuamente.

**Desventajas:** no encaja con una fuente histórica cuya publicación es diaria ni con agregaciones sobre períodos cerrados. También obligaría a tratar como flujo un dato que actualmente no llega como flujo.

**Resultado:** descartada.

### Alternativa D — Data Mesh

Organizar la plataforma alrededor de múltiples dominios propietarios del dato y gobierno federado.

**Ventajas:** puede ser apropiada para organizaciones grandes con múltiples dominios y equipos independientes.

**Desventajas:** introduce una estructura organizativa que el proyecto no necesita. El caso actual tiene un dominio principal, una fuente y un equipo pequeño.

**Resultado:** descartada para el alcance actual.

### Alternativa E — Arquitectura híbrida: batch + flujo acotado

Mantener el histórico en batch y utilizar flujo únicamente para el requisito que exige segundos.

**Ventajas:** cada requisito recibe el paradigma que realmente necesita; se evita duplicar el procesamiento histórico y se mantiene acotada la complejidad.

**Desventajas:** existen dos vías de procesamiento que deben gobernarse y documentarse para evitar diferencias semánticas.

**Resultado:** seleccionada.

## 4. Decisión

**Se adopta una arquitectura híbrida con dominancia de lotes:**

1. La fuente histórica IDEAM/Socrata continúa por una vía **batch**.
2. La capa `raw` conserva el dato histórico original y permite reproducibilidad.
3. La capa refinada utiliza **Parquet con Zstandard (Zstd)**, de acuerdo con la medición de T6.
4. Las consultas y agregaciones históricas se mantienen en procesamiento por lotes.
5. El requisito del panel operativo se atiende mediante procesamiento **casi real** en ventanas de 2–5 minutos, sin crear una segunda implementación completa de la lógica histórica.
6. La alerta de precipitación súbita se atiende mediante un componente **de flujo** independiente y acotado.
7. El componente de flujo se considera **planificado**, porque la fuente de telemetría continua todavía no forma parte de la implementación actual del proyecto.

La decisión no consiste en adoptar una plataforma de streaming completa. Consiste en introducir flujo solamente donde la frescura de segundos lo hace necesario.

## 5. Evidencia que soporta la decisión

| Evidencia | Resultado | Implicación arquitectónica |
|---|---|---|
| T1 · Tamaño diario | 141.007 registros y 21.953.076 bytes | El histórico puede manejarse como particiones batch. |
| T1 · Frecuencia declarada | Diaria | No se justifica convertir la fuente histórica en un flujo continuo. |
| T4 · Combinador | Shuffle de 2.398.815 B → 5.080 B | El procesamiento distribuido debe optimizarse donde aporte valor; no se adopta complejidad sin evidencia. |
| T5 · Lago | Capa raw inmutable | Se conserva trazabilidad y reproducibilidad del dato original. |
| T6 · Parquet | 93,5× más rápido que CSV en la consulta medida | La capa refinada favorece consultas analíticas sin necesidad de una capa de velocidad adicional. |
| T6 · Codec | Zstd seleccionado por equilibrio medido | Se mantiene Zstd como codec de referencia. |
| T7 · Requisitos | 1 requisito de segundos y 3 de horas/días | La arquitectura debe ser híbrida, con predominio batch. |

## 6. Compromiso CAP para el componente crítico

Para el componente de alerta se adopta como criterio de diseño priorizar **Availability** sobre **Consistency** durante una partición de red.

La razón es operacional: para una alerta crítica es preferible que el sistema pueda entregar el último valor conocido, claramente marcado como **stale/desactualizado**, antes que dejar de responder por exigir consistencia inmediata.

Esto no significa ignorar la consistencia. La información utilizada para una alerta debe registrar su marca temporal y estado de frescura para que un consumidor pueda distinguir un dato actual de uno retenido temporalmente.

Este compromiso aplica al camino crítico de alerta; no redefine las garantías del procesamiento histórico por lotes.

## 7. Consecuencias

### Positivas

- La arquitectura responde a cada requisito según su frescura real.
- El histórico mantiene un camino sencillo, reproducible y medible.
- Se evita implementar Lambda sin una necesidad de reconciliación entre batch y velocidad.
- Se evita Kappa para una fuente que actualmente se publica por lotes.
- El componente de flujo queda limitado al caso que realmente exige segundos.
- Se conserva la inversión realizada en T1–T7.

### Negativas

- Existen dos paradigmas de procesamiento que deberán mantenerse coordinados.
- La vía de flujo requerirá infraestructura adicional cuando se implemente la telemetría.
- Puede existir una diferencia temporal o semántica entre la alerta y el consolidado histórico si sus fuentes no están alineadas.
- El componente de flujo deberá incorporar mecanismos de trazabilidad y auditoría.

### Compromisos de implementación

- Documentar en un único lugar la definición de los umbrales de alerta.
- Registrar timestamps y estado de frescura en los eventos de flujo.
- Cuando se implemente la telemetría, conservar sus eventos en el lago para permitir auditoría posterior.
- Revisar esta decisión si aumentan sustancialmente el número de dominios, fuentes o requisitos de tiempo real.

## 8. Estado y criterios de revisión

**Estado:** Aceptado para el alcance actual del proyecto.

La decisión debe revisarse si ocurre alguno de estos cambios:

- la fuente histórica comienza a publicar eventos continuamente;
- aparecen múltiples requisitos de tiempo real que compartan la misma lógica de negocio;
- el volumen o frecuencia supera significativamente las mediciones utilizadas en T1–T7;
- aparecen múltiples dominios y equipos propietarios del dato;
- la alerta requiere garantías de consistencia diferentes a las definidas en este ADR.

## 9. Relación con T8

T8 describe la arquitectura resultante y sus componentes. Este documento formaliza **una decisión arquitectónica concreta**: por qué se adopta una arquitectura híbrida con batch dominante y flujo acotado.

Por diseño, T8 y T9 permanecen separados: T8 responde **cómo está organizada la arquitectura** y T9 responde **por qué se tomó esta decisión**.

## 10. Referencias internas

- T1 · Ficha técnica y mediciones: `docs/T1/`
- T3 · Proyección de almacenamiento: `docs/T3_proyeccion_almacenamiento.md`
- T4 · MapReduce y mezcla: `docs/T4_mezcla.md`
- T5 · Lago de datos: `docs/T5_lago.md`
- T6 · Formato Parquet y codec: `docs/T6_formato.md`
- T7 · Paradigma y CAP: `docs/T7_paradigma.md`
- T8 · Arquitectura del proyecto: `docs/T8_arquitectura.md`

## Declaración de uso de asistentes de inteligencia artificial

Se utilizaron asistentes de inteligencia artificial como apoyo para estructurar y redactar este ADR. La decisión, las cifras y los compromisos técnicos se basan en las evidencias y mediciones documentadas en T1–T8.
