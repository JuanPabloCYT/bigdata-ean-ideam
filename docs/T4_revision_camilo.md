# T4 · Revisión del aporte de Camilo Rojas

## Aporte

Se revisó la documentación de la agregación MapReduce de precipitación promedio por departamento sobre la fuente consolidada del IDEAM.

La clave `departamento` es adecuada para la pregunta planteada porque permite obtener directamente el promedio de precipitación para cada departamento. El mapper emite la precipitación junto con un conteo (`valor,1`), mientras que el combinador realiza una agregación parcial de suma y conteo. El promedio definitivo se calcula únicamente en el reducer, después de reunir todos los valores de una misma clave.

También se revisó la explicación del efecto del combinador sobre la fase de shuffle. La reducción del volumen transferido se debe a que las tareas de mapeo pueden consolidar localmente los registros antes de enviarlos al reducer.

## Observación sobre el sesgo

La documentación identifica concentración de registros en la clave `BOGOTÁ`. Una alternativa para repartir mejor esa carga es utilizar una clave compuesta por `departamento` y `codigoestacion`. Esta alternativa mejora el paralelismo, pero cambia la granularidad del resultado y puede requerir una segunda agregación para recuperar el promedio por departamento.

## Verificación del aporte

Este documento registra la revisión realizada sobre la implementación y la documentación de T4. No se agregan cifras nuevas ni se presentan como propias ejecuciones del clúster que no hayan sido realizadas por este integrante.
