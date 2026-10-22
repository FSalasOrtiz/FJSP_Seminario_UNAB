import bisect
import random
import time
from deap import base, creator, tools

# NOTA (adaptación mínima para poder correr por lote y calibrar con
# Optuna, ver ../calibracion/): las secciones "cargar instancia" y
# "ejecución" originales corrían directo al importar el módulo, con
# INSTANCE_PATH y los hiperparámetros como constantes fijas — así no se
# puede correr una instancia distinta sin editar este archivo a mano.
# Esas dos secciones se movieron a _cargar_instancia() y resolver() al
# final del archivo. Ninguna función del algoritmo en sí (load_fjs,
# create_individual, repair_individual, decode_schedule,
# objective_function, crossover, mutation) fue tocada.
#
# CORRECCIÓN (oct 2026, gap promedio < 5% exigido por el profesor): tras un
# análisis de ablación se cambiaron estas piezas del algoritmo, manteniendo
# el mismo cromosoma, DEAP y la misma API de resolver():
#   1. decode_schedule: el cromosoma se lee como secuencia de trabajos (la
#      k-ésima aparición del trabajo j programa su operación k), en una sola
#      pasada, y el horario es ACTIVO (inserta en huecos libres). Cada
#      operación va a la máquina donde TERMINA ANTES; ante empate, a la del
#      gen. Antes era semi-activo, con la máquina fija del gen y barridos
#      repetidos + búsqueda lineal (muy lento).
#   2. crossover: POX (conserva el orden relativo de un subconjunto de
#      trabajos) + mezcla uniforme de máquinas. Antes cxTwoPoint generaba
#      duplicados y la reparación agregaba al final, con máquina aleatoria,
#      las operaciones perdidas (destruía a los hijos).
#   3. mutación: 1 intercambio de genes (con prob_mut_os) y 1 cambio de
#      máquina (con prob_mut_ms). Antes indpb=0.05 por gen (~15 + ~15
#      cambios en instancias de 300 operaciones).
#   4. resolver: elitismo (los `elitismo` mejores de la generación anterior
#      reemplazan a los peores hijos) e inmigrantes aleatorios cuando el
#      mejor se estanca. Antes el mejor solo quedaba en el HallOfFame.
#   5. Población inicial: la mitad con la máquina más rápida de cada
#      operación y 5 individuos construidos por despacho (trabajo con más
#      trabajo restante + máquina que termina antes).
# Los hiperparámetros de resolver() tienen los mismos nombres, valores por
# defecto y rangos de calibración que AG_IA, para que lo único distinto
# entre ambas sea la implementación.

INSTANCE_PATH = "instances/abz5_vdata.fjs"

n_jobs = n_machines = variant = jobs = operations = None
N_OPERATIONS = MAX_ALTERNATIVES = None


# ============================================================
# 1. LECTURA DE INSTANCIA FJS
# ============================================================

def load_fjs(path):

    with open(path, "r") as file:
        lines = [
            line.strip()
            for line in file
            if line.strip()
        ]

    # Primera línea:
    # trabajos, máquinas, parámetro de variante
    first = lines[0].split()

    n_jobs = int(first[0])
    n_machines = int(first[1])
    variant = float(first[2])

    jobs = []
    operations = []

    operation_id = 0

    for job_id in range(n_jobs):

        values = list(map(int, lines[job_id + 1].split()))

        pos = 0

        # Número de operaciones del trabajo
        n_operations = values[pos]
        pos += 1

        job_operations = []

        for operation_id_job in range(n_operations):

            # Número de máquinas alternativas
            n_alternatives = values[pos]
            pos += 1

            alternatives = []

            for _ in range(n_alternatives):

                machine = values[pos]
                processing_time = values[pos + 1]

                pos += 2

                alternatives.append(
                    (machine, processing_time)
                )

            operation = {
                "id": operation_id,
                "job": job_id,
                "operation": operation_id_job,
                "alternatives": alternatives
            }

            operations.append(operation)
            job_operations.append(operation_id)

            operation_id += 1

        jobs.append(job_operations)

    return (
        n_jobs,
        n_machines,
        variant,
        jobs,
        operations
    )


def _cargar_instancia(path, verbose=False):
    """Carga `path` en las globales del módulo (n_jobs, operations, etc.).

    Antes esto corría directo al importar el módulo, con INSTANCE_PATH
    fijo — ahora es una función para poder cargar instancias distintas en
    llamadas sucesivas (necesario para correr por lote y para calibrar).
    """
    global n_jobs, n_machines, variant, jobs, operations
    global N_OPERATIONS, MAX_ALTERNATIVES

    n_jobs, n_machines, variant, jobs, operations = load_fjs(path)

    N_OPERATIONS = len(operations)
    MAX_ALTERNATIVES = max(
        len(op["alternatives"])
        for op in operations
    )

    if verbose:
        print("Trabajos:", n_jobs)
        print("Máquinas:", n_machines)
        print("Operaciones:", N_OPERATIONS)


