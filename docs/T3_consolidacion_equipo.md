# T3 · Consolidación del equipo

**IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean**
Paso cero de T3: de tres fichas y tres repositorios, a uno solo.

> **Decisión tomada: fuente A, Precipitación del IDEAM.** Las tres columnas están llenas y la justificación está en la sección 3. Falta que Camilo firme el acuerdo de la sección 4 — su commit anterior fue solo de datos comparativos, no de aceptación.

---

## 1. Criterios de decisión

La fuente elegida acompaña al equipo hasta la sesión 30, así que la decisión no se toma por preferencia. Se decide contra los **cuatro requisitos mínimos de T1**, más tres criterios técnicos que pesan en las sesiones que vienen.

### Requisitos mínimos · eliminatorios

Una fuente que falle cualquiera de estos queda descartada, por buena que sea en lo demás.

| # | Requisito | Cómo se verifica |
|---|---|---|
| 1 | Volumen conocido y medido | Existe una cifra en bytes obtenida con `os.path.getsize()`, no una estimación |
| 2 | Licencia clara | Está declarada en los metadatos oficiales de la fuente |
| 3 | Tasa de crecimiento conocida | Hay dos períodos comparables medidos, no un supuesto |
| 4 | Formato declarado | Se conoce el esquema, los tipos y si es estable entre períodos |

### Criterios de desempate · técnicos

Si más de una fuente cumple los cuatro, se decide por estos, en este orden.

| Criterio | Por qué pesa | En qué sesión se cobra |
|---|---|---|
| Clave candidata verificada | Permite ingesta incremental idempotente sin trabajo previo de limpieza | T5, ingesta |
| Acceso programático con conteo previo | Hace verificable cada carga y barata la estimación de crecimiento | T3 en adelante |
| Columna categórica con buena cardinalidad | Es la clave de agrupación de MapReduce; si una categoría concentra todo, hay sesgo | S4, T4 |
| Esquema estable entre períodos | Un esquema que cambia obliga a rehacer el pipeline | S9, variedad |

---

## 2. Comparación de las tres fuentes

> Completar en la reunión. La columna de la fuente A está llena con datos medidos, no declarados; las otras dos deben llenarse con el mismo nivel de evidencia. **Si un dato no está medido, se escribe «no medido», no se estima.**

| | **A · Precipitación IDEAM** | **B · SECOP II** | **C · Resultados Agregados Saber 11 (ICFES)** |
|---|---|---|---|
| **Integrante** | Juan Pablo Castro | Camilo Rojas | Lina Ramírez |
| **Conjunto** | `s54a-sgyg`, Datos Abiertos | `p6dx-8zbt`, Datos Abiertos | Resultados Agregados Saber 11, portal oficial ICFES (no tiene ID tipo Socrata; es descarga directa por período) |
| **1. Volumen medido** | 21.953.076 B por partición diaria; 141.007 registros | 8,89 millones de registros; 59 columnas | 1.859.817 B (1,86 MB) por archivo de período; 14.045 registros consolidados, 21 columnas |
| **2. Licencia** | CC BY-SA 4.0 | CC BY-SA 4.0 | No declarada explícitamente en el portal ICFES |
| **3. Tasa de crecimiento** | −4,780861 % anual, de conteos jun-2025 vs jun-2026 | **+6,42 % anual**, de conteos 2024 vs 2025 | +0,59 % anual, de conteos consolidados 2024-2 (13.963) vs 2025-2 (14.045) |
| **4. Formato y esquema** | CSV sin comprimir, 12 columnas, estable entre dos días completos | CSV sin comprimir, 59 columnas, estable entre los dos períodos comparados | xlsx, 21 columnas |
| Clave candidata | Sí, verificada: 0 duplicados, 0 nulos en 141.007 filas | Verificada: 0 duplicados, 0 nulos en la muestra analizada | 0 duplicados en 14.045 filas |
| Acceso programático | Sí, API Socrata con `count(*)` previo y paginación | Sí, API Socrata/OData, con consulta y paginación | No, descarga manual de archivo `.xlsx` por período, sin `count(*)` previo |
| Columna categórica | `departamento`, `municipio`, `codigoestacion` | `departamento_entidad`, `ciudad_entidad`, `entidad`, `fase` | `DEPARTAMENTO`, `CALENDARIO` y `NATURALEZA` |
| Factor de expansión *k* | 3,2396, medido con `deep=True` | 3,1847, medido con `deep=True` | 3,91, medido con `deep=True` |
| Repositorio T2 | <https://github.com/JuanPabloCYT/bigdata-ean-ideam> | _(falta enlace)_ |https://github.com/yuyisramirezsa2005-lgtm/proyecto-acueducto |

