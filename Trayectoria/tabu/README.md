# Búsqueda Tabú (Tabu Search)

Migración de `Tabú/taboo_search.py` (repositorio anterior,
`Metaheur-sticas_FJSP-main`) al contrato único de `core/`. El README de esa
versión describía el método correctamente y el vecindario basado en ruta
crítica se conservó casi intacto; lo que cambió es todo lo que
`METODOLOGIA.md` exige que sea compartido: decodificador, presupuesto,
aleatoriedad y codificación de la solución. Ver el docstring de
`algorithm.py` para la lista completa de diferencias, y
`docs/auditoria_experimento_previo.md` para el contexto de por qué importan.

## 1. Idea central

Búsqueda Tabú explora el espacio de soluciones moviéndose siempre al mejor
vecino disponible —incluso si empeora la solución actual—, pero prohibiendo
temporalmente revertir un movimiento reciente (la "lista tabú"), para evitar
ciclos cortos entre las mismas soluciones. Una excepción, el criterio de
aspiración, permite un movimiento prohibido si de todos modos produce la
mejor solución vista hasta el momento. Esta variante concentra el esfuerzo
de búsqueda en las operaciones que están sobre el camino crítico —el que
determina el makespan—, en vez de considerar toda la instancia por igual.

## 2. Origen y referencia

Glover, F. (1989). Tabu search — Part I. *ORSA Journal on Computing*, 1(3),
190-206. La adaptación a scheduling mediante vecindarios de ruta crítica
sigue la línea de Nowicki, E., & Smutnicki, C. (1996). A fast taboo search
algorithm for the job shop problem. *Management Science*, 42(6), 797-813.

## 3. Pseudocódigo

```
s <- solución inicial (mejor de varios arranques)
mejor <- s
mientras presupuesto no agotado:
    críticas <- operaciones sobre el camino crítico de s
    N <- vecinos de s que reasignan una operación crítica a otra máquina,
         o reordenan la secuencia tocando una operación crítica
    elegir s' en N de menor makespan, entre los no-tabú
           (o tabú si mejora a "mejor": criterio de aspiración)
    aplicar s <- s'; marcar el movimiento inverso como tabú
    si costo(s) < costo(mejor):
        mejor <- s
    si N iteraciones sin mejora:
        perturbar s a partir de "mejor" (diversificación); limpiar lista tabú
devolver mejor
```

## 4. Mapeo al FJSP

- **Solución**: el par canónico `(MS, OS)` (D4). `OS` cumple exactamente el
  rol de la `secuencia` de la versión anterior; la diferencia está en `MS`,
  que guarda el *índice de alternativa* de cada operación, no el número de
  máquina (ver `core/solution.py`).
- **Ruta crítica**: se deriva del `schedule` que devuelve
  `core.objective.evaluar` (no de un decodificador propio). Para cada
  máquina se ordenan sus operaciones por instante de inicio y se identifica
  el predecesor inmediato; luego se traza hacia atrás desde la operación que
  termina en el makespan, prefiriendo el arco de máquina sobre el de trabajo
  cuando ambos son "ajustados" (el predecesor termina justo cuando la
  operación actual empieza) — igual que en la versión anterior.
- **Vecino**:
  - **N1 (reasignación)**: para una operación crítica, cambiar su
    alternativa de máquina (`MS[g]`) a cualquier otra elegible.
  - **N2 (intercambio adyacente)**: intercambiar dos posiciones consecutivas
    de `OS` de trabajos distintos, si al menos una toca una operación
    crítica.
  - **N3 (reubicación)**: mover una operación crítica 2, 4 u 8 posiciones
    antes en `OS`.
- **Lista tabú**: al aplicar un movimiento se prohíbe su reverso (volver a
  la máquina anterior, o repetir el mismo intercambio) durante una tenencia
  aleatoria entre `tenencia_min` y `tenencia_max`, medida en **evaluaciones
  consumidas** (`presupuesto.usadas`), no en iteraciones del bucle.
- **Diversificación**: tras `iter_sin_mejora_diversif` iteraciones sin
  mejorar el mejor makespan global, se limpia la lista tabú y se retoma
  desde la mejor solución archivada, aplicándole reasignaciones e
  intercambios aleatorios.

## 5. Parámetros

Ver `params.yaml` para el detalle y la justificación de cada valor. Ninguno
está calibrado con Optuna todavía (pendiente, punto 7 del acta 2026-08-25);
los valores actuales son heredados de la versión anterior o ajustados a mano
por el cambio de presupuesto (segundos → evaluaciones).

## 6. Complejidad

Por iteración externa: identificar la ruta crítica es O(total_ops · log
total_ops) (una vez por máquina para ordenar por inicio). Generar el
vecindario es O(total_ops) en el peor caso. Cada vecino evaluado cuesta una
decodificación completa, igual que en el resto de las metaheurísticas del
repositorio; con `max_vecinos` acotando cuántos vecinos se evalúan por
iteración, el costo dominante sigue siendo el número de evaluaciones que
permite el presupuesto.

## 7. Fortalezas y debilidades esperadas

*(Registrado antes de correr el experimento — METODOLOGIA.md, plantilla del
punto 7.)*

**Fortalezas esperadas**: al concentrar el vecindario en operaciones
críticas en vez de generar vecinos genéricos, se espera que converja más
rápido por evaluación que un método con vecindario no informado (como el SA
de referencia). El mecanismo de aspiración y diversificación debería evitar
que la lista tabú bloquee mejoras genuinas.

**Debilidades esperadas**: el costo por iteración externa es mayor que el
de un método de vecino único (SA): cada iteración evalúa hasta
`max_vecinos` candidatos antes de moverse, así que con un presupuesto
medido en evaluaciones (D8), el número de iteraciones externas reales puede
ser bajo en instancias pequeñas — es exactamente el mismo trade-off que
`params.yaml` documenta para `max_vecinos`. También depende de que
`iter_sin_mejora_diversif` esté bien calibrado: muy bajo, diversifica antes
de explotar el vecindario; muy alto, se estanca en un óptimo local sin
reaccionar.

## 8. Ejemplo reproducible

```bash
python -m experiments.run --mh tabu --instancia mk01 --semilla 1000
```

Salida esperada: un makespan finito y válido (BKS de mk01 = 40, instancia
cerrada); no se espera igualar ni superar el BKS con parámetros sin
calibrar. Cualquier resultado por debajo de 40 se marca automáticamente
como sospechoso (D10) y debe verificarse a mano antes de creerlo
(`results/VERIFICACIONES.md`).