# ============================================================
# 2. REPRESENTACIÓN DEL CROMOSOMA
# ============================================================

# Cada gen representa:
#
#     operación + máquina alternativa
#
# Ejemplo:
#
#     (operación 5, alternativa 2)
#
# Para facilitar el uso de DEAP se codifica como:
#
#     operation_id * MAX_ALTERNATIVES + alternative


def encode_gene(operation_id, alternative):

    return (
        operation_id * MAX_ALTERNATIVES
        + alternative
    )


def decode_gene(gene):

    operation_id = gene // MAX_ALTERNATIVES
    alternative = gene % MAX_ALTERNATIVES

    return operation_id, alternative


# ============================================================
# 3. CREACIÓN DEL INDIVIDUO
# ============================================================

def create_individual():

    chromosome = []

    for operation in operations:

        alternative = random.randrange(
            len(operation["alternatives"])
        )

        chromosome.append(
            encode_gene(
                operation["id"],
                alternative
            )
        )

    # El orden de las operaciones es aleatorio
    random.shuffle(chromosome)

    return chromosome


def fastest_machines(individual):

    # Asigna a cada operación su alternativa de menor tiempo de proceso
    for i, gene in enumerate(individual):

        operation_id, _ = decode_gene(gene)

        alternatives = operations[operation_id]["alternatives"]

        fastest = min(
            range(len(alternatives)),
            key=lambda k: alternatives[k][1]
        )

        individual[i] = encode_gene(operation_id, fastest)


def dispatch_individual(individual, noise):

    # Construye el cromosoma con una regla de despacho: en cada paso se
    # programa el trabajo con más trabajo restante (con un ruido relativo
    # `noise` para variar entre individuos) en la máquina que termina antes
    def min_time(operation_id):
        return min(p for _, p in operations[operation_id]["alternatives"])

    remaining = {
        job_id: sum(min_time(o) for o in jobs[job_id])
        for job_id in range(n_jobs)
    }
    next_operation = {job_id: 0 for job_id in range(n_jobs)}
    job_finish = {job_id: 0 for job_id in range(n_jobs)}
    machine_intervals = {
        machine_id: []
        for machine_id in range(1, n_machines + 1)
    }

    chromosome = []

    for _ in range(N_OPERATIONS):

        candidates = [
            job_id for job_id in range(n_jobs)
            if next_operation[job_id] < len(jobs[job_id])
        ]

        job = max(
            candidates,
            key=lambda j: remaining[j] * (1 + noise * random.random())
        )

        operation_id = jobs[job][next_operation[job]]

        best = None

        for k, (machine, processing_time) in enumerate(
            operations[operation_id]["alternatives"]
        ):

            start = find_gap(
                machine_intervals[machine],
                job_finish[job],
                processing_time
            )

            if best is None or start + processing_time < best[0]:
                best = (start + processing_time, k, machine, start)

        finish, alternative, machine, start = best

        bisect.insort(machine_intervals[machine], (start, finish))
        job_finish[job] = finish
        next_operation[job] += 1
        remaining[job] -= min_time(operation_id)

        chromosome.append(encode_gene(operation_id, alternative))

    individual[:] = chromosome


# ============================================================
# 4. REPARACIÓN DEL CROMOSOMA
# ============================================================

def repair_individual(individual):

    repaired = []
    used_operations = set()

    # Mantener una sola aparición por operación
    for gene in individual:

        operation_id, alternative = decode_gene(gene)

        if operation_id >= N_OPERATIONS:
            continue

        if operation_id in used_operations:
            continue

        max_alt = len(
            operations[operation_id]["alternatives"]
        )

        # Corregir alternativa inválida
        if alternative >= max_alt:
            alternative = random.randrange(max_alt)

        repaired.append(
            encode_gene(
                operation_id,
                alternative
            )
        )

        used_operations.add(operation_id)

    # Agregar operaciones que se perdieron
    for operation in operations:

        operation_id = operation["id"]

        if operation_id not in used_operations:

            alternative = random.randrange(
                len(operation["alternatives"])
            )

            repaired.append(
                encode_gene(
                    operation_id,
                    alternative
                )
            )

    return repaired


