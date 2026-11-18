#!/usr/bin/env python3
"""T15 · Modelo de datos del acueducto (compartido por los generadores).

Dimensiones fijas para base y ampliación:
  * 12 sectores, 40 días -> 480 grupos (fecha, sector).
  * Base común: 1.200 medidores por sector (uniforme) -> 14.400 medidores y
    14.400 x 40 = 576.000 lecturas; 1.200 lecturas por (sector, día).
  * Ampliación: medidores por equipo, con un sector dominante que concentra
    una fracción p de los medidores (sesgo).

`consumo` es determinista por (medidor_id, día) y se guarda con 2 decimales
(m³), de modo que la suma por grupo, redondeada a 6 decimales, reconcilia
entre pandas (referencia) y Spark (salida) dentro de la tolerancia de 1e-6.
"""
from datetime import date, timedelta

SECTORES = [
    "RESIDENCIAL", "INDUSTRIAL", "COMERCIAL", "OFICIAL", "RURAL",
    "COMUNITARIO", "INSTITUCIONAL", "SERVICIOS",
]
N_DIAS = 60
BASE_DATE = date(2026, 1, 1)
MEDIDORES_POR_SECTOR_BASE = 1200  # base común: uniforme
# 8 sectores x 60 días = 480 grupos (fecha, sector); 1.200 x 8 x 60 = 576.000 lecturas.
# Con 8 sectores, groupByKey(sector, numPartitions=8) deja un sector por tarea.

# Perfil de ampliación por equipo: (medidores, fracción p, sector dominante).
# El conjunto completo (medidores, p, dominante) es único por equipo.
PERFILES_AMPLIACION = {
    "equipo-1": dict(medidores=18000, p=0.30, dominante="COMERCIAL"),
    "equipo-2": dict(medidores=30000, p=0.40, dominante="INDUSTRIAL"),
    "equipo-3": dict(medidores=24000, p=0.35, dominante="RESIDENCIAL"),
    "equipo-4": dict(medidores=15000, p=0.25, dominante="OFICIAL"),
    "equipo-5": dict(medidores=27000, p=0.45, dominante="RURAL"),
    "equipo-6": dict(medidores=21000, p=0.33, dominante="SERVICIOS"),
}


def fecha_iso(dia):
    return (BASE_DATE + timedelta(days=dia)).isoformat()


def consumo(medidor_id, dia):
    """Consumo determinista en m³ con 2 decimales."""
    return round(10.0 + (medidor_id % 100) * 0.7 + (dia % 30) * 0.3, 2)


def quality_flag(medidor_id, dia):
    """~95 % OK, ~5 % REVISAR (determinista). El agregado filtrado por OK
    NO reconcilia con el total: por eso el filtro de calidad es un contraste."""
    return "OK" if (medidor_id * 31 + dia * 17) % 20 != 0 else "REVISAR"
