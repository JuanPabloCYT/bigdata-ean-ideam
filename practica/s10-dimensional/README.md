# Práctica S10 · El modelo dimensional del proyecto

Sesión 10 · Juan Pablo Castro

Esta sesión no levanta ningún motor: se **diseña un modelo lógico**. La implementación, la carga con muestra y las consultas medidas son de la sesión 11.

El modelo completo, con el grano declarado y las cuatro dimensiones justificadas, está en [`docs/T10_modelo_dimensional.md`](../../docs/T10_modelo_dimensional.md). Este archivo recoge lo que la guía de la práctica pide producir en sus tres niveles y el reto de diseño.

> **La regla que ordena la práctica:** no se dibuja ninguna tabla hasta que el grano esté escrito en una frase. Se cumplió en ese orden: primero el grano, luego las medidas, luego las dimensiones.

## Qué hay aquí

| Archivo | Qué es |
|---|---|
| `modelo_estrella.drawio` | El esquema estrella, editable en draw.io |
| `modelo_estrella.mmd` · `.png` | La fuente Mermaid y la imagen embebida en T10 |
| `copo_de_nieve.mmd` · `.png` | La variante normalizada del nivel Frontera |
| `resultados/cardinalidades.txt` | Salida de `src/modelo/medir_cardinalidades.py`, medida contra la fuente |

Las cifras que sostienen el modelo se pueden rehacer:

```bash
python3 src/modelo/medir_cardinalidades.py --date 2026-06-22
```

---

## Nivel 1 · Guiado · el grano y la tabla de hechos

**Grano:** una fila es la observación de precipitación que un sensor de una estación registró en un instante.

Sin la conjunción «y», como exige la primera prueba. La tabla de hechos que se sostiene sobre él:

| `hechos_precipitacion` | Tipo |
|---|---|
| `sk_fecha`, `sk_hora_del_dia`, `sk_estacion`, `sk_sensor` | Claves foráneas |
| `valor_precipitacion_mm` | Medida, en milímetros |

**Las tres pruebas del grano, con su evidencia:**

| Prueba | Resultado | Evidencia |
|---|---|---|
| Se dice en una frase sin «y» | Cumple | La frase de arriba |
| Toda medida existe a ese nivel | Cumple | `valor_precipitacion_mm` es el registro del instante, no una agregación |
| Toda dimensión aplica a cada fila | Cumple | T1 midió 0,0 de nulos en las 12 columnas, en dos particiones |

Además, T1 ya había verificado que `codigoestacion` + `codigosensor` + `fechaobservacion` da 141.007 combinaciones únicas en 141.007 filas: el grano identifica una fila y solo una.

---

## Nivel 2 · Aplicado · el esquema estrella

![Esquema estrella](modelo_estrella.png)

Cuatro dimensiones conformadas, cada una con su clave subrogada distinta de la clave de origen, todas planas y conectadas directo al centro. El detalle de atributos y el porqué de cada una están en [`docs/T10_modelo_dimensional.md`](../../docs/T10_modelo_dimensional.md), sección 3.

| Dimensión | Clave subrogada | Clave natural conservada | Filas |
|---|---|---|---|
| `dim_fecha` | `sk_fecha` | `fecha` | ~365 por año |
| `dim_hora_del_dia` | `sk_hora_del_dia` | `hora_minuto` | 1.440, fijas |
| `dim_estacion` | `sk_estacion` | `codigoestacion` | 524 medidas |
| `dim_sensor` | `sk_sensor` | `codigosensor` | 2 medidas |

---

## Nivel 3 · Frontera · la dimensión en copo de nieve

Se normalizó `dim_estacion` separando su geografía, **y se descarta**. El análisis completo está en la sección 5 de T10; el resumen es que las tres razones son medidas, no de opinión: la dimensión tiene 524 filas y no hay casi nada que ahorrar; el costo son dos uniones más justo en la consulta principal del proyecto; y **18 de las 31 zonas hidrográficas cruzan más de un departamento**, así que la jerarquía que justificaría la normalización no existe en el dato.

---

## Reto de diseño · ¿responde el modelo una pregunta nueva?

**La situación.** Con el modelo al grano del instante ya diseñado, la gerencia pide analizar la **precipitación promedio mensual por departamento**, para el informe de planeación.

**¿El grano actual responde la pregunta?** Sí, sin tocar el modelo. El grano del instante es más fino que el que la pregunta necesita, y un grano fino se agrega hacia arriba. Si el modelo se hubiera diseñado al grano del día, o del departamento, esta pregunta habría obligado a rehacerlo; al revés no ocurre.

**Cómo se resuelve.** Una sola consulta sobre la estrella, sin tablas nuevas:

```sql
SELECT f.anio, f.mes, e.departamento, avg(h.valor_precipitacion_mm) AS promedio_mm
FROM   hechos_precipitacion h
JOIN   dim_fecha    f ON f.sk_fecha    = h.sk_fecha
JOIN   dim_estacion e ON e.sk_estacion = h.sk_estacion
GROUP  BY f.anio, f.mes, e.departamento
```

**Qué dimensiones reutiliza.** Solo `dim_fecha` y `dim_estacion`, las dos que ya existen. El mes sale de `dim_fecha` sin crear una dimensión de mes, y el departamento sale de `dim_estacion` sin crear una dimensión de geografía: por eso son conformadas. `dim_hora_del_dia` y `dim_sensor` simplemente no participan, y eso no es un problema — una consulta usa las dimensiones que necesita.

Es, además, la misma pregunta que el equipo respondió en T4 con MapReduce sobre la partición diaria, y dio 33 departamentos. El modelo dimensional no cambia la respuesta: cambia el costo de obtenerla y la facilidad de cortarla por otro lado.

**Cuándo haría falta más.** Una tabla de hechos agregada —tema de la sesión 11— se justificaría solo si esta consulta se ejecutara tan seguido, o sobre tantos años, que recorrer el grano fino empezara a costar. Hoy no es el caso: T6 midió que la consulta de referencia sobre Parquet tarda **0,0015 s** sobre la partición diaria. Precalcular un agregado para ahorrar milisegundos añadiría una tabla que hay que mantener sincronizada, a cambio de nada. La señal para reevaluarlo es que el histórico crezca a varios años y la consulta se vuelva interactiva, no que la tabla agregada suene más profesional.

---

## Referencias

Kimball, R., y Ross, M. (2013). *The data warehouse toolkit: The definitive guide to dimensional modeling* (3.ª ed.). John Wiley & Sons.

Reis, J., y Housley, M. (2022). *Fundamentals of data engineering*. O'Reilly Media.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para diseñar el modelo, construir los diagramas y redactar este documento.

El orden de trabajo fue el que la guía impone y no el inverso: se declaró el grano, se verificó contra la clave candidata que T1 ya había medido, y solo entonces se eligieron medidas y dimensiones. Las cardinalidades que justifican el descarte del copo de nieve se midieron contra la fuente con un script versionado, no se estimaron.
