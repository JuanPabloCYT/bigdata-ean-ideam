T14 · El memo que decide, con las bajas duras de su propio equipo, si un SELECT con marca temporal alcanza para el maestro de suscriptores

Equipo: equipo-2
Integrantes: Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Proyecto: Plataforma de datos del acueducto (proyecto integrador)
Identificador de equipo (--equipo): equipo-2
Motor usado: DuckDB embebido con el motivo documentado (el perfil s12 del archivo de servicios —PostgreSQL 17 en el contenedor `ideam_db`— no estaba disponible en la sesión: Docker apagado; la instalación nativa de PostgreSQL del host es solo la librería cliente `libpq`, sin binario de servidor. DuckDB 2.0.0 reproduce sin servidor las semánticas que el prototipo necesita: marca de agua sobre `updated_at`, `INSERT … ON CONFLICT`, funciones de ventana y `greatest()`. La conclusión es independiente del motor y se traslada a la pila PostgreSQL de T12/T13.)
Fecha: 2026-11-18

> Reemplacen cada marca [completar: ...] por el contenido que describe. No cambien los títulos de sección: la revisión los busca por nombre. Cada sección numerada corresponde a una condición de aceptación o a un criterio de la rúbrica de la tarea. El código que produce cada cifra va versionado en el repositorio del equipo. No hay una respuesta única correcta en la decisión de mitigación ni en la decisión final de método de CDC: lo que se valora en las secciones 2 a 5 es la calidad de la documentación de la decisión, no su coincidencia con la decisión de referencia.

***
0. Perfil de cambios del equipo

> Es lo que distingue esta entrega de la de los otros cinco equipos. Un perfil se identifica por el conjunto completo de sus valores, no por uno solo: dos equipos pueden coincidir en un indicador aislado (por ejemplo, el mismo número de bajas) sin que eso signifique nada.

Comando exacto usado para generar el perfil de cambios: `python practica/s14-cdc-suscriptores/generar_cambios_suscriptores.py --equipo equipo-2`

Valor del perfil | Cifra que reporta el generador
total_suscriptores | 160
Número de cambios | 42
n_alta | 14
n_modificacion | 18
n_baja | 10
prob_baja_dura | 0.0625

***
1. Las tres tablas nuevas y su nomenclatura

> Nomenclatura exacta y carga inicial. Condición de aceptación no negociable.

Ruta del cuaderno o script en el repositorio: `practica/s14-cdc-suscriptores/prototipo_cdc_suscriptores.py` (script) y `practica/s14-cdc-suscriptores/control_t14.ipynb` (cuaderno); DDL en `sql/T14_cdc_suscriptores.sql`.
Nombre de la tabla fuente: maestro_suscriptores — confirmado que es exacto.
Nombre de la tabla de staging de cambios capturados: stg_cambios_suscriptor — confirmado que es exacto.
Nombre de la tabla de checkpoint: estado_cdc_suscriptores — confirmado que es exacto.
Filas cargadas en maestro_suscriptores tras la población inicial: 160

***
2. Evidencia cuantitativa del punto ciego (rúbrica: evidencia cuantitativa del punto ciego)

> Es el corazón técnico de la tarea: correr el prototipo antes y después del flujo de cambios, sobre el perfil propio del equipo, y mostrar que las bajas duras nunca se capturan. Condición de aceptación no negociable.

Tipo de cambio | Generadas (perfil del equipo) | Capturadas por el prototipo
Altas | 14 | 14 (iguala a las generadas)
Modificaciones | 18 | 18 (iguala a las generadas)
Bajas duras | 10 | 0 (debe ser 0, sin importar cuántas se generaron)

Archivo de evidencia del Nivel 2 (obligatorio): `practica/s14-cdc-suscriptores/resultados/evidencia_nivel2_equipo-2.md`, generado por el cuaderno/script; sus cifras coinciden con la tabla anterior.

Comando o celda exacta usada para correr las dos corridas del prototipo (antes y después):

```bash
python practica/s14-cdc-suscriptores/prototipo_cdc_suscriptores.py --equipo equipo-2
```

El prototipo ejecuta, en orden: (1) población inicial de `maestro_suscriptores` con `updated_at = T0 = 2026-11-18 08:00:00`; (2) corrida ANTES con checkpoint nulo → captura las 160 iniciales como ALTAS y deja el checkpoint en T0; (3) flujo de cambios con `updated_at = T1 = 2026-11-18 12:00:00` (14 altas + 18 modificaciones + 10 bajas duras); (4) corrida DESPUÉS con checkpoint = T0 → captura 32 (14 altas + 18 modif + 0 bajas) y avanza el checkpoint a T1. En el cuaderno, esto corresponde a la celda «2. Prototipo de CDC» que invoca `prototipo_cdc_suscriptores.main()` con `--equipo equipo-2`.

