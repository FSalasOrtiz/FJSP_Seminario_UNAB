"""
Poblacion/PSO/PSO_IA/algorithm.py
===================================
Optimización por Enjambre de Partículas (PSO) para el FJSP — implementación
con apoyo de Claude, para el experimento "implementación humana vs.
asistida por IA" (acta de reunión, 07-09-2026).

Autocontenido A PROPÓSITO: no importa nada de `core/`, ni comparte código
con `Poblacion/PSO/PSO_IA/../PSO_Alumno/`. Ver el docstring equivalente en
`Poblacion/AG/AG_IA/algorithm.py` para la explicación completa del porqué.

Qué contiene este archivo (y nada más — línea de comandos y escritura de
Salida/ viven en revision/sanity_check.py):
  1. Instancia + leer_instancia   — parser del formato .fjs estándar
  2. decodificar                  — decodificador de horario ACTIVO
  3. ParticleSwarmOptimization     — el algoritmo en sí, como clase

Nota sobre el diseño: PSO es un optimizador para espacios CONTINUOS
(posición y velocidad son vectores de números reales), pero el FJSP es
combinatorio. La técnica estándar para tender ese puente es la
codificación por "claves aleatorias" (random keys): la partícula vive en
un espacio continuo, y se traduce a una solución discreta (OS, MS) recién
al momento de evaluarla. Ver la sección 4 de README.md para el detalle de
cómo se traduce cada componente.
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
    op_jo        : op_jo[g] = (j, o).
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
# 3) PSO — Optimización por Enjambre de Partículas, codificación por claves
# =============================================================================

class ParticleSwarmOptimization:
    """PSO para el FJSP, con codificación por claves aleatorias.

    Cada partícula tiene DOS vectores continuos de posición, de longitud
    total_ops cada uno:
      - pos_os[g] en [0, 1]           -> se traduce a la secuencia OS
      - pos_ms[g] en [0, n_alt(g)-1]  -> se traduce a la máquina elegida (MS)

    Traducción de pos_os a OS ("smallest position value" por trabajo):
    en cada paso, entre todas las operaciones "listas" (la siguiente
    pendiente de cada trabajo), se elige la de menor pos_os[g]. Esto
    SIEMPRE produce una secuencia válida (respeta precedencia de trabajo
    por construcción), sin importar los valores continuos que traiga la
    partícula.

    Traducción de pos_ms a MS: redondeo al entero más cercano, recortado a
    [0, n_alt(g)-1].

    Uso:
        pso = ParticleSwarmOptimization(semilla=1000, n_particulas=30, ...)
        resultado = pso.resolver(instancia, max_iteraciones=100)
    """

    def __init__(self, n_particulas=30, w_max=0.9, w_min=0.4, c1=1.5, c2=1.5,
                 semilla=None):
        self.n_particulas = n_particulas
        self.w_max = w_max
        self.w_min = w_min
        self.c1 = c1
        self.c2 = c2
        self.rng = random.Random(semilla)

    # -- ciclo principal --------------------------------------------------

    def resolver(self, instancia, max_iteraciones, tiempo_limite_s=None):
        import time
        t0 = time.time()

        n = instancia.total_ops
        limites_ms = [instancia.n_alternativas(g) - 1 for g in range(n)]

        # --- inicialización del enjambre ---
        enjambre = []
        for _ in range(self.n_particulas):
            pos_os = [self.rng.random() for _ in range(n)]
            pos_ms = [self.rng.uniform(0, limites_ms[g]) for g in range(n)]
            vel_os = [0.0] * n
            vel_ms = [0.0] * n
            enjambre.append({
                "pos_os": pos_os, "pos_ms": pos_ms,
                "vel_os": vel_os, "vel_ms": vel_ms,
            })

        pbest = []
        gbest = None
        gbest_mk = None

        for particula in enjambre:
            os_vec, ms_vec = self._decodificar_posicion(instancia, particula["pos_os"], particula["pos_ms"])
            mk, _ = decodificar(instancia, os_vec, ms_vec)
            particula["pbest_pos_os"] = list(particula["pos_os"])
            particula["pbest_pos_ms"] = list(particula["pos_ms"])
            particula["pbest_mk"] = mk
            pbest.append(mk)
            if gbest_mk is None or mk < gbest_mk:
                gbest_mk = mk
                gbest = {"pos_os": list(particula["pos_os"]), "pos_ms": list(particula["pos_ms"]),
                          "os": os_vec, "ms": ms_vec}

        traza = [(round(time.time() - t0, 4), gbest_mk)]

        iteracion = 0
        while iteracion < max_iteraciones:
            if tiempo_limite_s is not None and (time.time() - t0) >= tiempo_limite_s:
                break

            w = self.w_max - (self.w_max - self.w_min) * (iteracion / max(1, max_iteraciones - 1))

            for particula in enjambre:
                for g in range(n):
                    r1, r2 = self.rng.random(), self.rng.random()
                    particula["vel_os"][g] = (
                        w * particula["vel_os"][g]
                        + self.c1 * r1 * (particula["pbest_pos_os"][g] - particula["pos_os"][g])
                        + self.c2 * r2 * (gbest["pos_os"][g] - particula["pos_os"][g])
                    )
                    particula["vel_os"][g] = max(-1.0, min(1.0, particula["vel_os"][g]))
                    particula["pos_os"][g] += particula["vel_os"][g]
                    particula["pos_os"][g] = max(0.0, min(1.0, particula["pos_os"][g]))

                    r1, r2 = self.rng.random(), self.rng.random()
                    rango_ms = max(1, limites_ms[g])
                    particula["vel_ms"][g] = (
                        w * particula["vel_ms"][g]
                        + self.c1 * r1 * (particula["pbest_pos_ms"][g] - particula["pos_ms"][g])
                        + self.c2 * r2 * (gbest["pos_ms"][g] - particula["pos_ms"][g])
                    )
                    particula["vel_ms"][g] = max(-rango_ms, min(rango_ms, particula["vel_ms"][g]))
                    particula["pos_ms"][g] += particula["vel_ms"][g]
                    particula["pos_ms"][g] = max(0.0, min(limites_ms[g], particula["pos_ms"][g]))

                os_vec, ms_vec = self._decodificar_posicion(instancia, particula["pos_os"], particula["pos_ms"])
                mk, _ = decodificar(instancia, os_vec, ms_vec)

                if mk < particula["pbest_mk"]:
                    particula["pbest_mk"] = mk
                    particula["pbest_pos_os"] = list(particula["pos_os"])
                    particula["pbest_pos_ms"] = list(particula["pos_ms"])

                if mk < gbest_mk:
                    gbest_mk = mk
                    gbest = {"pos_os": list(particula["pos_os"]), "pos_ms": list(particula["pos_ms"]),
                              "os": os_vec, "ms": ms_vec}

            iteracion += 1
            traza.append((round(time.time() - t0, 4), gbest_mk))

        _, mejor_horario = decodificar(instancia, gbest["os"], gbest["ms"])
        return {
            "os": gbest["os"],
            "ms": gbest["ms"],
            "makespan": gbest_mk,
            "horario": mejor_horario,
            "traza": traza,
            "iteraciones": iteracion,
            "tiempo_s": round(time.time() - t0, 4),
        }

    # -- traducción posición continua -> (OS, MS) discreto -----------------

    def _decodificar_posicion(self, instancia, pos_os, pos_ms):
        prox_op = [0] * instancia.n_trabajos
        os_vec = []
        ms_vec = [0] * instancia.total_ops

        for _ in range(instancia.total_ops):
            mejor_j, mejor_g, mejor_valor = None, None, None
            for j in range(instancia.n_trabajos):
                o = prox_op[j]
                if o >= len(instancia.trabajos[j]):
                    continue
                g = instancia.offset[j] + o
                if mejor_valor is None or pos_os[g] < mejor_valor:
                    mejor_j, mejor_g, mejor_valor = j, g, pos_os[g]

            os_vec.append(mejor_j)
            n_alt = instancia.n_alternativas(mejor_g)
            k = int(round(pos_ms[mejor_g]))
            k = max(0, min(n_alt - 1, k))
            ms_vec[mejor_g] = k
            prox_op[mejor_j] += 1

        return os_vec, ms_vec
