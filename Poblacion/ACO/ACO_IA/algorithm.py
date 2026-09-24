"""
Poblacion/ACO/ACO_IA/algorithm.py
===================================
ACO — MAX-MIN Ant System (MMAS) para el FJSP — implementación con apoyo de
Claude, para el experimento "implementación humana vs. asistida por IA"
(acta de reunión, 07-09-2026).

Autocontenido A PROPÓSITO: no importa nada de `core/`, ni de
`Poblacion/ACO/algorithm.py` (el ACO "oficial" del experimento principal,
que sí usa `core/` y compite contra SA/Tabú/AG bajo el mismo contrato
D1-D10), ni comparte código con `Poblacion/ACO/ACO_IA/../ACO_Alumno/`. Es
la condición para que la comparación IA vs. Alumno sea justa — ver el
docstring equivalente en `Poblacion/AG/AG_IA/algorithm.py` para la
explicación completa del porqué.

Qué contiene este archivo (y nada más — línea de comandos y escritura de
Salida/ viven en revision/sanity_check.py):
  1. Instancia + leer_instancia   — parser del formato .fjs estándar
  2. decodificar                  — decodificador de horario ACTIVO
  3. AntColonyMMAS                 — el algoritmo en sí, como clase
"""

import random


# =============================================================================
# 1) LECTURA DE INSTANCIAS — formato estándar .fjs
# =============================================================================

class Instancia:
    """Una instancia FJSP ya parseada.

    Atributos
    ---------
    nombre       : nombre del archivo de origen.
    n_trabajos   : número de trabajos.
    n_maquinas   : número de máquinas.
    trabajos     : trabajos[j][o] = lista de (máquina, duración), máquina en base 0.
    offset       : offset[j] = índice global de la primera operación del trabajo j.
    total_ops    : número total de operaciones en toda la instancia.
    op_jo        : op_jo[g] = (j, o) — a qué trabajo/operación corresponde el índice global g.
    """

    def __init__(self, nombre, n_trabajos, n_maquinas, trabajos):
        self.nombre = nombre
        self.n_trabajos = n_trabajos
        self.n_maquinas = n_maquinas
        self.trabajos = trabajos
        self.offset = []
        self.op_jo = []
        contador = 0
        for j, ops in enumerate(trabajos):
            self.offset.append(contador)
            for o in range(len(ops)):
                self.op_jo.append((j, o))
            contador += len(ops)
        self.total_ops = contador

    def alternativas(self, g):
        j, o = self.op_jo[g]
        return self.trabajos[j][o]

    def n_alternativas(self, g):
        return len(self.alternativas(g))


def leer_instancia(ruta):
    with open(ruta, "r") as f:
        contenido = f.read().split("\n")
    lineas = [ln.strip() for ln in contenido if ln.strip() != ""]

    cabecera = lineas[0].split()
    n_trabajos = int(cabecera[0])
    n_maquinas = int(cabecera[1])

    trabajos = []
    for j in range(n_trabajos):
        tokens = lineas[1 + j].split()
        idx = 0
        n_ops = int(tokens[idx]); idx += 1
        ops = []
        for _o in range(n_ops):
            n_maq = int(tokens[idx]); idx += 1
            alternativas = []
            for _k in range(n_maq):
                m = int(tokens[idx]) - 1  # base 1 -> base 0
                p = int(tokens[idx + 1])
                idx += 2
                alternativas.append((m, p))
            ops.append(alternativas)
        trabajos.append(ops)

    return Instancia(_basename(ruta), n_trabajos, n_maquinas, trabajos)


def _basename(ruta):
    return ruta.replace("\\", "/").rsplit("/", 1)[-1]


# =============================================================================
# 2) DECODIFICADOR — horario ACTIVO con inserción en huecos
# =============================================================================

