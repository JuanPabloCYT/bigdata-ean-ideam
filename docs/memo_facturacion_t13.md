# Memo · Lectura de Medidores — Lote Parcial

**Para:** Área de Facturación  
**De:** Equipo de Datos  
**Fecha:** 2026-06-22  
**Asunto:** Situación del lote de lecturas del día y qué esperar

---

## Qué ocurrió

Durante la recolección de lecturas de medidores del día 22 de junio de 2026, el sistema intentó procesar un lote de **15 registros** distribuidos en 3 grupos.

- Los grupos 1 y 2 se completaron sin inconvenientes: **10 registros** quedaron almacenados correctamente.
- El grupo 3 presentó interrupciones en la comunicación con el sistema de origen. El sistema realizó intentos adicionales de forma automática.
  - En el perfil donde los intentos adicionales tuvieron éxito: los **5 registros restantes** se recuperaron y el lote quedó **completo (15/15)**.
  - En el perfil donde los intentos se agotaron: los 5 registros del grupo 3 quedaron **pendientes (10/15 procesados)**.

---

## Qué NO debe asumir el área de facturación

Estas interrupciones **no indican** que los medidores estén inactivos ni que el consumo sea cero durante ese periodo.

Los valores de consumo casi siempre están siendo acumulados en el sistema de origen. La interrupción solo afecta la transferencia de los datos a nuestra base; los medidores siguen registrando.

**No emitir estimaciones ni ajustes de consumo** basados en la ausencia temporal de un registro. Esperar la confirmación de lote completo.

---

## Cuándo se considera completo el lote

El lote está completo cuando se cumplan **ambas** condiciones:

1. El campo de estado de la corrida muestra **COMPLETA**.
2. La cantidad de registros almacenados en la base coincide exactamente con el total informado por el sistema de origen (**15 registros**).

El sistema reintenta de forma automática al relanzar la carga. Una vez que ambas condiciones se cumplen, el área de facturación puede proceder con normalidad.

---

## Acción requerida

Si el lote no queda completo antes del cierre del día, notificar al equipo de datos para lanzar una nueva carga antes de las 20:00.

No procesar facturación parcial sobre registros incompletos.

---

*Área de Datos · Proyecto IDEAM*
