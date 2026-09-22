# Práctica S09 · El ADR del proyecto

Sesión 9 · Juan Pablo Castro

Esta sesión no levanta ningún motor: se **decide y se documenta**. La decisión —almacén, lago o lakehouse— y su matriz ponderada viven en el ADR, que es el entregable de T9: [`docs/adr/0001-almacenamiento.md`](../../docs/adr/0001-almacenamiento.md).

> **La regla que ordena la práctica:** el número no decide por el equipo. La matriz ordena y hace comparable el análisis; la decisión se justifica.

## Qué hay aquí

| Archivo | Qué es |
|---|---|
| `calcular_matriz.py` | Calcula los puntajes y localiza el punto de basculación |
| `resultados/matriz_ponderada.txt` | Su salida, versionada como evidencia |

```bash
python3 practica/s09-adr/calcular_matriz.py
```

El script **comprueba que los pesos sumen 100 y falla si no**. Los puntajes del ADR salen de ahí, no de una suma a mano.

---

## Nivel 1 · Guiado · la matriz con los pesos justificados

Los seis criterios son comunes a todos los equipos; los pesos son nuestros. Dos de ellos se apartan bastante del ejemplo del acueducto, y por eso conviene decir de dónde salen:

| Criterio | Nuestro peso | El del ejemplo | Por qué difiere |
|---|---:|---:|---|
| Costo de almacenamiento | **10 %** | 25 % | T3 proyectó 22,5 GB para el año con réplica 3, y T1 midió crecimiento **negativo** (−4,78 %). A esta escala el costo no discrimina entre las opciones; darle 25 % dejaría que un no-problema decidiera |
| Complejidad operativa | **25 %** | 20 % | Somos tres estudiantes sin gente de operación, y lo que nos han evaluado todo el semestre es que un clon limpio levante con `docker compose up`, verificado en macOS y Windows |
| Flexibilidad de esquema | **10 %** | 10 % | T1 comparó dos particiones: `esquema_identico = True`, mismas 12 columnas, mismos tipos, mismo orden. Un esquema que no se mueve no necesita pagarse |

El resto de pesos y las calificaciones están en la matriz del ADR. Resultado:

| Opción | Puntaje |
|---|---:|
| Almacén | 3,30 |
| **Lago** | **4,30** |
| Lakehouse | 3,90 |

---

## Nivel 2 · Aplicado · el ADR completo

[`docs/adr/0001-almacenamiento.md`](../../docs/adr/0001-almacenamiento.md), con sus cuatro partes y la matriz dentro, no como anexo.

**Decisión: se mantiene el lago por capas.** No se evoluciona a lakehouse por ahora, y el ADR dice por qué con una frase que resume el argumento: pagar la complejidad de un registro de transacciones para arbitrar una concurrencia que no existe —un solo escritor, una vez al día, idempotente— sería comprar la solución antes que el problema.

---

## Nivel 3 · Frontera · análisis de sensibilidad

El criterio que más nos hizo dudar fue el soporte transaccional, el único donde el lakehouse es netamente superior. Moviendo peso desde complejidad operativa hacia él:

| Peso transaccional | Lago | Lakehouse | Gana |
|---:|---:|---:|---|
| 15 % (el nuestro) | 4,30 | 3,90 | Lago |
| 23 % | 4,06 | 4,06 | Empate |
| 24 % | 4,03 | 4,08 | Lakehouse |

**Punto de basculación: 24 %, es decir +9 puntos porcentuales.** La decisión es moderadamente robusta: no se voltea moviendo un punto, pero tampoco está lejos. Y deja expuesta la tentación: bastaba con haber puesto 25 % desde el principio para que el lakehouse ganara «según la matriz». No se hizo.

---

## Reto de comunicación · las consecuencias para quien llegue después

La sección **Consecuencias** del ADR está escrita para una persona que entra al equipo en seis meses y no puede preguntarle a nadie. Nombra tres cosas que el proyecto **no** tiene y que es fácil descubrir a golpes:

1. No hay transacciones de tabla: si añades un segundo escritor, el último gana.
2. No hay viaje en el tiempo de tablas. Sí hay versionado de objetos en la cruda, que es otra cosa y se confunde fácil.
3. Una carga defectuosa se corrige reejecutando desde la capa cruda, no con un comando de la plataforma.

Y cierra con cinco condiciones concretas para reabrir la decisión, más el dato de que ya está calculado en qué peso bascula, para que quien la reabra no tenga que rehacer la matriz.

---

## Referencias

Armbrust, M., Ghodsi, A., Xin, R., y Zaharia, M. (2021). Lakehouse: A new generation of open platforms that unify data warehousing and advanced analytics. *Proceedings of the 11th Conference on Innovative Data Systems Research (CIDR)*.

Nygard, M. (2011). *Documenting architecture decisions* [Entrada de blog]. Cognitect.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para construir la matriz, el script de cálculo y este documento.

Los pesos se fijaron antes de calcular ningún puntaje, a partir de mediciones que el proyecto ya tenía, y no se movieron después de ver el resultado. El análisis de sensibilidad se incluye justamente para dejar a la vista lo cerca que quedó la alternativa, en vez de presentar la decisión como más sólida de lo que es.
