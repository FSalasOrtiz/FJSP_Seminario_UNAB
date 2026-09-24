"""
Poblacion/AG/AG_IA/calibracion/calibrar_optuna.py
===================================================
Calibra los hiperparámetros de AlgoritmoGeneticoAG (algorithm.py) con
Optuna, buscando en los rangos sugeridos en ../params.yaml.

Por qué un subconjunto de instancias y no las 297
---------------------------------------------------
Cada trial de Optuna corre el AG entero sobre cada instancia de
calibración y cada semilla. Correr las 297 instancias por trial haría
que incluso 30 trials tardaran horas. En su lugar se usa un subconjunto
fijo (INSTANCIAS_CALIBRACION) elegido a mano para cubrir la variedad real
del benchmark: distintas familias (Brandimarte, Hurink, Dauzère-Pérès) y
distintos tamaños (6x6 hasta 30x15). Los parámetros encontrados así
generalizan razonablemente al resto porque el comportamiento del AG
depende sobre todo del tamaño/dificultad relativa, no de la instancia
puntual.

Qué mide cada trial
--------------------
Para cada combinación (instancia, semilla): gap %% = 100 * (makespan -
upper_bound) / upper_bound, usando las cotas congeladas en
../Entrada/bks.json. El objetivo a minimizar es el promedio de esos gaps.
Se usa gap normalizado (no makespan crudo) porque las instancias tienen
escalas de makespan muy distintas (decenas vs. miles) y promediar
makespan crudo dejaría que las instancias grandes dominen el objetivo.

Presupuesto por trial: menos generaciones que una corrida "oficial" (ver
--generaciones, default 60 contra 200 en revision/sanity_check.py) — es
un proxy más rápido de qué tan buena es una combinación de parámetros,
no una corrida final.

Uso
---
    python calibrar_optuna.py                      # 40 trials, valores por defecto
    python calibrar_optuna.py --n-trials 100
    python calibrar_optuna.py --instancias mk01,mk15,la01_edata

El estudio se persiste en calibracion.db (sqlite) — si se corta a la
mitad, correr de nuevo el mismo comando retoma los trials ya hechos en
vez de perderlos.

Al terminar escribe mejores_parametros.json, listo para pasarle a
revision/sanity_check.py con --parametros-json.
"""

import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from algorithm import AlgoritmoGeneticoAG, leer_instancia  # noqa: E402

import optuna  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../AG_IA
INSTANCES_DIR = os.path.join(BASE, "Entrada", "instances")
BKS_PATH = os.path.join(BASE, "Entrada", "bks.json")
AQUI = os.path.dirname(os.path.abspath(__file__))

# Subconjunto de calibración: cubre las 3 familias del benchmark y tamaños
# desde 6x6 hasta 30x15 (ver PROCEDENCIA.md para el origen de cada familia).
INSTANCIAS_CALIBRACION = [
    "ft06_edata",   # Brandimarte/clásica, 6x6 — piso del rango de tamaño
    "la01_edata",   # Hurink, 10x5, chica
    "la21_edata",   # Hurink, 15x10, mediana
    "mk01",         # Brandimarte, 10x6
    "mk07",         # Brandimarte, 20x5
    "mk10",         # Brandimarte, 20x15, alta flexibilidad
    "mk15",         # Brandimarte, 30x15 — techo del rango de tamaño
    "abz7_edata",   # Hurink, 20x15, difícil
    "dpp01a",       # Dauzère-Pérès
    "dpp10a",       # Dauzère-Pérès, otro punto de la familia
]

SEMILLAS_CALIBRACION = [1000, 2000]

RANGOS = {
    "tam_poblacion": ("int", 40, 150),
    "prob_cruce": ("float", 0.7, 0.95),
    "prob_mut_os": ("float", 0.1, 0.4),
    "prob_mut_ms": ("float", 0.1, 0.5),
    "k_torneo": ("int", 2, 5),
    "elitismo": ("int", 1, 5),
    "estancamiento_max": ("int", 8, 40),
    "frac_inmigrantes": ("float", 0.1, 0.3),
}


def cargar_bks():
    with open(BKS_PATH) as f:
        return json.load(f)


def cargar_instancias(nombres):
    instancias = {}
    for nombre in nombres:
        ruta = os.path.join(INSTANCES_DIR, nombre + ".fjs")
        instancias[nombre] = leer_instancia(ruta)
    return instancias


def construir_objetivo(instancias, bks, semillas, generaciones):
    def objetivo(trial):
        params = {}
        for clave, (tipo, lo, hi) in RANGOS.items():
            if tipo == "int":
                params[clave] = trial.suggest_int(clave, lo, hi)
            else:
                params[clave] = trial.suggest_float(clave, lo, hi)

        gaps = []
        for nombre, instancia in instancias.items():
            ub = bks[nombre]["upper_bound"]
            for semilla in semillas:
                ag = AlgoritmoGeneticoAG(semilla=semilla, **params)
                resultado = ag.resolver(instancia, max_generaciones=generaciones)
                gap = 100.0 * (resultado["makespan"] - ub) / ub
                gaps.append(gap)

        return statistics.mean(gaps)

    return objetivo


def main():
    ap = argparse.ArgumentParser(description="Calibración de AG_IA con Optuna.")
    ap.add_argument("--n-trials", type=int, default=40)
    ap.add_argument("--generaciones", type=int, default=60,
                     help="Presupuesto de generaciones por corrida DENTRO de un trial "
                          "(menor que el default de sanity_check.py a propósito: es un proxy rápido).")
    ap.add_argument("--instancias", default=None,
                     help="Lista separada por comas (sin extensión), p.ej. mk01,mk15. "
                          "Por defecto usa el subconjunto curado del script.")
    ap.add_argument("--semillas", default=None,
                     help="Lista separada por comas, p.ej. 1000,2000,3000.")
    ap.add_argument("--storage", default=f"sqlite:///{os.path.join(AQUI, 'calibracion.db')}",
                     help="Storage de Optuna (permite retomar si se corta). Pasar '' para no persistir.")
    ap.add_argument("--study-name", default="ag_ia_fjsp")
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

    instancias = cargar_instancias(nombres)
    objetivo = construir_objetivo(instancias, bks, semillas, args.generaciones)

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
