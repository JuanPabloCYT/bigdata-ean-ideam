#!/usr/bin/env python3
"""Combinador de la agregación T4: agrega localmente antes de la mezcla.

Recibe los mismos pares que produce el mapper, `departamento \t
valor,1`, ordenados por clave dentro de la tarea de mapeo. Suma y
cuenta por departamento, igual que el reductor, pero EMITE SUMA Y
CONTEO, nunca un promedio: el promedio de promedios no es el promedio.

Hadoop no garantiza que el combinador corra; puede correr cero, una o
varias veces sobre la salida de un mismo mapper. Por eso su formato de
salida es idéntico a su formato de entrada (dos números separados por
coma), y encadenarlo consigo mismo o con el reductor da el mismo
resultado.
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
        print("{}\t{:.6f},{}".format(actual, suma, conteo))
        suma, conteo = 0.0, 0

    actual = departamento
    suma += parcial_suma
    conteo += parcial_conteo

if actual is not None:
    print("{}\t{:.6f},{}".format(actual, suma, conteo))
