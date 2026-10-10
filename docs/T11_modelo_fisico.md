# T11 · Modelo físico, carga y medición

**Proyecto:** precipitación del IDEAM · Universidad Ean  
**Motor:** PostgreSQL  
**Modelo de partida:** [T10 · Modelo lógico dimensional](T10_modelo_dimensional.md)  
**Guion de reconstrucción:** [sql/T11_modelo_fisico.sql](../sql/T11_modelo_fisico.sql)

> **Pendiente de ejecución:** los tiempos y conteos finales deben obtenerse en el entorno del equipo. No se reportan números inventados.

## 1. Modelo físico

El grano es una observación de precipitación de un sensor de una estación en un instante. El esquema está en el namespace `dw` para separarlo de la fuente `public.precipitacion`.

| Tabla | Propósito |
|---|---|
| dw.dim_fecha | Calendario y atributos de fecha |
| dw.dim_hora_del_dia | Hora y minuto del día, 1.440 valores |
| dw.dim_estacion | Estación con vigencia temporal tipo 2 |
| dw.dim_sensor | Catálogo con corrección tipo 1 |
| dw.hechos_precipitacion | Valor observado en milímetros y claves foráneas |

## 2. Reconstrucción y carga

Requisitos: PostgreSQL disponible y la tabla fuente creada con `sql/01_esquema.sql`.

    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/T11_modelo_fisico.sql

El guion toma hasta 10.000 observaciones reales. Si la fuente está vacía, carga tres observaciones sintéticas marcadas como DEMO para validar la estructura. La estación 99999999 es una entidad de prueba aislada de las estaciones reales; se usa para demostrar dos versiones SCD tipo 2 sin inventar historia de una estación real.

Después de ejecutar, completar los conteos que imprime el guion:

| Tabla | Filas de la ejecución |
|---|---:|
| dw.dim_fecha | Pendiente |
| dw.dim_hora_del_dia | Pendiente |
| dw.dim_estacion | Pendiente |
| dw.dim_sensor | Pendiente |
| dw.hechos_precipitacion | Pendiente |

## 3. Dimensión tipo 1: sensor

La dimensión dw.dim_sensor usa tipo 1 porque una corrección descriptiva debe reflejar el valor actual, sin conservar una versión anterior para análisis histórico. El guion normaliza la descripción con upper(trim(...)) por sobrescritura. La clave natural codigosensor no cambia y no se crea una fila adicional.

Consulta de comprobación:

    SELECT codigosensor, descripcion_sensor, unidad_medida
    FROM dw.dim_sensor
    ORDER BY codigosensor;

## 4. Dimensión tipo 2: estación

La dimensión dw.dim_estacion contiene vigente_desde, vigente_hasta y es_actual. Cuando una estación tiene atributos distintos en diferentes instantes de la muestra, el guion conserva las combinaciones como versiones temporales. Para garantizar una demostración repetible incluso si no hay cambios en la muestra, crea dos versiones de la estación DEMO 99999999.

    SELECT codigoestacion, departamento, vigente_desde, vigente_hasta, es_actual
    FROM dw.dim_estacion
    WHERE codigoestacion = 99999999
    ORDER BY vigente_desde;

La evidencia debe mostrar dos filas: la anterior cerrada con es_actual = false y la nueva abierta con es_actual = true y vigente_hasta IS NULL. No se simula tipo 2 con un solo UPDATE.

## 5. Cinco consultas analíticas

El benchmark automatizado está en [src/modelo/medir_t11.py](../src/modelo/medir_t11.py). Ejecutarlo desde la raíz después de cargar el modelo:

    python -m src.modelo.medir_t11

Configurar las variables POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER y POSTGRES_PASSWORD igual que en el entorno del proyecto. El script mide las cinco consultas siete veces, descarta la primera como calentamiento y reporta la mediana de las seis restantes. También compara Q2 con una tabla agregada temporal y calcula la aceleración. El tiempo incluye recuperar las filas en el cliente. Copiar los valores reales de la salida a las tablas de esta documentación.

Para mediciones comparables, mantener constantes el volumen y las condiciones de ejecución.

### Q1 · Precipitación promedio por departamento

    SELECT e.departamento, avg(h.valor_precipitacion_mm) AS promedio_mm
    FROM dw.hechos_precipitacion h
    JOIN dw.dim_estacion e USING (sk_estacion)
    GROUP BY e.departamento
    ORDER BY promedio_mm DESC NULLS LAST;

