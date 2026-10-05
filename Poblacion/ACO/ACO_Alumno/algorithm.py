#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Poblacion/ACO/ACO_Referencia/algorithm.py
============================================
Algoritmo de Optimización por Colonia de Hormigas (ACO) - Variante MAX-MIN
Ant System (MMAS) para el Flexible Job Shop Scheduling Problem (FJSP).
Minimización del Makespan (Cmax).

ORIGEN: este código NO fue escrito por el alumno ni por Claude en este
repositorio — se le pidió a otra IA (prompt documentado en el acta/chat del
equipo) generar una implementación de referencia de ACO para FJSP, usando
el mismo formato de instancias y el mismo contrato de salida que el resto
del proyecto. Se guarda como una TERCERA referencia (además de
`../ACO_IA/` y, eventualmente, `../ACO_Alumno/`), no como sustituto de
ninguna de las dos.

VERIFICACIÓN REALIZADA (por Claude, antes de integrarlo a este repositorio):
  - Parser probado contra 4 familias del benchmark (Brandimarte, Hurink
    *_edata/*_vdata, Dauzère-Pérès), incluyendo instancias con el campo de
    flexibilidad promedio en formato decimal — coincide exactamente con los
    valores esperados.
  - Corrida completa verificada de forma INDEPENDIENTE (con un chequeo de
    factibilidad escrito aparte, no usando `verificar_factibilidad` de este
    mismo archivo) — sin problemas encontrados.
  - Determinismo confirmado (misma semilla -> mismo resultado).
  - Probado en una instancia grande (225 operaciones) sin errores.
  - Diferencia de diseño frente a `../ACO_IA/`, documentada para quien
    compare ambas: la fórmula de tau_min/tau_max sigue la formulación de
    Stützle & Hoos (basada en p_dec y el promedio de alternativas por
    operación), distinta a la fórmula más simple
    (tau_max / (2 * total_ops)) usada en `../ACO_IA/algorithm.py`. Ambas
    son válidas en la literatura MMAS, pero no son la misma fórmula — no
    comparar sus resultados asumiendo que calibran igual.

No se modificó ninguna línea de la lógica del algoritmo (parser,
decodificador, construcción de hormigas, actualización de feromona) al
integrarlo aquí; solo se separó en dos archivos (este, con las clases, y
revision/sanity_check.py, con el CLI y la escritura de resultados) para
seguir la misma convención que el resto del repositorio.
"""

import math
import random


# =============================================================================
# 1. PARSER Y ESTRUCTURAS DE DATOS
# =============================================================================

class InstanciaFJSP:
    """Clase para almacenar y parsear las instancias .fjs del benchmark FJSPLib."""

    def __init__(self, ruta_archivo: str):
        self.nombre_archivo = ruta_archivo.replace("\\", "/").rsplit("/", 1)[-1]
        self.num_trabajos = 0
        self.num_maquinas = 0
        self.flexibilidad_promedio = 0.0
        # trabajos[j][k] = lista de tuplas (maquina_idx, duracion) para la op k del trabajo j
        self.trabajos = []
        self._cargar_instancia(ruta_archivo)

    def _cargar_instancia(self, ruta_archivo: str):
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()

        tokens = contenido.split()
        if not tokens:
            raise ValueError(f"El archivo {ruta_archivo} está vacío.")

        ptr = 0
        self.num_trabajos = int(tokens[ptr])
        ptr += 1
        self.num_maquinas = int(tokens[ptr])
        ptr += 1

        # El tercer campo es la flexibilidad promedio; puede ser decimal
        # (p.ej. "1.15", "7.50") -- por eso se lee como float, no como int.
        self.flexibilidad_promedio = float(tokens[ptr])
        ptr += 1

        self.trabajos = []
        for j in range(self.num_trabajos):
            num_operaciones = int(tokens[ptr])
            ptr += 1
            operaciones_trabajo = []

            for k in range(num_operaciones):
                num_alternativas = int(tokens[ptr])
                ptr += 1
                alternativas = []

                for _ in range(num_alternativas):
                    maq_1based = int(tokens[ptr])
                    ptr += 1
                    duracion = int(tokens[ptr])
                    ptr += 1

                    # Convertir máquina de base 1 a base 0
                    alternativas.append((maq_1based - 1, duracion))

                operaciones_trabajo.append(alternativas)

            self.trabajos.append(operaciones_trabajo)


class Solucion:
    """Representación de una solución al FJSP."""

    def __init__(self, secuencia_operaciones, asignacion_maquinas):
        """
        :param secuencia_operaciones: Lista de IDs de trabajo (0..N-1), la i-ésima aparición
                                       indica la i-ésima operación de ese trabajo.
        :param asignacion_maquinas: Dict (j, k) -> maquina_elegida_idx
        """
        self.secuencia_operaciones = secuencia_operaciones
        self.asignacion_maquinas = asignacion_maquinas
        self.makespan = math.inf
        self.horario = []  # Lista de tuplas: (trabajo, operacion, maquina, inicio, fin)


# =============================================================================
# 2. DECODIFICADOR ACTIVO (ACTIVE SCHEDULER)
# =============================================================================

def decodificar_activo(instancia: InstanciaFJSP, secuencia: list, asignacion_maquinas: dict) -> tuple:
    """
    Decodifica una secuencia de operaciones y una asignación de máquinas en un horario activo
    buscando el primer hueco (gap) factible en la máquina asignada.

    :return: (makespan, horario)
    """
    progreso_trabajo = [0] * instancia.num_trabajos
    fin_trabajo = [0] * instancia.num_trabajos
    ocupacion_maquina = {m: [] for m in range(instancia.num_maquinas)}

    horario = []
    makespan = 0

    for trabajo in secuencia:
        op_idx = progreso_trabajo[trabajo]
        progreso_trabajo[trabajo] += 1

        maq_elegida = asignacion_maquinas[(trabajo, op_idx)]
        duracion = next(dur for m, dur in instancia.trabajos[trabajo][op_idx] if m == maq_elegida)

        tiempo_listo_trabajo = fin_trabajo[trabajo]

        intervalos = ocupacion_maquina[maq_elegida]
        tiempo_inicio = None

        if not intervalos:
            tiempo_inicio = tiempo_listo_trabajo
        else:
            if intervalos[0][0] - max(0, tiempo_listo_trabajo) >= duracion:
                tiempo_inicio = tiempo_listo_trabajo
            else:
                for i in range(len(intervalos) - 1):
                    gap_start = max(intervalos[i][1], tiempo_listo_trabajo)
                    gap_end = intervalos[i + 1][0]
                    if gap_end - gap_start >= duracion:
                        tiempo_inicio = gap_start
                        break

                if tiempo_inicio is None:
                    tiempo_inicio = max(intervalos[-1][1], tiempo_listo_trabajo)

        tiempo_fin = tiempo_inicio + duracion

        fin_trabajo[trabajo] = tiempo_fin
        horario.append((trabajo, op_idx, maq_elegida, tiempo_inicio, tiempo_fin))

        intervalos.append((tiempo_inicio, tiempo_fin))
        intervalos.sort(key=lambda x: x[0])

        if tiempo_fin > makespan:
            makespan = tiempo_fin

    horario.sort(key=lambda x: (x[3], x[2], x[0], x[1]))
    return makespan, horario


# =============================================================================
# 3. VERIFICADOR DE FACTIBILIDAD
# =============================================================================

def verificar_factibilidad(instancia: InstanciaFJSP, horario: list, makespan: int) -> bool:
    """Valida formalmente si un horario cumple con todas las restricciones del FJSP."""
    for t, op, m, ini, fin in horario:
        alternativas = instancia.trabajos[t][op]
        maquinas_validas = [alt[0] for alt in alternativas]
        if m not in maquinas_validas:
            print(f"Error: Máquina {m} no válida para Trabajo {t}, Op {op}.")
            return False
        duracion_esperada = next(d for maq, d in alternativas if maq == m)
        if fin - ini != duracion_esperada:
            print(f"Error: Duración incorrecta en Trabajo {t}, Op {op}. "
                  f"Esperada: {duracion_esperada}, Real: {fin - ini}.")
            return False

    ops_por_trabajo = {}
    for t, op, m, ini, fin in horario:
        ops_por_trabajo.setdefault(t, {})[op] = (ini, fin)

    for t, ops in ops_por_trabajo.items():
        for op in range(len(ops) - 1):
            if ops[op][1] > ops[op + 1][0]:
                print(f"Error de precedencia en Trabajo {t}: Op {op} termina en {ops[op][1]} "
                      f"y Op {op+1} inicia en {ops[op+1][0]}.")
                return False

    ops_por_maquina = {}
    for t, op, m, ini, fin in horario:
        ops_por_maquina.setdefault(m, []).append((ini, fin, t, op))

    for m, tareas in ops_por_maquina.items():
        tareas_ordenadas = sorted(tareas, key=lambda x: x[0])
        for i in range(len(tareas_ordenadas) - 1):
            if tareas_ordenadas[i][1] > tareas_ordenadas[i + 1][0]:
                print(f"Error de solapamiento en Máquina {m}: Tarea "
                      f"({tareas_ordenadas[i][2]},{tareas_ordenadas[i][3]}) se cruza con "
                      f"({tareas_ordenadas[i+1][2]},{tareas_ordenadas[i+1][3]}).")
                return False

    max_fin = max(fin for _, _, _, _, fin in horario) if horario else 0
    if max_fin != makespan:
        print(f"Error: Makespan reportado ({makespan}) no coincide con el máximo tiempo de fin ({max_fin}).")
        return False

    return True


# =============================================================================
# 4. ALGORITMO ACO (MAX-MIN ANT SYSTEM)
# =============================================================================

class ACO_FJSP:
    """Implementación de MAX-MIN Ant System (MMAS) para FJSP."""

    def __init__(self, instancia: InstanciaFJSP, n_hormigas: int = 30, alpha: float = 1.0,
                 beta: float = 2.0, rho: float = 0.1, q0: float = 0.0,
                 semilla: int = 42):
        self.instancia = instancia
        self.n_hormigas = n_hormigas
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.q0 = q0
        self.rng = random.Random(semilla)

        # Matriz de feromonas: tau[(j, k, m)]
        self.tau = {}
        # Matriz de heurística: eta[(j, k, m)] = 1.0 / duracion
        self.eta = {}
        self._inicializar_matrices()

        self.tau_max = 1.0
        self.tau_min = 0.01

    def _inicializar_matrices(self):
        for j, trabajo in enumerate(self.instancia.trabajos):
            for k, operacion in enumerate(trabajo):
                for m, duracion in operacion:
                    self.tau[(j, k, m)] = 1.0
                    self.eta[(j, k, m)] = 1.0 / duracion if duracion > 0 else 1.0

    def _estimar_bounds_feromona(self, mejor_makespan: int):
        """Calcula tau_max y tau_min según la formulación teórica de MMAS
        (Stützle & Hoos, 2000)."""
        if mejor_makespan <= 0 or mejor_makespan == math.inf:
            return
        self.tau_max = 1.0 / (self.rho * mejor_makespan)
        p_dec = 0.05  # probabilidad de seleccionar la mejor opción teórica
        avg_options = (sum(len(op) for t in self.instancia.trabajos for op in t)
                       / sum(len(t) for t in self.instancia.trabajos))
        st = math.pow(p_dec, 1.0 / max(1.0, avg_options))
        self.tau_min = min(self.tau_max, self.tau_max * (1.0 - st) / max(1e-5, ((avg_options - 1.0) * st)))
        if self.tau_min >= self.tau_max:
            self.tau_min = self.tau_max * 0.01

    def _construir_solucion_hormiga(self) -> Solucion:
        """Construye una solución válida respetando las reglas de precedencia y selección probabilística."""
        total_ops = sum(len(t) for t in self.instancia.trabajos)
        progreso = [0] * self.instancia.num_trabajos

        secuencia = []
        asignaciones = {}

        for _ in range(total_ops):
            candidatos_trabajo = [j for j in range(self.instancia.num_trabajos)
                                   if progreso[j] < len(self.instancia.trabajos[j])]

            opciones = []
            atractivos = []

            for j in candidatos_trabajo:
                k = progreso[j]
                for m, _ in self.instancia.trabajos[j][k]:
                    tau_val = self.tau[(j, k, m)]
                    eta_val = self.eta[(j, k, m)]
                    atractivo = (tau_val ** self.alpha) * (eta_val ** self.beta)
                    opciones.append((j, k, m))
                    atractivos.append(atractivo)

            if self.rng.random() < self.q0:
                # Explotación pura: elegir el máximo atractivo (desempate al azar)
                max_atr = -1.0
                mejores_opciones = []
                for idx, atr in enumerate(atractivos):
                    if atr > max_atr:
                        max_atr = atr
                        mejores_opciones = [opciones[idx]]
                    elif math.isclose(atr, max_atr):
                        mejores_opciones.append(opciones[idx])
                j_elegido, k_elegido, m_elegido = self.rng.choice(mejores_opciones)
            else:
                # Transición probabilística proporcional (ruleta)
                suma_atractivos = sum(atractivos)
                if suma_atractivos <= 0:
                    j_elegido, k_elegido, m_elegido = self.rng.choice(opciones)
                else:
                    probs = [a / suma_atractivos for a in atractivos]
                    r = self.rng.random()
                    acum = 0.0
                    j_elegido, k_elegido, m_elegido = opciones[-1]
                    for idx, p in enumerate(probs):
                        acum += p
                        if r <= acum:
                            j_elegido, k_elegido, m_elegido = opciones[idx]
                            break

            secuencia.append(j_elegido)
            asignaciones[(j_elegido, k_elegido)] = m_elegido
            progreso[j_elegido] += 1

        sol = Solucion(secuencia, asignaciones)
        sol.makespan, sol.horario = decodificar_activo(self.instancia, sol.secuencia_operaciones, sol.asignacion_maquinas)
        return sol

    def resolver(self, max_iteraciones: int, tiempo_limite_s: float = None) -> tuple:
        """
        Ejecuta la metaheurística MMAS.

        :return: (mejor_solucion, traza_convergencia, iteraciones_realizadas)
        """
        import time
        tiempo_inicio = time.time()
        mejor_solucion_global = None
        traza_convergencia = []  # Lista de tuplas (tiempo_transcurrido, mejor_makespan)

        for clave in self.tau:
            self.tau[clave] = self.tau_max

        iteracion = 0
        while iteracion < max_iteraciones:
            tiempo_actual = time.time() - tiempo_inicio
            if tiempo_limite_s and tiempo_actual >= tiempo_limite_s:
                break

            iteracion += 1
            soluciones_iteracion = []

            for _ in range(self.n_hormigas):
                sol = self._construir_solucion_hormiga()
                soluciones_iteracion.append(sol)

            mejor_iteracion = min(soluciones_iteracion, key=lambda s: s.makespan)

            if mejor_solucion_global is None or mejor_iteracion.makespan < mejor_solucion_global.makespan:
                mejor_solucion_global = mejor_iteracion
                self._estimar_bounds_feromona(mejor_solucion_global.makespan)

            # Evaporación
            for clave in self.tau:
                self.tau[clave] = (1.0 - self.rho) * self.tau[clave]

            # Depósito (solo en las celdas usadas por la mejor solución global)
            delta_tau = 1.0 / mejor_solucion_global.makespan
            for (j, k), m in mejor_solucion_global.asignacion_maquinas.items():
                self.tau[(j, k, m)] += self.rho * delta_tau

            # Límites MMAS
            for clave in self.tau:
                if self.tau[clave] > self.tau_max:
                    self.tau[clave] = self.tau_max
                elif self.tau[clave] < self.tau_min:
                    self.tau[clave] = self.tau_min

            tiempo_transcurrido = time.time() - tiempo_inicio
            traza_convergencia.append((tiempo_transcurrido, mejor_solucion_global.makespan))

        return mejor_solucion_global, traza_convergencia, iteracion
