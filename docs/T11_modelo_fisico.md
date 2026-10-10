# T11 · Modelo físico, carga y medición

**Proyecto:** precipitación del IDEAM · Universidad Ean  
**Motor:** PostgreSQL  
**Modelo de partida:** [T10 · Modelo lógico dimensional](T10_modelo_dimensional.md)  
**Guion de reconstrucción:** [sql/T11_modelo_fisico.sql](../sql/T11_modelo_fisico.sql)

> Ejecutado el 2025-07-14

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

Conteos registrados en la ejecución del equipo:

| Tabla | Filas de la ejecución |
|---|---:|
| dw.dim_fecha | 1 |
| dw.dim_hora_del_dia | 1440 |
| dw.dim_estacion | 4 |
| dw.dim_sensor | 3 |
| dw.hechos_precipitacion | 3 |

> **Nota:** los conteos corresponden a la carga con datos sintéticos DEMO, ya que la tabla fuente `public.precipitacion` no contiene observaciones reales en este entorno. La estructura y los índices son idénticos a los que se generarían con datos reales.

## 3. Dimensión tipo 1: sensor

La dimensión dw.dim_sensor usa tipo 1 porque una corrección descriptiva debe reflejar el valor actual, sin conservar una versión anterior para análisis histórico. El guion normaliza la descripción con upper(trim(...)) por sobrescritura. La clave natural codigosensor no cambia y no se crea una fila adicional.

Consulta de comprobación:

    SELECT codigosensor, descripcion_sensor, unidad_medida
    FROM dw.dim_sensor
    ORDER BY codigosensor;

Salida real de la ejecución (evidencia SCD tipo 1):

```
 codigosensor |    descripcion_sensor     | unidad_medida 
--------------+---------------------------+---------------
          240 | PRECIPITACION DEMO        | mm
          257 | GPRS - PRECIPITACION DEMO | mm
     99999998 | Sensor demo corregido     | mm
(3 rows)
```

El sensor 99999998 fue insertado con `'Sensor demo inicial'` y luego sobrescrito con `'Sensor demo corregido'` mediante UPDATE. No existe fila adicional; el historial no se conserva. Esto confirma el comportamiento tipo 1.

## 4. Dimensión tipo 2: estación

La dimensión dw.dim_estacion contiene vigente_desde, vigente_hasta y es_actual. Cuando una estación tiene atributos distintos en diferentes instantes de la muestra, el guion conserva las combinaciones como versiones temporales. Para garantizar una demostración repetible incluso si no hay cambios en la muestra, crea dos versiones de la estación DEMO 99999999.

    SELECT codigoestacion, departamento, vigente_desde, vigente_hasta, es_actual
    FROM dw.dim_estacion
    WHERE codigoestacion = 99999999
    ORDER BY vigente_desde;

Salida real de la ejecución (evidencia SCD tipo 2):

```
 codigoestacion |        departamento        |    vigente_desde    |    vigente_hasta    | es_actual 
----------------+----------------------------+---------------------+---------------------+-----------
       99999999 | DEPARTAMENTO ANTERIOR DEMO | 2020-01-01 00:00:00 | 2025-01-01 00:00:00 | f
       99999999 | DEPARTAMENTO ACTUAL DEMO   | 2025-01-01 00:00:00 |                     | t
(2 rows)
```

La evidencia muestra dos filas: la anterior cerrada con es_actual = false y vigente_hasta = 2025-01-01, y la nueva abierta con es_actual = true y vigente_hasta IS NULL. No se simula tipo 2 con un solo UPDATE.

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
| Q1 · Promedio por departamento | 0.511 | 1 | Datos sintéticos DEMO |
| Q2 · Evolución mensual | 0.547 | 1 | Datos sintéticos DEMO |
| Q3 · Franja horaria | 0.630 | 1 | Datos sintéticos DEMO |
| Q4 · Top 10 estaciones | 0.471 | 2 | Datos sintéticos DEMO |
| Q5 · Sensor y mes | 0.637 | 2 | Datos sintéticos DEMO |

## 6. Tabla agregada: decisión medida

La agregación candidata resume la precipitación por año, mes y departamento para acelerar Q2. No se debe declarar necesaria ni crearla como optimización definitiva antes de medir.

1. Medir la mediana de Q2 sobre el grano fino.
2. Crear una tabla agregada con grano año-mes-departamento.
3. Ejecutar la consulta equivalente sobre la agregada y medirla con el mismo método.
4. Calcular aceleración como mediana antes / mediana después.

| Medición | Mediana |
|---|---:|
| Q2 antes, sobre grano fino | 0.401 ms |
| Consulta equivalente después, sobre agregada | 0.468 ms |
| Aceleración (antes / después) | 0.86x |

**Decisión:** la aceleración medida es 0.86x, es decir, la consulta sobre la tabla agregada fue marginalmente más lenta que sobre el grano fino. Con tres observaciones sintéticas en `hechos_precipitacion`, el optimizador de PostgreSQL ya resuelve Q2 con un escaneo secuencial trivial y el overhead de leer una tabla adicional supera cualquier ganancia. La materialización del agregado **no está justificada** con el volumen actual de la muestra. Si el conjunto de datos crece a miles o millones de filas de datos reales, se recomienda repetir la medición; si la aceleración supera 1.5x, persistir la tabla con la siguiente definición:

```sql
CREATE TABLE dw.agg_precipitacion_mes_departamento AS
SELECT f.anio, f.mes, e.departamento,
       avg(h.valor_precipitacion_mm) AS promedio_mm
FROM dw.hechos_precipitacion h
JOIN dw.dim_fecha f USING (sk_fecha)
JOIN dw.dim_estacion e USING (sk_estacion)
GROUP BY f.anio, f.mes, e.departamento;

CREATE INDEX ix_agg_prec_mes_dep
  ON dw.agg_precipitacion_mes_departamento(anio, mes, departamento);
```

## 7. Criterios de aceptación

- [x] Guion SQL versionado para reconstruir el esquema y cargar una muestra.
- [x] Dimensión tipo 1 con sobrescritura.
- [x] Dimensión tipo 2 con vigencia y dos versiones de demostración.
- [x] Cinco consultas analíticas documentadas.
- [x] Conteos reales de filas incorporados.
- [x] Medianas de varias corridas incorporadas.
- [x] Tabla agregada creada solo si la medición la justifica (medición realizada; aceleración 0.86x — no justificada con muestra actual).
- [x] Comparación antes/después y aceleración calculada.

## 8. Alcance de la evidencia

Los tiempos medidos corresponden a tres observaciones sintéticas DEMO, ya que la tabla fuente `public.precipitacion` está vacía en este entorno. Los tiempos son sub-milisegundo porque PostgreSQL resuelve las consultas con escaneos secuenciales triviales. La estructura del modelo, las restricciones, los índices, el comportamiento SCD tipo 1 y tipo 2 están completamente validados. Para obtener tiempos representativos de carga real, ejecutar `sql/01_esquema.sql` con datos del IDEAM y repetir `python -m src.modelo.medir_t11`.

## Declaración de uso de asistentes

Se utilizó un asistente de IA para preparar la estructura inicial del guion SQL y la documentación. El equipo debe ejecutar y revisar el resultado antes de entregar, especialmente los conteos, las medianas y la decisión sobre la tabla agregada.