Diferencia entre lo que ve el destino y lo que hay en el origen (filas del destino si aplicara solo lo capturado, menos filas reales del maestro): 174 frente a 164 (diferencia 10). El destino, reconstruyendo el maestro con solo lo capturado, conserva los 10 suscriptores que el origen borró; en el ejemplo de clase fue 99 frente a 94.

Por qué el resultado de bajas capturadas es una propiedad estructural del método, no un error del prototipo: la CDC basada en consulta filtra con `updated_at > checkpoint`. Una baja dura elimina la fila del origen, de modo que esa llave deja de existir y nunca satisface el predicado: no hay `updated_at` que supere el checkpoint porque la fila ya no está. El método de sondeo con marca de agua no tiene forma de enterarse de algo que dejó de existir; no es un bug de implementación, es la definición del método.

Si el perfil del equipo generó cero bajas duras por redondeo: no aplica. `prob_baja_dura = 0.0625 = 10/160` es exacta (sin redondeo) y produce `n_baja = 10 ≠ 0`, así que el punto ciego sí se manifiesta de forma material en este perfil.

2.1 Repetición con el checkpoint restablecido (Nivel 2, obligatoria)

> Repetir la corrida con el checkpoint restablecido a la fecha de la población inicial y contar lo que vuelve a capturarse. Condición de aceptación no negociable.

Filas duplicadas en stg_cambios_suscriptor tras repetir la corrida: 32 (igualan exactamente a las altas más las modificaciones del perfil: 14 + 18 = 32; en equipo-1 del ejemplo fue 21).
Filas sobrantes por pareja subscriber_id y tipo_cambio: 32 (cada pareja del flujo aparece dos veces; las 160 de la población inicial siguen una sola vez).
Checkpoint tras la repetición: 2026-11-18 12:00:00 (vuelve a la fecha del flujo de cambios, T1).
Párrafo de decisión sobre cómo evitar los duplicados: el checkpoint debe avanzar de forma monótona con `greatest(checkpoint_actual, max(updated_at))` —nunca retrocede— y la inserción en el staging debe ser idempotente con `ON CONFLICT (subscriber_id, updated_at) DO NOTHING`, porque `(subscriber_id, updated_at)` identifica unívocamente un evento de cambio. Opción elegida: `greatest()` + `ON CONFLICT DO NOTHING` sobre esa llave única. Como alternativa más simple, un margen de solapamiento acotado (re-procesar los últimos N segundos, p. ej. `N = T = 60 s`) con la misma llave única también elimina los duplicados: la re-captura repite filas pero la llave única las descarta. El prototipo usa un INSERT puro (sin la guarda) justamente para evidenciar el problema; con la guarda, las 32 duplicadas serían 0.

***
3. Decisión de mitigación del nivel 3 (rúbrica: decisión de mitigación del nivel 3)

> No se valora si el equipo copia la alternativa del ejemplo resuelto en clase. Se valora si la elección está justificada con las cifras propias del perfil del equipo y si se estima el costo de las alternativas descartadas.

Alternativa | ¿Elegida? | Costo estimado | Beneficio
Bandera de baja lógica en el origen | No | Cambio de esquema y de lógica de borrado en el sistema operacional del acueducto, fuera del control del equipo de plataforma | Detecta bajas con latencia 60 s y costo de lectura bajo (delta de cambios), sin barrido completo
Reconciliación periódica de conjunto completo | Sí (como barrido complementario de bajas) | `K = M × B = 160 × 4 = 640` llaves leídas/día (trivial a esta escala) + un LEFT JOIN periódico | Detecta las 10 bajas; latencia máxima `86400/B = 21600 s` (6 h); no toca el origen
Migración a CDC basada en registro de transacciones | No | Réplica lógica (slot + `REPLICA IDENTITY`) sobre un origen que el equipo no opera; costo operativo desproporcionado para un maestro de 160 filas | Detecta bajas en tiempo real; lee solo los cambios del WAL

Cálculos de apoyo (consultas por día `N = 86400 / T`; llaves leídas por día `K = M × B`, con `M = total_suscriptores = 160` y `B` los barridos por día; latencia máxima de una baja, `L_max = T = 60 s` en el sondeo y `86400 / B = 21600 s` en la reconciliación), calculados con las cuatro funciones de costo del cuaderno: `N = 1440` consultas/día (sondeo, `T = 60 s`); `K = 640` llaves/día (reconciliación, `B = 4`); `L_sondeo = 60 s`; `L_recon = 21600 s`.