# ============================================================
# 5. DECODIFICACIÓN DEL CROMOSOMA
# ============================================================

def find_gap(intervals, release, processing_time):

    # Primer instante >= release donde la operación cabe completa
    # sin solaparse con lo ya programado en la máquina
    start = release

    for (busy_start, busy_finish) in intervals:

        if start + processing_time <= busy_start:
            return start

        if start < busy_finish:
            start = busy_finish

    return start


def decode_schedule(individual):

    individual = repair_individual(individual)

    # Alternativa (máquina) elegida para cada operación
    alternative_of = {}

    for gene in individual:

        operation_id, alternative = decode_gene(gene)
        alternative_of[operation_id] = alternative

    # Intervalos ocupados de cada máquina, ordenados por inicio
    machine_intervals = {
        machine_id: []
        for machine_id in range(1, n_machines + 1)
    }

    # Fin de la última operación de cada trabajo
    job_finish = {
        job_id: 0
        for job_id in range(n_jobs)
    }

    # Próxima operación pendiente de cada trabajo
    next_operation = {
        job_id: 0
        for job_id in range(n_jobs)
    }

    schedule = []

    # El cromosoma se lee como secuencia de trabajos: la k-ésima vez que
    # aparece un gen del trabajo j se programa la operación k de j.
    # Así la precedencia se cumple siempre, en una sola pasada.
    for gene in individual:

        gene_operation_id, _ = decode_gene(gene)

        job = operations[gene_operation_id]["job"]
        operation_number = next_operation[job]
        operation_id = jobs[job][operation_number]

        alternatives = operations[operation_id]["alternatives"]
        preferred = alternative_of[operation_id]

        # Horario activo: en cada máquina se usa el primer hueco libre
        # posterior al fin de la operación anterior del trabajo. Se parte
        # de la máquina del gen y se cambia solo si otra termina antes.
        machine, processing_time = alternatives[preferred]
        start = find_gap(
            machine_intervals[machine],
            job_finish[job],
            processing_time
        )

        for k, (other_machine, other_time) in enumerate(alternatives):

            if k == preferred:
                continue

            other_start = find_gap(
                machine_intervals[other_machine],
                job_finish[job],
                other_time
            )

            if other_start + other_time < start + processing_time:
                machine = other_machine
                processing_time = other_time
                start = other_start

        finish = start + processing_time

        bisect.insort(
            machine_intervals[machine],
            (start, finish)
        )

        schedule.append({
            "operation_id": operation_id,
            "job": job,
            "operation": operation_number,
            "machine": machine,
            "processing_time": processing_time,
            "start": start,
            "finish": finish
        })

        job_finish[job] = finish
        next_operation[job] += 1

    return schedule


# ============================================================
# 6. FUNCIÓN OBJETIVO
# ============================================================

def objective_function(individual):

    schedule = decode_schedule(individual)

    makespan = max(
        operation["finish"]
        for operation in schedule
    )

    return (makespan,)


# ============================================================
# 7. OPERADORES GENÉTICOS
# ============================================================

def job_of(gene):

    operation_id, _ = decode_gene(gene)

    return operations[operation_id]["job"]


def pox_crossover(parent1, parent2):

    # POX: los genes de un subconjunto aleatorio de trabajos quedan en la
    # misma posición que en parent1; los huecos se llenan con los genes de
    # los demás trabajos en el orden en que aparecen en parent2
    job_ids = list(range(n_jobs))
    random.shuffle(job_ids)

    if n_jobs > 1:
        cut = random.randint(1, n_jobs - 1)
    else:
        cut = 1

    kept_jobs = set(job_ids[:cut])

    rest = iter([
        gene for gene in parent2
        if job_of(gene) not in kept_jobs
    ])

    return [
        gene if job_of(gene) in kept_jobs else next(rest)
        for gene in parent1
    ]


def mix_machines(child, parent1, parent2):

    # Cada operación hereda la máquina de uno de los padres al azar
    alternatives1 = dict(decode_gene(gene) for gene in parent1)
    alternatives2 = dict(decode_gene(gene) for gene in parent2)

    mixed = []

    for gene in child:

        operation_id, _ = decode_gene(gene)

        if random.random() < 0.5:
            alternative = alternatives1[operation_id]
        else:
            alternative = alternatives2[operation_id]

        mixed.append(
            encode_gene(operation_id, alternative)
        )

    return mixed


def crossover(parent1, parent2):

    if len(parent1) < 2:
        return parent1, parent2

    p1 = list(parent1)
    p2 = list(parent2)

    parent1[:] = mix_machines(pox_crossover(p1, p2), p1, p2)
    parent2[:] = mix_machines(pox_crossover(p2, p1), p1, p2)

    return parent1, parent2


