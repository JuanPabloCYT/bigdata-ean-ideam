# Por qué guardamos cada dato tres veces

**Para la gerencia · Juan Pablo Castro · Sesión 3**
*Competencia Emprendimiento Sostenible*

---

**Recomendación: mantener tres copias de las mediciones de los sensores, y bajar a dos copias en todo lo demás.**

## La cifra

Guardar el año de mediciones una sola vez ocupa **7,5 GB**. Con dos copias son 15 GB y con tres, **22,5 GB**. Cada copia cuesta exactamente lo mismo que el original: no hay descuento.

Lo que se compra con cada copia es cuántos servidores pueden dañarse al mismo tiempo sin que perdamos nada:

| Copias | Espacio al año | Servidores que pueden fallar |
|---:|---:|---|
| 1 | 7,5 GB | Ninguno |
| 2 | 15 GB | Uno |
| 3 | 22,5 GB | Dos a la vez |

Estos números salen de nuestra propia medición, no de un manual: medimos cuánto pesa un día real de datos y lo proyectamos a doce meses.

## Qué pasa de verdad si tenemos una sola copia

No es un riesgo teórico. Lo probamos: cargamos el mismo archivo con una copia y con tres, y apagamos un servidor.

Con tres copias, el archivo se siguió leyendo **completo y sin un solo error**. Con una sola copia, el archivo **no se pudo abrir en absoluto**: no se leyó ni un byte.

Ese es el punto que suele malinterpretarse. Con una sola copia el archivo no queda «parcialmente dañado» ni «un poco incompleto»: queda **inservible**. Es como una carpeta a la que le arrancaron un tercio de las páginas al azar.

## Qué dato es crítico y cuál no

**Crítico e irrecuperable: las mediciones de los sensores.** Son lecturas de un instante que ya pasó. Si perdemos las mediciones del 22 de junio, no hay forma de volver a tomarlas. Podríamos pedirlas otra vez a la entidad que las publica, pero eso significa depender de que un tercero las conserve, sin ningún compromiso de su parte con nosotros.

**Recuperable: los reportes y resúmenes que calculamos.** Los promedios mensuales, los consolidados por estación, cualquier tabla derivada. Si se pierden, se vuelven a calcular a partir de las mediciones originales. Basta con dos copias.

## La recomendación, y por qué

**Tres copias para las mediciones. Dos para todo lo derivado.**

La razón no es técnica, es de negocio: el sobrecosto de la tercera copia son **7,5 GB al año**, una cantidad que a los precios actuales de almacenamiento es prácticamente irrelevante. A cambio, cubrimos el escenario de dos fallas simultáneas, que es exactamente lo que ocurre cuando falla un equipo mientras otro está en mantenimiento.

Dicho de forma directa: **a nuestro volumen, discutir esta tercera copia para ahorrar cuesta más en horas de reunión que en disco.** La conversación cambiaría por completo si manejáramos miles de veces más datos; entonces sí valdría la pena optimizar cada copia.

## Cuándo revisar esta decisión

Cuando el volumen crezca lo suficiente para que el almacenamiento pese en el presupuesto, conviene evaluar los **códigos de borrado**, una técnica que da una protección parecida a la de tres copias ocupando alrededor de 1,5 veces el tamaño original en lugar de 3. A cambio, recuperar un dato tras una falla es más lento y exige más cálculo.

No la proponemos hoy porque a 22,5 GB el ahorro no compensa la complejidad añadida. El umbral razonable para volver a mirarlo es cuando el almacenamiento llegue al orden de los terabytes, o cuando su costo se vuelva una línea visible en el presupuesto de infraestructura.

---

*Cifras obtenidas de mediciones propias sobre la fuente del proyecto y de pruebas ejecutadas en un clúster real de cuatro nodos. El detalle técnico y las pruebas están en `bitacora.md`.*
