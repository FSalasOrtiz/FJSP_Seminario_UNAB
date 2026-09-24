# ACO_IA — MAX-MIN Ant System, implementación con apoyo de Claude

Parte del experimento "implementación humana vs. asistida por IA" (acta de
reunión, 07-09-2026). Su contraparte es `../ACO_Alumno/`, construida sin
apoyo de IA. Mismo formato de entrada, mismo contrato de salida que
`AG_IA/`, para que `herramientas_comparacion/` pueda comparar sin conocer
el código interno de ninguna.

**Independiente a propósito:** no importa nada de `core/`, ni de
`Poblacion/ACO/algorithm.py` (el ACO del experimento principal), ni
comparte código con `ACO_Alumno/`. Ver el docstring de `algorithm.py`.

## 1. Idea central

ACO imita cómo una colonia de hormigas encuentra caminos cortos: cada
hormiga construye una solución completa paso a paso, guiada por la
**feromona** (experiencia acumulada de hormigas anteriores) y una
**heurística local** (qué tan atractiva es una candidata por sí sola,
independiente de la experiencia). Tras cada iteración, la feromona se
evapora un poco y se refuerza en las combinaciones usadas por la mejor
solución encontrada.

## 2. Origen y referencia

Dorigo, M., & Stützle, T. (2004). *Ant Colony Optimization*. MIT Press.
Variante MAX-MIN Ant System: Stützle, T., & Hoos, H. H. (2000). MAX–MIN Ant
System. *Future Generation Computer Systems*, 16(8), 889-914.

## 3. Pseudocódigo

```
tau <- 1.0 en cada (operación, máquina) elegible
mejor <- ninguna
mientras no se cumpla el criterio de parada:
    para cada una de n_ants hormigas:
        construir una solución completa (OS, MS) eligiendo, paso a paso,
        la siguiente operación pendiente y su máquina con probabilidad
        proporcional a tau^alpha * eta^beta
        evaluar la solución completa
    si la mejor hormiga de esta iteración supera al mejor histórico:
        mejor <- esa hormiga
        aplicar búsqueda local sobre mejor (opcional)
    evaporar tau; reforzar tau según mejor; recortar a [tau_min, tau_max]
devolver mejor
```

## 4. Mapeo al FJSP

- **Construcción**: en cada paso, cada trabajo con operaciones pendientes
  ofrece su siguiente operación como candidata, una vez por cada máquina
  elegible. Se elige por ruleta ponderada por `tau[g][m]^alpha * eta^beta`
  (o la de mayor peso, con probabilidad `q0`). El orden en que se eligen
  las operaciones define `OS`; la máquina elegida define `MS[g]`.
- **Heurística (`eta`)**: `1 / duración` de la alternativa candidata —
  información puramente local, sin necesidad de simular el estado de las
  máquinas (heurística SPT, estándar en ACO para scheduling).
- **Feromona (`tau`)**: una entrada por cada par (operación, máquina)
  elegible, inicializada en 1.0, recalculada desde cero en cada llamada a
  `resolver`.
- **Actualización MMAS**: evaporación `tau *= (1 - rho)`, refuerzo
  `+= 1/makespan` sobre las celdas usadas por la mejor solución, recorte a
  `[tau_min, tau_max]` con `tau_max = 1/(rho · mejor_makespan)` y
  `tau_min = tau_max / (2 · total_ops)`.
- **Búsqueda local** (opcional): cuando una hormiga mejora el óptimo
  global, se recorre cada operación probando cada alternativa de máquina
  distinta a la actual (secuencia `OS` fija), aceptando la primera que
  mejore, en pasadas repetidas hasta que una pasada completa no mejore.

## 5. Parámetros

Ver `params.yaml`. Sin calibrar con Optuna todavía.

## 6. Complejidad

Construir una hormiga es O(total_ops · flexibilidad_media). Con `n_ants`
hormigas por iteración, el costo dominante por iteración es `n_ants`
decodificaciones completas, más el costo de la búsqueda local cuando
aplica (hasta `total_ops · (flexibilidad_media - 1)` decodificaciones en
el peor caso de una pasada sin mejora).

## 7. Fortalezas y debilidades esperadas

**Fortalezas esperadas**: construir soluciones completas guiadas por
feromona en vez de perturbar una solución al azar debería converger hacia
buenas combinaciones operación-máquina consistentes más rápido que un
método de trayectoria genérico, especialmente combinado con la búsqueda
local.

**Debilidades esperadas**: sensible a la calibración de `alpha`/`beta`; mal
calibrado, puede converger prematuramente a una única combinación
reforzada por la feromona. La búsqueda local, aunque mejora la calidad,
puede ser costosa en instancias con muchas operaciones/alternativas.

## 8. Ejemplo reproducible

```bash
cd Poblacion/ACO/ACO_IA/revision
python sanity_check.py ../Entrada/instances/mk01.fjs --semilla 1000
```

Salida esperada: un makespan finito y válido (BKS de mk01 = 40), y una
carpeta nueva en `../Salida/dd_mm_aaaa_hh_mm_ss/` con los 7 archivos del
contrato.

**Nota:** este código no se corrió como parte de esta entrega — solo se
verificó sintaxis e imports. Las corridas "oficiales" para la comparación
con `ACO_Alumno` se hacen localmente, en el mismo hardware.
