# T8 · Verificación independiente (Lina Ramírez)

A diferencia de T5 y T6, T8 no tiene un script que se ejecute: es un documento de arquitectura y tres formatos de un mismo diagrama. La verificación consiste en trazar cada cifra citada hasta su origen medido, y comprobar que los tres formatos del diagrama (Mermaid, draw.io, Structurizr) dicen exactamente lo mismo. No modifiqué ningún archivo hasta terminar la comprobación.

## 1. Cada cifra de la sección 5 de `T8_arquitectura.md`, contra su fuente

| Cifra citada en T8 | Fuente | Verificado contra |
|---|---|---|
| `S0 = 21.953.076 bytes`, 141.007 filas | T1 | `docs/T1/evidencia/resultados_medicion.json` → `disco.S0_bytes` y `disco.filas`, idénticos |
| `k = 3,2396` | T1 | `resultados_medicion.json` → `dataframe.k = 3.239579182434389`, redondea igual |
| `g = −4,78 %` | T1 | `resultados_medicion.json` → `crecimiento.g_historico_anual = -0.04780860917729424`, redondea igual |
| Horizonte de saturación, 313,5 años al 1 % anual | T1 | `resultados_medicion.json` → `umbral.t_umbral_referencia_anios = 313.4724129716826`, redondea igual |
| Clave candidata sin duplicados | T1 | `resultados_medicion.json` → `clave.filas_en_grupos_duplicados = 0`, `es_clave_unica_en_el_periodo = true` |
| `R = 3` crudo / `R = 2` derivado, `CORRUPT` con 4/10 bloques vs `HEALTHY` con MD5 idéntico, +7,5 GB/año | T3 | `docs/T3_proyeccion_almacenamiento.md` líneas 163-189: mismo texto, mismas cifras |
| Shuffle bytes 2.398.815 → 5.080, −99,788 % | T4 | `docs/T4_mezcla.md` líneas 58-66: mismos números |
| Parquet zstd 312.373 B, consulta 0,0015 s vs 0,1429 s CSV, 93,5× | T6 | `docs/T6_formato.md` líneas 27-88: mismos números (T8 redondea 0,0016 s de T6 a 0,0015 s de la sección 3, que es la cifra correcta a citar) |
| Compromiso CAP: disponibilidad en la alerta | T7 | `docs/T7_paradigma.md`, Parte B: mismo argumento, mismo requisito |

Ninguna cifra de la sección 5 se inventó ni se redondeó de forma distinta a su fuente. La cadena de trazabilidad que promete la sección 6 (`de la huella SHA-256 de la partición cruda hasta el agregado por departamento`) se sostiene.

## 2. Consistencia entre los tres formatos del diagrama

Comparé `c4_nivel1_contexto.mmd`/`.drawio`, `c4_nivel2_contenedor.mmd`/`.drawio` y `workspace.dsl` elemento por elemento, sin ejecutar nada (no hay Node.js disponible en este equipo para regenerar los `.png` con `mermaid-cli`; ver nota al final).

| Elemento | Mermaid | draw.io | Structurizr |
|---|---|---|---|
| Telemetría de estaciones | `[Sistema externo · PLANIFICADO]`, `classDef planificado` con `stroke-dasharray` | `dashed=1`, etiqueta `PLANIFICADO` | tag `"Planificado"` |
| Detector de umbral | `[Contenedor de flujo · PLANIFICADO]`, relleno distinto (`planificadoInt`) | `dashed=1`, etiqueta `PLANIFICADO, no implementado` | `"Componente de flujo · no implementado" "Planificado"` |
| Relación telemetría→plataforma/detector | flecha punteada (`-.->`) | `dashed=1` | etiqueta `"planificado"` (el DSL no tiene línea punteada nativa, pero el `element "Planificado"` en la vista de estilos cumple la misma función) |
| Relación detector→lago (auditoría) | punteada, etiqueta `PLANIFICADO` | `dashed=1`, etiqueta `PLANIFICADO` | etiqueta `"planificado"` |

