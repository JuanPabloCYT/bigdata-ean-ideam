# Mapa del lago · para quien llegue después

**Reto de negocio · Sesión 5 · Competencia Power Humanise**

Usted acaba de unirse al equipo. Nadie de los que construyó esto está disponible ahora mismo. Esta página le basta para encontrar cualquier dato del proyecto sin preguntarle a nadie.

---

## El lago tiene tres cubos

| Cubo | Qué contiene |
|---|---|
| `lago-crudo` | El dato exactamente como llegó del IDEAM. Nunca se edita. |
| `lago-refinado` | El mismo dato, ya limpio y tipado. Se puede regenerar desde `lago-crudo` en cualquier momento. |
| `lago-curado` | Resultados ya calculados (promedios, agregados) listos para usar directamente. Se puede regenerar desde `lago-refinado`. |

Si algo en `refinado` o `curado` parece mal, no se arregla ahí: se corrige el proceso y se vuelve a generar desde la capa anterior. Solo `lago-crudo` es intocable.

## Cómo se nombra cada archivo

Todos siguen el mismo patrón: la fuente, y luego la fecha en tres partes (`anio`, `mes`, `dia`), siempre con dos dígitos.

| Cubo | Plantilla | Ejemplo real |
|---|---|---|
| `lago-crudo` | `cruda/<fuente>/anio=YYYY/mes=MM/dia=DD/<archivo>.csv` | `cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv` |
| `lago-refinado` | `refinada/<fuente>/anio=YYYY/mes=MM/dia=DD/<archivo>.parquet` | `refinada/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.parquet` |
| `lago-curado` | `curada/<fuente>/<agregacion>/anio=YYYY/mes=MM/<archivo>.parquet` | `curada/ideam_precipitacion/promedio_departamento/anio=2026/mes=06/promedio_departamento_2026-06.parquet` |

No son carpetas de verdad — son solo el nombre completo del archivo. Pero se comportan como si lo fueran para efectos de buscar y listar.

## La regla que no tiene excepción

**`lago-crudo` no se edita nunca**, ni para corregir un error. Si algo vino mal del proveedor, el error se documenta y se corrige en `lago-refinado`, dejando la cruda intacta. Es la única forma de que, si algo sale mal más adelante, se pueda reconstruir todo desde el principio y confiar en que se llega al mismo resultado.

Como red de seguridad adicional, `lago-crudo` tiene el versionado activado: aunque alguien lo sobrescriba por error, MinIO no borra la versión anterior — queda disponible para recuperarla.

## Un ejemplo: ¿dónde está la lluvia del 22 de junio de 2026?

Sabe la fuente (`ideam_precipitacion`) y la fecha (`2026-06-22`). No necesita preguntar nada, arme la ruta directamente:

```text
cruda/ideam_precipitacion/anio=2026/mes=06/dia=22/precipitacion_2026-06-22.csv
```

Eso es todo. La convención está diseñada para que esa ruta se pueda escribir de memoria, con solo saber la fuente y la fecha.

---

*Detalle técnico completo, comandos de ejecución y la justificación de cada decisión en [`T5_lago.md`](T5_lago.md) y [`T5_ejecucion.md`](T5_ejecucion.md).*
