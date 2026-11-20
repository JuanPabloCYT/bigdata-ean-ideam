#!/usr/bin/env python3
"""T16 · Modelo de datos del acueducto — dimensiones y funciones compartidas.

Dimensiones fijas para la capa refinada:
  * 8 sectores, 120 días  → 960 grupos (fecha, sector).
  * Base común: 600 medidores por sector (uniforme) → 4.800 medidores ×
    120 días = 576.000 lecturas; 4.800 filas/día → 120 carpetas de día.
  * Reconciliacion 3-clave: fecha × sector × quality_flag →
    120 × 8 × 2 = 1.920 grupos (máximo; puede haber menos si algún par no
    tiene ambas banderas en todos los días, pero la combinatoria cierra a
    1.920; usamos 1.440 asumiendo que ~20 % de los días/sectores solo tienen
    un flag — en la práctica todos tienen los dos porque quality_flag es
    determinista; los 1.440 de la plantilla son los grupos reales del CSV de
    referencia heredado, aquí los calculamos del CSV real).
  * Reproceso de 6 días: 6 × 4.800 = 28.800 filas.

La capa de cruda usa CSV (120 archivos, uno por día).
La capa refinada hereda el esquema del paquete del curso:
  meter_id, timestamp (TimestampType, INT64 μs UTC), sector, consumo_m3,
  presion_bar, quality_flag.
"""
from datetime import date, timedelta, datetime, timezone

SECTORES = [
    "RESIDENCIAL", "INDUSTRIAL", "COMERCIAL", "OFICIAL",
    "RURAL", "COMUNITARIO", "INSTITUCIONAL", "SERVICIOS",
]
N_DIAS = 120
N_FECHAS = N_DIAS          # alias
BASE_DATE = date(2026, 1, 1)
MEDIDORES_POR_SECTOR_BASE = 600   # base común: uniforme; 600×8=4800 medidores
# 4800 medidores × 120 días = 576.000 lecturas; 4800 filas/día → 120 carpetas

# Perfil de ampliación por equipo (igual que T15, solo cambian las columnas
# porque ahora incluimos presion_bar; los perfiles son los mismos).
PERFILES_AMPLIACION = {
    "equipo-1": dict(medidores=18000, p=0.30, dominante="COMERCIAL"),
    "equipo-2": dict(medidores=30000, p=0.40, dominante="INDUSTRIAL"),
    "equipo-3": dict(medidores=24000, p=0.35, dominante="RESIDENCIAL"),
    "equipo-4": dict(medidores=15000, p=0.25, dominante="OFICIAL"),
    "equipo-5": dict(medidores=27000, p=0.45, dominante="RURAL"),
    "equipo-6": dict(medidores=21000, p=0.33, dominante="SERVICIOS"),
}


def fecha_iso(dia: int) -> str:
    return (BASE_DATE + timedelta(days=dia)).isoformat()


def timestamp_utc(dia: int, medidor_id: int) -> datetime:
    """Marca temporal determinista (hora = medidor_id % 24, min = dia % 60)."""
    d = BASE_DATE + timedelta(days=dia)
    return datetime(d.year, d.month, d.day,
                    medidor_id % 24, dia % 60, 0,
                    tzinfo=timezone.utc)


def consumo_m3(medidor_id: int, dia: int) -> float:
    """Consumo determinista en m³ con 2 decimales."""
    return round(10.0 + (medidor_id % 100) * 0.7 + (dia % 30) * 0.3, 2)


def presion_bar(medidor_id: int, dia: int) -> float:
    """Presión determinista en bar con 2 decimales (rango 0.5–5.0).
    Clases: baja < 1.0, normal [1.0, 3.0), alta >= 3.0."""
    return round(0.5 + (medidor_id % 46) * 0.1 + (dia % 5) * 0.1, 2)


def quality_flag(medidor_id: int, dia: int) -> str:
    """~95 % OK, ~5 % REVISAR (determinista)."""
    return "OK" if (medidor_id * 31 + dia * 17) % 20 != 0 else "REVISAR"


def nivel_presion(p: float):
    """Clasificación nativa (escalar). Usada también en la UDF por fila."""
    if p is None:
        return None
    if p < 1.0:
        return "baja"
    if p < 3.0:
        return "normal"
    return "alta"


def medidores_por_sector(medidores: int, p: float, dom_idx: int):
    """Distribuye `medidores` entre los 8 sectores con sesgo en dom_idx."""
    dom = int(round(p * medidores))
    other = medidores - dom
    otros = len(SECTORES) - 1
    base = other // otros
    resto = other % otros
    counts = [0] * len(SECTORES)
    j = 0
    for i in range(len(SECTORES)):
        if i == dom_idx:
            continue
        counts[i] = base + (1 if j < resto else 0)
        j += 1
    counts[dom_idx] = dom
    return counts
