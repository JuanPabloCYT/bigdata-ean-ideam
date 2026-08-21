# Por qué el Parquet baja la factura sin frenar las consultas

**Para la gerencia · Juan Pablo Castro, Camilo Rojas, Lina Ramírez · Sesión 6**
*Competencia Emprendimiento Sostenible*

---

**Recomendación: convertir el dato a Parquet con compresión `zstd` en la capa refinada, sin tocar el original.**

## El ahorro de espacio

El mismo día completo de mediciones (141.007 lecturas) pesa **21,95 MB** en el formato que usamos hoy (CSV) y **0,31 MB** en Parquet comprimido. Es una reducción del **98,6 %**: el archivo queda en menos de una sesentava parte de su tamaño.

Ese ahorro se sostiene con el volumen. En la proyección que ya le presentamos (T3), un año de esta fuente ocupa cerca de 7,5 GB sin comprimir. Con la misma reducción, ese mismo año en Parquet ocuparía apenas unos **100 MB** — la diferencia entre necesitar varios gigabytes de disco por año y necesitar una fracción de uno.

## El efecto en la velocidad

Probamos la misma consulta que ya usamos para el reporte de precipitación por región (T4): promedio de lluvia agrupado por departamento. Sobre el CSV tardó 0,14 segundos. Sobre el Parquet, 0,0015 segundos.

**La consulta fue 93 veces más rápida**, no más lenta. Parquet no es solo más liviano: para las preguntas que hacemos habitualmente —que piden pocas columnas de un archivo con muchas— es también más rápido, porque el motor solo lee las columnas que la pregunta necesita, en vez de recorrer el archivo completo.

## El costo técnico

A este volumen de datos, comprimir con `zstd` no cuesta nada perceptible: escribir el archivo tarda dos centésimas de segundo, más rápido incluso que la opción menos comprimida que evaluamos. No hay que elegir entre ahorrar espacio y gastar tiempo de cómputo — con este codec, a esta escala, se obtienen ambas cosas.

Esto puede cambiar si el volumen crece mucho más: con archivos de mayor tamaño, comprimir más siempre cuesta algo más de proceso. Por ahora, ese costo es cero en la práctica.

## La recomendación

**Convertir a Parquet con `zstd`, dejando el CSV original intacto donde está.** No se trata de elegir entre guardar barato o consultar rápido: con este cambio se consigue lo primero sin sacrificar lo segundo, y sin gasto adicional de cómputo que se note a nuestra escala actual.

El dato original nunca se toca ni se borra: se guarda tal como llega, y el Parquet se genera aparte, como una copia optimizada para consultar. Si algo sale mal con la conversión, el original sigue intacto y se puede rehacer.

---

*Cifras medidas sobre la fuente real del proyecto, con la metodología y la evidencia completa en [`T6_formato.md`](T6_formato.md).*
