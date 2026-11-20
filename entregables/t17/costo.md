# Costo de leer · equipo-2

IFPN0025 · Big Data e Ingeniería de Datos · Universidad Ean

Un cierre diario que lee más de lo que necesita cuesta cada día. Esta sección convierte lo que medimos en archivos y bytes por cierre, lo proyecta a un año y calcula si el diseño de partición se paga.

## 1. Supuestos

| Supuesto | Valor |
|---|---|
| Tamaño por archivo diario (`tamano_archivos_leidos_b` de A, bitácora) | 43 855 B (~43 KiB) |
| Tamaño total de la capa (120 archivos × 43 855 B) | 5 262 600 B (~5,0 MiB) |
| Historia inicial de la capa $H$ | 120 días |
| Cierres proyectados $D$ (un año de cierres diarios) | 365 |
| Crecimiento del tamaño diario | ninguno (supuesto) |
| Costo por archivo abierto | no se usa precio monetario; se usa el volumen en bytes como proxy del costo de I/O |

## 2. Archivos y bytes por cierre y en un año

**Con partición por día (consulta A, poda exacta):** cada cierre lee **1 archivo** = 43 855 B. En 365 cierres: 365 archivos = 16,0 MiB.

**Sin partición o con filtro por columna interna (consulta A-fecha):** cada cierre lee los archivos cargados hasta ese día. En el primer cierre del año (día $H+1 = 121$) ya hay 121 archivos; en el último ($H+D = 485$) hay 485 archivos. Total de archivos abiertos en un año:

$$\sum_{d=H+1}^{H+D} d = \sum_{d=121}^{485} d = \frac{365 \cdot (2 \cdot 120 + 365 + 1)}{2} = \frac{365 \cdot 606}{2} = 110\,595 \ \text{archivos}$$

En bytes: $110\,595 \times 43\,855 \approx 4\,850 \ \text{MiB}$ (~4,7 GiB).

**Razón sin poda / con poda:**
$$\frac{2H + D + 1}{2} = \frac{2 \cdot 120 + 365 + 1}{2} = \frac{606}{2} = 303×$$

## 3. Tabla resumen

| Estrategia | Archivos por cierre (fin de año) | Total archivos en 1 año | Total bytes en 1 año | Razón vs. poda |
|---|---|---|---|---|
| Con poda por día (A) | 1 | 365 | 16,0 MiB | 1× |
| Sin poda / columna interna (A-fecha) | 485 | 110 595 | ~4 744 MiB | **303×** |

## 4. Lectura

La partición por día reduce el I/O de lectura en un factor de 303× al cabo de un año de operación, respecto a leer la capa completa en cada cierre. A la escala de esta práctica (43 KiB por archivo) la diferencia es pequeña en bytes absolutos; en producción, con archivos de cientos de MB, el factor de 303× representa la diferencia entre minutos y horas de lectura por cierre.

El costo de diseñar la partición (120 carpetas, una por día) es fijo e independiente del número de cierres; el beneficio crece linealmente con $H$ y $D$.