bajas_detectadas por reconciliación sobre la base de su equipo: 10 (ids 19, 20, 21, 22, 23, 24, 25, 26, 27, 28) — iguala a las bajas generadas por su perfil (n_baja = 10).

Tabla comparacion con las tres alternativas (alternativa, detecta_bajas, intervalo_sondeo_s, barridos_por_dia, consultas_por_dia, llaves_leidas_por_dia, latencia_max_baja_s):

| alternativa | detecta_bajas | intervalo_sondeo_s | barridos_por_dia | consultas_por_dia | llaves_leidas_por_dia | latencia_max_baja_s |
|---|---|---|---|---|---|---|
| Bandera de baja lógica en el origen | sí | 60 | 1440 | 1440 | 42 | 60 |
| Reconciliación periódica de conjunto completo | sí | 21600 | 4 | 4 | 640 | 21600 |
| CDC basada en registro de transacciones | sí | 0 | 0 | 0 | 42 | 0 |

(El sondeo con marca de agua lee solo el delta del cambio, no `M` por barrido; por eso la bandera lógica y la CDC por registro leen 42 llaves/día —los cambios del día— mientras la reconciliación barre el maestro completo, `M × B = 640`.)

Justificación de la alternativa elegida, conectada con prob_baja_dura y el volumen de bajas propios del equipo: con `prob_baja_dura = 0.0625` y `n_baja = 10` (6.25 % del maestro), el punto ciego es material (10 suscriptores fantasma). No se puede aceptar el statu quo, pero el maestro es operacional y externo al equipo de plataforma, así que la bandera lógica (que exige modificar el origen) queda descartada y la CDC por registro (que exige réplica lógica sobre un origen ajeno) es desproporcionada para 160 filas. La reconciliación, en cambio, barre 160 suscriptores 4 veces/día (640 llaves/día, despreciable) y detecta las 10 bajas con 6 h de latencia máxima —aceptable para un maestro donde una baja no es crítica de minuto— sin tocar el origen. De ahí la híbrida: sondeo barato y de baja latencia (60 s) para altas/modificaciones (el mismo patrón ya resuelto en T12/T13) + reconciliación barata (640 llaves/día) solo para bajas.

Costo estimado de las dos alternativas descartadas: (1) Bandera lógica: costo de modificar el esquema y la lógica de borrado del sistema operacional del acueducto, fuera del alcance del equipo; su beneficio (latencia de bajas de 60 s) no se necesita en un maestro de suscriptores. (2) CDC por registro: costo de operar un slot de réplica lógica con `REPLICA IDENTITY` sobre un origen ajeno, desproporcionado para 160 filas; su beneficio (bajas en tiempo real) no justifica el costo operativo.

Solo si una alternativa es la CDC basada en registro de transacciones: identidad de réplica `DEFAULT`, porque el destino solo necesita la llave (`subscriber_id`, que es PK) para registrar la baja; `FULL` enviaría toda la fila vieja en cada cambio sin beneficio adicional, solo con más volumen en el WAL. (Se documenta aunque la alternativa se descartó.)

***
4. Memo de decisión ADR, Emprendimiento Sostenible (rúbrica: memo de decisión ADR)

> Formato ADR breve. Este memo es el núcleo de T14 y la evidencia de la competencia Ean de la sesión.

