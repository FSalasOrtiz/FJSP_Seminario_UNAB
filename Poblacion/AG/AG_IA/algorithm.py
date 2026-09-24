"""
Poblacion/AG/AG_IA/algorithm.py
================================
Algoritmo Genético (AG) para el FJSP — implementación con apoyo de Claude,
para el experimento "implementación humana vs. asistida por IA" (acta de
reunión, 07-09-2026).

Autocontenido A PROPÓSITO: no importa nada de `core/` ni de ningún otro
módulo del repositorio, y no comparte una sola línea con
`Poblacion/AG/AG_Alumno/`. Esto es intencional, no un descuido — es la
condición para que la comparación entre ambas implementaciones sea justa:
si esta versión reutilizara el parser/decodificador/validador ya maduros de
`core/` (construidos en sesiones anteriores), partiría con una ventaja de
infraestructura que la versión del alumno, escrita desde cero, no tiene. La
comparación que le interesa al profesor es sobre el PROCESO de construcción
completo, no solo sobre el algoritmo de búsqueda en sí.

Nota para quien lo lea junto a `Poblacion/AG/algorithm.py` (el AG "oficial"
del experimento principal, que sí usa `core/` y compite contra SA/Tabú/ACO
bajo el mismo contrato D1-D10): son dos implementaciones DISTINTAS del
mismo algoritmo, con propósitos distintos. No es duplicación accidental.

Qué contiene este archivo (y nada más que esto — la lectura de argumentos
de línea de comandos y la escritura de Salida/ viven en revision/sanity_check.py,
igual que en el resto de las metaheurísticas del repositorio):
  1. Instancia + leer_instancia   — parser del formato .fjs estándar
  2. decodificar                  — decodificador de horario ACTIVO
  3. AlgoritmoGeneticoAG           — el algoritmo en sí, como clase
"""

import random


# =============================================================================
# 1) LECTURA DE INSTANCIAS — formato estándar .fjs
# =============================================================================
#
# Línea 1:  <n_jobs> <n_machines> [<flexibilidad_promedio>]  (el 3er campo, si
#           aparece, es informativo y se ignora)
# Línea j:  <n_operaciones> luego, por cada operación:
#               <k> (cantidad de máquinas alternativas)
#               seguido de k pares (<máquina>, <tiempo>) — máquinas en base 1
#           en el archivo; se convierten a base 0 al leer.

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
        """Alternativas (máquina, duración) de la operación de índice global g."""
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
#
# "Activo" significa: una operación puede insertarse en un hueco libre de la
# máquina, anterior a la última operación ya programada en ella, siempre que
# quepa completa sin atrasar nada de lo ya programado. Un decodificador
# SEMI-ACTIVO (que solo permite encolar al final de cada máquina) subestima
# sistemáticamente la calidad real de una solución.

def decodificar(instancia, os_vec, ms_vec):
    """Decodifica un cromosoma (OS, MS) en un horario activo.

    os_vec: lista de longitud total_ops, cada elemento es un id de trabajo
            (con repetición): el orden en que aparece cada trabajo indica
            en qué orden se programan sus operaciones sucesivas.
    ms_vec: ms_vec[g] = índice de la alternativa elegida (dentro de
            instancia.alternativas(g)) para la operación global g.

    Devuelve (makespan, horario), donde horario es una lista de tuplas
    (trabajo, operacion, maquina, inicio, fin), indexada por operación
    global g (horario[g] corresponde a la operación g).
    """
    intervalos_ocupados = [[] for _ in range(instancia.n_maquinas)]  # por máquina: [(inicio, fin), ...] ordenado
    fin_trabajo = [0] * instancia.n_trabajos
    siguiente_op = [0] * instancia.n_trabajos
    horario = [None] * instancia.total_ops
    makespan = 0

    for j in os_vec:
        o = siguiente_op[j]
        g = instancia.offset[j] + o
        k = ms_vec[g]
        maquina, dur = instancia.alternativas(g)[k]

        liberacion = fin_trabajo[j]  # no puede empezar antes de que termine su predecesora
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
    """Primer instante >= liberacion donde cabe una tarea de largo `duracion`
    sin solapar los intervalos ya ocupados (lista ordenada por inicio)."""
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
# 3) ALGORITMO GENÉTICO — como clase
# =============================================================================

