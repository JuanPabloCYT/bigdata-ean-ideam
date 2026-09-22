# ADR 0001 · Paradigma de almacenamiento del proyecto

---

## Título y estado

**Título:** Paradigma de almacenamiento del proyecto de precipitación del IDEAM (`s54a-sgyg`)
**Estado:** Aceptado
**Fecha:** 2026-09-22
**Equipo:** `bigdata-ean-ideam` · Juan Pablo Castro, Camilo Rojas, Lina Ramírez

---

## Contexto

El proyecto **ya tiene** un lago por capas sobre almacenamiento de objetos, construido en T5 (`lago-crudo`, `lago-refinado`, `lago-curado` sobre MinIO), con la capa refinada en Parquet y codec `zstd` elegido por medición propia en T6. La arquitectura de T8 es una vía única por lotes con un componente de flujo acotado, y T10 acaba de diseñar sobre la capa curada un modelo dimensional en estrella.

La fuerza que obliga a decidir no es que falte almacenamiento, sino que hay que resolver **si ese lago se mantiene tal cual o se evoluciona a lakehouse** antes de materializar el modelo dimensional sobre él. Decidirlo después sería rehacer la capa curada.

---

## Decisión

**Opción elegida:** Lago de datos por capas, el que ya existe. No se evoluciona a lakehouse por ahora.

### Matriz de criterios ponderados

Los criterios son comunes a todos los equipos. Los pesos los asigna y justifica este equipo. Calificación de 1 a 5 por opción. El peso suma 100.

| Criterio | Peso | Justificación del peso | Almacén | Lago | Lakehouse |
|---|---|---|---|---|---|
| Costo de almacenamiento | 10 % | Bajo a propósito. T3 proyectó **22,5 GB para el año completo con réplica 3**, y T1 midió una tasa de crecimiento **negativa (−4,78 % interanual)**. A esta escala el costo de guardar no discrimina entre las tres opciones: darle más peso dejaría que un no-problema decidiera la arquitectura | 2 | 5 | 4 |
| Flexibilidad de esquema | 10 % | Bajo, y también medido. T1 comparó dos particiones distintas de la fuente y encontró `esquema_identico = True`: **las mismas 12 columnas, los mismos tipos, en el mismo orden**. Un esquema que no se mueve no necesita que se pague por poder moverlo | 2 | 5 | 4 |
| Rendimiento de consulta analítica | 25 % | Alto. Es el uso central: la agregación por departamento de T4, la consulta selectiva de T6 y el modelo en estrella de T10 son todos consulta analítica | 5 | 4 | 4 |
| Soporte transaccional y viaje en el tiempo | 15 % | Medio, no nulo. T5 ya exige inmutabilidad de la capa cruda, y T8 dejó comprometido auditar qué vio la alerta cuando el componente de flujo se implemente. Pero hoy la escritura es de un solo actor, una vez al día e idempotente por ETag: no hay concurrencia que arbitrar | 3 | 2 | 5 |
| Complejidad operativa | 25 % | Alto, empatado con el rendimiento. El equipo son tres estudiantes sin gente de operación, y **la credibilidad del proyecto se ha sostenido todo el semestre en que un clon limpio levanta con `docker compose up`**, verificado en macOS y en Windows. Lo que estorbe esa propiedad ataca justo lo que nos han venido evaluando | 3 | 5 | 3 |
| Adecuación al volumen y la frescura | 15 % | Medio-alto. Son las cifras de T7: tres de los cuatro requisitos toleran horas o días, y concentran casi todo el volumen (141.007 registros diarios, ~4,2 millones mensuales) | 3 | 5 | 4 |
| **Puntaje ponderado** | **100 %** | | **3,30** | **4,30** | **3,90** |

Los puntajes no se sumaron a mano: salen de [`practica/s09-adr/calcular_matriz.py`](../../practica/s09-adr/calcular_matriz.py), que además comprueba que los pesos sumen 100 y falla si no.

**Lectura de ingeniería.** El lago gana con 4,30 frente a 3,90 del lakehouse y 3,30 del almacén, y conviene decir de dónde sale esa diferencia en vez de quedarse con el número.