Ruta del memo en el repositorio: `docs/memo_adr_t14.md`
Contexto (qué fuente se evalúa y qué pregunta detonó la decisión): se evalúa `maestro_suscriptores`, el maestro operacional de suscriptores del acueducto, que mezcla altas, modificaciones y bajas duras. La pregunta detonante: ¿alcanza una CDC basada en consulta con marca temporal (`updated_at > checkpoint`) para replicarlo, o el punto ciego de las bajas duras obliga a otra cosa?
Evidencia (bajas generadas, bajas capturadas, prob_baja_dura del equipo, de la sección 2): bajas generadas 10, bajas capturadas 0, `prob_baja_dura = 0.0625`; diferencia destino vs origen 174 frente a 164 (diferencia 10); la reconciliación detecta las 10 bajas.
Decisión (mantener CDC basada en consulta, migrar a CDC basada en registro de transacciones o estrategia híbrida): estrategia híbrida — mantener la CDC basada en consulta con marca de agua (sondeo cada 60 s, `ON CONFLICT (subscriber_id, updated_at) DO NOTHING`, checkpoint monótono con `greatest`) para altas y modificaciones, y añadir una reconciliación periódica de conjunto completo cada 6 h para detectar las bajas duras.
Alternativas descartadas y su costo: bandera lógica (descartada: exige modificar el origen operacional, fuera de alcance); CDC por registro de transacciones (descartada: réplica lógica sobre un origen ajeno, desproporcionada para 160 filas; si se eligiera, `REPLICA IDENTITY DEFAULT` alcanzaría).
Justificación por costo, latencia e impacto sobre el sistema de origen: costo despreciable (sondeo lee el delta, 42 cambios/día; reconciliación 640 llaves/día); latencia 60 s para altas/modificaciones y 6 h máxima para bajas (aceptable para un maestro de suscriptores); impacto sobre el sistema de origen nulo (no se modifica el esquema ni la lógica de borrado, ni se exige réplica lógica; el sondeo y la reconciliación solo leen).
Intervalo de sondeo y margen de solapamiento elegidos, si aplica, y por qué: intervalo de sondeo `T = 60 s` para altas/modificaciones (mismo patrón de T12/T13); margen de solapamiento acotado a los últimos 60 s, con checkpoint monótono (`greatest`) e inserción idempotente (`ON CONFLICT (subscriber_id, updated_at) DO NOTHING`), de modo que una corrida repetida o un retraso del origen no duplica filas; reconciliación `B = 4/día` (cada 6 h).
Datos personales (opcional): si el maestro fuera real y contuviera datos personales, la decisión no cambia de fondo (la híbrida sigue siendo adecuada), pero la reconciliación se ejecutaría sobre una proyección mínima (solo `subscriber_id` y `updated_at`, sin columnas personales), el `stg_cambios_suscriptor` seudonimizaría las columnas personales, y una solicitud de borrado (cumplimiento de protección de datos) reforzaría la necesidad de registrar la baja explícitamente en lugar de detectarla por diferencia.

***
5. Integración con el proyecto integrador (rúbrica: integración con el proyecto integrador)

> El memo no se valora de forma aislada: debe situar el costo de la CDC del maestro de suscriptores junto al de las fuentes ya resueltas del mismo proyecto.

Cómo se compara el patrón de cambio de maestro_suscriptores con el de stg_lecturas (T12, solo agrega filas) y stg_estado_medidor (T13, estado paginado vía API): `stg_lecturas` es append-only (solo agrega filas por `fechaobservacion`; nunca actualiza ni borra), así que su CDC incremental por marca de agua no tiene punto ciego de bajas —no hay bajas—. `stg_estado_medidor` es estado paginado vía API con UPSERT por `meter_id`; el mock no expone bajas, así que su CDC por sondeo de API + UPSERT idempotente tampoco tiene punto ciego de bajas en ese perfil. `maestro_suscriptores` es la única de las tres fuentes con bajas duras reales (`prob_baja_dura = 0.0625`, 10 bajas), y por eso es la única que necesita la reconciliación/híbrida: su CDC es la más costosa de las tres.

Por qué el memo no descalifica la decisión del equipo si difiere de la de referencia, aunque esté bien documentada: confirmamos que el memo no descalifica la decisión del equipo por diferir de una de referencia. La decisión se justifica con los números propios del perfil (`prob_baja_dura = 0.0625`, 10 bajas, `M = 160`) y con el costo/latencia/impacto propios, no con la coincidencia con un caso de referencia; otra decisión bien documentada y coherente con su propio perfil no quedaría descalificada.

***
6. Instrucciones de reproducción (rúbrica: reproducibilidad y trazabilidad)

> Lo que otra persona necesita para repetir la corrida sin preguntarle nada al equipo, incluido con qué identificador de equipo. Condición de aceptación no negociable y criterio de la rúbrica.

