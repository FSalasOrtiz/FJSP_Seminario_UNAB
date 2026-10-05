"""
Poblacion/PSO/PSO_Alumno/revision/sanity_check.py
===================================================
Punto de entrada ejecutable de PSO_Alumno: corre FJSP_PSO sobre una
instancia y escribe el contrato de salida completo en ../Salida/ (mismo
contrato de 8 archivos que AG_IA).

Adaptado a la API real de ../algorithm.py (antes era una copia sin adaptar
del sanity_check de PSO_IA, que importaba ParticleSwarmOptimization — clase
que no existe acá). No se modificó ninguna línea de algorithm.py: este
archivo solo lo llama y traduce su resultado al contrato de salida.

Diferencias con PSO_IA que se reflejan acá (propias del diseño del alumno):
  - Parámetros: population_size, inertia, c1, c2 (inercia inicial con
    reducción fija de 0.3 a lo largo de la corrida, no w_max/w_min).
    Valores por defecto = los del bloque __main__ de algorithm.py.
  - solve() no acepta límite de tiempo: no hay --tiempo-limite.
  - solve() imprime una línea por iteración; se silencia desde acá.
  - El historial de solve() guarda el mejor makespan por ITERACIÓN, sin
    tiempo: g1.csv / g1.png usan iteración en el eje X (no segundos).
    El tiempo total se mide desde este script.
  - MS se escribe como la MÁQUINA elegida por operación.

Uso:
    python sanity_check.py <ruta_instancia.fjs> [opciones]
    python sanity_check.py ../Entrada/instances/mk01.fjs --semilla 1000

Ver --help para todas las opciones.
"""

import argparse
import contextlib
import csv
import io
import json
import os
import platform
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from algorithm import FJSP_PSO, read_fjsp_instance  # noqa: E402


# =============================================================================
# HARDWARE
# =============================================================================

def detectar_hardware():
    return {
        "sistema": f"{platform.system()} {platform.release()}",
        "procesador": platform.processor() or "no disponible",
        "nucleos_logicos": os.cpu_count() or "no disponible",
        "python": platform.python_version(),
        "passmark_cpu": "PENDIENTE - medir con https://www.cpubenchmark.net/ y completar a mano",
        "id_equipo": "PENDIENTE - asignar un identificador fijo por equipo fisico usado",
    }


# =============================================================================
# ESCRITURA DE SALIDA — mismo contrato que AG_IA
# =============================================================================

