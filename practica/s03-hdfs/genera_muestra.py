# genera_muestra.py · muestra reproducible de ~15 MB
import csv, random
random.seed(42)  # semilla fija: todas las personas obtienen el mismo archivo

filas = 320_000  # aproxima 15 MB
with open("muestra/muestra.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["sensor_id", "timestamp", "caudal_l_s", "presion_bar"])
    for i in range(filas):
        w.writerow([
            random.randint(1, 500),
            f"2026-01-{random.randint(1,28):02d}T{random.randint(0,23):02d}:00",
            round(random.uniform(0.5, 45.0), 2),
            round(random.uniform(1.0, 6.0), 2),
        ])
print("Muestra generada en muestra/muestra.csv")