1. Clonar el repositorio y, en la raíz, crear/activar el entorno virtual e instalar dependencias: `python -m venv .venv && source .venv/bin/activate && pip install duckdb` (DuckDB ya figura en `requirements.txt`; esta entrega usó 2.0.0).
2. Generar el perfil de cambios del equipo (motor DuckDB embebido, sin servidor): `python practica/s14-cdc-suscriptores/generar_cambios_suscriptores.py --equipo equipo-2`. Salida esperada en consola: `total_suscriptores=160, numero_cambios=42, n_alta=14, n_modificacion=18, n_baja=10, prob_baja_dura=0.0625`, y el archivo `perfil_equipo-2.json`.
3. Correr el prototipo de CDC (población inicial, flujo de cambios, doble corrida antes/después, repetición con checkpoint restablecido, funciones de costo y reconciliación): `python practica/s14-cdc-suscriptores/prototipo_cdc_suscriptores.py --equipo equipo-2`.
4. Salida esperada en consola: población inicial = 160; corrida ANTES captura 160 (altas); flujo genera 14 altas + 18 modif + 10 bajas y deja el maestro en 164; corrida DESPUÉS captura 32 (14 altas + 18 modif + 0 bajas); diferencia 174 frente a 164 (diferencia 10); `bajas_detectadas = 10`; repetición con checkpoint restablecido: filas_duplicadas = 32 y sobrantes por pareja = 32, checkpoint vuelve a T1; funciones de costo `N=1440, K=640, L_sondeo=60, L_recon=21600`; tabla `comparacion` con las tres alternativas.
5. El prototipo escribe `practica/s14-cdc-suscriptores/resultados/evidencia_nivel2_equipo-2.md` (evidencia Nivel 2 obligatoria) y `practica/s14-cdc-suscriptores/resultados/perfil_equipo-2.json`.
6. Para correr con el cuaderno: abrir `practica/s14-cdc-suscriptores/control_t14.ipynb` y ejecutar todas las celdas; la celda «2. Prototipo de CDC» invoca `prototipo_cdc_suscriptores.main()` con `--equipo equipo-2` y produce la misma salida y el mismo archivo de evidencia.
7. Para reproducir otro equipo, repetir los pasos 2 y 3 con `--equipo equipo-1|equipo-3|equipo-4|equipo-5|equipo-6`; cada equipo tiene un perfil distinto (ver `generar_cambios_suscriptores.py`).

***
7. Declaración de uso de asistentes de inteligencia artificial

Se utilizó Claude (Kiro) para implementar el generador de perfiles, el prototipo de CDC, el DDL y el cuaderno, y para redactar el memo ADR y esta documentación. Las cifras provienen de la ejecución real del prototipo sobre el perfil del equipo (`equipo-2`); no se inventó ningún número. Las decisiones de diseño (marca de agua monótona con `greatest`, llave única `(subscriber_id, updated_at)`, clasificación por instantánea del checkpoint, decisión híbrida sondeo + reconciliación) fueron tomadas por el equipo y el asistente las implementó.

***
Autoverificación antes de entregar

Marquen cada casilla. Las seis primeras corresponden a las condiciones de aceptación de la sección 5 del enunciado en Canvas. Las cinco siguientes corresponden a los criterios de la rúbrica de la sección 8 del enunciado.

Condiciones de aceptación.

- [x] Las tablas se llaman exactamente maestro_suscriptores, stg_cambios_suscriptor y estado_cdc_suscriptores.
- [x] El prototipo se ejecuta contra el perfil propio del equipo (--equipo) y deja evidencia cuantitativa de altas, modificaciones y bajas generadas frente a las capturadas, con el archivo evidencia_nivel2_equipo-2.md (obligatorio) adjunto.
- [x] La repetición con el checkpoint restablecido (sección 2.1, obligatoria) queda ejecutada, con las filas duplicadas contadas (32) y el párrafo de decisión sobre cómo evitarlas.
- [x] El nivel 3 (sección 3) incluye las cuatro funciones de costo, bajas_detectadas (10) y la tabla comparacion de las tres alternativas.
- [x] El memo cuantifica al menos un caso de baja dura no detectada, con el dato numérico propio del equipo (10 bajas generadas, 0 capturadas, diferencia 174 vs 164).
- [x] El memo declara una decisión explícita (estrategia híbrida) con justificación por costo, latencia e impacto sobre el sistema de origen.
- [x] El memo no descalifica la decisión del equipo por diferir de la de referencia.
- [x] El código y el memo están versionados con el identificador de --equipo usado (equipo-2) y las instrucciones de la sección 6.

Rúbrica (calidad de las decisiones documentadas).

- [x] La sección 2 muestra la doble corrida y explica por qué el resultado es estructural, no un error.
- [x] La sección 3 justifica la alternativa de mitigación elegida con las cifras propias del perfil y estima el costo de las descartadas.
- [x] La sección 4 conecta la decisión del memo con la evidencia cuantitativa propia y pondera costo, latencia e impacto sobre el sistema de origen.
- [x] La sección 5 sitúa el costo de la CDC del maestro de suscriptores junto al de stg_lecturas y stg_estado_medidor.
- [x] Las instrucciones de reproducción de la sección 6 alcanzan para que otra persona repita la corrida sin preguntar nada.

***
