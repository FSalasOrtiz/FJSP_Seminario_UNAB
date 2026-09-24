import random

# ============================================================
# 1. INSTANCE READING
# ============================================================

def read_fjsp_instance(filename):
    
    with open(filename, "r", encoding="utf-8") as file:
        tokens = []
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens.extend(line.split())

    pos = 0

    number_of_jobs = int(tokens[pos]); pos += 1
    number_of_machines = int(tokens[pos]); pos += 1
    pos += 1  # flexibilidad promedio: informativa, se descarta sin convertir a int

    jobs = []

    for _ in range(number_of_jobs):
        number_of_operations = int(tokens[pos])
        pos += 1

        operations = []

        for _ in range(number_of_operations):
            number_of_alternatives = int(tokens[pos])
            pos += 1

            alternatives = []
            for _ in range(number_of_alternatives):
                machine = int(tokens[pos]) - 1
                duration = int(tokens[pos + 1])
                pos += 2
                alternatives.append((machine, duration))

            operations.append(alternatives)

        jobs.append(operations)

    return jobs, number_of_machines


# ============================================================
# 2. PSO SOLVER
# ============================================================

class Particle:
    def __init__(self, dimension, rng):
        self.position_order = [rng.random() for _ in range(dimension)]
        self.position_machine = [rng.random() for _ in range(dimension)]

        self.velocity_order = [rng.uniform(-0.2, 0.2) for _ in range(dimension)]
        self.velocity_machine = [rng.uniform(-0.2, 0.2) for _ in range(dimension)]

        self.best_order = self.position_order[:]
        self.best_machine = self.position_machine[:]
        self.best_fitness = float("inf")


class FJSP_PSO:
    def __init__(
        self,
        jobs,
        number_of_machines,
        population_size=30,
        iterations=100,
        inertia=0.7,
        c1=1.4,
        c2=1.4,
        seed=42,
    ):
        self.jobs = jobs
        self.number_of_machines = number_of_machines
        self.population_size = population_size
        self.iterations = iterations
        self.inertia = inertia
        self.c1 = c1
        self.c2 = c2
        self.rng = random.Random(seed)

        # Every operation gets one integer index.
        self.operations = []
        for job_id, job in enumerate(self.jobs):
            for operation_id in range(len(job)):
                self.operations.append((job_id, operation_id))

        self.operation_index = {
            operation: index
            for index, operation in enumerate(self.operations)
        }

        self.dimension = len(self.operations)

        self.swarm = []
        self.global_best_order = None
        self.global_best_machine = None
        self.global_best_fitness = float("inf")
        self.global_best_schedule = None

    # --------------------------------------------------------
    # Decode particle position into a valid FJSP schedule
    # --------------------------------------------------------
    def decode(self, position_order, position_machine):
        # ----- Build an operation order while preserving job precedence.
        # For every job we can only select its next operation.
        next_operation = [0 for _ in self.jobs]
        operation_sequence = []

        while len(operation_sequence) < self.dimension:
            candidates = []

            for job_id, job in enumerate(self.jobs):
                operation_id = next_operation[job_id]

                if operation_id < len(job):
                    index = self.operation_index[(job_id, operation_id)]
                    priority = position_order[index]
                    candidates.append((priority, job_id, operation_id))

            _, job_id, operation_id = min(candidates)
            operation_sequence.append((job_id, operation_id))
            next_operation[job_id] += 1

        # ----- Choose a machine and schedule each operation.
        machine_ready = [0 for _ in range(self.number_of_machines)]
        job_ready = [0 for _ in self.jobs]
        schedule = []

        for job_id, operation_id in operation_sequence:
            index = self.operation_index[(job_id, operation_id)]
            alternatives = self.jobs[job_id][operation_id]

            # Convert [0, 1] into one eligible-machine index.
            choice = int(position_machine[index] * len(alternatives))
            choice = min(choice, len(alternatives) - 1)

            machine, duration = alternatives[choice]

            start = max(job_ready[job_id], machine_ready[machine])
            end = start + duration

            schedule.append({
                "job": job_id,
                "operation": operation_id,
                "machine": machine,
                "duration": duration,
                "start": start,
                "end": end,
            })

            job_ready[job_id] = end
            machine_ready[machine] = end

        makespan = max((item["end"] for item in schedule), default=0)

        return makespan, schedule, operation_sequence

    # --------------------------------------------------------
    # Fitness
    # --------------------------------------------------------
    def fitness(self, position_order, position_machine):
        makespan, _, _ = self.decode(position_order, position_machine)

        # We maximize fitness while minimizing makespan.
        return 1.0 / (1.0 + makespan)

    # --------------------------------------------------------
    # Main PSO loop
    # --------------------------------------------------------
    def solve(self):
        self.swarm = []

        # Initial population
        for _ in range(self.population_size):
            particle = Particle(self.dimension, self.rng)
            particle.best_fitness = self.fitness(
                particle.position_order,
                particle.position_machine,
            )

            self.swarm.append(particle)

            if (
                self.global_best_order is None
                or particle.best_fitness > self.global_best_fitness
            ):
                self.global_best_fitness = particle.best_fitness
                self.global_best_order = particle.best_order[:]
                self.global_best_machine = particle.best_machine[:]

        history = []

        # PSO iterations
        for iteration in range(self.iterations):
            # Small inertia reduction for a little more exploration early
            # and a little more exploitation near the end.
            current_inertia = self.inertia - (
                0.3 * iteration / max(1, self.iterations - 1)
            )

            for particle in self.swarm:
                for i in range(self.dimension):
                    r1 = self.rng.random()
                    r2 = self.rng.random()

                    # Operation-order velocity
                    particle.velocity_order[i] = (
                        current_inertia * particle.velocity_order[i]
                        + self.c1 * r1 * (
                            particle.best_order[i] - particle.position_order[i]
                        )
                        + self.c2 * r2 * (
                            self.global_best_order[i] - particle.position_order[i]
                        )
                    )

                    # Machine-selection velocity
                    particle.velocity_machine[i] = (
                        current_inertia * particle.velocity_machine[i]
                        + self.c1 * r1 * (
                            particle.best_machine[i] - particle.position_machine[i]
                        )
                        + self.c2 * r2 * (
                            self.global_best_machine[i] - particle.position_machine[i]
                        )
                    )

                    particle.position_order[i] += particle.velocity_order[i]
                    particle.position_machine[i] += particle.velocity_machine[i]

                    # Keep random keys inside [0, 1]
                    particle.position_order[i] = max(
                        0.0, min(1.0, particle.position_order[i])
                    )
                    particle.position_machine[i] = max(
                        0.0, min(1.0, particle.position_machine[i])
                    )

                current_fitness = self.fitness(
                    particle.position_order,
                    particle.position_machine,
                )

                if current_fitness > particle.best_fitness:
                    particle.best_fitness = current_fitness
                    particle.best_order = particle.position_order[:]
                    particle.best_machine = particle.position_machine[:]

                # Global best is based on the particle's current solution.
                if current_fitness > self.global_best_fitness:
                    self.global_best_fitness = current_fitness
                    self.global_best_order = particle.position_order[:]
                    self.global_best_machine = particle.position_machine[:]

            makespan, schedule, sequence = self.decode(
                self.global_best_order,
                self.global_best_machine,
            )
            self.global_best_schedule = schedule
            history.append(makespan)

            print(
                f"Iteración {iteration + 1:3d}/{self.iterations} "
                f"| Makespan = {makespan}"
            )

        makespan, schedule, sequence = self.decode(
            self.global_best_order,
            self.global_best_machine,
        )

        return makespan, schedule, sequence, history


