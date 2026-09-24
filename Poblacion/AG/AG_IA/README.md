# AG_IA — Algoritmo Genético, implementación con apoyo de Claude

Parte del experimento "implementación humana vs. asistida por IA" (acta de
reunión, 07-09-2026). Su contraparte es `../AG_Alumno/`, construida sin
apoyo de IA — ambas resuelven el mismo problema, reciben el mismo formato
de entrada, y producen el mismo contrato de salida, para que
`herramientas_comparacion/` pueda medir el delta entre ellas sin conocer el
código interno de ninguna.

**Independiente a propósito:** no importa nada de `core/` ni comparte
código con `AG_Alumno/`. Ver el docstring de `algorithm.py` para el porqué.

## 1. Idea central

Un Algoritmo Genético mantiene una población de soluciones candidatas y las
hace evolucionar por generaciones: los individuos con mejor makespan tienen
más probabilidad de reproducirse (selección por torneo), sus "genes" se
combinan (cruce) para producir hijos, y esos hijos sufren pequeñas
alteraciones al azar (mutación). Con el tiempo la población converge hacia
soluciones cada vez mejores; el mecanismo de inmigrantes aleatorios evita
que se estanque en un óptimo local.

## 2. Origen y referencia

Holland, J. H. (1975). *Adaptation in Natural and Artificial Systems*.
University of Michigan Press. La codificación de dos vectores (secuencia +
asignación de máquina) y el cruce POX sobre la parte de secuencia siguen a
Zhang, G., Gao, L., & Shi, Y. (2011). An effective genetic algorithm for
the flexible job-shop scheduling problem. *Expert Systems with
Applications*, 38(4), 3563-3573.

## 3. Pseudocódigo

```
P <- población inicial de tam_poblacion individuos (OS, MS)
mejor <- el mejor individuo de P
mientras no se cumpla el criterio de parada:
    P' <- los `elitismo` mejores de P (se copian sin cambios)
    si estancamiento >= estancamiento_max:
        agregar a P' un número de inmigrantes aleatorios
        estancamiento <- 0
    mientras |P'| < tam_poblacion:
        p1, p2 <- selección por torneo sobre P
        hijo <- cruce(p1, p2) con probabilidad prob_cruce, si no copia de p1
        mutar(hijo) con las probabilidades correspondientes
        evaluar hijo; agregar a P'
        si costo(hijo) < costo(mejor): mejor <- hijo
    P <- P'
    actualizar estancamiento según si mejoró el makespan global
devolver mejor
```

## 4. Mapeo al FJSP

- **Individuo**: el par `(OS, MS)`. `OS` es un vector de longitud
  `total_ops` con repetición de ids de trabajo — el orden de aparición de
  cada trabajo define el orden de sus operaciones sucesivas. `MS[g]` es el
  índice (no el número de máquina) de la alternativa elegida para la
  operación global `g`, dentro de `instancia.alternativas(g)`.
- **Decodificador**: horario ACTIVO con inserción en huecos (`decodificar`
  en `algorithm.py`) — una operación puede insertarse en un hueco libre
  anterior al final de la máquina, si cabe completa sin atrasar nada ya
  programado. Un decodificador semi-activo (solo encolar al final)
  subestimaría la calidad real de las soluciones.
- **Cruce OS — POX** (Precedence-preserving Order-based Crossover): se
  parte el conjunto de trabajos en dos grupos al azar; el hijo hereda de un
  padre las posiciones de un grupo y completa el resto con el orden
  relativo del otro padre. Preserva precedencias por construcción.
- **Cruce MS — uniforme**: cada gen del hijo viene de uno u otro padre con
  probabilidad 0.5, independiente por operación.
- **Mutación OS**: intercambia dos posiciones al azar, o reubica una
  operación en otra posición.
- **Mutación MS**: cambia la alternativa de máquina de una operación al
  azar.
- **Selección**: torneo de tamaño `k_torneo`.
- **Elitismo**: los `elitismo` mejores individuos pasan intactos.
- **Inmigrantes**: tras `estancamiento_max` generaciones sin mejora del
  makespan global, se inyecta una fracción `frac_inmigrantes` de individuos
  aleatorios nuevos.

## 5. Parámetros

Ver `params.yaml` para el detalle y la justificación de cada valor.
Sin calibrar con Optuna todavía.

## 6. Complejidad

Por generación: generar `tam_poblacion` hijos cuesta `tam_poblacion`
decodificaciones completas, cada una O(total_ops · log total_ops) en el
peor caso (por la búsqueda de hueco en cada máquina). El costo de
selección por torneo es O(k_torneo) por selección; los operadores de
cruce/mutación son O(total_ops) cada uno.

## 7. Fortalezas y debilidades esperadas

**Fortalezas esperadas**: al mantener diversidad en una población, se
espera mejor exploración de regiones distintas del espacio de soluciones
que un método de trayectoria, y mayor robustez frente a óptimos locales
gracias a los inmigrantes.

**Debilidades esperadas**: el costo de evaluar una población completa en
cada generación es alto comparado con un método de vecino único; en
instancias grandes, con un límite de generaciones fijo, puede alcanzar
muchas menos "iteraciones lógicas" que un método de trayectoria con tiempo
equivalente.

## 8. Ejemplo reproducible

```bash
cd Poblacion/AG/AG_IA/revision
python sanity_check.py ../Entrada/instances/mk01.fjs --semilla 1000
```

(`../Entrada/instances/` trae su propia copia de las 297 instancias del
benchmark FJSPLib — no depende de tener el resto del repositorio clonado.)

Salida esperada: un makespan finito y válido (BKS de mk01 = 40), y una
carpeta nueva en `../Salida/dd_mm_aaaa_hh_mm_ss/` con los 7 archivos del
contrato (`forma1.txt`, `parametros.txt`, `salida1.txt`,
`representacion1.txt`, `tiempos.txt`, `hardware.txt`, `g1.csv`/`g1.png`).

**Nota:** este código no se corrió como parte de esta entrega — la
verificación fue solo de sintaxis/imports (ver el mensaje que acompaña
esta entrega). Las corridas "oficiales" para la comparación con
`AG_Alumno` se hacen localmente, en el mismo hardware, para que el delta
de tiempo sea válido.