def decodificar(instancia, os_vec, ms_vec):
    """Decodifica un cromosoma (OS, MS) en un horario activo.

    Devuelve (makespan, horario), horario indexado por operación global g:
    horario[g] = (trabajo, operacion, maquina, inicio, fin).
    """
    intervalos_ocupados = [[] for _ in range(instancia.n_maquinas)]
    fin_trabajo = [0] * instancia.n_trabajos
    siguiente_op = [0] * instancia.n_trabajos
    horario = [None] * instancia.total_ops
    makespan = 0

    for j in os_vec:
        o = siguiente_op[j]
        g = instancia.offset[j] + o
        k = ms_vec[g]
        maquina, dur = instancia.alternativas(g)[k]

        liberacion = fin_trabajo[j]
        inicio = _buscar_hueco(intervalos_ocupados[maquina], liberacion, dur)
        fin = inicio + dur

        _insertar_intervalo(intervalos_ocupados[maquina], inicio, fin)
        horario[g] = (j, o, maquina, inicio, fin)

        fin_trabajo[j] = fin
        siguiente_op[j] += 1
        if fin > makespan:
            makespan = fin

    return makespan, horario


def _buscar_hueco(intervalos, liberacion, duracion):
    inicio = liberacion
    for (s, e) in intervalos:
        if inicio + duracion <= s:
            return inicio
        if inicio < e:
            inicio = e
    return inicio


def _insertar_intervalo(intervalos, inicio, fin):
    i = 0
    while i < len(intervalos) and intervalos[i][0] < inicio:
        i += 1
    intervalos.insert(i, (inicio, fin))


# =============================================================================
# 3) ACO — MAX-MIN Ant System
# =============================================================================

