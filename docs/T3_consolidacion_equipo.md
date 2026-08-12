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

| | **A · Precipitación IDEAM** | **B · _(por definir)_** | **C · _(por definir)_** |
|---|---|---|---|
| **Integrante** | Juan Pablo Castro | | |
| **Conjunto** | `s54a-sgyg`, Datos Abiertos | | |
| **1. Volumen medido** | 21.953.076 B por partición diaria; 141.007 registros | | |
| **2. Licencia** | CC BY-SA 4.0 | | |
| **3. Tasa de crecimiento** | −4,780861 % anual, de conteos jun-2025 vs jun-2026 | | |
| **4. Formato y esquema** | CSV sin comprimir, 12 columnas, estable entre dos días completos | | |
| Clave candidata | Sí, verificada: 0 duplicados, 0 nulos en 141.007 filas | | |
| Acceso programático | Sí, API Socrata con `count(*)` previo y paginación | | |
| Columna categórica | `departamento`, `municipio`, `codigoestacion` | | |
| Factor de expansión *k* | 3,2396, medido con `deep=True` | | |
| Repositorio T2 | <https://github.com/JuanPabloCYT/bigdata-ean-ideam> | | |

### Cómo llenar las columnas B y C en diez minutos

Cada integrante abre su propia ficha T1 y saca los datos de ahí. Si su repositorio T2 conserva el JSON de evidencias, casi todo sale de un comando:

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