> **Datos de la columna B aportados por Camilo Rojas**, commits `6d25399` y `3531904`.
>
> **Qué falta de la columna B**, y conviene cerrarlo antes de decidir:
> - El **volumen en bytes**. Están los registros y las columnas, pero no el tamaño en disco medido con `os.path.getsize()`, que es el insumo directo de la proyección de T3.
> - El **enlace al repositorio T2** de esa fuente.
> - El alcance de «la muestra analizada» en la clave candidata: cuántas filas se comprobaron, para saber si la unicidad se verificó sobre un período completo o sobre un extracto.

### Cómo llenar las columnas B y C en diez minutos

Cada integrante abre su propia ficha T1 y saca los datos de ahí. Si su repositorio T2 conserva el JSON de evidencias, casi todo sale de un comando **ejecutado dentro de su propio repositorio T2**:

```bash
python3 -c "
import json; d=json.load(open('docs/T1/evidencia/resultados_medicion.json'))
print('volumen  :', d['disco']['S0_bytes'], 'bytes')
print('licencia :', d['dataset']['licencia'])
print('g anual  :', d['crecimiento']['g_historico_anual'])
print('columnas :', len(d['dataframe']['tipos']))
print('k        :', d['dataframe']['k'])
"
```

Si su ficha T1 no guardó ese JSON, los datos están igualmente en su `ficha_tecnica.md`. Lo que **no** vale es estimarlos: si un dato no se midió, en la tabla va «no medido», y eso también informa la decisión.

---

### Instrucciones para los integrantes B y C

**Antes de empezar necesitan acceso de escritura.** El repositorio es público, así que pueden clonarlo sin más, pero el `push` fallará con un error de permisos si Juan Pablo no los ha añadido como colaboradores. Pásenle su usuario de GitHub primero.

**1. Clonar y entrar:**

```bash
git clone https://github.com/JuanPabloCYT/bigdata-ean-ideam.git
cd bigdata-ean-ideam
```

**2. Antes de editar, traer lo último.** Los tres van a tocar este mismo archivo, y si dos parten de versiones distintas aparecen conflictos:

```bash
git pull origin main
```

**3. Editar solo su propia columna** de la tabla de la sección 2. No tocar las columnas de los demás: si cada quien edita solo lo suyo, Git resuelve casi todo automáticamente. Y **avisar al grupo antes de empezar**, para no editar los tres a la vez.

**4. Commit con mensaje que explique qué cambió.** La rúbrica penaliza los commits sin mensaje, así que nada de «update» o «cambios»:

```bash
git add docs/T3_consolidacion_equipo.md
git commit -m "Consolidacion: datos medidos de la fuente <nombre> (integrante <su nombre>)"
git push origin main
```

**5. Si el push es rechazado** porque alguien subió antes:

```bash
git pull --rebase origin main
git push origin main
```

**Qué NO subir:** archivos de datos (CSV, parquet). El `.gitignore` ya los bloquea, pero si alguno aparece en `git status`, no lo fuercen — avisen y se revisa.

> El commit de cada integrante en este archivo es, además, la evidencia de autoría distribuida que pide la rúbrica. No hace falta inventar trabajo: llenar la propia columna con datos medidos ya es una contribución real y verificable.

---

## 3. Decisión

**Fuente elegida: A · Precipitación del IDEAM (`s54a-sgyg`).**

### Justificación técnica, contra los criterios de la sección 1

**Requisito eliminatorio 2 decide antes que nada.** La fuente C, Saber 11 (ICFES), no tiene licencia declarada en su portal oficial. La sección 1 de este mismo documento establece que una fuente que falle un requisito mínimo queda descartada «por buena que sea en lo demás». Publicar o redistribuir un derivado de un dato sin licencia clara es un riesgo legal que el equipo no puede asumir solo porque el resto de sus cifras sean sólidas. Con esto, la decisión real es entre A y B.

**Entre A y B, ambas cumplen los cuatro requisitos mínimos.** La diferencia la hacen los criterios de desempate:

| Criterio de desempate | A · IDEAM | B · SECOP II |
|---|---|---|
| Clave candidata verificada | Sí, sobre un día completo: 141.007 filas, 0 duplicados, 0 nulos | Sí, pero sobre «la muestra analizada» — el alcance no está precisado |
| Acceso programático con conteo previo | Sí, API Socrata con `count(*)` | Sí, API Socrata/OData con `count(*)` — empatan |
| Columna categórica | `departamento`, `municipio`, `codigoestacion` — cardinalidad media, sin evidencia de sesgo | `entidad`, `fase` — con 8,89 M de registros y muchas entidades, mayor riesgo de que unas pocas concentren el volumen (sesgo de clave, S4) |
| Esquema estable | Verificado entre dos días completos | Verificado entre dos períodos — empatan |