# ============================================================
# 3. PRINT RESULT
# ============================================================

def print_solution(makespan, schedule, sequence):
    print("\n" + "=" * 65)
    print("MEJOR SOLUCIÓN ENCONTRADA")
    print("=" * 65)
    print(f"Makespan: {makespan}")

    print("\nOrden de operaciones:")
    for position, (job, operation) in enumerate(sequence, start=1):
        print(f"  {position:2d}. Job {job + 1} - Operación {operation + 1}")

    print("\nDetalle de planificación:")
    ordered_schedule = sorted(schedule, key=lambda item: (item["start"], item["machine"]))

    for item in ordered_schedule:
        print(
            f"  Job {item['job'] + 1}, "
            f"Op {item['operation'] + 1} -> "
            f"Máquina {item['machine'] + 1} | "
            f"Inicio {item['start']} | "
            f"Fin {item['end']} | "
            f"Duración {item['duration']}"
        )

    print("\nPor máquina:")
    machines = {}
    for item in schedule:
        machines.setdefault(item["machine"], []).append(item)

    for machine in sorted(machines):
        machines[machine].sort(key=lambda item: item["start"])
        print(f"  Máquina {machine + 1}:")
        for item in machines[machine]:
            print(
                f"    Job {item['job'] + 1} - Op {item['operation'] + 1}: "
                f"[{item['start']}, {item['end']}]"
            )


# ============================================================
# 4. MAIN
# ============================================================

if __name__ == "__main__":
    # Reemplaza esta ruta por la instancia que quieras correr, p.ej.:
    # "data/instances/mk01.fjs" o "Entrada/instances/mk01.fjs"
    INSTANCE_FILE = "ruta/a/tu/instancia.fjs"
    jobs, number_of_machines = read_fjsp_instance(INSTANCE_FILE)
    print(f"Usando instancia: {INSTANCE_FILE}\n")

    solver = FJSP_PSO(
        jobs=jobs,
        number_of_machines=number_of_machines,
        population_size=40,
        iterations=100,
        inertia=0.7,
        c1=1.4,
        c2=1.4,
        seed=42,
    )

    makespan, schedule, sequence, history = solver.solve()
    print_solution(makespan, schedule, sequence)
