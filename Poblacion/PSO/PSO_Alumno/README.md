# PSO_IA — Particle Swarm Optimization, implementación con apoyo de Claude

Parte del experimento "implementación humana vs. asistida por IA" (acta de
reunión, 07-09-2026). Su contraparte es `../PSO_Alumno/`, construida sin
apoyo de IA. Mismo formato de entrada, mismo contrato de salida que
`AG_IA/` y `ACO_IA/`.

**Independiente a propósito:** no importa nada de `core/` ni comparte
código con `PSO_Alumno/`. Ver el docstring de `algorithm.py`.

## 1. Idea central

PSO imita el movimiento de una bandada: cada "partícula" es una solución
candidata que se mueve por el espacio de búsqueda con una velocidad propia,
atraída hacia dos puntos — el mejor lugar que ELLA MISMA ha visitado
(`pbest`) y el mejor lugar que CUALQUIERA del enjambre ha visitado
(`gbest`). Con el tiempo, todas las partículas convergen hacia regiones
prometedoras del espacio.

## 2. Origen y referencia

Kennedy, J., & Eberhart, R. (1995). Particle swarm optimization.
*Proceedings of ICNN'95 — International Conference on Neural Networks*,
4, 1942-1948. Peso de inercia decreciente: Shi, Y., & Eberhart, R. (1998).
A modified particle swarm optimizer. *IEEE International Conference on
Evolutionary Computation*. Adaptación a FJSP mediante codificación por
claves aleatorias: en la línea de Xia, W., & Wu, Z. (2005). An effective
hybrid optimization approach for multi-objective flexible job-shop
scheduling problems. *Computers & Industrial Engineering*, 48(2), 409-425.

## 3. Pseudocódigo

```
inicializar n_particulas con posición (pos_os, pos_ms) al azar
para cada partícula: pbest <- posición inicial; evaluar
gbest <- la mejor entre todos los pbest
mientras no se cumpla el criterio de parada:
    w <- interpola linealmente entre w_max y w_min según la iteración actual
    para cada partícula:
        actualizar velocidad hacia pbest propio y gbest del enjambre (peso w)
        actualizar posición; recortar a los límites válidos
        decodificar posición -> (OS, MS); evaluar
        si mejora su propio pbest: actualizar pbest
        si mejora el mejor global: actualizar gbest
devolver gbest
```

## 4. Mapeo al FJSP — la parte que distingue a PSO de AG/ACO

PSO es, en su forma original, un optimizador para espacios **continuos**;
el FJSP es combinatorio. El puente entre ambos es la codificación por
**claves aleatorias**:

- **Posición de una partícula**: dos vectores continuos de longitud
  `total_ops` cada uno — `pos_os` (una clave por operación, en `[0, 1]`) y
  `pos_ms` (una clave por operación, en `[0, n_alternativas(g) - 1]`).
- **Traducción `pos_os` -> `OS`** (regla de "menor valor de posición",
  aplicada por trabajo): en cada paso de la decodificación, entre todas
  las operaciones "listas" (la siguiente operación pendiente de cada
  trabajo), se elige para ir a continuación la que tenga el `pos_os[g]`
  más chico. Esto SIEMPRE produce una secuencia válida —nunca puede violar
  la precedencia de un trabajo—, sin importar qué valores traiga la
  partícula: es la misma garantía estructural que usa la construcción de
  `ACO_IA`, aplicada acá con un criterio de orden distinto (menor clave)
  en vez de ruleta ponderada.
- **Traducción `pos_ms` -> `MS`**: redondeo al entero más cercano,
  recortado a `[0, n_alternativas(g) - 1]`.
- **Velocidad**: se actualiza igual que el PSO clásico, con recorte
  (clamping) tanto de velocidad como de posición a los límites válidos de
  cada componente, para que la partícula no "se escape" del espacio de
  búsqueda representable.

## 5. Parámetros

Ver `params.yaml`. Sin calibrar con Optuna todavía. Nota: PSO_IA no tiene
parámetros de mutación/cruce (a diferencia de AG_IA) — toda su dinámica de
exploración vive en `w`, `c1`, `c2`.

## 6. Complejidad

Por iteración: O(n_particulas · total_ops) para actualizar velocidad y
posición de todas las partículas, más `n_particulas` decodificaciones
completas (una por partícula, para evaluarla tras moverse).

## 7. Fortalezas y debilidades esperadas

**Fortalezas esperadas**: la dinámica de velocidad suele converger rápido
en las primeras iteraciones (buen desempeño con presupuestos chicos); no
requiere operadores de cruce/mutación diseñados a mano para el problema,
lo que lo hace más simple de adaptar a una representación nueva que un AG.

**Debilidades esperadas**: la codificación por claves aleatorias introduce
una capa de indirección entre "dónde está la partícula" y "qué tan buena
es la solución" que no existe en AG/ACO — dos posiciones continuas
cercanas pueden decodificar a soluciones muy distintas si cambian cuál
operación queda "primera" en el orden. Es más propenso a convergencia
prematura que AG (sin un mecanismo de inmigrantes o diversificación
explícito en esta versión).

## 8. Ejemplo reproducible

```bash
cd Poblacion/PSO/PSO_IA/revision
python sanity_check.py ../Entrada/instances/mk01.fjs --semilla 1000
```

Salida esperada: un makespan finito y válido (BKS de mk01 = 40), y una
carpeta nueva en `../Salida/dd_mm_aaaa_hh_mm_ss/` con los 7 archivos del
contrato.

**Nota:** este código no se corrió como parte de esta entrega — solo se
verificó sintaxis e imports. Las corridas "oficiales" para la comparación
con `PSO_Alumno` se hacen localmente, en el mismo hardware.
