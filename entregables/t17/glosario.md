# Glosario ES/EN · lectura de planes

IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean

| Término (inglés) | Equivalente en español | Definición de una línea |
|---|---|---|
| logical plan | plan lógico | Representación de las operaciones de una consulta antes de que el optimizador elija cómo ejecutarlas físicamente. |
| physical plan | plan físico | Conjunto de operaciones concretas que Spark ejecutará: qué nodo lee, qué nodo ordena, qué nodo mezcla. |
| predicate pushdown | empuje de predicado | Traslado de un filtro desde la capa de Spark al lector de Parquet para descartar filas lo antes posible. |
| partition pruning | poda de particiones | Eliminación de carpetas de partición enteras sin abrir sus archivos, basándose en los literales del filtro. |
| broadcast join | unión por difusión | Estrategia en la que la tabla más pequeña se envía completa a cada ejecutor para evitar la mezcla de la tabla grande. |
| sort-merge join | unión por ordenación y mezcla | Estrategia en la que ambas tablas se ordenan por la clave de unión y se mezclan en paralelo, con intercambio de datos entre particiones. |
| shuffle | mezcla | Redistribución de datos entre particiones a través de la red o del disco, necesaria para operaciones que requieren que los mismos valores de clave estén en la misma partición. |
| selectivity | selectividad | Fracción de filas que satisface un predicado; una alta selectividad (pocos resultados) hace más valioso el pushdown y la poda. |