### Q2 · Evolución mensual por departamento

    SELECT f.anio, f.mes, e.departamento,
           avg(h.valor_precipitacion_mm) AS promedio_mm
    FROM dw.hechos_precipitacion h
    JOIN dw.dim_fecha f USING (sk_fecha)
    JOIN dw.dim_estacion e USING (sk_estacion)
    GROUP BY f.anio, f.mes, e.departamento
    ORDER BY f.anio, f.mes, e.departamento;

### Q3 · Precipitación por franja horaria

    SELECT dh.franja, avg(h.valor_precipitacion_mm) AS promedio_mm, count(*) AS observaciones
    FROM dw.hechos_precipitacion h
    JOIN dw.dim_hora_del_dia dh USING (sk_hora_del_dia)
    GROUP BY dh.franja
    ORDER BY promedio_mm DESC NULLS LAST;

### Q4 · Diez estaciones con mayor precipitación promedio

    SELECT e.codigoestacion, e.nombre_estacion, e.departamento,
           avg(h.valor_precipitacion_mm) AS promedio_mm, count(*) AS observaciones
    FROM dw.hechos_precipitacion h
    JOIN dw.dim_estacion e USING (sk_estacion)
    GROUP BY e.codigoestacion, e.nombre_estacion, e.departamento
    ORDER BY promedio_mm DESC NULLS LAST
    LIMIT 10;

### Q5 · Precipitación por sensor y mes

    SELECT f.anio, f.mes, s.codigosensor, s.descripcion_sensor,
           sum(h.valor_precipitacion_mm) AS suma_mm, count(*) AS observaciones
    FROM dw.hechos_precipitacion h
    JOIN dw.dim_fecha f USING (sk_fecha)
    JOIN dw.dim_sensor s USING (sk_sensor)
    GROUP BY f.anio, f.mes, s.codigosensor, s.descripcion_sensor
    ORDER BY f.anio, f.mes, s.codigosensor;

| Consulta | Mediana (ms) | Filas devueltas | Observaciones |
|---|---:|---:|---|
| Q1 · Promedio por departamento | Pendiente de medir | Pendiente | |
| Q2 · Evolución mensual | Pendiente de medir | Pendiente | |
| Q3 · Franja horaria | Pendiente de medir | Pendiente | |
| Q4 · Top 10 estaciones | Pendiente de medir | Pendiente | |
| Q5 · Sensor y mes | Pendiente de medir | Pendiente | |

## 6. Tabla agregada: decisión medida

La agregación candidata resume la precipitación por año, mes y departamento para acelerar Q2. No se debe declarar necesaria ni crearla como optimización definitiva antes de medir.

1. Medir la mediana de Q2 sobre el grano fino.
2. Crear una tabla agregada con grano año-mes-departamento.
3. Ejecutar la consulta equivalente sobre la agregada y medirla con el mismo método.
4. Calcular aceleración como mediana antes / mediana después.

| Medición | Mediana |
|---|---:|
| Q2 antes, sobre grano fino | Pendiente de medir |
| Consulta equivalente después, sobre agregada | Pendiente de medir |
| Aceleración (antes / después) | Pendiente de medir |

**Decisión:** pendiente de evidencia. Si la mejora es marginal en la muestra, documentar que no se justifica materializar el agregado todavía. Si es sustancial, añadir la definición de la tabla y su reconstrucción al guion SQL.

## 7. Criterios de aceptación

- [x] Guion SQL versionado para reconstruir el esquema y cargar una muestra.
- [x] Dimensión tipo 1 con sobrescritura.
- [x] Dimensión tipo 2 con vigencia y dos versiones de demostración.
- [x] Cinco consultas analíticas documentadas.
- [ ] Conteos reales de filas incorporados.
- [ ] Medianas de varias corridas incorporadas.
- [ ] Tabla agregada creada solo si la medición la justifica.
- [ ] Comparación antes/después y aceleración calculada.

## 8. Alcance de la evidencia

Los archivos del repositorio permiten preparar el modelo, pero no medir por sí solos el rendimiento de una instancia PostgreSQL en ejecución. Por eso los tiempos y la decisión final de materialización quedan pendientes hasta ejecutar el guion en el entorno del equipo. La muestra sintética sirve para comprobar la estructura; no debe presentarse como evidencia de rendimiento con datos reales.

## Declaración de uso de asistentes

Se utilizó un asistente de IA para preparar la estructura inicial del guion SQL y la documentación. El equipo debe ejecutar y revisar el resultado antes de entregar, especialmente los conteos, las medianas y la decisión sobre la tabla agregada.
