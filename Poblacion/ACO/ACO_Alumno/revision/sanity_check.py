"""
Poblacion/ACO/ACO_Alumno/revision/sanity_check.py
===================================================
Punto de entrada ejecutable de ACO_Alumno: corre ACO_FJSP sobre una
instancia y escribe el contrato de salida completo en ../Salida/ (mismo
contrato de 8 archivos que AG_IA).

Adaptado a la API real de ../algorithm.py (antes era una copia sin adaptar
del sanity_check de ACO_IA, que importaba AntColonyMMAS — clase que no
existe acá). No se modificó ninguna línea de algorithm.py: este archivo
solo lo llama y traduce su resultado al contrato de salida.

Diferencias con ACO_IA que se reflejan acá (propias del diseño del alumno):
  - ACO_FJSP recibe la instancia en el constructor, y resolver() devuelve
    (mejor_solucion, traza, iteraciones) en vez de un dict; el tiempo total
    se mide desde este script.
  - Parámetros: n_hormigas, alpha, beta, rho, q0 (no tiene opción de
    búsqueda local).
  - MS se escribe como la MÁQUINA elegida por operación (así la guarda
    Solucion.asignacion_maquinas), no como índice de alternativa.

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
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from algorithm import ACO_FJSP, InstanciaFJSP  # noqa: E402


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

def escribir_salida(directorio, instancia, ruta_instancia_original, resultado, parametros, semilla):
    os.makedirs(directorio, exist_ok=True)

    with open(ruta_instancia_original, "r") as f_in:
        contenido = f_in.read()
    with open(os.path.join(directorio, "forma1.txt"), "w") as f_out:
        f_out.write(contenido)

    with open(os.path.join(directorio, "parametros.txt"), "w") as f:
        f.write("algoritmo: ACO (MAX-MIN Ant System)\n")
        f.write("implementacion: ACO_Alumno\n")
        f.write(f"semilla: {semilla}\n")
        for clave, valor in parametros.items():
            f.write(f"{clave}: {valor}\n")

    with open(os.path.join(directorio, "salida1.txt"), "w") as f:
        f.write(f"instancia: {instancia.nombre_archivo}\n")
        f.write(f"makespan: {resultado['makespan']}\n")
        f.write("# horario: trabajo operacion maquina inicio fin\n")
        for (j, o, m, inicio, fin) in sorted(resultado["horario"], key=lambda x: x[3]):
            f.write(f"{j} {o} {m} {inicio} {fin}\n")

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
        plt.title(f"Convergencia — ACO_Alumno — {instancia.nombre_archivo}")
        plt.tight_layout()
        plt.savefig(os.path.join(directorio, "g1.png"), dpi=120)
        plt.close()
    except ImportError:
        pass


# =============================================================================
# LÍNEA DE COMANDOS
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description="ACO_Alumno — corrida de revisión / generación de Salida/.")
    ap.add_argument("instancia", help="Ruta al archivo de instancia (.fjs)")
    ap.add_argument("--semilla", type=int, default=1000)
    ap.add_argument("--iteraciones", type=int, default=100)
    ap.add_argument("--tiempo-limite", type=float, default=None)
    ap.add_argument("--n-hormigas", type=int, default=30)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", type=float, default=2.0)
    ap.add_argument("--rho", type=float, default=0.1)
    ap.add_argument("--q0", type=float, default=0.0)
    ap.add_argument("--parametros-json", default=None,
                     help="Ruta a un JSON con parámetros (p.ej. de una calibración con Optuna). "
                          "Un flag explícito en la línea de comandos tiene prioridad sobre el JSON.")
    ap.add_argument("--out", default=None,
                     help="Carpeta base donde crear Salida/. Por defecto, ../Salida relativo a este script.")
    args = ap.parse_args()

    valores_por_defecto = {"n_hormigas": 30, "alpha": 1.0, "beta": 2.0, "rho": 0.1, "q0": 0.0}
    if args.parametros_json:
        with open(args.parametros_json) as f:
            desde_json = json.load(f)
        for clave, valor in desde_json.items():
            if clave in valores_por_defecto and getattr(args, clave) == valores_por_defecto[clave]:
                setattr(args, clave, valor)

    instancia = InstanciaFJSP(args.instancia)

    t0 = time.time()
    aco = ACO_FJSP(
        instancia,
        n_hormigas=args.n_hormigas,
        alpha=args.alpha,
        beta=args.beta,
        rho=args.rho,
        q0=args.q0,
        semilla=args.semilla,
    )
    mejor, traza, iteraciones = aco.resolver(max_iteraciones=args.iteraciones,
                                             tiempo_limite_s=args.tiempo_limite)
    tiempo_s = round(time.time() - t0, 4)

    claves_ops = sorted(mejor.asignacion_maquinas)
    resultado = {
        "makespan": mejor.makespan,
        "horario": mejor.horario,
        "os": mejor.secuencia_operaciones,
        "ms": [mejor.asignacion_maquinas[k] for k in claves_ops],
        "traza": traza,
        "iteraciones": iteraciones,
        "tiempo_s": tiempo_s,
    }

    marca_tiempo = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    base_salida = args.out or os.path.join(os.path.dirname(__file__), "..", "Salida")
    directorio = os.path.join(base_salida, marca_tiempo)

    parametros = {
        "n_hormigas": args.n_hormigas, "alpha": args.alpha, "beta": args.beta,
        "rho": args.rho, "q0": args.q0,
        "max_iteraciones": args.iteraciones, "tiempo_limite_s": args.tiempo_limite,
    }
    escribir_salida(directorio, instancia, args.instancia, resultado, parametros, args.semilla)

    print(f"Makespan final: {resultado['makespan']}")
    print(f"Iteraciones corridas: {resultado['iteraciones']}")
    print(f"Tiempo total: {resultado['tiempo_s']} s")
    print(f"Salida escrita en: {directorio}")


if __name__ == "__main__":
    main()
