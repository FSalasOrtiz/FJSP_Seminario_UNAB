"""
revision/sanity_check.py — corrida manual de sa para inspección
rápida.

No es un test automático (para eso está tests/test_sa.py, con la
batería V1-V8). Esto es para cuando alguien quiere correrlo y mirar el
resultado con sus propios ojos: makespan, horario completo, gráfico de
convergencia — todo queda en ../Salida/, siguiendo el mismo contrato que
usa experimento_humano_ia/ (ver core/salida_writer.py).

Uso:
    python sanity_check.py [--instancia mk01] [--semilla 1000] [--evaluaciones 50000]
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from core.evaluation_budget import Presupuesto  # noqa: E402
from core.objective import evaluar  # noqa: E402
from core.parser import leer_instancia  # noqa: E402
from core.rng import crear_rng  # noqa: E402
from core.salida_writer import escribir_salida  # noqa: E402
from core.validator import validar  # noqa: E402
from Trayectoria.sa.algorithm import SimulatedAnnealing  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Corrida manual de sa para revisión.")
    ap.add_argument("--instancia", default="mk01")
    ap.add_argument("--semilla", type=int, default=1000)
    ap.add_argument("--evaluaciones", type=int, default=50000)
    args = ap.parse_args()

    raiz = os.path.join(os.path.dirname(__file__), "..", "..", "..")
    ruta_instancia = os.path.join(raiz, "data", "instances", f"{args.instancia}.fjs")
    instancia = leer_instancia(ruta_instancia)

    mh = SimulatedAnnealing(params={})
    rng = crear_rng(args.semilla)
    presupuesto = Presupuesto(args.evaluaciones)

    t0 = time.time()
    resultado = mh.resolver(instancia, rng, presupuesto)
    tiempo_total = time.time() - t0

    makespan, horario = evaluar(instancia, resultado.ms, resultado.os)
    es_valido = validar(instancia, horario, makespan)

    directorio_salida = os.path.join(os.path.dirname(__file__), "..", "Salida")
    ruta = escribir_salida(
        directorio_salida, "sa", instancia, ruta_instancia, resultado,
        parametros={}, semilla=args.semilla, tiempo_total_s=tiempo_total,
        evaluaciones_usadas=presupuesto.usadas, evaluaciones_maximas=presupuesto.maximo,
    )

    print(f"Instancia: {args.instancia}")
    print(f"Makespan: {makespan}")
    print(f"Válido: {es_valido}")
    print(f"Tiempo: {tiempo_total:.3f} s")
    print(f"Evaluaciones usadas: {presupuesto.usadas}/{presupuesto.maximo}")
    print(f"Salida escrita en: {ruta}")


if __name__ == "__main__":
    main()
