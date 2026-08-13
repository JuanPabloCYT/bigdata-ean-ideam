# T3 · Consolidación del equipo

**IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean**
Paso cero de T3: de tres fichas y tres repositorios, a uno solo.

> **Documento en curso.** Las columnas de las otras dos fuentes se completan en la reunión del equipo. La decisión no está tomada mientras las tres columnas no estén llenas y los tres integrantes no hayan firmado la sección 4.

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
| Acceso programático | Sí, API Socrata con `count(*)` previo y paginación | Sí, API Socrata/OData, con consulta y paginación |No,Descarga manual de archivo `.xlsx` por período, ni `count(*)` previo |
| Columna categórica | `departamento`, `municipio`, `codigoestacion` | `departamento_entidad`, `ciudad_entidad`, `entidad`, `fase` |`DEPARTAMENTO`, `CALENDARIO` y `NATURALEZA` |
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

> Completar tras la comparación.

**Fuente elegida:** _(por definir)_

**Justificación técnica**, contra los criterios de la sección 1, no por preferencia:

_(por definir)_

**Qué se descartó y por qué.** Descartar es más difícil que elegir, y es lo que la rúbrica valora como «elección justificada por criterios técnicos». Para cada fuente no elegida, una línea con la razón concreta:

| Fuente | Razón del descarte |
|---|---|
| | |
| | |

**Qué se rescata de las fuentes no elegidas.** El enunciado permite «combinar lo mejor de ellas». Si alguna aporta algo —una técnica de medición, una comprobación de calidad, un cruce posible— se anota aquí para no perderlo:

_(por definir)_

---

## 4. Repositorio único del equipo

**Repositorio consolidado:** _(por definir)_

Si la fuente elegida es la A, el repositorio base es <https://github.com/JuanPabloCYT/bigdata-ean-ideam>, que ya contiene el entorno reproducible de T2, la ficha T1 versionada, la práctica del clúster y la proyección. Los otros dos integrantes se añaden como colaboradores con permiso de escritura.

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
| _(por definir)_ | | |
| _(por definir)_ | | |

---

## 5. Reparto del trabajo

> El enunciado pide «una línea sobre qué aportó cada uno», y la rúbrica evalúa que la historia de commits refleje el reparto real. Este cuadro se llena con lo que cada quien hizo de verdad, no con lo que se le asignó.

| Integrante | Aporte | Evidencia en el repositorio |
|---|---|---|
| Juan Pablo Castro | Fuente y ficha T1, entorno reproducible T2, práctica del clúster HDFS, script de proyección y documento T3 | Commits `19727b2` a `1c9b855` |
| _(por definir)_ | | |
| _(por definir)_ | | |
