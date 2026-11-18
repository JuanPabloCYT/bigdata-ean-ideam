# Práctica S14 · CDC del maestro de suscriptores

Sesión 14 · Juan Pablo Castro, Camilo Rojas, Lina Ramírez
Proyecto integrador: Plataforma de datos del acueducto · fuente `maestro_suscriptores`

Esta sesión demuestra que una CDC **basada en consulta** (sondeo con marca de
agua sobre `updated_at`) captura altas y modificaciones pero **nunca** captura
las bajas duras del maestro, porque una fila borrada del origen ya no satisface
`updated_at > checkpoint`. El punto ciego es estructural del método, no un error
del prototipo. El equipo decide una mitigación y la documenta como un ADR.

## Qué hay aquí

| Archivo | Qué es |
|---|---|
| `generar_cambios_suscriptores.py` | Generador del perfil de cambios por equipo (`--equipo`) |
| `prototipo_cdc_suscriptores.py` | Prototipo de CDC: población, flujo de cambios, doble corrida, repetición con checkpoint restablecido, funciones de costo y reconciliación |
| `control_t14.ipynb` | Cuaderno que ejecuta el prototipo y genera la evidencia |
| `resultados/evidencia_nivel2_equipo-2.md` | Evidencia del Nivel 2 (la genera el prototipo) |
| `resultados/perfil_equipo-2.json` | Perfil del equipo en JSON |

DDL: [`sql/T14_cdc_suscriptores.sql`](../../sql/T14_cdc_suscriptores.sql)
Memo ADR: [`docs/memo_adr_t14.md`](../../docs/memo_adr_t14.md)
Documentación Nivel 3: [`docs/T14_cdc_suscriptores.md`](../../docs/T14_cdc_suscriptores.md)
Plantilla de entrega: [`docs/T14_plantilla_entrega.md`](../../docs/T14_plantilla_entrega.md)

## Motor de ejecución

**DuckDB embebido (2.0.0).** El perfil s12 del archivo de servicios (PostgreSQL
17 en el contenedor `ideam_db`) no estaba disponible en la sesión y la
instalación nativa de PostgreSQL del host es solo la librería cliente `libpq`,
sin binario de servidor. DuckDB reproduce sin servidor las semánticas que el
prototipo necesita (`updated_at` como marca de agua, `INSERT … ON CONFLICT`,
funciones de ventana, `greatest()`). La conclusión (las bajas duras no se
capturan) es independiente del motor y se traslada a la pila PostgreSQL que usan
`stg_lecturas` (T12) y `stg_estado_medidor` (T13).

## Reproducción (sección 6 de la plantilla)

```bash
cd /Users/camilorojas/Projects/BigData/bigdata-ean-ideam
# 1) Entorno: venv con duckdb (ya en requirements.txt)
source .venv/bin/activate
python -m pip install duckdb          # si no está instalado

# 2) Generar el perfil de cambios del equipo
python practica/s14-cdc-suscriptores/generar_cambios_suscriptores.py --equipo equipo-2

# 3) Correr el prototipo de CDC (población inicial, flujo de cambios, doble
#    corrida antes/después, repetición con checkpoint restablecido, funciones
#    de costo, reconciliación). Escribe resultados/evidencia_nivel2_equipo-2.md
python practica/s14-cdc-suscriptores/prototipo_cdc_suscriptores.py --equipo equipo-2
```

Salida esperada en consola (resumen): el perfil del equipo, la tabla
generadas vs. capturadas (bajas capturadas = 0), la diferencia entre lo que ve
el destino y lo que hay en el origen (174 frente a 164), las filas duplicadas
tras repetir la corrida (32), la tabla `comparacion` de las tres alternativas,
`bajas_detectadas` por reconciliación (= 10) y las cuatro funciones de costo.
