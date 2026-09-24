# Simulated Annealing (SA)

Metaheurística de **referencia** de la Fase 2. Ver METODOLOGIA.md, sección
8.1: antes de migrar las siete metaheurísticas existentes, se implementa un
método real contra el núcleo para descubrir qué falta en el contrato de
`core.metaheuristic.Metaheuristica` mientras corregirlo cuesta un día y no
tres semanas.

## 1. Idea central

SA explora el espacio de soluciones moviéndose entre vecinos, aceptando
siempre las mejoras y aceptando empeoramientos con una probabilidad que
depende de una "temperatura" que decrece con el tiempo. Al principio
(temperatura alta) casi cualquier movimiento se acepta, lo que permite
escapar de óptimos locales; al final (temperatura baja) el método se
comporta como una búsqueda local estricta. Es una analogía con el proceso
físico de recocido de metales, de donde toma el nombre.

## 2. Origen y referencia

Kirkpatrick, S., Gelatt, C. D., & Vecchi, M. P. (1983). Optimization by
simulated annealing. *Science*, 220(4598), 671-680.

## 3. Pseudocódigo

```
s <- solución inicial
mejor <- s
mientras presupuesto no agotado:
    T <- temperatura(fracción de presupuesto consumida)
    s' <- vecino(s)
    delta <- costo(s') - costo(s)
    si delta <= 0:
        s <- s'
    si no:
        s <- s' con probabilidad exp(-delta / T)
    si costo(s) < costo(mejor):
        mejor <- s
devolver mejor
```

## 4. Mapeo al FJSP

- **Solución**: el par canónico `(MS, OS)` (D4). No se mantiene ninguna
  representación paralela.
- **Vecino**: se genera con uno de dos movimientos elementales, elegidos al
  azar con `rng` (nunca con `random` global, D9):
  - **Movimiento OS**: swap de dos posiciones del vector `OS`. Siempre
    produce un `OS` válido porque no cambia la multiplicidad de ningún
    trabajo.
  - **Movimiento MS**: para una operación elegida al azar, cambia la
    alternativa de máquina asignada (si tiene más de una disponible).
- **Temperatura**: se ata a la *fracción de presupuesto consumida*
  (`presupuesto.usadas / presupuesto.maximo`), no al tiempo de reloj ni al
  número de iteraciones, porque D8 exige que el presupuesto -y todo lo que
  depende de "cuánto llevamos"- se mida en evaluaciones.

## 5. Parámetros

| Parámetro | Valor | Rango explorado | Justificación |
|---|---|---|---|
| `temperatura_inicial` | 100.0 | [50, 500] | Calibración preliminar sobre Mk01-Mk03 para ~80-90% de aceptación inicial; ver `params.yaml` |
| `temperatura_minima` | 0.001 | [0.0001, 0.01] | Umbral convencional de temperatura ≈ 0; no sensible en este rango |
| `prob_movimiento_ms` | 0.3 | [0.1, 0.5] | Pondera hacia movimientos OS porque el movimiento MS puede ser un no-op en instancias sin flexibilidad (sdata/edata) |

Calibración formal con Optuna pendiente para la Fase 4 (ver Parte 7.2 del
documento de contexto), sobre un conjunto de instancias distinto al de
evaluación.

## 6. Complejidad

Por iteración: generar un vecino es O(1) (swap o cambio de una entrada);
evaluarlo cuesta una decodificación completa, O(total_ops · log(total_ops))
en el peor caso por la búsqueda de hueco en cada máquina (inserción en una
lista ordenada de intervalos). El costo dominante del método es el número
de evaluaciones permitidas por el presupuesto, no el trabajo por iteración.

## 7. Fortalezas y debilidades esperadas

*(Registrado ANTES de correr el experimento, para no racionalizar los
resultados después - METODOLOGIA.md, plantilla del punto 7.)*

**Fortalezas esperadas**: al ser un método de trayectoria simple, con un
único vecino evaluado por iteración, debería aprovechar bien un presupuesto
medido en evaluaciones (a diferencia de métodos poblacionales, que gastan
varias evaluaciones por "iteración lógica"). Se espera que sea competitivo
en instancias pequeñas y medianas.

**Debilidades esperadas**: la vecindad es genérica (swap + cambio de
máquina) y no usa ningún conocimiento estructural del FJSP (por ejemplo,
vecindades basadas en el camino crítico). En instancias grandes o con
mucha flexibilidad, es esperable que quede por debajo de métodos con
vecindades más informadas o de métodos poblacionales bien ajustados.

## 8. Ejemplo reproducible

```bash
python -m experiments.run --mh sa --instancia mk01 --semilla 1000
```

Salida esperada: un makespan finito y válido (BKS de mk01 = 40, instancia
cerrada); no se espera igualar ni superar el BKS con parámetros sin
calibrar. Cualquier resultado por debajo de 40 se marca automáticamente
como sospechoso (D10) y debe verificarse a mano antes de creerlo.
