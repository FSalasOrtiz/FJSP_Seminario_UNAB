"""
Poblacion/AG/AG_Alumno/revision/sanity_check.py
=================================================
Punto de entrada ejecutable de AG_Alumno: corre resolver() (algorithm.py)
sobre una instancia y escribe el contrato de salida completo en
../Salida/, con el MISMO formato de 7 archivos que usa AG_IA — para que
ambas implementaciones se puedan comparar sin conocer el código interno
de la otra.

Adaptado a la API real de este algoritmo (DEAP, cromosoma único, sin
separar OS/MS, sin inmigrantes ni elitismo explícito más allá del
HallOfFame) — no es una copia de AG_IA/revision/sanity_check.py, que
importaba nombres (AlgoritmoGeneticoAG, leer_instancia) que no existen acá.

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
from algorithm import resolver  # noqa: E402


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
# ESCRITURA DE SALIDA — mismo contrato de 7 archivos que AG_IA
# =============================================================================

def escribir_salida(directorio, nombre_instancia, ruta_instancia_original, resultado, parametros, semilla):
    os.makedirs(directorio, exist_ok=True)

    # forma1.txt — copia exacta de la instancia usada
    with open(ruta_instancia_original, "r") as f_in:
        contenido = f_in.read()
    with open(os.path.join(directorio, "forma1.txt"), "w") as f_out:
        f_out.write(contenido)

    # parametros.txt
    with open(os.path.join(directorio, "parametros.txt"), "w") as f:
        f.write("algoritmo: AG (Algoritmo Genetico)\n")
        f.write("implementacion: AG_Alumno\n")
        f.write(f"semilla: {semilla}\n")
        for clave, valor in parametros.items():
            f.write(f"{clave}: {valor}\n")

    # salida1.txt — solución final, mismo formato que AG_IA
    # (nota: las máquinas acá quedan en base 1, tal como las lee load_fjs;
    # AG_IA las convierte a base 0 al leer — diferencia de implementación,
    # no un error de ninguna de las dos)
    with open(os.path.join(directorio, "salida1.txt"), "w") as f:
        f.write(f"instancia: {nombre_instancia}\n")
        f.write(f"makespan: {resultado['makespan']}\n")
        f.write("# horario: trabajo operacion maquina inicio fin\n")
        horario_ordenado = sorted(resultado["horario"], key=lambda op: op["start"])
        for op in horario_ordenado:
            f.write(f"{op['job']} {op['operation']} {op['machine']} {op['start']} {op['finish']}\n")

    # representacion1.txt — codificación interna (cromosoma único, no OS/MS)
    with open(os.path.join(directorio, "representacion1.txt"), "w") as f:
        f.write("# codificación: gene = operation_id * MAX_ALTERNATIVES + alternativa\n")
        f.write("CROMOSOMA: " + " ".join(str(x) for x in resultado["individuo"]) + "\n")

    # tiempos.txt
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
        plt.title(f"Convergencia — AG_Alumno — {nombre_instancia}")
        plt.tight_layout()
        plt.savefig(os.path.join(directorio, "g1.png"), dpi=120)
        plt.close()
    except ImportError:
        pass  # matplotlib no disponible: el CSV ya queda igual disponible


# =============================================================================
# LÍNEA DE COMANDOS
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description="AG_Alumno — corrida de revisión / generación de Salida/.")
    ap.add_argument("instancia", help="Ruta al archivo de instancia (.fjs)")
    ap.add_argument("--semilla", type=int, default=1000)
    ap.add_argument("--generaciones", type=int, default=100)
    ap.add_argument("--tiempo-limite", type=float, default=None,
                     help="Límite de tiempo en segundos (opcional, además del límite de generaciones)")
    ap.add_argument("--tam-poblacion", type=int, default=50)
    ap.add_argument("--prob-cruce", type=float, default=0.3)
    ap.add_argument("--prob-mutacion", type=float, default=0.2)
    ap.add_argument("--tournsize", type=int, default=5)
    ap.add_argument("--parametros-json", default=None,
                     help="Ruta a un JSON con parámetros (p.ej. la salida de una calibración con Optuna). "
                          "Sobrescribe los valores por defecto; un flag explícito en la línea de comandos "
                          "sigue teniendo prioridad sobre el JSON.")
    ap.add_argument("--out", default=None,
                     help="Carpeta base donde crear Salida/. Por defecto, ../Salida relativo a este script.")
    args = ap.parse_args()

    valores_por_defecto = {
        "tam_poblacion": 50, "prob_cruce": 0.3, "prob_mutacion": 0.2, "tournsize": 5,
    }
    if args.parametros_json:
        with open(args.parametros_json) as f:
            desde_json = json.load(f)
        for clave, valor in desde_json.items():
            clave_attr = clave  # los nombres del JSON ya coinciden con los atributos de argparse
            if clave_attr in valores_por_defecto and getattr(args, clave_attr, None) == valores_por_defecto[clave_attr]:
                setattr(args, clave_attr, valor)

    resultado = resolver(
        args.instancia,
        tam_poblacion=args.tam_poblacion,
        prob_cruce=args.prob_cruce,
        prob_mutacion=args.prob_mutacion,
        tournsize=args.tournsize,
        max_generaciones=args.generaciones,
        tiempo_limite_s=args.tiempo_limite,
        semilla=args.semilla,
    )

    marca_tiempo = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    base_salida = args.out or os.path.join(os.path.dirname(__file__), "..", "Salida")
    directorio = os.path.join(base_salida, marca_tiempo)

    parametros = {
        "tam_poblacion": args.tam_poblacion,
        "prob_cruce": args.prob_cruce,
        "prob_mutacion": args.prob_mutacion,
        "tournsize": args.tournsize,
        "max_generaciones": args.generaciones,
        "tiempo_limite_s": args.tiempo_limite,
    }
    nombre_instancia = os.path.splitext(os.path.basename(args.instancia))[0]
    escribir_salida(directorio, nombre_instancia, args.instancia, resultado, parametros, args.semilla)

    print(f"Makespan final: {resultado['makespan']}")
    print(f"Generaciones corridas: {resultado['generaciones']}")
    print(f"Tiempo total: {resultado['tiempo_s']} s")
    print(f"Salida escrita en: {directorio}")


if __name__ == "__main__":
    main()
