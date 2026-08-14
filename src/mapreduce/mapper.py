#!/usr/bin/env python3
"""Mapper de la agregación T4: precipitación promedio por departamento.

Emite, por cada lectura válida, la clave `departamento` y el valor
`valorobservado,1` (suma parcial y conteo parcial). El mapper NUNCA
emite un promedio: siempre un par (suma, conteo), para que el
combinador y el reductor final consuman exactamente el mismo formato,
sin importar si el combinador corrió cero, una o varias veces.
"""
import csv
import sys

COL_VALOR = 3           # valorobservado
COL_DEPARTAMENTO = 5    # departamento

lector = csv.reader(sys.stdin)
for campos in lector:
    if len(campos) <= COL_DEPARTAMENTO:
        continue
    if campos[0] == "codigoestacion":
        # Encabezado. Con el archivo partido en varios splits, esta
        # línea solo aparece al inicio absoluto del archivo, pero se
        # verifica por contenido y no por posición, porque cada split
        # de Hadoop Streaming empieza a leer donde le tocó, no
        # necesariamente en la primera línea del archivo.
        continue
    departamento = campos[COL_DEPARTAMENTO].strip()
    if not departamento:
        continue
    try:
        valor = float(campos[COL_VALOR])
    except ValueError:
        continue
    # .format() en vez de f-strings: el nodemanager solo tiene
    # Python 3.5 (Debian Stretch, sin soporte), y las f-strings
    # llegaron en Python 3.6. Ver docs/T4_ejecucion.md.
    print("{}\t{},1".format(departamento, valor))
