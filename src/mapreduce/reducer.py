#!/usr/bin/env python3
"""Reductor de la agregación T4: precipitación promedio por departamento.

Recibe pares `departamento \t suma_parcial,conteo_parcial`, ordenados
por clave (lo garantiza la mezcla de Hadoop). Acumula suma y conteo
por departamento y solo al final, al cerrar cada grupo, calcula el
promedio. Nunca promedia promedios.

Funciona sin cambios reciba pares del mapper (`valor,1`) o del
combinador (`suma,conteo`): ambos son dos números separados por coma,
así que el reductor no necesita saber si el combinador corrió.
"""
import sys

actual, suma, conteo = None, 0.0, 0
for linea in sys.stdin:
    departamento, resto = linea.rstrip("\n").split("\t")
    parcial_suma_texto, parcial_conteo_texto = resto.split(",")
    parcial_suma = float(parcial_suma_texto)
    parcial_conteo = int(parcial_conteo_texto)

    if departamento != actual and actual is not None:
        # .format() en vez de f-strings: ver mapper.py.
        print("{}\t{:.4f}\t{}".format(actual, suma / conteo, conteo))
        suma, conteo = 0.0, 0

    actual = departamento
    suma += parcial_suma
    conteo += parcial_conteo

if actual is not None:
    print("{}\t{:.4f}\t{}".format(actual, suma / conteo, conteo))
