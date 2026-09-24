"""Búsqueda Tabú (Tabu Search) para el FJSP.

Migración de `Tabú/taboo_search.py` (repositorio anterior) al contrato único
de `core/` (METODOLOGIA.md, sección 4). Ver `README.md` de esta carpeta para
el mapeo detallado y la lista de diferencias respecto a la versión original.

Diferencias de fondo respecto a la versión anterior (no son detalles
cosméticos, son las que la hacen comparable con el resto del repositorio):

1. No decodifica por su cuenta. La versión anterior traía su propio
   `decodificar()` en `taboo_search.py`. Aquí toda evaluación pasa por
   `core.objective.evaluar`, que a su vez invoca el decodificador único de
   D5. Esto no corrige un bug de magnitud como el de ACO/TS+VNS (hallazgo 2
   de la auditoría: ese Tabú simple sí construía un horario activo), pero
   sí es la misma violación de D2/D5 en espíritu: un decodificador propio
   es una fuente de divergencia silenciosa aunque hoy calcule lo mismo.
2. El presupuesto se mide en evaluaciones (D8), no en segundos de reloj. La
   versión anterior corría con `limite_tiempo=60.0`.
3. La aleatoriedad viene exclusivamente de `rng` (D9), nunca de
   `random.Random(semilla)` creado y usado localmente sin pasar por el
   contrato.
4. La solución se representa como el par canónico `(MS, OS)` (D4), no como
   `(asignación, secuencia)`. `OS` es exactamente lo que la versión anterior
   llamaba `secuencia`: un vector con repetición de trabajos. La diferencia
   está en el ruteo: la versión anterior guardaba el número de máquina
   directamente en `asignacion[j][o]`; aquí `MS[g]` guarda el ÍNDICE de la
   alternativa dentro de `instancia.alternativas(g)`, nunca el número de
   máquina (ver `core/solution.py`).
5. La tenencia tabú y el criterio de diversificación se miden en
   EVALUACIONES consumidas (`presupuesto.usadas`), no en un contador de
   iteraciones del bucle de búsqueda. Es la misma idea que usa el SA de
   referencia para su enfriamiento (`presupuesto.usadas / presupuesto.maximo`
   en `Trayectoria/sa/algorithm.py`): todo lo que en el algoritmo depende
   de "cuánto llevamos" se ata a la única unidad de tiempo válida bajo D8.
6. Cuando ningún movimiento no-tabú (o admitido por aspiración) resultó
   evaluable dentro del presupuesto, esta versión aplica el mejor movimiento
   ya evaluado en la misma pasada, en vez de volver a evaluar todos los
   candidatos ignorando el estatus tabú (así lo hacía la versión anterior).
   Evaluar dos veces el mismo conjunto de vecinos consumiría el doble de
   presupuesto por el mismo resultado, lo cual es exactamente lo que D8
   quiere evitar.
"""

from core import solution as S
from core.metaheuristic import Metaheuristica, Resultado
from core.objective import evaluar


