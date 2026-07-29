# Evidencias

- `metadata_dataset.json`: metadatos oficiales de Socrata.
- `precipitacion_2026-06-22.csv`: partición diaria principal cruda.
- `precipitacion_2026-06-21.csv`: partición diaria comparable cruda.
- `consulta_descarga.txt`: consultas diarias y conteos históricos mensuales.
- `resultados_medicion.json`: cifras estructuradas usadas para la ficha.
- `procesos_memoria.csv`: programas con mayor memoria RSS al medir M.
- `verificacion_clave.csv`: nulos y duplicados de la clave candidata.
- `frecuencia_observada.csv`: intervalos temporales más frecuentes.
- `comparacion_esquema.csv`: comparación de columnas, orden, tipos y nulos.
- `estimacion_crecimiento.csv`: conteos de junio de 2025 y junio de 2026.
- `sensibilidad_umbral.csv`: horizontes para escenarios positivos.

`S0` corresponde al tamaño de una partición diaria. Los archivos mensuales
no se descargaron: la API permitió obtener sus conteos con `count(*)`.
