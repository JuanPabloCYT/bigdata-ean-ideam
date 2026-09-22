# Registros de decisión de arquitectura (ADR)

Un ADR documenta **una decisión**, no el sistema. Vive en el repositorio y se versiona con el código, para que dentro de seis meses alguien pueda entender por qué el proyecto es como es sin tener a quién preguntarle (Nygard, 2011).

| ADR | Decisión | Estado | Archivo |
|---|---|---|---|
| 0001 | Paradigma de almacenamiento: almacén, lago o lakehouse | Aceptado | [`0001-almacenamiento.md`](0001-almacenamiento.md) |
| — | Paradigma de procesamiento: lotes, Lambda, Kappa, malla o híbrido | Aceptado | [`../T9_ADR.md`](../T9_ADR.md) |

## Sobre la numeración

El ADR de paradigma de **procesamiento**, escrito por Camilo Rojas, está todavía en `docs/T9_ADR.md` y se titula a sí mismo «ADR-001». Es un ADR legítimo y bien construido —compara cinco alternativas, cita la evidencia de T1 a T7 y nombra sus costos—, pero registra la decisión de arquitectura de **T8**, no la de almacenamiento que pide T9.

Lo natural sería renumerarlo como `0002-paradigma-de-procesamiento.md` y moverlo a esta carpeta, para que los dos ADR queden juntos y numerados en orden. **No se ha movido todavía**, a la espera de acordarlo con su autor: mover un archivo ajeno sin avisar rompe los enlaces que otros hayan puesto y borra el rastro para quien lo busque donde lo dejó.

## Referencias

Nygard, M. (2011). *Documenting architecture decisions* [Entrada de blog]. Cognitect.
