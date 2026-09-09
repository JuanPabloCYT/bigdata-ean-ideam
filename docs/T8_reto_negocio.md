# T8 · Por qué esta arquitectura y no otra

**Una página para la gerencia. Sin tecnicismos.**

Proyecto: plataforma de datos de precipitación del IDEAM · equipo `bigdata-ean-ideam` · 2026-09-08

---

## La objeción

Cuando presentamos la arquitectura, la pregunta razonable de la gerencia fue: *«¿por qué no ponemos todo por lotes, que es más barato?»*. Y su reverso, igual de razonable: *«si vamos a tener una parte en tiempo real, ¿por qué no hacer todo así y quedar mejor preparados?»*.

Las dos preguntas tienen la misma respuesta: **porque la urgencia y el volumen están en lados distintos del proyecto.**

## Lo que elegimos

Una **vía única por lotes**, que es como funciona hoy todo el sistema, **más un solo componente en tiempo real** para la alerta de lluvia intensa. Nada más.

## Por qué no todo por lotes

Porque hay un requisito, y solo uno, donde llegar tarde no significa llegar con menos calidad: significa **no llegar**. La alerta de creciente súbita en una cuenca urbana tiene que evaluarse en segundos, porque el agua tarda minutos en llegar al punto crítico. Si esa alerta se procesa con el mismo ritmo que el resto —una vez al día—, se dispararía después de que la creciente ya ocurrió. Deja de ser una alerta y pasa a ser un informe de algo que ya pasó.

Ese costo no aparece en la factura de la nube, pero es el más caro de todos: se traslada a la comunidad que no tuvo tiempo de reaccionar.

## Por qué no todo en tiempo real

Porque los otros tres requisitos no ganan nada y sí cuestan.

La fuente del IDEAM **publica una sola vez al día**. Consultarla en tiempo real no traería ni un dato nuevo: sería cómputo encendido las veinticuatro horas para descargar lo mismo. Y el reporte mensual da exactamente el mismo número si se calcula el día 1 o el día 3 del mes siguiente.

La cifra que ordena la decisión es esta: esos tres requisitos concentran **prácticamente todo el volumen** del proyecto —unos 141.000 registros diarios, unos 4,2 millones al mes—, mientras que la alerta trabaja sobre **decenas de registros por minuto** en una sola cuenca. Poner todo en tiempo real sería pagar la infraestructura más cara para el 99 % del dato que no la necesita.

## Por qué tampoco la «malla de datos»

Es la arquitectura de moda, y por eso vale la pena decir explícitamente que **no la vamos a usar**. La malla resuelve un problema de organización: muchas áreas, cada una dueña de su dato, que ya no caben en una plataforma central. Nosotros somos **un equipo de tres personas, un tema y una fuente**. Adoptarla sería montar la estructura de coordinación de una empresa grande para un proyecto que no la tiene. Sería complejidad pagada sin beneficio recibido.

Tendría sentido reevaluarla el día en que la plataforma sirva a áreas distintas con dueños distintos —por ejemplo, si se sumaran calidad del agua o consumo, cada una con su propio equipo.

## Lo que aceptamos a cambio

Ninguna decisión es gratis, y esta tiene un costo que preferimos nombrar: **las dos vías no comparten historia**. La parte por lotes tiene trazabilidad completa, desde el archivo original hasta el reporte. La alerta, en cambio, mirará un canal de datos que no pasa por ese camino. Con el tiempo, la definición de «lluvia intensa» que usa la alerta y la que usa el reporte podrían separarse sin que nadie lo note.

Lo asumimos con dos compromisos concretos: esa definición se escribe en **un solo lugar** y las dos vías la citan de ahí, y la alerta guardará copia de lo que vio para poder revisarlo después. Es un costo bastante menor que la alternativa: mantener para siempre dos versiones del mismo cálculo, que es lo que costaría la arquitectura que descartamos.

## En una frase

Pagamos tiempo real **solo donde el retraso tiene consecuencias irreversibles**, y usamos el camino barato en todo lo demás, que es donde está casi todo el dato.