def mutate_order(individual):

    # Cambiar orden: intercambiar dos genes
    if len(individual) > 1:

        i = random.randrange(len(individual))
        k = random.randrange(len(individual))

        individual[i], individual[k] = individual[k], individual[i]

    return individual,


def mutate_machine(individual):

    # Cambiar máquina de una operación
    i = random.randrange(len(individual))

    operation_id, current_alternative = \
        decode_gene(individual[i])

    n_alternatives = len(
        operations[operation_id]["alternatives"]
    )

    if n_alternatives > 1:

        possible = list(
            range(n_alternatives)
        )

        possible.remove(
            current_alternative
        )

        individual[i] = encode_gene(
            operation_id,
            random.choice(possible)
        )

    return individual,


# ============================================================
# 8. CONFIGURACIÓN DEL ALGORITMO GENÉTICO
# ============================================================

def _construir_toolbox(k_torneo):
    """Registra creator/toolbox de DEAP. Separado en función (antes corría
    directo al importar) para poder reconstruir el toolbox por cada
    instancia/trial sin arrastrar estado de una corrida anterior."""

    if not hasattr(creator, "FitnessMin"):
        creator.create(
            "FitnessMin",
            base.Fitness,
            weights=(-1.0,)
        )

    if not hasattr(creator, "Individual"):
        creator.create(
            "Individual",
            list,
            fitness=creator.FitnessMin
        )

    toolbox = base.Toolbox()

    # Generación del individuo
    toolbox.register(
        "individual",
        tools.initIterate,
        creator.Individual,
        create_individual
    )

    # Población
    toolbox.register(
        "population",
        tools.initRepeat,
        list,
        toolbox.individual
    )

    # Fitness
    toolbox.register(
        "evaluate",
        objective_function
    )

    # Selección
    toolbox.register(
        "select",
        tools.selTournament,
        tournsize=k_torneo
    )

    # Cruce
    toolbox.register(
        "mate",
        crossover
    )

    # Mutación del orden
    toolbox.register(
        "mutate_os",
        mutate_order
    )

    # Mutación de máquina
    toolbox.register(
        "mutate_ms",
        mutate_machine
    )

    return toolbox


# ============================================================
# 9. PARÁMETROS POR DEFECTO
# ============================================================
# Los mismos valores que traía el script original, ahora como defaults de
# resolver() en vez de constantes fijas — así se pueden barrer con Optuna
# o pasar por CLI sin editar el archivo.

POP_SIZE = 60
CROSSOVER_PROB = 0.9
MUTATION_OS_PROB = 0.2
MUTATION_MS_PROB = 0.3
TOURNAMENT_SIZE = 3
ELITISM = 2
STAGNATION_MAX = 15
IMMIGRANT_FRACTION = 0.15
GENERATIONS = 200
DISPATCH_INDIVIDUALS = 5


# ============================================================
# 10. EJECUCIÓN
# ============================================================
# eaSimple de DEAP no expone el tiempo transcurrido por generación (hace
# falta para g1.csv/g1.png, igual que en AG_IA), así que acá se reimplementa
# su mismo bucle (selección -> cruce/mutación -> evaluación -> reemplazo,
# ver la documentación de deap.algorithms.eaSimple) agregando solo el
# cronómetro por generación y (corrección oct 2026) elitismo e inmigrantes
# por estancamiento.