Los tres formatos marcan exactamente los mismos dos elementos y las mismas tres relaciones como no construidos, con la misma consistencia que exige la regla que el propio `practica/s08-c4/README.md` se impone («lo que no está construido se dibuja como no construido»). No encontré un elemento marcado como planificado en un formato y como real en otro.

## 3. Enlaces relativos

Verifiqué con un script simple que cada enlace relativo de `docs/T8_arquitectura.md`, `docs/T8_reto_negocio.md` y `practica/s08-c4/README.md` resuelve a un archivo existente en el repositorio (no solo que la URL "se vea bien"). Los 14 enlaces relativos de `T8_arquitectura.md` y los 3 de `s08-c4/README.md` resuelven; `T8_reto_negocio.md` no tiene enlaces relativos, solo prosa.

## 4. Lo que no pude reproducir en esta máquina

Esta máquina no tiene Node.js instalado, así que no pude ejecutar `npx @mermaid-js/mermaid-cli` para regenerar los `.png` desde los `.mmd` y comparar byte a byte, como sí hice con los scripts de Python de T5 y T6. Esto es una limitación de mi entorno, no un hallazgo sobre el proyecto: los `.mmd` que leí manualmente coinciden en contenido con lo que muestran los `.png` ya embebidos en `T8_arquitectura.md` (mismas cajas, mismas etiquetas, mismos elementos punteados), pero la comprobación de que el comando de la sección "Cómo se regeneran las imágenes" del `README.md` de `s08-c4` produce el archivo exacto queda pendiente para quien tenga Node disponible.

## Conclusión

Sin hallazgos nuevos ni correcciones. Cada cifra de `T8_arquitectura.md` remite a la medición original de T1, T3, T4, T6 o T7 sin alteración, y los tres formatos del modelo C4 (Mermaid, draw.io, Structurizr) son consistentes entre sí en qué está construido y qué está planificado. La única comprobación que quedó fuera de alcance —regenerar los `.png` desde los `.mmd`— es una limitación de esta máquina, documentada arriba para quien la reproduzca con Node.js instalado.


---

## Addendum · cierre del punto 4, por Juan Pablo Castro (2026-09-22)

Lina dejó explícitamente pendiente la única comprobación que su equipo no podía hacer: regenerar los `.png` desde los `.mmd` con el comando documentado y compararlos byte a byte. La ejecuté en un equipo con Node.js, sobre una copia de los `.mmd` en un directorio aparte para no sobrescribir los archivos versionados.

Se usó el comando exacto de la sección «Cómo se regeneran las imágenes» de [`practica/s08-c4/README.md`](../practica/s08-c4/README.md), sin modificarlo.

| Archivo | SHA-256 del versionado | SHA-256 del regenerado | Resultado |
|---|---|---|---|
| `c4_nivel1_contexto.png` | `83cd60b2…9b8cb75` | `83cd60b2…9b8cb75` | Idénticos byte a byte |
| `c4_nivel2_contenedor.png` | `656ed003…2f64ab672` | `656ed003…2f64ab672` | Idénticos byte a byte |

Entorno: macOS, Node.js v24.18.0, `@mermaid-js/mermaid-cli` 11.17.0.

**Conclusión:** el comando documentado reproduce los archivos versionados de forma exacta, no solo equivalente. Con esto queda cerrada la única comprobación que la verificación de Lina no pudo cubrir, y la reproducibilidad de T8 pasa a ser completa: las cifras trazan a su medición (secciones 1 y 2 de este documento) y las imágenes trazan a su fuente editable (este addendum).

**Una precisión sobre el alcance.** La identidad byte a byte depende de la versión de `mermaid-cli`: una versión distinta puede producir un PNG visualmente igual pero no idéntico. Por eso la versión usada queda anotada arriba y en el `README.md` de la práctica. Lo que el proyecto garantiza es que el comando documentado, con esa versión, reproduce exactamente lo versionado.