class AlgoritmoGeneticoAG:
    """AG para el FJSP: individuo = (OS, MS), cruce POX + uniforme, mutación,
    selección por torneo, elitismo, inmigrantes por estancamiento.

    Uso:
        ag = AlgoritmoGeneticoAG(semilla=1000, tam_poblacion=60, ...)
        resultado = ag.resolver(instancia, max_generaciones=200)

    `resultado` es un dict con: os, ms, makespan, horario, traza,
    generaciones, tiempo_s. Ver revision/sanity_check.py para cómo se usa
    de punta a punta, incluyendo la escritura del contrato Salida/.
    """

    def __init__(self, tam_poblacion=60, prob_cruce=0.9, prob_mut_os=0.2,
                 prob_mut_ms=0.3, k_torneo=3, elitismo=2,
                 estancamiento_max=15, frac_inmigrantes=0.15, semilla=None):
        self.tam_poblacion = tam_poblacion
        self.prob_cruce = prob_cruce
        self.prob_mut_os = prob_mut_os
        self.prob_mut_ms = prob_mut_ms
        self.k_torneo = k_torneo
        self.elitismo = elitismo
        self.estancamiento_max = estancamiento_max
        self.frac_inmigrantes = frac_inmigrantes
        self.rng = random.Random(semilla)

    # -- ciclo principal --------------------------------------------------

    def resolver(self, instancia, max_generaciones, tiempo_limite_s=None):
        """Corre el AG. Se detiene por número máximo de generaciones, o
        antes si se agota `tiempo_limite_s` (si se especifica).

        Devuelve un diccionario con la mejor solución, su horario, y la
        traza de convergencia: lista de (tiempo_transcurrido_s, mejor_makespan).
        """
        import time
        t0 = time.time()

        poblacion = [self._individuo_aleatorio(instancia) for _ in range(self.tam_poblacion)]
        fitness = [self._evaluar(instancia, ind)[0] for ind in poblacion]

        bi = min(range(len(fitness)), key=lambda i: fitness[i])
        mejor_os = list(poblacion[bi][0])
        mejor_ms = list(poblacion[bi][1])
        mejor_mk = fitness[bi]

        traza = [(round(time.time() - t0, 4), mejor_mk)]
        estancamiento = 0
        mejor_prev = mejor_mk

        generacion = 0
        while generacion < max_generaciones:
            if tiempo_limite_s is not None and (time.time() - t0) >= tiempo_limite_s:
                break

            orden = sorted(range(len(fitness)), key=lambda i: fitness[i])
            nueva_pob = [list(poblacion[i]) for i in orden[: self.elitismo]]
            nuevo_fit = [fitness[i] for i in orden[: self.elitismo]]

            if estancamiento >= self.estancamiento_max:
                n_inm = max(1, int(self.tam_poblacion * self.frac_inmigrantes))
                for _ in range(n_inm):
                    ind = self._individuo_aleatorio(instancia)
                    mk, _ = self._evaluar(instancia, ind)
                    nueva_pob.append(ind)
                    nuevo_fit.append(mk)
                    if mk < mejor_mk:
                        mejor_os, mejor_ms, mejor_mk = list(ind[0]), list(ind[1]), mk
                estancamiento = 0

            while len(nueva_pob) < self.tam_poblacion:
                p1 = poblacion[self._seleccion_torneo(fitness)]
                p2 = poblacion[self._seleccion_torneo(fitness)]

                if self.rng.random() < self.prob_cruce:
                    hijo_os = self._cruce_pox(instancia, p1[0], p2[0])
                    hijo_ms = self._cruce_uniforme(p1[1], p2[1])
                else:
                    hijo_os, hijo_ms = list(p1[0]), list(p1[1])

                if self.rng.random() < self.prob_mut_os:
                    self._mutar_os(hijo_os)
                if self.rng.random() < self.prob_mut_ms:
                    self._mutar_ms(instancia, hijo_ms)

                mk, _ = self._evaluar(instancia, (hijo_os, hijo_ms))
                nueva_pob.append([hijo_os, hijo_ms])
                nuevo_fit.append(mk)
                if mk < mejor_mk:
                    mejor_os, mejor_ms, mejor_mk = list(hijo_os), list(hijo_ms), mk

            poblacion, fitness = nueva_pob, nuevo_fit
            estancamiento = 0 if min(fitness) < mejor_prev else estancamiento + 1
            mejor_prev = mejor_mk
            generacion += 1

            traza.append((round(time.time() - t0, 4), mejor_mk))

        _, mejor_horario = self._evaluar(instancia, (mejor_os, mejor_ms))
        return {
            "os": mejor_os,
            "ms": mejor_ms,
            "makespan": mejor_mk,
            "horario": mejor_horario,
            "traza": traza,
            "generaciones": generacion,
            "tiempo_s": round(time.time() - t0, 4),
        }

    # -- individuos y evaluación -------------------------------------------

    def _individuo_aleatorio(self, instancia):
        os_vec = []
        for j in range(instancia.n_trabajos):
            os_vec += [j] * len(instancia.trabajos[j])
        self.rng.shuffle(os_vec)
        ms_vec = [self.rng.randrange(instancia.n_alternativas(g)) for g in range(instancia.total_ops)]
        return [os_vec, ms_vec]

    def _evaluar(self, instancia, individuo):
        return decodificar(instancia, individuo[0], individuo[1])

    # -- operadores genéticos ----------------------------------------------

    def _cruce_pox(self, instancia, p1_os, p2_os):
        jobs = list(range(instancia.n_trabajos))
        self.rng.shuffle(jobs)
        corte = self.rng.randint(1, instancia.n_trabajos - 1) if instancia.n_trabajos > 1 else 1
        j1 = set(jobs[:corte])

        hijo = [None] * len(p1_os)
        for i, g in enumerate(p1_os):
            if g in j1:
                hijo[i] = g
        resto = iter(g for g in p2_os if g not in j1)
        for i in range(len(hijo)):
            if hijo[i] is None:
                hijo[i] = next(resto)
        return hijo

    def _cruce_uniforme(self, p1_ms, p2_ms):
        return [p1_ms[i] if self.rng.random() < 0.5 else p2_ms[i] for i in range(len(p1_ms))]

    def _mutar_os(self, os_vec):
        n = len(os_vec)
        i, k = self.rng.randrange(n), self.rng.randrange(n)
        os_vec[i], os_vec[k] = os_vec[k], os_vec[i]

    def _mutar_ms(self, instancia, ms_vec):
        g = self.rng.randrange(instancia.total_ops)
        n_alt = instancia.n_alternativas(g)
        if n_alt > 1:
            ms_vec[g] = self.rng.randrange(n_alt)

    def _seleccion_torneo(self, fitness):
        mejor = self.rng.randrange(len(fitness))
        for _ in range(self.k_torneo - 1):
            c = self.rng.randrange(len(fitness))
            if fitness[c] < fitness[mejor]:
                mejor = c
        return mejor
