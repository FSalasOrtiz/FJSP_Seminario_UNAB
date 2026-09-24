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

def decode_schedule(individual):

    individual = repair_individual(individual)

    # Información de cada operación
    operation_info = {}

    for gene in individual:

        operation_id, alternative = decode_gene(gene)

        operation = operations[operation_id]

        machine, processing_time = \
            operation["alternatives"][alternative]

        operation_info[operation_id] = {
            "job": operation["job"],
            "operation": operation["operation"],
            "machine": machine,
            "processing_time": processing_time
        }

    # Operaciones pendientes
    unscheduled = set(operation_info.keys())

    # Fin de la última operación de cada trabajo
    job_finish = {
        job_id: 0
        for job_id in range(n_jobs)
    }

    # Fin de la última operación de cada máquina
    machine_finish = {
        machine_id: 0
        for machine_id in range(1, n_machines + 1)
    }

    schedule = []

    # Programar hasta que todas las operaciones estén listas
    while unscheduled:

        progress = False

        # Recorremos el cromosoma respetando su prioridad
        for gene in individual:

            operation_id, _ = decode_gene(gene)

            if operation_id not in unscheduled:
                continue

            info = operation_info[operation_id]

            job = info["job"]
            operation_number = info["operation"]
            machine = info["machine"]
            processing_time = info["processing_time"]

            # Verificar precedencia
            if operation_number > 0:

                previous_operation_id = jobs[job][
                    operation_number - 1
                ]

                previous_scheduled = next(
                    (
                        x for x in schedule
                        if x["operation_id"] ==
                        previous_operation_id
                    ),
                    None
                )

                if previous_scheduled is None:
                    continue

                previous_finish = previous_scheduled["finish"]

            else:
                previous_finish = 0

            # La operación comienza cuando:
            # 1. termina la operación anterior del trabajo
            # 2. queda disponible la máquina
            start = max(
                previous_finish,
                machine_finish[machine],
                job_finish[job]
            )

            finish = start + processing_time

            schedule.append({
                "operation_id": operation_id,
                "job": job,
                "operation": operation_number,
                "machine": machine,
                "processing_time": processing_time,
                "start": start,
                "finish": finish
            })

            machine_finish[machine] = finish
            job_finish[job] = finish

            unscheduled.remove(operation_id)

            progress = True

        # Evita quedarse atrapado si existe un cromosoma inválido
        if not progress:
            raise ValueError(
                "No fue posible decodificar el cromosoma."
            )

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

def crossover(parent1, parent2):

    child1, child2 = tools.cxTwoPoint(
        parent1,
        parent2
    )

    child1[:] = repair_individual(child1)
    child2[:] = repair_individual(child2)

    return child1, child2


def mutation(individual):

    # Cambiar orden
    if len(individual) > 1:

        tools.mutShuffleIndexes(
            individual,
            indpb=0.05
        )

    # Cambiar máquina de algunas operaciones
    for i in range(len(individual)):

        if random.random() < 0.05:

            operation_id, current_alternative = \
                decode_gene(individual[i])

            operation = operations[operation_id]

            n_alternatives = len(
                operation["alternatives"]
            )

            if n_alternatives > 1:

                possible = list(
                    range(n_alternatives)
                )

                possible.remove(
                    current_alternative
                )

                new_alternative = random.choice(
                    possible
                )

                individual[i] = encode_gene(
                    operation_id,
                    new_alternative
                )

    individual[:] = repair_individual(individual)

    return individual,


# ============================================================
# 8. CONFIGURACIÓN DEL ALGORITMO GENÉTICO
# ============================================================

def _construir_toolbox(tournsize):
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
        tournsize=tournsize
    )

    # Cruce
    toolbox.register(
        "mate",
        crossover
    )

    # Mutación
    toolbox.register(
        "mutate",
        mutation
    )

    return toolbox


# ============================================================
# 9. PARÁMETROS POR DEFECTO
# ============================================================
# Los mismos valores que traía el script original, ahora como defaults de
# resolver() en vez de constantes fijas — así se pueden barrer con Optuna
# o pasar por CLI sin editar el archivo.

POP_SIZE = 50
CROSSOVER_PROB = 0.3
MUTATION_PROB = 0.2
GENERATIONS = 100
TOURNSIZE = 5


# ============================================================
# 10. EJECUCIÓN
# ============================================================
# eaSimple de DEAP no expone el tiempo transcurrido por generación (hace
# falta para g1.csv/g1.png, igual que en AG_IA), así que acá se reimplementa
# su mismo bucle (selección -> cruce/mutación -> evaluación -> reemplazo,
# ver la documentación de deap.algorithms.eaSimple) agregando solo el
# cronómetro por generación. La secuencia de operadores y probabilidades es
# idéntica a la del script original; no se cambió ninguna regla del AG.

def resolver(instance_path, tam_poblacion=POP_SIZE, prob_cruce=CROSSOVER_PROB,
             prob_mutacion=MUTATION_PROB, tournsize=TOURNSIZE,
             max_generaciones=GENERATIONS, tiempo_limite_s=None, semilla=None):
    """Corre el AG sobre `instance_path` y devuelve el resultado.

    Devuelve un dict con: individuo (cromosoma), makespan, horario (lista
    de dicts, ver decode_schedule), generaciones, tiempo_s, traza (lista
    de (tiempo_transcurrido_s, mejor_makespan)).
    """
    if semilla is not None:
        random.seed(semilla)

    _cargar_instancia(instance_path)
    toolbox = _construir_toolbox(tournsize)

    t0 = time.time()

    poblacion = toolbox.population(n=tam_poblacion)
    hall_of_fame = tools.HallOfFame(1)

    fitnesses = map(toolbox.evaluate, poblacion)
    for ind, fit in zip(poblacion, fitnesses):
        ind.fitness.values = fit
    hall_of_fame.update(poblacion)

    traza = [(time.time() - t0, hall_of_fame[0].fitness.values[0])]
    generaciones_corridas = 0

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
            if random.random() < prob_mutacion:
                descendencia[i], = toolbox.mutate(descendencia[i])
                del descendencia[i].fitness.values

        invalidos = [ind for ind in descendencia if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalidos)
        for ind, fit in zip(invalidos, fitnesses):
            ind.fitness.values = fit

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
