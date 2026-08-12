# T3 · Trabajo pendiente y reparto

Lo que falta para cerrar T3, con qué queda por hacer de verdad. Cada tarea es trabajo real: produce algo que hoy no existe y que la entrega necesita.

**No es relleno para justificar commits.** La rúbrica evalúa que la historia refleje el reparto real del trabajo, así que quien haga la tarea es quien debe hacer el commit.

---

## Tarea 1 · La prueba del tercero sobre las cifras

**Peso: es el criterio de aceptación de toda la entrega (35 pts).**

El enunciado lo pide de forma explícita: *«Entreguen su proyección a otra persona junto con la ficha del equipo. Esa persona, siguiendo solo lo escrito, debe llegar a las mismas cifras.»*

Quien no escribió la proyección clona el repositorio en limpio y la reproduce:

```bash
git clone https://github.com/JuanPabloCYT/bigdata-ean-ideam.git
cd bigdata-ean-ideam
python3 src/proyeccion_almacenamiento.py
```

**Qué produce:** un archivo `docs/T3_verificacion_tercero.md` que responda tres cosas.

1. ¿Las cifras coinciden con las de `T3_proyeccion_almacenamiento.md`? Pegar la salida obtenida.
2. ¿Se entiende de dónde sale cada número **sin preguntarle a quien lo escribió**? Si hubo que preguntar algo, ese algo falta en el documento y hay que anotarlo.
3. ¿Se pudo rehacer a mano al menos una cifra con la fórmula del documento? Por ejemplo, comprobar que `7,4967 GB × 3 = 22,490 GB`.

Si algo no cuadra, **no se arregla en silencio**: se anota qué faltaba. Un fallo encontrado y documentado vale más que una verificación que dice «todo bien».

---

## Tarea 2 · Componente en inglés

**Peso: 10 pts. Hoy está en cero.**

Requiere el extracto de **Kleppmann (2017) sobre replicación** que está en Canvas. Nadie del equipo lo ha subido al repositorio todavía.

**Qué produce:**

1. Un párrafo de **80 a 120 palabras en inglés**, en `docs/T3_lectura_kleppmann.md`, que explique con palabras propias **qué problema resuelve la replicación y qué compromiso introduce**. La rúbrica premia «párrafo claro y propio, con dominio del vocabulario técnico», así que no sirve una traducción automática sin revisar.
2. **Tres términos** de esa lectura añadidos a `docs/glosario_bilingue.md`, en la sección que ya está reservada al final, con su definición breve en español.

**Sugerencia de enfoque para el párrafo**, para que no se quede en describir: la replicación resuelve dos problemas a la vez —disponibilidad ante fallos y cercanía del dato a quien lo consulta— pero introduce el problema de mantener las copias coherentes entre sí. Ese es el compromiso que el enunciado pide nombrar. Conecta directo con lo que el equipo midió: factor 3 dio tolerancia, y costó el triple de disco.

---

## Tarea 3 · Verificar la tolerancia a dos caídas simultáneas

**Peso: refuerza la recomendación de factor (30 pts).**

En la práctica quedó una limitación declarada y sin resolver: **no se pudo comprobar que con factor 3 el sistema tolera dos nodos caídos**. Con tres nodos de datos, apagar dos deja uno solo y el clúster no sostiene el factor. El equipo donde se hizo la práctica tiene 8 GB de RAM y la VM de Docker solo 3,83 GB.

**Si algún integrante tiene un equipo con 16 GB**, puede cerrarla:

1. Levantar el clúster de `practica/s03-hdfs/` añadiendo un cuarto nodo de datos.
2. Cargar un archivo con factor 3.
3. Detener **dos** nodos que alojen réplicas.
4. Comprobar con `hdfs fsck` que el archivo sigue `HEALTHY` y se lee íntegro.

**Qué produce:** la salida de `fsck` en `practica/s03-hdfs/resultados/`, y la actualización de la sección «Lo que no se pudo verificar» de `practica/s03-hdfs/bitacora.md`.

Es la única afirmación de la recomendación que hoy se sostiene solo por teoría y no por medición propia.

---

## Tarea 4 · Llenar la comparación de las tres fuentes

**Peso: 15 pts de consolidación.**

`docs/T3_consolidacion_equipo.md` tiene la tabla comparativa con la columna A llena y las columnas B y C vacías. Cada integrante llena la suya con datos **medidos**, sacándolos de su propia ficha T1 con el comando que está en ese documento.

**Qué produce:** las columnas B y C completas, más la sección 3 con la decisión, la justificación técnica y —lo que la rúbrica valora como «Destacado»— **la razón concreta por la que se descartó cada fuente no elegida**.

Descartar es más difícil que elegir. «No la elegimos porque sí» no puntúa; «no la elegimos porque su tasa de crecimiento era un supuesto y no una medición» sí.

---

## Tarea 5 · Revisar la recomendación desde fuera

**Peso: refuerza los 30 pts de recomendación.**

La recomendación actual —factor 3 para el dato crudo, factor 2 para el derivado— la escribió una sola persona. El enunciado la dirige a **una gerencia que no es técnica**.

**Qué produce:** una revisión de la sección 7 de `T3_proyeccion_almacenamiento.md` por alguien que no la escribió, verificando dos cosas.

1. ¿Un gerente sin formación técnica entendería el argumento? Cada término técnico sin definir en la misma línea es un problema.
2. ¿La recomendación se sostiene si la fuente elegida **no** es la del IDEAM? Si el equipo elige otra, el argumento de «telemetría irrecuperable» puede no aplicar y hay que rehacerlo.

---

## Resumen

| # | Tarea | Quién puede hacerla | Bloquea |
|---|---|---|---|
| 1 | Prueba del tercero sobre las cifras | Cualquiera que no escribió la proyección | 35 pts |
| 2 | Párrafo en inglés y tres términos | Quien tenga el extracto de Canvas | 10 pts |
| 3 | Tolerancia a dos caídas | Quien tenga 16 GB de RAM | Refuerza 30 pts |
| 4 | Comparación de las tres fuentes | Los tres, cada uno su columna | 15 pts |
| 5 | Revisión de la recomendación | Quien no la escribió | Refuerza 30 pts |

Las tareas 1, 4 y 5 no dependen de nada externo y se pueden hacer hoy. La 2 depende de bajar el extracto de Canvas. La 3 depende del hardware.
