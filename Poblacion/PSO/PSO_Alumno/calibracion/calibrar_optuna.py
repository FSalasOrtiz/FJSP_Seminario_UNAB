"""
Poblacion/PSO/PSO_Alumno/calibracion/calibrar_optuna.py
=========================================================
Calibra los hiperparámetros de FJSP_PSO (algorithm.py) con Optuna,
buscando en los rangos sugeridos en ../params.yaml. Es la contraparte de
../../PSO_IA/calibracion/calibrar_optuna.py — misma metodología (pedido
del profesor guía: 100 trials por metaheurística), para que ambas
implementaciones se calibren en igualdad de condiciones:
  - TPE con seed=42, 100 trials por defecto.
  - Mismas 10 instancias de calibración y mismas 2 semillas.
  - Objetivo: gap % promedio contra el BKS (upper_bound de
    ../Entrada/bks.json), gap = 100 * (makespan - UB) / UB.
  - Presupuesto reducido por corrida dentro de un trial: 30 iteraciones,
    el 30 % de las 100 por defecto de revision/sanity_check.py (misma
    proporción que AG_IA y PSO_IA).

Diferencia con PSO_IA: acá se calibran los 4 hiperparámetros que expone
este diseño (population_size, inertia, c1, c2) — no hay w_max/w_min.
No se modificó algorithm.py; solve() imprime una línea por iteración y se
silencia desde acá.

Uso
---
    python calibrar_optuna.py                      # 100 trials (pedido del profesor guía)
    python calibrar_optuna.py --n-trials 100

El estudio se persiste en calibracion.db (sqlite) — si se corta a la
mitad, correr de nuevo el mismo comando retoma los trials ya hechos.

Al terminar escribe mejores_parametros.json, listo para pasarle a
revision/sanity_check.py con --parametros-json.
"""

import argparse
import contextlib
import io
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from algorithm import FJSP_PSO, read_fjsp_instance  # noqa: E402

import optuna  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../PSO_Alumno
INSTANCES_DIR = os.path.join(BASE, "Entrada", "instances")
BKS_PATH = os.path.join(BASE, "Entrada", "bks.json")
AQUI = os.path.dirname(os.path.abspath(__file__))

# Mismo subconjunto que AG_IA/PSO_IA — necesario para que la comparación
# entre implementaciones sea justa.
INSTANCIAS_CALIBRACION = [
    "ft06_edata",
    "la01_edata",
    "la21_edata",
    "mk01",
    "mk07",
    "mk10",
    "mk15",
    "abz7_edata",
    "dpp01a",
    "dpp10a",
]

SEMILLAS_CALIBRACION = [1000, 2000]

# Rangos de ../params.yaml (rango_sugerido de cada parámetro).
RANGOS = {
    "population_size": ("int", 15, 60),
    "inertia": ("float", 0.5, 1.0),
    "c1": ("float", 1.0, 2.5),
    "c2": ("float", 1.0, 2.5),
}


def cargar_bks():
    with open(BKS_PATH) as f:
        return json.load(f)


def cargar_instancias(nombres):
    instancias = {}
    for nombre in nombres:
        ruta = os.path.join(INSTANCES_DIR, nombre + ".fjs")
        instancias[nombre] = read_fjsp_instance(ruta)  # (jobs, number_of_machines)
    return instancias


def construir_objetivo(instancias, bks, semillas, iteraciones):
    def objetivo(trial):
        params = {}
        for clave, (tipo, lo, hi) in RANGOS.items():
            if tipo == "int":
                params[clave] = trial.suggest_int(clave, lo, hi)
            else:
                params[clave] = trial.suggest_float(clave, lo, hi)

        gaps = []
        for nombre, (jobs, number_of_machines) in instancias.items():
            ub = bks[nombre]["upper_bound"]
            for semilla in semillas:
                solver = FJSP_PSO(
                    jobs=jobs,
                    number_of_machines=number_of_machines,
                    iterations=iteraciones,
                    seed=semilla,
                    **params,
                )
                with contextlib.redirect_stdout(io.StringIO()):  # solve() imprime cada iteración
                    makespan, _, _, _ = solver.solve()
                gap = 100.0 * (makespan - ub) / ub
                gaps.append(gap)

        return statistics.mean(gaps)

    return objetivo


def main():
    ap = argparse.ArgumentParser(description="Calibración de PSO_Alumno con Optuna.")
    ap.add_argument("--n-trials", type=int, default=100)
    ap.add_argument("--iteraciones", type=int, default=30,
                     help="Presupuesto de iteraciones por corrida DENTRO de un trial "
                          "(menor que el default de sanity_check.py a propósito: es un proxy rápido).")
    ap.add_argument("--instancias", default=None,
                     help="Lista separada por comas (sin extensión), p.ej. mk01,mk15. "
                          "Por defecto usa el subconjunto curado del script.")
    ap.add_argument("--semillas", default=None,
                     help="Lista separada por comas, p.ej. 1000,2000,3000.")
    ap.add_argument("--storage", default=f"sqlite:///{os.path.join(AQUI, 'calibracion.db')}",
                     help="Storage de Optuna (permite retomar si se corta). Pasar '' para no persistir.")
    ap.add_argument("--study-name", default="pso_alumno_fjsp")
    args = ap.parse_args()

    nombres = args.instancias.split(",") if args.instancias else INSTANCIAS_CALIBRACION
    semillas = [int(s) for s in args.semillas.split(",")] if args.semillas else SEMILLAS_CALIBRACION

    bks = cargar_bks()
    faltantes = [n for n in nombres if n not in bks]
    if faltantes:
        sys.exit(f"Sin BKS en bks.json para: {faltantes}")

    print(f"Instancias de calibración ({len(nombres)}): {', '.join(nombres)}")
    print(f"Semillas: {semillas} | iteraciones/trial: {args.iteraciones} | trials: {args.n_trials}")
    print(f"Corridas por trial: {len(nombres) * len(semillas)}")

    instancias = cargar_instancias(nombres)
    objetivo = construir_objetivo(instancias, bks, semillas, args.iteraciones)

    study = optuna.create_study(
        study_name=args.study_name,
        storage=args.storage or None,
        load_if_exists=bool(args.storage),
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    ya_hechos = len(study.trials)
    if ya_hechos:
        print(f"Retomando estudio existente: {ya_hechos} trials ya corridos.")

    study.optimize(objetivo, n_trials=args.n_trials, show_progress_bar=True)

    print("\nMejor gap promedio encontrado: {:.3f}%".format(study.best_value))
    print("Mejores parámetros:")
    for clave, valor in study.best_params.items():
        print(f"  {clave}: {valor}")

    salida = {
        "gap_promedio_calibracion_pct": study.best_value,
        "instancias_calibracion": nombres,
        "semillas_calibracion": semillas,
        "iteraciones_por_trial": args.iteraciones,
        "n_trials": len(study.trials),
        **study.best_params,
    }
    ruta_salida = os.path.join(AQUI, "mejores_parametros.json")
    with open(ruta_salida, "w") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)
    print(f"\nParámetros escritos en: {ruta_salida}")
    print("Para usarlos en una corrida real:")
    print("  cd ../revision && python sanity_check.py <instancia> "
          f"--parametros-json {ruta_salida}")


if __name__ == "__main__":
    main()
