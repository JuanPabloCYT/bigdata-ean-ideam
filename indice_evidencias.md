# Índice de evidencias del pipeline del acueducto · equipo-2

IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean

| Etapa | Qué verifica | Comando | Resultado esperado | Commit | Resultado obtenido | Responsable |
|---|---|---|---|---|---|---|
| t12 | Carga idempotente: sin claves repetidas y una marca de agua por sector | `python pipeline/verificar_etapa.py --etapa t12` | `Etapa t12: APROBADA (4 de 4 comprobaciones)` | 0df1d4e | Etapa t12: APROBADA (4 de 4 comprobaciones) | Juan Pablo Castro |
| t13 | Estado de medidores sin duplicar y bitácora de intentos | `python pipeline/verificar_etapa.py --etapa t13` | `Etapa t13: APROBADA (5 de 5 comprobaciones)` | 0df1d4e | Etapa t13: APROBADA (5 de 5 comprobaciones) | Lina Ramírez |
| t14 | Cambios por tipo y punto de control | `python pipeline/verificar_etapa.py --etapa t14` | `Etapa t14: APROBADA (3 de 3 comprobaciones)` | 0df1d4e | Etapa t14: APROBADA (3 de 3 comprobaciones) | Camilo Rojas |
| t15 | Agregado diario por sector reconciliado y bitácora | `python pipeline/verificar_etapa.py --etapa t15` | `Etapa t15: APROBADA (6 de 6 comprobaciones)` | 7060371 | Etapa t15: APROBADA (6 de 6 comprobaciones) | Juan Pablo Castro |
| t16 | Esquema declarado, tipo físico de la marca temporal, particiones por día, reconciliación y bitácora | `python pipeline/verificar_etapa.py --etapa t16` | `Etapa t16: APROBADA (15 de 15 comprobaciones)` | a069c61 | Etapa t16: APROBADA (15 de 15 comprobaciones) | Lina Ramírez |
| t17 | Planes normalizados y versionados, hipótesis antes de medir, resultado idéntico entre variantes, lago sin cambios y entregables de texto | `python pipeline/verificar_etapa.py --etapa t17 --volumen ampliacion` | `Etapa t17: APROBADA (18 de 18 comprobaciones)` | (commit T17) | Etapa t17: APROBADA (18 de 18 comprobaciones) | Camilo Rojas |