class BusquedaTabu(Metaheuristica):

    nombre = "tabu"
    version = "1.0.0"

    def __init__(self, params: dict):
        self.params = params
        self.max_vecinos = params.get("max_vecinos", 40)
        self.iter_sin_mejora_diversif = params.get("iter_sin_mejora_diversif", 40)
        self.intentos_inicial = params.get("intentos_inicial", 5)
        self.tenencia_min = params.get("tenencia_min", None)
        self.tenencia_max_extra = params.get("tenencia_max_extra", 6)

    # -- ciclo principal ----------------------------------------------------

    def resolver(self, instancia, rng, presupuesto) -> Resultado:
        mejor_ms, mejor_os, mejor_mk, mejor_sched = self._solucion_inicial(
            instancia, rng, presupuesto
        )

        ms_actual = list(mejor_ms)
        os_actual = list(mejor_os)
        mk_actual = mejor_mk
        schedule_actual = mejor_sched

        traza = [(presupuesto.usadas, mejor_mk)]

        tenencia_min = self.tenencia_min or max(5, round(instancia.total_ops ** 0.5))
        tenencia_max = tenencia_min + self.tenencia_max_extra

        tabu = {}  # clave de movimiento -> evaluaciones en que expira
        sin_mejora = 0

        while not presupuesto.agotado():
            criticas = self._ruta_critica(instancia, schedule_actual, mk_actual)
            op_en_pos = self._posiciones(instancia, os_actual)

            candidatos = self._generar_candidatos(
                instancia, ms_actual, os_actual, criticas, op_en_pos, rng
            )
            if not candidatos:
                break  # solución trivial sin vecinos

            mov_admisible, mk_admisible, sched_admisible = None, None, None
            mov_cualquiera, mk_cualquiera, sched_cualquiera = None, None, None

            for mov in candidatos:
                if presupuesto.agotado():
                    break
                cand_mk, cand_sched = self._evaluar_movimiento(
                    instancia, ms_actual, os_actual, mov, presupuesto
                )

                if mov_cualquiera is None or cand_mk < mk_cualquiera:
                    mov_cualquiera, mk_cualquiera, sched_cualquiera = (
                        mov, cand_mk, cand_sched,
                    )

                clave = self._clave(mov, op_en_pos)
                es_tabu = tabu.get(clave, -1) > presupuesto.usadas
                aspira = cand_mk < mejor_mk
                if es_tabu and not aspira:
                    continue
                if mov_admisible is None or cand_mk < mk_admisible:
                    mov_admisible, mk_admisible, sched_admisible = (
                        mov, cand_mk, cand_sched,
                    )

            if mov_admisible is not None:
                mov_elegido, mk_elegido, sched_elegido = (
                    mov_admisible, mk_admisible, sched_admisible,
                )
            else:
                mov_elegido, mk_elegido, sched_elegido = (
                    mov_cualquiera, mk_cualquiera, sched_cualquiera,
                )

            if mov_elegido is None:
                break  # presupuesto agotado antes de evaluar ningún candidato

            self._aplicar_movimiento(ms_actual, os_actual, mov_elegido)
            ten = rng.randint(tenencia_min, tenencia_max)
            tabu[self._clave(mov_elegido, op_en_pos)] = presupuesto.usadas + ten

            mk_actual = mk_elegido
            schedule_actual = sched_elegido

            if mk_actual < mejor_mk:
                mejor_ms = list(ms_actual)
                mejor_os = list(os_actual)
                mejor_mk = mk_actual
                sin_mejora = 0
            else:
                sin_mejora += 1

            traza.append((presupuesto.usadas, mejor_mk))

            if sin_mejora >= self.iter_sin_mejora_diversif and not presupuesto.agotado():
                sin_mejora = 0
                tabu.clear()
                ms_actual, os_actual = self._perturbar(instancia, mejor_ms, mejor_os, rng)
                mk_actual, schedule_actual = evaluar(
                    instancia, ms_actual, os_actual, presupuesto
                )
                traza.append((presupuesto.usadas, mejor_mk))

        return Resultado(ms=mejor_ms, os=mejor_os, makespan=mejor_mk, traza=traza)

    # -- solución inicial -----------------------------------------------

    def _solucion_inicial(self, instancia, rng, presupuesto):
        """Multi-arranque: varios puntos de partida, conserva el mejor.

        Cada intento combina asignación por carga balanceada
        (`core.solution.ms_carga_balanceada`) con una secuencia aleatoria.
        Si el presupuesto se agota antes de completar un intento, se resuelve
        con lo que haya (al menos un arranque) o con una solución aleatoria
        mínima si ni eso alcanzó.
        """
        mejor_ms = mejor_os = mejor_sched = None
        mejor_mk = None

        for _ in range(self.intentos_inicial):
            if presupuesto.agotado():
                break
            ms_i = S.ms_carga_balanceada(instancia, rng)
            os_i = S.os_aleatorio(instancia, rng)
            mk_i, sched_i = evaluar(instancia, ms_i, os_i, presupuesto)
            if mejor_mk is None or mk_i < mejor_mk:
                mejor_ms, mejor_os, mejor_mk, mejor_sched = ms_i, os_i, mk_i, sched_i

        if mejor_ms is None:
            os_i = S.os_aleatorio(instancia, rng)
            ms_i = S.ms_aleatorio(instancia, rng)
            mk_i, sched_i = evaluar(instancia, ms_i, os_i, presupuesto)
            mejor_ms, mejor_os, mejor_mk, mejor_sched = ms_i, os_i, mk_i, sched_i

        return mejor_ms, mejor_os, mejor_mk, mejor_sched

    # -- ruta crítica -----------------------------------------------------

    def _ruta_critica(self, instancia, schedule, makespan):
        """Operaciones (índice global) en un camino crítico del schedule.

        Se deriva de `schedule`, que ya fue construido por el decodificador
        único (D5/D6): esto no es un decodificador alternativo, es análisis
        posterior sobre lo que `core.objective.evaluar` ya entregó — el
        mismo tipo de derivación que `core.active_decoder.por_maquina` hace
        para el diagrama de Gantt.
        """
        pred_maquina = {}
        por_maquina = [[] for _ in range(instancia.n_maquinas)]
        for g, (_j, _o, m, inicio, _fin) in enumerate(schedule):
            por_maquina[m].append((inicio, g))
        for fila in por_maquina:
            fila.sort()
            anterior = None
            for _, g in fila:
                pred_maquina[g] = anterior
                anterior = g

        fin_g, mejor_ini = None, -1
        for g, (_j, _o, _m, inicio, fin) in enumerate(schedule):
            if fin == makespan and inicio > mejor_ini:
                mejor_ini, fin_g = inicio, g

        criticas = set()
        actual = fin_g
        while actual is not None:
            criticas.add(actual)
            inicio_actual = schedule[actual][3]
            if inicio_actual == 0:
                break

            j, o = instancia.op_jo[actual]
            pred_trabajo = actual - 1 if o > 0 else None
            pt_ajustado = (
                pred_trabajo is not None
                and schedule[pred_trabajo][4] == inicio_actual
            )
            pm = pred_maquina.get(actual)
            pm_ajustado = pm is not None and schedule[pm][4] == inicio_actual

            if pm_ajustado:
                actual = pm
            elif pt_ajustado:
                actual = pred_trabajo
            else:
                candidatos = []
                if pm is not None:
                    candidatos.append((schedule[pm][4], pm))
                if pred_trabajo is not None:
                    candidatos.append((schedule[pred_trabajo][4], pred_trabajo))
                if not candidatos:
                    break
                candidatos.sort()
                actual = candidatos[-1][1]

        return criticas

    # -- vecindarios --------------------------------------------------------

    def _posiciones(self, instancia, os_vec):
        """Posición en OS -> índice global de operación."""
        siguiente = [0] * instancia.n_trabajos
        op_en_pos = [0] * len(os_vec)
        for i, j in enumerate(os_vec):
            o = siguiente[j]
            op_en_pos[i] = instancia.offset[j] + o
            siguiente[j] += 1
        return op_en_pos

    def _generar_candidatos(self, instancia, ms, os_vec, criticas, op_en_pos, rng):
        """Movimientos candidatos, sin evaluar todavía.

        - ("MS", g, k_nueva, k_vieja): reasignar la operación global g a la
          alternativa de máquina k_nueva.
        - ("SWAP", i): intercambiar las posiciones i, i+1 de OS.
        - ("INSERT", i, destino): reubicar el token de la posición i unas
          posiciones antes en OS.
        """
        candidatos = []

        # N1: reasignar operaciones críticas a otra alternativa de máquina.
        for g in criticas:
            k_actual = ms[g]
            for k in range(instancia.n_alternativas(g)):
                if k != k_actual:
                    candidatos.append(("MS", g, k, k_actual))

        # N2: intercambios adyacentes (trabajos distintos) que tocan al
        # menos una operación crítica.
        for i in range(len(os_vec) - 1):
            if os_vec[i] != os_vec[i + 1]:
                if op_en_pos[i] in criticas or op_en_pos[i + 1] in criticas:
                    candidatos.append(("SWAP", i))

        # N3: reubicar una operación crítica algunas posiciones antes en OS.
        for i in range(len(os_vec)):
            if op_en_pos[i] in criticas:
                for salto in (2, 4, 8):
                    destino = i - salto
                    if destino >= 0 and os_vec[destino] != os_vec[i]:
                        candidatos.append(("INSERT", i, destino))

        if not candidatos:
            # Sin candidatos críticos (caso raro): recurrir a todos los
            # intercambios posibles para no quedar sin vecindario.
            for i in range(len(os_vec) - 1):
                if os_vec[i] != os_vec[i + 1]:
                    candidatos.append(("SWAP", i))

        if len(candidatos) > self.max_vecinos:
            candidatos = rng.sample(candidatos, self.max_vecinos)

        return candidatos

    def _evaluar_movimiento(self, instancia, ms, os_vec, mov, presupuesto):
        tipo = mov[0]
        if tipo == "MS":
            _, g, k_nueva, k_vieja = mov
            ms[g] = k_nueva
            mk, sched = evaluar(instancia, ms, os_vec, presupuesto)
            ms[g] = k_vieja
            return mk, sched
        elif tipo == "SWAP":
            i = mov[1]
            os_vec[i], os_vec[i + 1] = os_vec[i + 1], os_vec[i]
            mk, sched = evaluar(instancia, ms, os_vec, presupuesto)
            os_vec[i], os_vec[i + 1] = os_vec[i + 1], os_vec[i]
            return mk, sched
        else:  # "INSERT"
            i, destino = mov[1], mov[2]
            valor = os_vec.pop(i)
            os_vec.insert(destino, valor)
            mk, sched = evaluar(instancia, ms, os_vec, presupuesto)
            os_vec.pop(destino)
            os_vec.insert(i, valor)
            return mk, sched

    def _aplicar_movimiento(self, ms, os_vec, mov):
        tipo = mov[0]
        if tipo == "MS":
            _, g, k_nueva, _k_vieja = mov
            ms[g] = k_nueva
        elif tipo == "SWAP":
            i = mov[1]
            os_vec[i], os_vec[i + 1] = os_vec[i + 1], os_vec[i]
        else:  # "INSERT"
            i, destino = mov[1], mov[2]
            valor = os_vec.pop(i)
            os_vec.insert(destino, valor)

    def _clave(self, mov, op_en_pos):
        tipo = mov[0]
        if tipo == "MS":
            _, g, _k_nueva, k_vieja = mov
            return ("MS", g, k_vieja)  # prohíbe volver a la alternativa vieja
        elif tipo == "SWAP":
            i = mov[1]
            a, b = op_en_pos[i], op_en_pos[i + 1]
            return ("SWAP", (a, b) if a <= b else (b, a))
        else:  # "INSERT"
            return ("INSERT", op_en_pos[mov[1]])

    def _perturbar(self, instancia, ms, os_vec, rng):
        """Diversificación: reasignaciones e intercambios aleatorios sobre
        la mejor solución archivada, conservándola sin modificar."""
        ms_p = list(ms)
        os_p = list(os_vec)
        n_kick = max(2, instancia.total_ops // 20)

        for _ in range(n_kick):
            g = rng.randrange(instancia.total_ops)
            n_alt = instancia.n_alternativas(g)
            if n_alt > 1:
                ms_p[g] = rng.randrange(n_alt)

        for _ in range(n_kick):
            if len(os_p) < 2:
                break
            i = rng.randrange(len(os_p) - 1)
            os_p[i], os_p[i + 1] = os_p[i + 1], os_p[i]

        return ms_p, os_p
