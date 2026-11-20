# Registro de decisiones · lectura de planes · equipo-2

IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean

Tres decisiones justificadas con cifras de la bitácora del equipo (ampliación, 426 medidores, 1.226.880 lecturas, sector dominante S-SUR 54,9 %).

---

## Decisión 1 · Diseño físico de la capa para la consulta dominante

**Contexto.** La consulta dominante del acueducto es el cierre diario: consumo por sector de un día. ¿Cómo particionar `refinada_spark/` para que esa consulta lea el mínimo de datos?

**Opciones consideradas.**
- Sin partición: Spark lee todos los archivos en cada cierre.
- Partición por mes: Spark poda al mes (~30 archivos); sigue leyendo más de lo necesario.
- Partición por día (`anio/mes/dia`): Spark poda al día exacto y lee **1 archivo**.
- Columnas de partición como texto con ceros (`'04'` no `4`): el literal del filtro debe coincidir en tipo y en ceros con la columna; sin ceros el predicado no coindice y no hay poda.

**Evidencia (bitácora, ampliación).**
- Consulta A con partición por día: `archivos_leidos = 1`, `tamano_archivos_leidos_b = 43 855 B` (43 KiB de 5,0 MiB totales).
- Consulta A-fecha sin poda (columna interna): `archivos_leidos = 120`, `tamano_archivos_leidos_b = 5 254 487 B` (5,0 MiB).
- Razón: 120× más datos leídos sin poda.

**Decisión.** Partición por `anio/mes/dia` con columnas de texto con ceros. La poda reduce los datos leídos de 5,0 MiB a 43 KiB (razón 120×) en cada cierre diario.

**Alternativa descartada y su costo.** Columna `fecha` como filtro (A-fecha): lee los 120 archivos (5,0 MiB), 120× más que con la poda por ruta.

**Consecuencias.** El cierre diario lee 1 archivo; los cierres históricos siguen leyendo todos los archivos cargados. El árbol de directorios tiene 120 carpetas.

**Cifra que obligaría a revisarla.** Si el número de archivos por día crece a >100 (escrituras incrementales), la poda por día podría dejar de ser suficiente y habría que agregar una partición por sector.

---

## Decisión 4 · Estrategia de unión y umbral de difusión

**Contexto.** La consulta C une las 1.226.880 lecturas con `medidores.parquet` (426 filas, ~5 KB). ¿Qué estrategia de unión conviene y cuál es el umbral adecuado?

**Opciones consideradas.**
- Dejar a Catalyst con umbral por omisión (~10 MiB): si `medidores.parquet` está por debajo del umbral, Catalyst elige BroadcastHashJoin automáticamente.
- Forzar BroadcastHashJoin con pista `F.broadcast()`: garantiza la difusión incluso si las estadísticas de Catalyst son inexactas.
- Deshabilitar la difusión (umbral -1): obliga a SortMergeJoin; es el escenario de diagnóstico de C-forzada.

**Evidencia (bitácora, ampliación).**
- C (omisión): `estrategia_union = BroadcastHashJoin`, `bytes_mezcla = 704 B`, `etapas = 3`, `tareas = 13`.
- C-forzada (umbral -1): `estrategia_union = SortMergeJoin`, `bytes_mezcla = 9 541 106 B` (9,1 MiB), `etapas = 4`, `tareas = 21`.
- Razón de bytes de mezcla: 9 541 106 / 704 = **13 549×** más mezcla con SortMergeJoin.
- C-aqe: AQE mantiene BroadcastHashJoin incluso con AQE activa (estadísticas en tiempo de ejecución confirman que medidores es pequeño).

**Decisión.** Dejar a Catalyst con el umbral por omisión. `medidores.parquet` pesa ~5 KB, muy por debajo del umbral de ~10 MiB, así que Catalyst elige BroadcastHashJoin de forma fiable. No hace falta una pista `F.broadcast()` explícita (aunque sería una alternativa válida para garantizarlo en producción).

**Alternativa descartada y su costo.** SortMergeJoin (umbral -1): 13.549× más bytes de mezcla (9,1 MiB vs 704 B), 8 tareas más y una etapa más.

**Consecuencias.** La unión no genera mezcla de las lecturas; los 426 medidores se difunden en memoria. Si la tabla de medidores crece por encima del umbral, Catalyst cambiará a SortMergeJoin automáticamente.

**Cifra que obligaría a revisarla.** Si `medidores.parquet` supera ~10 MiB (tamaño en disco del umbral por omisión), Catalyst dejará de elegir BroadcastHashJoin; en ese caso habría que añadir una pista explícita o filtrar la referencia a los medidores vigentes (`es_actual = true`) para reducirla.

---

## Decisión 6 · Qué evidencia se guarda de un plan

**Contexto.** ¿Cómo guardar la evidencia de un plan de ejecución para que sea reproducible y verificable?

**Opciones consideradas.**
- Captura de pantalla de la interfaz de Spark: no es versionable ni comparable automáticamente.
- Plan normalizado en texto + hash: el plan normalizado elimina los identificadores que cambian entre ejecuciones (números de expresión, `plan_id`, rutas); el hash permite comparar dos corridas sin abrir el archivo.
- Solo los tiempos de reloj: varían hasta ×3 entre corridas; no son evidencia de qué se leyó.
- Plan + métricas en bitácora (archivos, bytes, mezcla, etapas, tareas) + hash del resultado: permite verificar que el plan no cambió entre corridas y que el resultado es correcto.

**Evidencia (bitácora, ampliación).**
- Dos corridas de la consulta A: `hash_plan_normalizado` idéntico en ambas (`cb0dd229881b…`).
- Dos corridas de C: `hash_resultado` idéntico (`c0db0e7c5589…`).
- C vs C-forzada vs C-aqe: `hash_resultado` idéntico en las tres; `hash_plan_normalizado` diferente (tres planes distintos, mismo resultado).

**Decisión.** Plan normalizado en texto + hash del plan + métricas en `bitacora_planes.jsonl` + hash del resultado. El hash del plan detecta cambios de plan entre versiones de Spark o de configuración; el hash del resultado verifica la corrección; las métricas cuantifican el costo.

**Alternativa descartada y su costo.** Solo tiempos: no permiten saber si el plan cambió ni cuántos datos se leyeron; una corrida lenta puede deberse a la carga del equipo, no a una regresión del plan.

**Consecuencias.** La bitácora es la fuente de verdad; los planes normalizados en `planes/` son el archivo versionado. Si el hash del plan cambia entre versiones de Spark, es una señal de que el optimizador tomó una decisión diferente.

**Cifra que obligaría a revisarla.** Si el hash del plan cambia en producción sin cambio de código, es una señal de que las estadísticas del catálogo o la configuración cambiaron; habría que investigar antes de seguir.

---

## Revisión de una etapa anterior con evidencia nueva

La evidencia de T17 confirma la decisión de T16 (ADR-5) de usar `partitionBy("fecha")` con sobrescritura dinámica: la consulta A lee 1 archivo de 43 KiB sobre los 120 existentes (razón 120×). Si la capa no estuviera particionada por día, cada cierre diario leería los 5,0 MiB completos. La decisión se **mantiene** con esta cifra adicional.
