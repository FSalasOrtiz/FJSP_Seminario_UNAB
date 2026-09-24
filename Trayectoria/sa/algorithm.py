"""Simulated Annealing (recocido simulado) para el FJSP.

Metaheurística de REFERENCIA de la Fase 2 (ver METODOLOGIA.md, sección 8.1).
Su único propósito adicional a resolver el problema es someter el contrato
de core/ a un algoritmo real antes de migrar las otras siete. No copia nada
del SA del repositorio anterior: ese SA no tenía código (Hallazgo 3 de la
auditoría, ver docs/auditoria_experimento_previo.md), solo resultados en CSV.

Lo único que puede variar entre metaheurísticas es la estrategia de
búsqueda (METODOLOGIA.md, 4.1). Este archivo NO decodifica, NO calcula
makespan por su cuenta, y NO usa aleatoriedad fuera de `rng`.
"""

import math

from core.metaheuristic import Metaheuristica, Resultado
from core.objective import evaluar
from core.solution import ms_aleatorio, os_canonico


class SimulatedAnnealing(Metaheuristica):

    nombre = "sa"
    version = "1.0.0"

    def __init__(self, params: dict):
        self.params = params
        self.t0 = params.get("temperatura_inicial", 100.0)
        self.t_min = params.get("temperatura_minima", 1e-3)
        self.prob_movimiento_ms = params.get("prob_movimiento_ms", 0.3)

    def resolver(self, instancia, rng, presupuesto) -> Resultado:
        # --- solución inicial -------------------------------------------
        os_actual = os_canonico(instancia)
        rng.shuffle(os_actual)
        ms_actual = ms_aleatorio(instancia, rng)

        mk_actual, _ = evaluar(instancia, ms_actual, os_actual, presupuesto)

        mejor_ms = list(ms_actual)
        mejor_os = list(os_actual)
        mejor_mk = mk_actual

        traza = [(presupuesto.usadas, mejor_mk)]

        # El enfriamiento se ata a la FRACCIÓN DE PRESUPUESTO CONSUMIDA, no
        # al tiempo de reloj ni al número de iteraciones: D8 exige que el
        # presupuesto sea en evaluaciones, y por lo tanto el criterio de
        # parada -y todo lo que depende de "cuánto llevamos"- debe medirse
        # en esa misma unidad. Enfriamiento geométrico clásico
        # (Kirkpatrick et al., 1983): T(f) = t0 * (t_min/t0)^f, con
        # f = fracción de evaluaciones usadas, f en [0, 1].
        max_evaluaciones = presupuesto.maximo
        razon = self.t_min / self.t0 if self.t0 > 0 else 1.0

        # --- bucle principal --------------------------------------------
        while not presupuesto.agotado():
            fraccion = presupuesto.usadas / max_evaluaciones
            temperatura = max(self.t0 * (razon ** fraccion), self.t_min)

            ms_vecino, os_vecino = self._generar_vecino(instancia, ms_actual, os_actual, rng)
            mk_vecino, _ = evaluar(instancia, ms_vecino, os_vecino, presupuesto)

            delta = mk_vecino - mk_actual
            if delta <= 0:
                acepta = True
            else:
                # Metropolis: acepta un empeoramiento con probabilidad
                # exp(-delta / T). Toda la aleatoriedad sale de `rng`
                # (D9); nunca del módulo random global.
                acepta = rng.random() < math.exp(-delta / temperatura)

            if acepta:
                ms_actual, os_actual, mk_actual = ms_vecino, os_vecino, mk_vecino

            if mk_actual < mejor_mk:
                mejor_ms = list(ms_actual)
                mejor_os = list(os_actual)
                mejor_mk = mk_actual

            traza.append((presupuesto.usadas, mejor_mk))

        return Resultado(ms=mejor_ms, os=mejor_os, makespan=mejor_mk, traza=traza)

    def _generar_vecino(self, instancia, ms, os_vec, rng):
        """Genera un vecino aplicando UNO de dos movimientos elementales,
        elegido con `rng` según `prob_movimiento_ms`.

        Movimiento OS (swap): intercambia dos posiciones del vector OS.
        Como OS es una permutación con repetición, cualquier intercambio de
        posiciones produce otro OS válido (misma multiplicidad por trabajo)
        sin necesidad de reparación.

        Movimiento MS (reasignación): elige una operación al azar y le
        cambia la alternativa de máquina, si tiene más de una disponible.
        No requiere aplicarse siempre: si la operación elegida es rígida
        (una sola máquina posible), el vecino generado es idéntico al
        actual y el propio criterio de Metropolis lo trata como delta=0.
        """
        ms_vecino = list(ms)
        os_vecino = list(os_vec)

        if rng.random() < self.prob_movimiento_ms:
            gid = rng.randrange(instancia.total_ops)
            n_alt = len(instancia.alternativas(gid))
            if n_alt > 1:
                actual = ms_vecino[gid]
                nueva = rng.randrange(n_alt - 1)
                if nueva >= actual:
                    nueva += 1
                ms_vecino[gid] = nueva
        else:
            i, k = rng.sample(range(instancia.total_ops), 2)
            os_vecino[i], os_vecino[k] = os_vecino[k], os_vecino[i]

        return ms_vecino, os_vecino
