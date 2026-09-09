# Práctica S08 · Diagramado en C4

Sesión 8 · Hito A · Juan Pablo Castro

Esta sesión no tiene laboratorio de software: se **modela y se comunica una arquitectura**. Lo que queda producido son los diagramas que son el corazón del documento de arquitectura del Hito A, [`docs/T8_arquitectura.md`](../../docs/T8_arquitectura.md).

> **La regla que ordena la práctica:** el diagrama debe ser coherente con el paradigma de T7. Nuestro proyecto es **híbrido con dominancia de lotes**, así que el diagrama muestra la vía por lotes construida y **un solo** componente de flujo acotado — no una arquitectura de flujo puro que no decidimos.

## Qué hay aquí

| Archivo | Nivel | Qué es |
|---|---|---|
| `c4_nivel1_contexto.drawio` | 1 · Guiado | Diagrama de contexto, editable en draw.io |
| `c4_nivel2_contenedor.drawio` | 2 · Aplicado | Diagrama de contenedor, editable en draw.io |
| `workspace.dsl` | 3 · Frontera | El mismo modelo como código, en Structurizr |

Los tres archivos son **editables y versionables**, como pide la §6 de la guía: van al repositorio en formato editable, no solo como imagen. Los diagramas renderizados se ven directamente en [`docs/T8_arquitectura.md`](../../docs/T8_arquitectura.md), sección 4.

## Cómo abrirlos

**draw.io.** Entrar a https://app.diagrams.net, `Archivo → Abrir desde → Dispositivo` y seleccionar el `.drawio`. No hace falta activar la biblioteca de formas C4: las cajas son rectángulos con la paleta y el formato de etiqueta de C4 (`nombre · [tipo] · descripción`), para que el archivo abra en cualquier draw.io sin dependencias.

**Structurizr.** El `.dsl` se renderiza con Structurizr Lite:

```bash
cd practica/s08-c4
docker run -it --rm -p 8080:8080 -v "$PWD":/usr/local/structurizr structurizr/lite
```

y abrir `http://localhost:8080`. Genera las tres vistas del mismo modelo.

## Las cuatro reglas de notación, y cómo las cumple cada diagrama

| Regla | Cómo se cumple |
|---|---|
| Cada elemento se nombra y se tipifica | Toda caja lleva nombre, `[tipo]` y una línea de responsabilidad |
| Cada flecha lleva etiqueta y dirección | Las 6 relaciones del nivel 1 y las 9 del nivel 2 tienen etiqueta; las de contenedor llevan además tecnología o protocolo |
| Un diagrama, un nivel de abstracción | El nivel 1 no muestra ninguna pieza interna; el nivel 2 no muestra clases |
| El de contexto es una sola caja | En el nivel 1 la plataforma es una única caja azul |

## Dos decisiones de notación que conviene explicar

**El contenedor de C4 no es el de Docker, y en este proyecto no coinciden.** El cuaderno de análisis y la base analítica sí corren dentro de contenedores de Docker declarados en `docker-compose.yml`. El lago corre en el contenedor de MinIO, pero como contenedor de C4 es un **almacén**, no un proceso. Y la ingesta y el refinador son procesos de Python que se ejecutan en el equipo del anfitrión, **sin Docker**, y aun así son contenedores de C4 de pleno derecho porque se ejecutan de forma independiente. El diagrama lo dice en su propia leyenda para que nadie lea el mapeo como uno a uno.

**Lo que no está construido se dibuja como no construido.** El detector de umbral de lluvia intensa y el canal de telemetría aparecen con línea discontinua y la marca `PLANIFICADO`. T7 ya había declarado que el requisito de alerta se apoya en un canal que el proyecto hoy no consume. Dibujarlo como si existiera haría el diagrama más vistoso y menos cierto; ninguna de las dos piezas se ha ejecutado nunca.

## Qué se omitió a propósito en el nivel 2

Los tres actores del nivel 1 no se repiten en el diagrama de contenedor, siguiendo el criterio de correctitud de la guía («no repite el nivel de contexto»). Sí se conservan los dos sistemas externos de origen, porque son el otro extremo de las relaciones de ingesta: sin ellos, la ingesta y el detector quedarían con una flecha que no llega a ninguna parte, y la guía también pide que ningún contenedor quede suelto.

## Cómo se conecta con la entrega

| Elemento de la §6 de la guía | Dónde está |
|---|---|
| Diagrama C4 de contexto, editable | `c4_nivel1_contexto.drawio` · renderizado en T8 §4.1 |
| Diagrama C4 de contenedor, editable | `c4_nivel2_contenedor.drawio` · renderizado en T8 §4.2 |
| Nivel 3 o modelo como código | `workspace.dsl` · vía elegida: modelo como código, con la razón declarada dentro del archivo |
| Justificación de la arquitectura | [`docs/T8_reto_negocio.md`](../../docs/T8_reto_negocio.md) y, en versión técnica, T8 §3 |

## Referencias

Brewer, E. A. (2012). CAP twelve years later: How the "rules" have changed. *Computer, 45*(2), 23-29. https://doi.org/10.1109/MC.2012.37

Dehghani, Z. (2022). *Data mesh: Delivering data-driven value at scale*. O'Reilly Media.

Kleppmann, M. (2017). *Designing data-intensive applications*. O'Reilly Media.

---

## Declaración de uso de asistentes de inteligencia artificial

Se utilizó **Claude Code** para construir los tres archivos de diagrama y redactar este documento.

Los elementos del modelo no se inventaron: cada contenedor corresponde a una pieza que existe en el repositorio (`src/ingesta/`, `src/refinar/`, `src/mapreduce/`, `sql/01_esquema.sql`, los servicios de `docker-compose.yml`), y los componentes del nivel 3 corresponden a funciones reales de `src/ingesta/cargar_cruda.py`. La única pieza del modelo que no existe se marca como planificada en los tres archivos y en el texto.