def resolver(instance_path, tam_poblacion=POP_SIZE, prob_cruce=CROSSOVER_PROB,
             prob_mut_os=MUTATION_OS_PROB, prob_mut_ms=MUTATION_MS_PROB,
             k_torneo=TOURNAMENT_SIZE, elitismo=ELITISM,
             estancamiento_max=STAGNATION_MAX,
             frac_inmigrantes=IMMIGRANT_FRACTION,
             max_generaciones=GENERATIONS, tiempo_limite_s=None, semilla=None):
    """Corre el AG sobre `instance_path` y devuelve el resultado.

    Devuelve un dict con: individuo (cromosoma), makespan, horario (lista
    de dicts, ver decode_schedule), generaciones, tiempo_s, traza (lista
    de (tiempo_transcurrido_s, mejor_makespan)).
    """
    if semilla is not None:
        random.seed(semilla)

    _cargar_instancia(instance_path)
    toolbox = _construir_toolbox(k_torneo)

    t0 = time.time()

    poblacion = toolbox.population(n=tam_poblacion)

    # La mitad de la población parte con la máquina más rápida de cada
    # operación (el orden sigue siendo aleatorio)
    for ind in poblacion[: tam_poblacion // 2]:
        fastest_machines(ind)

    # Los últimos 5 individuos se construyen por despacho (el primero sin
    # ruido, el resto con ruido para que no sean idénticos)
    for h in range(min(DISPATCH_INDIVIDUALS, tam_poblacion)):
        dispatch_individual(poblacion[-1 - h], noise=0.0 if h == 0 else 0.2)

    hall_of_fame = tools.HallOfFame(1)

    fitnesses = map(toolbox.evaluate, poblacion)
    for ind, fit in zip(poblacion, fitnesses):
        ind.fitness.values = fit
    hall_of_fame.update(poblacion)

    traza = [(time.time() - t0, hall_of_fame[0].fitness.values[0])]
    generaciones_corridas = 0
    estancamiento = 0

    for gen in range(1, max_generaciones + 1):

        if tiempo_limite_s is not None and (time.time() - t0) >= tiempo_limite_s:
            break

        # -- varAnd: clonar, cruzar y mutar (igual que algorithms.eaSimple) --
        descendencia = list(map(toolbox.clone, toolbox.select(poblacion, len(poblacion))))

        for i in range(1, len(descendencia), 2):
            if random.random() < prob_cruce:
                descendencia[i - 1], descendencia[i] = toolbox.mate(
                    descendencia[i - 1], descendencia[i]
                )
                del descendencia[i - 1].fitness.values
                del descendencia[i].fitness.values

        for i in range(len(descendencia)):
            mutado = False
            if random.random() < prob_mut_os:
                descendencia[i], = toolbox.mutate_os(descendencia[i])
                mutado = True
            if random.random() < prob_mut_ms:
                descendencia[i], = toolbox.mutate_ms(descendencia[i])
                mutado = True
            if mutado:
                del descendencia[i].fitness.values

        invalidos = [ind for ind in descendencia if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalidos)
        for ind, fit in zip(invalidos, fitnesses):
            ind.fitness.values = fit

        # Elitismo: los `elitismo` mejores de la generación anterior
        # reemplazan a los peores hijos
        elite = tools.selBest(poblacion, elitismo)
        peores_hijos = sorted(
            range(len(descendencia)),
            key=lambda i: descendencia[i].fitness.values[0],
            reverse=True
        )[:elitismo]

        for i, ind in zip(peores_hijos, elite):
            descendencia[i] = toolbox.clone(ind)

        # Inmigrantes: si el mejor no mejora en `estancamiento_max`
        # generaciones, los peores hijos se reemplazan por individuos nuevos
        mejor_previo = hall_of_fame[0].fitness.values[0]

        if min(ind.fitness.values[0] for ind in descendencia) < mejor_previo:
            estancamiento = 0
        else:
            estancamiento += 1

        if estancamiento >= estancamiento_max:

            n_inmigrantes = max(1, int(len(descendencia) * frac_inmigrantes))
            peores = sorted(
                range(len(descendencia)),
                key=lambda i: descendencia[i].fitness.values[0],
                reverse=True
            )[:n_inmigrantes]

            for i in peores:
                inmigrante = toolbox.individual()
                inmigrante.fitness.values = toolbox.evaluate(inmigrante)
                descendencia[i] = inmigrante

            estancamiento = 0

        hall_of_fame.update(descendencia)
        poblacion[:] = descendencia
        generaciones_corridas = gen

        traza.append((time.time() - t0, hall_of_fame[0].fitness.values[0]))

    tiempo_s = time.time() - t0

    mejor_individuo = list(hall_of_fame[0])
    mejor_makespan = objective_function(hall_of_fame[0])[0]
    mejor_horario = decode_schedule(hall_of_fame[0])

    return {
        "individuo": mejor_individuo,
        "makespan": mejor_makespan,
        "horario": mejor_horario,
        "generaciones": generaciones_corridas,
        "tiempo_s": tiempo_s,
        "traza": traza,
    }


if __name__ == "__main__":
    resultado = resolver(INSTANCE_PATH)

    print("\n==============================")
    print("MEJOR SOLUCIÓN")
    print("==============================")

    print("Makespan:", resultado["makespan"])

    print("\nCromosoma:")
    print(resultado["individuo"])

    print("\nSchedule:")

    for operation in resultado["horario"]:

        print(
            f"Job {operation['job'] + 1} | "
            f"Op {operation['operation'] + 1} | "
            f"Machine {operation['machine']} | "
            f"{operation['start']} -> "
            f"{operation['finish']}"
        )