El almacén queda último por una razón que no es su calidad: es excelente en lo que mejor hace —consulta analítica, donde es el único que saca 5— pero exige esquema en escritura sobre una capa cruda que, por decisión de T5, debe guardarse **tal como llegó**, sin validar. Adoptarlo obligaría a tirar la propiedad que hace reproducible el proyecto: que el SHA-256 de la partición cruda coincide con el de la fuente.

Entre el lago y el lakehouse la diferencia es real pero estrecha, y se juega en dos criterios que tiran en sentido contrario. El lakehouse gana claramente en soporte transaccional (5 contra 2) y el lago gana en complejidad operativa (5 contra 3). Con nuestros pesos, la operación pesa más que las transacciones, porque hoy **no hay un problema transaccional que resolver**: un solo escritor, una vez al día, idempotente. Pagar la complejidad de un registro de transacciones para arbitrar una concurrencia que no existe sería comprar una solución antes que el problema.

Hay además un matiz que la matriz no captura y conviene dejar escrito: nuestro lago **no es un lago ingenuo**. Ya tiene capas gobernadas, versionado de objetos en la cruda, formato columnar y un codec elegido por medición. Buena parte de lo que motiva el salto al lakehouse —orden, rendimiento, poder volver atrás— lo tenemos por otras vías. Lo que de verdad nos falta es la semántica transaccional de tabla, y todavía no hay una pregunta del negocio que la pida. Por eso la calificación del lago en rendimiento analítico es 4 y no 3: T6 midió **0,0015 s** para la consulta de referencia sobre Parquet, 93,5 veces más rápido que sobre el CSV.

### Análisis de sensibilidad · nivel Frontera

El criterio que más nos hizo dudar fue el soporte transaccional, porque es el único donde el lakehouse es netamente superior. La pregunta del nivel Frontera es a partir de qué peso la decisión cambia.

Moviendo peso desde complejidad operativa hacia soporte transaccional, y dejando los otros cuatro criterios fijos:

| Peso del criterio transaccional | Almacén | Lago | Lakehouse | Gana |
|---:|---:|---:|---:|---|
| 15 % (el nuestro) | 3,30 | 4,30 | 3,90 | Lago |
| 23 % | 3,30 | 4,06 | 4,06 | Empate |
| 24 % | 3,30 | 4,03 | 4,08 | **Lakehouse** |

**El punto de basculación está en 24 %: hacen falta +9 puntos porcentuales**, más de la mitad del peso que hoy le damos a ese criterio. La decisión es **moderadamente robusta**: no se voltea moviendo un punto, pero tampoco está fuera de alcance. Si el proyecto adquiriera un requisito real de auditoría —por ejemplo, tener que demostrar ante un ente de control qué dato exacto disparó una alerta de creciente—, ese criterio subiría sin forzar nada y la respuesta correcta pasaría a ser el lakehouse.

Conviene nombrar la tentación que esto revela: habría bastado con poner 25 % en el criterio transaccional desde el principio para que el lakehouse ganara «según la matriz». No se hizo, y el peso de 15 % está justificado por lo que el proyecto hace hoy, no por el resultado que queríamos.

---

## Consecuencias

> Escrito para quien entre al equipo dentro de seis meses y no pueda preguntarle a nadie.

**Lo que se gana.** Sigues teniendo el lago por capas que ya funciona, sin aprender nada nuevo para operarlo. Clonas el repositorio, corres `docker compose up -d minio` y tienes el almacenamiento completo: no hay un motor de tablas transaccionales que instalar, ni un catálogo que registrar, ni una versión de Spark que hacer coincidir. La capa cruda es inmutable y está versionada a nivel de objeto, así que el dato original que descargó el equipo sigue ahí, byte a byte, con su huella comprobable. La capa refinada está en Parquet con `zstd`, que medimos: la consulta de referencia tarda 0,0015 s.

**Lo que se sacrifica.** Tres cosas concretas, y conviene que las sepas antes de chocarte con ellas:

1. **No hay transacciones de tabla.** Si dos procesos escriben a la vez sobre la misma partición de la capa curada, no hay nada que lo arbitre: el último gana. Hoy no pasa porque solo escribe la ingesta diaria, pero si añades un segundo escritor, eso es tuyo para resolver.
2. **No hay viaje en el tiempo de tablas.** Puedes recuperar una *versión anterior de un objeto*, porque MinIO tiene el versionado activo en la capa cruda; no puedes preguntar «cómo estaba la tabla curada el martes pasado». Son cosas distintas y es fácil confundirlas.
3. **Una carga defectuosa no se revierte con un comando.** Se corrige volviendo a ejecutar el proceso desde la capa cruda, que para eso es inmutable. Funciona, pero es un procedimiento manual, no una operación de la plataforma.

La renuncia fue razonable porque en el momento de decidir **ninguno de los tres era un problema real**: un solo escritor, una vez al día, con una fuente que se puede volver a descargar y una capa cruda que nunca se toca. Pagar complejidad por adelantado, para un equipo de tres personas sin gente de operación, habría costado más de lo que ahorraba.

**Cuándo reabrir la decisión.** Cualquiera de estas cinco cosas basta para volver a abrir este ADR, y ninguna requiere permiso de quien lo escribió:

- Aparece **un segundo proceso que escribe** sobre la misma capa, y hay que arbitrar concurrencia.
- Aparece un **requisito de auditoría** que obligue a demostrar el estado exacto de una tabla en una fecha pasada. Es el caso que más probablemente ocurra: el componente de alerta de T8, cuando se implemente, lo acerca.
- Se implementa la **telemetría en flujo** de T7 y empieza a haber escrituras continuas, no una diaria.
- El histórico crece hasta que **rehacer un cálculo desde la capa cruda deje de ser barato**. Hoy lo es, porque T1 midió una tasa de crecimiento negativa.
- Alguien mide que el rendimiento analítico **ya no alcanza** y necesita las estadísticas y el salto de archivos que un formato de tabla aporta sobre Parquet suelto.

Si abres esta decisión, el análisis de sensibilidad de arriba te ahorra trabajo: ya está calculado que basta con subir el criterio transaccional a 24 % para que el lakehouse gane. No hace falta rehacer la matriz desde cero, solo justificar el peso nuevo.

---

## Referencias

Armbrust, M., Ghodsi, A., Xin, R., y Zaharia, M. (2021). Lakehouse: A new generation of open platforms that unify data warehousing and advanced analytics. *Proceedings of the 11th Conference on Innovative Data Systems Research (CIDR)*.

Kleppmann, M. (2017). *Designing data-intensive applications*. O'Reilly Media.

Nygard, M. (2011). *Documenting architecture decisions* [Entrada de blog]. Cognitect.

Reis, J., y Housley, M. (2022). *Fundamentals of data engineering*. O'Reilly Media.

---

## Autoverificación antes de entregar

- [x] El ADR tiene las cuatro partes: título y estado, contexto, decisión y consecuencias.
- [x] La matriz ponderada está dentro del ADR, con pesos justificados que suman 100.
- [x] La decisión es coherente con la arquitectura de T8 y cita las cifras de T7.
- [x] Las consecuencias nombran al menos un costo aceptado y cuándo reabrir la decisión.
- [x] No se eligió lakehouse por defecto: la matriz respalda la decisión.
- [x] Los pesos no se ajustaron para forzar un resultado predeterminado.
- [x] El ADR está versionado en el repositorio, con historial en Git.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para estructurar la matriz, calcular los puntajes y redactar este ADR.

Los puntajes y el punto de basculación no se calcularon a mano: salen de `practica/s09-adr/calcular_matriz.py`, versionado junto a este documento, que además comprueba que los pesos sumen 100 y falla si no. Los pesos se fijaron antes de calcular ningún puntaje, a partir de mediciones ya existentes del proyecto (el crecimiento negativo de T1, el esquema idéntico entre particiones de T1, la proyección de T3 y las cifras de frescura de T7), y no se movieron después de ver el resultado. El análisis de sensibilidad se incluye precisamente para dejar expuesto cuán cerca estuvo la alternativa.