El desempate real no está en estos cuatro criterios, que quedan parejos, sino en algo que el propio proceso de T3 expuso: **el volumen físico de SECOP II en bytes nunca se aportó**. La columna B tiene registros (8,89 millones) y columnas (59), pero no el dato que la fórmula de T3 necesita como insumo directo, `S₀` medido con `os.path.getsize()`. Elegir B con ese vacío obligaría a estimar en vez de medir, justo lo que el criterio de aceptación de T3 prohíbe («si un dato no está medido, se escribe "no medido", no se estima»). Se pudo pedir esa medición antes de decidir, pero el equipo prioriza avanzar con la fuente que ya tiene el insumo completo y verificado.

**Costo de oportunidad reconocido, no ocultado.** La tasa de crecimiento de B es +6,42 % anual, positiva y simple de proyectar; la de A es −4,78 % anual, y obligó a declarar tres escenarios en `T3_proyeccion_almacenamiento.md` para poder dimensionar disco con sentido. Elegir A no es elegir el cálculo más fácil — es elegir la fuente con el insumo de volumen completo y la clave candidata verificada sobre un período cerrado, no sobre una muestra sin precisar.

### Qué se descartó y por qué

| Fuente | Razón del descarte |
|---|---|
| C · Saber 11 (ICFES) | Sin licencia declarada; falla el requisito eliminatorio 2 de la sección 1, independiente de sus otras cifras |
| B · SECOP II | Cumple los cuatro requisitos, pero no aportó el volumen en bytes ni el alcance exacto de la muestra donde verificó la clave candidata; su tasa de crecimiento positiva era su principal ventaja frente a A |

### Qué se rescata de las fuentes no elegidas

- **De SECOP II (B):** el criterio de tasa de crecimiento positiva queda registrado como referencia de contraste en `T3_proyeccion_almacenamiento.md` — sirve para mostrar que la elección de A no evita la dificultad, la asume con datos completos. Si en sesiones futuras (S9, variedad) el equipo necesita una fuente de alta cardinalidad para ilustrar sesgo de clave, SECOP II es candidata natural para un ejercicio comparativo.
- **De Saber 11 (C):** el método de Lina para verificar la clave candidata sobre datos consolidados por período (en vez de un extracto diario) es una técnica de comprobación distinta a la usada en A, y queda anotada para replicarla si el equipo trabaja con datos agregados más adelante.

---

## 4. Repositorio único del equipo

**Repositorio consolidado:** <https://github.com/JuanPabloCYT/bigdata-ean-ideam>

Al ser la fuente A la elegida, este es el repositorio base: ya contiene el entorno reproducible de T2, la ficha T1 versionada, la práctica del clúster HDFS y la proyección de T3. No hace falta migrar nada.

Los repositorios T2 individuales **no se borran**: quedan como evidencia de la entrega individual de cada quien, que sigue contando.

### Cómo dar acceso

```bash
gh repo edit JuanPabloCYT/bigdata-ean-ideam --add-collaborator USUARIO --permission push
```

O desde la web: `Settings` → `Collaborators` → `Add people`.

### Firma de los tres integrantes

La decisión está tomada cuando los tres han hecho al menos un commit en el repositorio consolidado.

| Integrante | Usuario de GitHub | De acuerdo con la fuente elegida |
|---|---|---|
| Juan Pablo Castro | `JuanPabloCYT` | Sí |
| Lina Ramírez | `yuyisramirezsa2005-lgtm` | Sí |
| Camilo Rojas | `Juanext81` | Sí |

---

## 5. Reparto del trabajo

> El enunciado pide «una línea sobre qué aportó cada uno», y la rúbrica evalúa que la historia de commits refleje el reparto real. Este cuadro se llena con lo que cada quien hizo de verdad, no con lo que se le asignó.

| Integrante | Aporte | Evidencia en el repositorio |
|---|---|---|
| Juan Pablo Castro | Fuente y ficha T1, entorno reproducible T2, práctica del clúster HDFS, script de proyección y documento T3 | Commits `19727b2` a `1c9b855` |
| Camilo Rojas | Medición y análisis de la fuente B (SECOP II) como candidata: volumen, tasa de crecimiento, clave candidata y factor de expansión, aportados a la comparación del equipo | Commits `6d25399`, `3531904` |
| Lina Ramírez | Medición y análisis de la fuente C (Saber 11 / ICFES) como candidata, y firma del acuerdo de la sección 4 | Commits `5816680`, `1369037` |

**Pendiente de cada integrante, ahora que la fuente está decidida:**

- **Camilo:** falta su firma de acuerdo en la sección 4 — su commit anterior fue solo la comparación técnica, no la aceptación de la fuente elegida. Y le queda la tarea 1 o la tarea 3 de [`T3_tareas_pendientes.md`](T3_tareas_pendientes.md) para sumar una contribución sobre el repositorio ya consolidado, no solo sobre la comparación de fuentes.
- **Lina:** ya firmó el acuerdo. Le queda la tarea 2 de [`T3_tareas_pendientes.md`](T3_tareas_pendientes.md) —el párrafo en inglés y el glosario— si tiene el extracto de Kleppmann, o cualquier otra de las cinco tareas repartidas.
