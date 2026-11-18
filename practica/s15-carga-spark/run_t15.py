#!/usr/bin/env python3
"""T15 · Orquestador de todas las corridas del pipeline de Spark.

Corre `pipeline/carga_spark.py` una vez por configuracion (cada corrida abre
su propia SparkSession y agrega una linea a bitacora_carga_spark.jsonl),
captura la linea RESULT de cada una y deja todo en resultados/. Al final
invoca el generador de evidencia.

Uso:  python practica/s15-carga-spark/run_t15.py --equipo equipo-2
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = os.path.join(REPO, ".venv-spark", "bin", "python")
CARGA = os.path.join(REPO, "pipeline", "carga_spark.py")
RES = os.path.join(REPO, "practica", "s15-carga-spark", "resultados")
BITACORA = os.path.join(RES, "bitacora_carga_spark.jsonl")
RESULTS = os.path.join(RES, "run_results.jsonl")

ENV = dict(os.environ)
ENV["JAVA_HOME"] = "/opt/homebrew/opt/openjdk@21"
ENV["PATH"] = "/opt/homebrew/opt/openjdk@21/bin:" + ENV.get("PATH", "")
ENV["PYSPARK_PYTHON"] = PY
ENV["PYSPARK_DRIVER_PYTHON"] = PY


def steps(equipo):
    s = []
    # Reproducibilidad: base x2 y ampliacion x2 (carga con escritura)
    for i in range(2):
        s.append(("base_carga_%d" % (i + 1),
                  ["--modo", "carga", "--volumen", "base", "--metodo", "reduceByKey", "--particiones-mezcla", "8"]))
    for i in range(2):
        s.append(("ampli_carga_%d" % (i + 1),
                  ["--modo", "carga", "--volumen", "ampliacion", "--metodo", "reduceByKey", "--particiones-mezcla", "8"]))
    # Barrido de particiones de mezcla: 3 valores x 3 corridas
    for n in (4, 8, 16):
        for i in range(3):
            s.append(("sweep_n%d_%d" % (n, i + 1),
                      ["--modo", "sweep", "--volumen", "ampliacion", "--metodo", "reduceByKey", "--particiones-mezcla", str(n)]))
    # Tarea que lee mas bytes: groupByKey por sector, 8 particiones
    s.append(("bytes_tarea", ["--modo", "bytes_tarea", "--volumen", "ampliacion"]))
    # groupBy de DataFrame: AQE on / off
    s.append(("aqe_on", ["--modo", "aqe", "--volumen", "ampliacion", "--aqe", "true"]))
    s.append(("aqe_off", ["--modo", "aqe", "--volumen", "ampliacion", "--aqe", "false"]))
    # Cache
    s.append(("cache", ["--modo", "cache", "--volumen", "ampliacion"]))
    # Contraste de formato: CSV vs parquet (sweep sobre csv_contraste, n=8)
    s.append(("csv_contraste", ["--modo", "sweep", "--volumen", "ampliacion", "--ruta", "csv_contraste", "--particiones-mezcla", "8"]))
    return [(name, ["--equipo", equipo] + args) for name, args in s]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equipo", required=True)
    args = ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    if os.path.exists(BITACORA):
        os.remove(BITACORA)
    if os.path.exists(RESULTS):
        os.remove(RESULTS)

    log_dir = os.path.join(RES, "logs")
    os.makedirs(log_dir, exist_ok=True)

    for name, cmd_args in steps(args.equipo):
        logf = open(os.path.join(log_dir, name + ".log"), "w")
        print(">>>", name, flush=True)
        try:
            out = subprocess.run([PY, CARGA] + cmd_args, env=ENV,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            logf.write(out.stdout)
            result = None
            for line in out.stdout.splitlines():
                if line.startswith("RESULT "):
                    result = json.loads(line[len("RESULT "):])
            with open(RESULTS, "a") as f:
                f.write(json.dumps({"step": name, "ok": out.returncode == 0,
                                    "result": result}, ensure_ascii=False) + "\n")
            print("    ok" if out.returncode == 0 else "    FAIL rc=%d" % out.returncode, flush=True)
        except Exception as e:
            print("    EXC", e, flush=True)
            with open(RESULTS, "a") as f:
                f.write(json.dumps({"step": name, "ok": False, "error": str(e)}) + "\n")
        finally:
            logf.close()

    print("=== generando evidencia ===", flush=True)
    subprocess.run([PY, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "generar_evidencia_t15.py"), "--equipo", args.equipo], env=ENV)
    print("=== listo ===", flush=True)


if __name__ == "__main__":
    main()