class AntColonyMMAS:
    """ACO (MMAS) para el FJSP.

    Cada hormiga construye una solución completa (OS, MS) paso a paso,
    eligiendo en cada paso la siguiente operación pendiente y su máquina
    con probabilidad proporcional a `tau[g][m] ** alpha * eta ** beta`,
    donde `eta = 1/duración` de la alternativa candidata (heurística SPT,
    puramente local — no requiere simular el estado de las máquinas).
    Tras cada iteración, se evapora la feromona y se refuerza según la
    mejor solución encontrada, con límites [tau_min, tau_max] (MMAS).

    Uso:
        aco = AntColonyMMAS(semilla=1000, n_ants=30, ...)
        resultado = aco.resolver(instancia, max_iteraciones=100)

    `resultado` es un dict con: os, ms, makespan, horario, traza,
    iteraciones, tiempo_s.
    """

    def __init__(self, n_ants=30, alpha=1.0, beta=2.0, rho=0.1, q0=0.0,
                 local_search=True, semilla=None):
        self.n_ants = n_ants
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.q0 = q0
        self.local_search = local_search
        self.rng = random.Random(semilla)

    # -- ciclo principal --------------------------------------------------

    def resolver(self, instancia, max_iteraciones, tiempo_limite_s=None):
        import time
        t0 = time.time()

        tau, celdas_validas = self._tau_inicial(instancia)

        mejor_os, mejor_ms = self._construir(instancia, tau)
        mejor_mk, _ = decodificar(instancia, mejor_os, mejor_ms)

        traza = [(round(time.time() - t0, 4), mejor_mk)]

        iteracion = 0
        while iteracion < max_iteraciones:
            if tiempo_limite_s is not None and (time.time() - t0) >= tiempo_limite_s:
                break

            iter_mejor_mk = None
            iter_mejor_os = iter_mejor_ms = None
            for _ in range(self.n_ants):
                os_ant, ms_ant = self._construir(instancia, tau)
                mk, _ = decodificar(instancia, os_ant, ms_ant)
                if iter_mejor_mk is None or mk < iter_mejor_mk:
                    iter_mejor_mk, iter_mejor_os, iter_mejor_ms = mk, os_ant, ms_ant

            nuevo_mejor = iter_mejor_mk < mejor_mk
            if nuevo_mejor:
                mejor_mk, mejor_os, mejor_ms = iter_mejor_mk, list(iter_mejor_os), list(iter_mejor_ms)

            if self.local_search and nuevo_mejor:
                mejor_ms, mejor_mk = self._busqueda_local(instancia, mejor_ms, mejor_os, mejor_mk)

            self._actualizar_feromona(instancia, tau, celdas_validas, mejor_ms, mejor_mk)

            iteracion += 1
            traza.append((round(time.time() - t0, 4), mejor_mk))

        _, mejor_horario = decodificar(instancia, mejor_os, mejor_ms)
        return {
            "os": mejor_os,
            "ms": mejor_ms,
            "makespan": mejor_mk,
            "horario": mejor_horario,
            "traza": traza,
            "iteraciones": iteracion,
            "tiempo_s": round(time.time() - t0, 4),
        }

    # -- feromona -----------------------------------------------------------

    def _tau_inicial(self, instancia):
        tau = [dict() for _ in range(instancia.total_ops)]
        celdas_validas = []
        for g in range(instancia.total_ops):
            for m, _dur in instancia.alternativas(g):
                tau[g][m] = 1.0
                celdas_validas.append((g, m))
        return tau, celdas_validas

    def _actualizar_feromona(self, instancia, tau, celdas_validas, mejor_ms, mejor_mk):
        for g, m in celdas_validas:
            tau[g][m] *= 1.0 - self.rho

        dep = 1.0 / mejor_mk
        for g in range(instancia.total_ops):
            m, _dur = instancia.alternativas(g)[mejor_ms[g]]
            tau[g][m] += dep

        tau_max = 1.0 / (self.rho * mejor_mk)
        tau_min = tau_max / (2.0 * instancia.total_ops)
        for g, m in celdas_validas:
            tau[g][m] = max(tau_min, min(tau_max, tau[g][m]))

    # -- construcción de una hormiga -------------------------------------

    def _construir(self, instancia, tau):
        prox_op = [0] * instancia.n_trabajos
        os_vec = []
        ms_vec = [0] * instancia.total_ops

        for _ in range(instancia.total_ops):
            candidatos = []
            pesos = []
            for j in range(instancia.n_trabajos):
                o = prox_op[j]
                if o >= len(instancia.trabajos[j]):
                    continue
                g = instancia.offset[j] + o
                for k, (m, dur) in enumerate(instancia.alternativas(g)):
                    eta = 1.0 / dur if dur > 0 else 1.0
                    peso = (tau[g][m] ** self.alpha) * (eta ** self.beta)
                    candidatos.append((j, g, k))
                    pesos.append(peso)

            total = sum(pesos)
            if total <= 0:
                pesos = [1.0] * len(candidatos)
                total = float(len(candidatos))

            if self.q0 > 0 and self.rng.random() < self.q0:
                idx = max(range(len(candidatos)), key=lambda i: pesos[i])
            else:
                r = self.rng.random() * total
                acumulado = 0.0
                idx = len(candidatos) - 1
                for i, peso in enumerate(pesos):
                    acumulado += peso
                    if acumulado >= r:
                        idx = i
                        break

            j, g, k = candidatos[idx]
            ms_vec[g] = k
            os_vec.append(j)
            prox_op[j] += 1

        return os_vec, ms_vec

    # -- búsqueda local (sobre MS, secuencia fija) -----------------------

    def _busqueda_local(self, instancia, ms, os_vec, mejor_mk):
        ms = list(ms)
        mejoro = True
        while mejoro:
            mejoro = False
            for g in range(instancia.total_ops):
                actual = ms[g]
                for k in range(instancia.n_alternativas(g)):
                    if k == actual:
                        continue
                    ms[g] = k
                    mk, _ = decodificar(instancia, os_vec, ms)
                    if mk < mejor_mk:
                        mejor_mk = mk
                        actual = k
                        mejoro = True
                        break
                    ms[g] = actual
        return ms, mejor_mk