def escribir_salida(directorio, nombre_instancia, ruta_instancia_original, resultado, parametros, semilla):
    os.makedirs(directorio, exist_ok=True)

    with open(ruta_instancia_original, "r") as f_in:
        contenido = f_in.read()
    with open(os.path.join(directorio, "forma1.txt"), "w") as f_out:
        f_out.write(contenido)

    with open(os.path.join(directorio, "parametros.txt"), "w") as f:
        f.write("algoritmo: PSO (Particle Swarm Optimization)\n")
        f.write("implementacion: PSO_Alumno\n")
        f.write(f"semilla: {semilla}\n")
        for clave, valor in parametros.items():
            f.write(f"{clave}: {valor}\n")

    with open(os.path.join(directorio, "salida1.txt"), "w") as f:
        f.write(f"instancia: {nombre_instancia}\n")
        f.write(f"makespan: {resultado['makespan']}\n")
        f.write("# horario: trabajo operacion maquina inicio fin\n")
        for op in sorted(resultado["horario"], key=lambda x: x["start"]):
            f.write(f"{op['job']} {op['operation']} {op['machine']} {op['start']} {op['end']}\n")

    with open(os.path.join(directorio, "representacion1.txt"), "w") as f:
        f.write("# OS: id de trabajo por posición; MS: máquina elegida por operación (orden trabajo, operación)\n")
        f.write("OS: " + " ".join(str(x) for x in resultado["os"]) + "\n")
        f.write("MS: " + " ".join(str(x) for x in resultado["ms"]) + "\n")

    with open(os.path.join(directorio, "tiempos.txt"), "w") as f:
        f.write(f"tiempo_total_s: {resultado['tiempo_s']}\n")
        f.write(f"iteraciones: {resultado['iteraciones']}\n")

    with open(os.path.join(directorio, "hardware.txt"), "w") as f:
        for clave, valor in detectar_hardware().items():
            f.write(f"{clave}: {valor}\n")

    # Convergencia por iteración (el historial del alumno no registra tiempo).
    with open(os.path.join(directorio, "g1.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["iteracion", "mejor_makespan"])
        for it, mk in enumerate(resultado["historial"], start=1):
            w.writerow([it, mk])

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        iteraciones = list(range(1, len(resultado["historial"]) + 1))
        plt.figure(figsize=(6, 4))
        plt.step(iteraciones, resultado["historial"], where="post")
        plt.xlabel("Iteración")
        plt.ylabel("Mejor makespan")
        plt.title(f"Convergencia — PSO_Alumno — {nombre_instancia}")
        plt.tight_layout()
        plt.savefig(os.path.join(directorio, "g1.png"), dpi=120)
        plt.close()
    except ImportError:
        pass


# =============================================================================
# LÍNEA DE COMANDOS
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description="PSO_Alumno — corrida de revisión / generación de Salida/.")
    ap.add_argument("instancia", help="Ruta al archivo de instancia (.fjs)")
    ap.add_argument("--semilla", type=int, default=1000)
    ap.add_argument("--iteraciones", type=int, default=100)
    ap.add_argument("--population-size", type=int, default=40)
    ap.add_argument("--inertia", type=float, default=0.7)
    ap.add_argument("--c1", type=float, default=1.4)
    ap.add_argument("--c2", type=float, default=1.4)
    ap.add_argument("--parametros-json", default=None,
                     help="Ruta a un JSON con parámetros (p.ej. de una calibración con Optuna). "
                          "Un flag explícito en la línea de comandos tiene prioridad sobre el JSON.")
    ap.add_argument("--out", default=None,
                     help="Carpeta base donde crear Salida/. Por defecto, ../Salida relativo a este script.")
    args = ap.parse_args()

    valores_por_defecto = {"population_size": 40, "inertia": 0.7, "c1": 1.4, "c2": 1.4}
    if args.parametros_json:
        with open(args.parametros_json) as f:
            desde_json = json.load(f)
        for clave, valor in desde_json.items():
            if clave in valores_por_defecto and getattr(args, clave) == valores_por_defecto[clave]:
                setattr(args, clave, valor)

    jobs, number_of_machines = read_fjsp_instance(args.instancia)
    nombre_instancia = os.path.basename(args.instancia)

    t0 = time.time()
    solver = FJSP_PSO(
        jobs=jobs,
        number_of_machines=number_of_machines,
        population_size=args.population_size,
        iterations=args.iteraciones,
        inertia=args.inertia,
        c1=args.c1,
        c2=args.c2,
        seed=args.semilla,
    )
    with contextlib.redirect_stdout(io.StringIO()):  # solve() imprime cada iteración
        makespan, schedule, sequence, history = solver.solve()
    tiempo_s = round(time.time() - t0, 4)

    maquina_por_op = {(op["job"], op["operation"]): op["machine"] for op in schedule}
    resultado = {
        "makespan": makespan,
        "horario": schedule,
        "os": [j for j, _ in sequence],
        "ms": [maquina_por_op[k] for k in sorted(maquina_por_op)],
        "historial": history,
        "iteraciones": len(history),
        "tiempo_s": tiempo_s,
    }

    marca_tiempo = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    base_salida = args.out or os.path.join(os.path.dirname(__file__), "..", "Salida")
    directorio = os.path.join(base_salida, marca_tiempo)

    parametros = {
        "population_size": args.population_size, "inertia": args.inertia,
        "c1": args.c1, "c2": args.c2, "max_iteraciones": args.iteraciones,
    }
    escribir_salida(directorio, nombre_instancia, args.instancia, resultado, parametros, args.semilla)

    print(f"Makespan final: {resultado['makespan']}")
    print(f"Iteraciones corridas: {resultado['iteraciones']}")
    print(f"Tiempo total: {resultado['tiempo_s']} s")
    print(f"Salida escrita en: {directorio}")


if __name__ == "__main__":
    main()
