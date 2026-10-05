"""
Poblacion/AG/AG_Alumno/calibracion/calibrar_optuna.py
=======================================================
Calibra los hiperparámetros de algorithm.resolver() (AG_Alumno) con
Optuna. Es la contraparte de ../../AG_IA/calibracion/calibrar_optuna.py —
misma metodología (mismas 10 instancias de calibración, mismas 2 semillas,
mismo presupuesto de 60 generaciones por corrida dentro de un trial, mismo
número de trials por defecto) para que ambas implementaciones se calibren
en igualdad de condiciones y la comparación final no esté sesgada por
haberle dado más esfuerzo de tuning a una que a la otra.

Diferencia con AG_IA: acá se calibran los 4 hiperparámetros que realmente
expone este algoritmo (tam_poblacion, prob_cruce, prob_mutacion,
tournsize) — no se inventan k_torneo/elitismo/estancamiento_max/
frac_inmigrantes porque esos mecanismos no existen en este diseño (no hay
inmigrantes aleatorios, ni elitismo explícito más allá del HallOfFame de
DEAP).

Uso
---
    python calibrar_optuna.py                      # 100 trials (pedido del profesor guía)
    python calibrar_optuna.py --n-trials 100

El estudio se persiste en calibracion.db (sqlite) — retomable si se corta.
Al terminar escribe mejores_parametros.json, compatible con
--parametros-json de ../revision/sanity_check.py.
"""

import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from algorithm import resolver  # noqa: E402

import optuna  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../AG_Alumno
INSTANCES_DIR = os.path.join(BASE, "Entrada", "instances")
BKS_PATH = os.path.join(BASE, "Entrada", "bks.json")
AQUI = os.path.dirname(os.path.abspath(__file__))

# Mismo subconjunto que AG_IA/calibracion/calibrar_optuna.py — necesario
# para que la comparación final sea justa (ver docstring del módulo).
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

# Rangos propios de este algoritmo (distinto set de hiperparámetros que
# AG_IA). tam_poblacion usa el mismo rango que AG_IA a propósito, para no
# darle de entrada más margen de población a una implementación que a la
# otra; prob_cruce/prob_mutacion/tournsize son los únicos otros knobs que
# expone este diseño (ver algorithm.py, sección 8-9).
RANGOS = {
    "tam_poblacion": ("int", 40, 150),
    "prob_cruce": ("float", 0.2, 0.95),
    "prob_mutacion": ("float", 0.05, 0.5),
    "tournsize": ("int", 2, 7),
}


def cargar_bks():
    with open(BKS_PATH) as f:
        return json.load(f)


def construir_objetivo(nombres, bks, semillas, generaciones):
    rutas = {n: os.path.join(INSTANCES_DIR, n + ".fjs") for n in nombres}

    def objetivo(trial):
        params = {}
        for clave, (tipo, lo, hi) in RANGOS.items():
            if tipo == "int":
                params[clave] = trial.suggest_int(clave, lo, hi)
            else:
                params[clave] = trial.suggest_float(clave, lo, hi)

        gaps = []
        for nombre, ruta in rutas.items():
            ub = bks[nombre]["upper_bound"]
            for semilla in semillas:
                resultado = resolver(
                    ruta,
                    tam_poblacion=params["tam_poblacion"],
                    prob_cruce=params["prob_cruce"],
                    prob_mutacion=params["prob_mutacion"],
                    tournsize=params["tournsize"],
                    max_generaciones=generaciones,
                    semilla=semilla,
                )
                gap = 100.0 * (resultado["makespan"] - ub) / ub
                gaps.append(gap)

        return statistics.mean(gaps)

    return objetivo


def main():
    ap = argparse.ArgumentParser(description="Calibración de AG_Alumno con Optuna.")
    ap.add_argument("--n-trials", type=int, default=100)
    ap.add_argument("--generaciones", type=int, default=60)
    ap.add_argument("--instancias", default=None)
    ap.add_argument("--semillas", default=None)
    ap.add_argument("--storage", default=f"sqlite:///{os.path.join(AQUI, 'calibracion.db')}")
    ap.add_argument("--study-name", default="ag_alumno_fjsp")
    args = ap.parse_args()

    nombres = args.instancias.split(",") if args.instancias else INSTANCIAS_CALIBRACION
    semillas = [int(s) for s in args.semillas.split(",")] if args.semillas else SEMILLAS_CALIBRACION

    bks = cargar_bks()
    faltantes = [n for n in nombres if n not in bks]
    if faltantes:
        sys.exit(f"Sin BKS en bks.json para: {faltantes}")

    print(f"Instancias de calibración ({len(nombres)}): {', '.join(nombres)}")
    print(f"Semillas: {semillas} | generaciones/trial: {args.generaciones} | trials: {args.n_trials}")
    print(f"Corridas por trial: {len(nombres) * len(semillas)}")

    objetivo = construir_objetivo(nombres, bks, semillas, args.generaciones)

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
        "generaciones_por_trial": args.generaciones,
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
