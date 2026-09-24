"""
Poblacion/PSO/PSO_IA/revision/sanity_check.py
================================================
Punto de entrada ejecutable de PSO_IA: corre ParticleSwarmOptimization
sobre una instancia y escribe el contrato de salida completo en ../Salida/.

Autocontenido, igual que algorithm.py.

Uso:
    python sanity_check.py <ruta_instancia.fjs> [opciones]
    python sanity_check.py ../Entrada/instances/mk01.fjs --semilla 1000

Ver --help para todas las opciones.
"""

import argparse
import csv
import json
import os
import platform
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from algorithm import ParticleSwarmOptimization, leer_instancia  # noqa: E402


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
# ESCRITURA DE SALIDA — mismo contrato que AG_IA / ACO_IA
# =============================================================================

def escribir_salida(directorio, instancia, ruta_instancia_original, resultado, parametros, semilla):
    os.makedirs(directorio, exist_ok=True)

    with open(ruta_instancia_original, "r") as f_in:
        contenido = f_in.read()
    with open(os.path.join(directorio, "forma1.txt"), "w") as f_out:
        f_out.write(contenido)

    with open(os.path.join(directorio, "parametros.txt"), "w") as f:
        f.write("algoritmo: PSO (Particle Swarm Optimization)\n")
        f.write("implementacion: PSO_IA\n")
        f.write(f"semilla: {semilla}\n")
        for clave, valor in parametros.items():
            f.write(f"{clave}: {valor}\n")

    with open(os.path.join(directorio, "salida1.txt"), "w") as f:
        f.write(f"instancia: {instancia.nombre}\n")
        f.write(f"makespan: {resultado['makespan']}\n")
        f.write("# horario: trabajo operacion maquina inicio fin\n")
        for (j, o, m, inicio, fin) in sorted(resultado["horario"], key=lambda x: x[3]):
            f.write(f"{j} {o} {m} {inicio} {fin}\n")

    with open(os.path.join(directorio, "representacion1.txt"), "w") as f:
        f.write("OS: " + " ".join(str(x) for x in resultado["os"]) + "\n")
        f.write("MS: " + " ".join(str(x) for x in resultado["ms"]) + "\n")

    with open(os.path.join(directorio, "tiempos.txt"), "w") as f:
        f.write(f"tiempo_total_s: {resultado['tiempo_s']}\n")
        f.write(f"iteraciones: {resultado['iteraciones']}\n")

    with open(os.path.join(directorio, "hardware.txt"), "w") as f:
        for clave, valor in detectar_hardware().items():
            f.write(f"{clave}: {valor}\n")

    with open(os.path.join(directorio, "g1.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tiempo_s", "mejor_makespan"])
        for t, mk in resultado["traza"]:
            w.writerow([t, mk])

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        tiempos = [t for t, _ in resultado["traza"]]
        makespans = [mk for _, mk in resultado["traza"]]
        plt.figure(figsize=(6, 4))
        plt.step(tiempos, makespans, where="post")
        plt.xlabel("Tiempo (s)")
        plt.ylabel("Mejor makespan")
        plt.title(f"Convergencia — PSO_IA — {instancia.nombre}")
        plt.tight_layout()
        plt.savefig(os.path.join(directorio, "g1.png"), dpi=120)
        plt.close()
    except ImportError:
        pass


# =============================================================================
# LÍNEA DE COMANDOS
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description="PSO_IA — corrida de revisión / generación de Salida/.")
    ap.add_argument("instancia", help="Ruta al archivo de instancia (.fjs)")
    ap.add_argument("--semilla", type=int, default=1000)
    ap.add_argument("--iteraciones", type=int, default=100)
    ap.add_argument("--tiempo-limite", type=float, default=None)
    ap.add_argument("--n-particulas", type=int, default=30)
    ap.add_argument("--w-max", type=float, default=0.9)
    ap.add_argument("--w-min", type=float, default=0.4)
    ap.add_argument("--c1", type=float, default=1.5)
    ap.add_argument("--c2", type=float, default=1.5)
    ap.add_argument("--parametros-json", default=None,
                     help="Ruta a un JSON con parámetros (p.ej. de una calibración con Optuna). "
                          "Un flag explícito en la línea de comandos tiene prioridad sobre el JSON.")
    ap.add_argument("--out", default=None,
                     help="Carpeta base donde crear Salida/. Por defecto, ../Salida relativo a este script.")
    args = ap.parse_args()

    valores_por_defecto = {"n_particulas": 30, "w_max": 0.9, "w_min": 0.4, "c1": 1.5, "c2": 1.5}
    if args.parametros_json:
        with open(args.parametros_json) as f:
            desde_json = json.load(f)
        for clave, valor in desde_json.items():
            if clave in valores_por_defecto and getattr(args, clave) == valores_por_defecto[clave]:
                setattr(args, clave, valor)

    instancia = leer_instancia(args.instancia)

    pso = ParticleSwarmOptimization(
        n_particulas=args.n_particulas,
        w_max=args.w_max,
        w_min=args.w_min,
        c1=args.c1,
        c2=args.c2,
        semilla=args.semilla,
    )
    resultado = pso.resolver(instancia, max_iteraciones=args.iteraciones,
                              tiempo_limite_s=args.tiempo_limite)

    marca_tiempo = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    base_salida = args.out or os.path.join(os.path.dirname(__file__), "..", "Salida")
    directorio = os.path.join(base_salida, marca_tiempo)

    parametros = {
        "n_particulas": args.n_particulas, "w_max": args.w_max, "w_min": args.w_min,
        "c1": args.c1, "c2": args.c2,
        "max_iteraciones": args.iteraciones, "tiempo_limite_s": args.tiempo_limite,
    }
    escribir_salida(directorio, instancia, args.instancia, resultado, parametros, args.semilla)

    print(f"Makespan final: {resultado['makespan']}")
    print(f"Iteraciones corridas: {resultado['iteraciones']}")
    print(f"Tiempo total: {resultado['tiempo_s']} s")
    print(f"Salida escrita en: {directorio}")


if __name__ == "__main__":
    main()
