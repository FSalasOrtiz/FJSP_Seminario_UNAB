"""
Poblacion/AG/AG_IA/revision/sanity_check.py
=============================================
Punto de entrada ejecutable de AG_IA: corre AlgoritmoGeneticoAG sobre una
instancia y escribe el contrato de salida completo en ../Salida/.

Autocontenido, igual que algorithm.py: la escritura de Salida/ AQUÍ es una
copia local, no una llamada a core/salida_writer.py — ese módulo vive en
core/ y está pensado para las metaheurísticas del experimento principal
(que sí comparten núcleo). Reusarlo desde acá rompería la independencia que
es la base de la comparación IA vs. Alumno.

Uso:
    python sanity_check.py <ruta_instancia.fjs> [opciones]
    python sanity_check.py ../../../data/instances/mk01.fjs --semilla 1000

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
from algorithm import AlgoritmoGeneticoAG, leer_instancia  # noqa: E402


# =============================================================================
# HARDWARE — registro básico (PassMark real requiere medirlo aparte)
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
# ESCRITURA DE SALIDA — contrato definido en experimento_humano_ia/README.md
# =============================================================================

def escribir_salida(directorio, instancia, ruta_instancia_original, resultado, parametros, semilla):
    os.makedirs(directorio, exist_ok=True)

    # forma1.txt — copia exacta de la instancia usada
    with open(ruta_instancia_original, "r") as f_in:
        contenido = f_in.read()
    with open(os.path.join(directorio, "forma1.txt"), "w") as f_out:
        f_out.write(contenido)

    # parametros.txt
    with open(os.path.join(directorio, "parametros.txt"), "w") as f:
        f.write("algoritmo: AG (Algoritmo Genetico)\n")
        f.write("implementacion: AG_IA\n")
        f.write(f"semilla: {semilla}\n")
        for clave, valor in parametros.items():
            f.write(f"{clave}: {valor}\n")

    # salida1.txt — solución final, formato simple y documentado
    with open(os.path.join(directorio, "salida1.txt"), "w") as f:
        f.write(f"instancia: {instancia.nombre}\n")
        f.write(f"makespan: {resultado['makespan']}\n")
        f.write("# horario: trabajo operacion maquina inicio fin\n")
        for (j, o, m, inicio, fin) in sorted(resultado["horario"], key=lambda x: x[3]):
            f.write(f"{j} {o} {m} {inicio} {fin}\n")

    # representacion1.txt — codificación interna (cromosoma)
    with open(os.path.join(directorio, "representacion1.txt"), "w") as f:
        f.write("OS: " + " ".join(str(x) for x in resultado["os"]) + "\n")
        f.write("MS: " + " ".join(str(x) for x in resultado["ms"]) + "\n")

    # tiempos.txt — separado de salida1.txt (acta, punto 6)
    with open(os.path.join(directorio, "tiempos.txt"), "w") as f:
        f.write(f"tiempo_total_s: {resultado['tiempo_s']}\n")
        f.write(f"generaciones: {resultado['generaciones']}\n")

    # hardware.txt
    with open(os.path.join(directorio, "hardware.txt"), "w") as f:
        for clave, valor in detectar_hardware().items():
            f.write(f"{clave}: {valor}\n")

    # g1.csv + g1.png — convergencia (makespan vs tiempo de reloj)
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
        plt.title(f"Convergencia — AG_IA — {instancia.nombre}")
        plt.tight_layout()
        plt.savefig(os.path.join(directorio, "g1.png"), dpi=120)
        plt.close()
    except ImportError:
        pass  # matplotlib no disponible: el CSV ya queda igual disponible


# =============================================================================
# LÍNEA DE COMANDOS
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description="AG_IA — corrida de revisión / generación de Salida/.")
    ap.add_argument("instancia", help="Ruta al archivo de instancia (.fjs)")
    ap.add_argument("--semilla", type=int, default=1000)
    ap.add_argument("--generaciones", type=int, default=200)
    ap.add_argument("--tiempo-limite", type=float, default=None,
                     help="Límite de tiempo en segundos (opcional, además del límite de generaciones)")
    ap.add_argument("--tam-poblacion", type=int, default=60)
    ap.add_argument("--prob-cruce", type=float, default=0.9)
    ap.add_argument("--prob-mut-os", type=float, default=0.2)
    ap.add_argument("--prob-mut-ms", type=float, default=0.3)
    ap.add_argument("--k-torneo", type=int, default=3)
    ap.add_argument("--elitismo", type=int, default=2)
    ap.add_argument("--estancamiento-max", type=int, default=15)
    ap.add_argument("--frac-inmigrantes", type=float, default=0.15)
    ap.add_argument("--parametros-json", default=None,
                     help="Ruta a un JSON con parámetros (p.ej. la salida de una calibración con Optuna). "
                          "Sobrescribe los valores por defecto; un flag explícito en la línea de comandos "
                          "sigue teniendo prioridad sobre el JSON.")
    ap.add_argument("--out", default=None,
                     help="Carpeta base donde crear Salida/. Por defecto, ../Salida relativo a este script.")
    args = ap.parse_args()

    valores_por_defecto = {
        "tam_poblacion": 60, "prob_cruce": 0.9, "prob_mut_os": 0.2, "prob_mut_ms": 0.3,
        "k_torneo": 3, "elitismo": 2, "estancamiento_max": 15, "frac_inmigrantes": 0.15,
    }
    if args.parametros_json:
        with open(args.parametros_json) as f:
            desde_json = json.load(f)
        for clave, valor in desde_json.items():
            if clave in valores_por_defecto and getattr(args, clave) == valores_por_defecto[clave]:
                setattr(args, clave, valor)

    instancia = leer_instancia(args.instancia)

    ag = AlgoritmoGeneticoAG(
        tam_poblacion=args.tam_poblacion,
        prob_cruce=args.prob_cruce,
        prob_mut_os=args.prob_mut_os,
        prob_mut_ms=args.prob_mut_ms,
        k_torneo=args.k_torneo,
        elitismo=args.elitismo,
        estancamiento_max=args.estancamiento_max,
        frac_inmigrantes=args.frac_inmigrantes,
        semilla=args.semilla,
    )
    resultado = ag.resolver(instancia, max_generaciones=args.generaciones,
                             tiempo_limite_s=args.tiempo_limite)

    marca_tiempo = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    base_salida = args.out or os.path.join(os.path.dirname(__file__), "..", "Salida")
    directorio = os.path.join(base_salida, marca_tiempo)

    parametros = {
        "tam_poblacion": args.tam_poblacion,
        "prob_cruce": args.prob_cruce,
        "prob_mut_os": args.prob_mut_os,
        "prob_mut_ms": args.prob_mut_ms,
        "k_torneo": args.k_torneo,
        "elitismo": args.elitismo,
        "estancamiento_max": args.estancamiento_max,
        "frac_inmigrantes": args.frac_inmigrantes,
        "max_generaciones": args.generaciones,
        "tiempo_limite_s": args.tiempo_limite,
    }
    escribir_salida(directorio, instancia, args.instancia, resultado, parametros, args.semilla)

    print(f"Makespan final: {resultado['makespan']}")
    print(f"Generaciones corridas: {resultado['generaciones']}")
    print(f"Tiempo total: {resultado['tiempo_s']} s")
    print(f"Salida escrita en: {directorio}")


if __name__ == "__main__":
    main()
