# Registro de cambios

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

**Regla.** Todo cambio a `core/` debe registrarse aquí indicando si **invalida resultados
previos**. Si los invalida, se reejecuta el experimento completo y se anota el tag afectado.

---

## [Sin publicar]

### Agregado
- Andamiaje inicial del repositorio.
- `METODOLOGIA.md` v1.0, aprobado por el equipo.
- Auditoría del experimento previo en `docs/`.
- Importadas 297 instancias y sus cotas desde FJSPLib (`tools/import_fjsplib.py`).
- Verificación cruzada de las 31 cotas del experimento previo contra FJSPLib:
  coincidencia exacta en LB y UB, cero discrepancias (2026-08-23).
- `docs/formato_instancias.md`: layout del formato `.fjs`, ejemplo comentado,
  estructura de `bks.json`, convención de nombres y nota sobre orb7. Cierra
  los puntos 4 y 5 de las observaciones del profesor guía (acta 2026-08-25).
- `docs/diseno_experimento.md`: diseño de experimento formal (factores,
  niveles, variable respuesta, réplicas, análisis estadístico previsto).
  Cierra el punto 6 de las observaciones del profesor guía (acta 2026-08-25).
  Deja explícitas tres decisiones aún abiertas que bloquean la corrida final:
  D1 (selección de instancias), D2 (partición calibración/evaluación) y D3
  (calibración del presupuesto).

### Agregado
- **Estructura interna por metaheurística**: cada carpeta (`Trayectoria/sa`,
  `Trayectoria/tabu`, `Poblacion/AG`, `Poblacion/ACO`) ahora tiene
  `revision/sanity_check.py` (corrida manual rápida, para inspección
  humana — no reemplaza la batería V1-V8 de `tests/`), `Entrada/` (índice
  de qué instancias se han probado) y `Salida/` (carpeta por corrida,
  contrato `dd_mm_aaaa_hh_mm_ss/` ya usado en `experimento_humano_ia/`:
  `forma1.txt`, `parametros.txt`, `salida1.txt`, `representacion1.txt`,
  `tiempos.txt`, `hardware.txt`, `g1.csv`/`g1.png`). La escritura de ese
  contrato se centralizó en `core/salida_writer.py` para no repetirla 4
  veces. Nota registrada en el docstring de ese módulo: el gráfico de
  convergencia usa EVALUACIONES en el eje X (la unidad de D8), no tiempo de
  reloj como pide textualmente el acta 07-09-2026 — cambiar eso requiere
  tocar `core.objective.evaluar` o cada `algorithm.py` para registrar
  tiempo por evaluación, pendiente de decidir con el equipo, no resuelto
  unilateralmente acá. `Salida/*/` se agrega a `.gitignore` (son artefactos
  generados, no código fuente); `results/raw/*.csv` sigue siendo el
  agregado estadístico versionado. Probado de punta a punta en las 4
  metaheurísticas sobre mk01; batería completa en verde (56/56).
- **Reorganización estructural**: `metaheuristics/` (carpeta plana) se
  reemplaza por `Trayectoria/` y `Poblacion/`, según la clasificación de
  Talbi (2009) del libro guía del ramo — trayectoria: una solución a la
  vez (`sa`, `tabu`); población: varias a la vez (`AG`, `ACO`, y a futuro
  `PSO`, `ABC`, `Memetico`). Motivación: el equipo se dividió en subgrupos
  por paradigma para el experimento de implementación humana vs. asistida
  por IA (acta 07-09-2026), y esta estructura refleja esa división en el
  propio repositorio. `experiments/run.py` reemplaza la resolución
  automática de ruta por un registro explícito (`REGISTRO_MH`), porque
  `AG`/`ACO` van en mayúscula (nombre de la sigla) y `sa`/`tabu` no — ya no
  es derivable con un simple f-string a partir del nombre corto usado en
  `--mh`. `metaheuristics/_template/` pasa a `_template/` en la raíz, al no
  pertenecer a ningún paradigma en particular. Todos los imports de
  `tests/`, `experiments/decoder_ablation/`, y las referencias cruzadas en
  documentación se actualizaron; batería completa verificada en verde
  (56/56) después del cambio.
- `metaheuristics/aco/`: migración de ACO (MAX-MIN Ant System) desde el
  repositorio anterior (`ACO/fjsp_aco.py`), adaptada al contrato de
  `core.metaheuristic.Metaheuristica`. Este era uno de los dos métodos
  señalados en el hallazgo 2 de la auditoría: su `decode()` original usaba
  el esquema semi-activo prohibido (`libre_maquina[m] = fin`), tanto para
  evaluar hormigas como dentro de su propia heurística constructiva. Se
  eliminó el decodificador propio por completo: la evaluación real pasa por
  `core.objective.evaluar`, y la heurística constructiva se simplificó de
  "1/tiempo de término proyectado" (que exigía simular el estado de las
  máquinas) a "1/duración" de la alternativa candidata — información
  puramente local, sin necesidad de ninguna simulación. Conserva la regla
  de transición MMAS, la actualización de feromona con límites
  `tau_min`/`tau_max`, y la búsqueda local sobre la asignación de máquina
  del original. Ver `metaheuristics/aco/README.md` y el docstring de
  `algorithm.py` para el detalle completo. Pasa V1–V8
  (`tests/test_aco.py`, 9 pruebas). Corrida de humo sobre mk01 (semilla
  1000, presupuesto por defecto): makespan 41 (BKS 40, gap 2.5 %) en 14.6 s.
  En mk10 (mediana) la corrida con `local_search=true` no terminó en 120 s
  de humo: confirma empíricamente el riesgo anotado en `params.yaml` —
  cada paso de la búsqueda local consume una evaluación real, y en
  instancias con más operaciones/alternativas eso puede volverse
  desproporcionadamente caro respecto al resto del presupuesto. Queda como
  un punto concreto a resolver en la calibración de D3 (quizás
  `local_search=false` para instancias medianas/grandes, o un tope propio
  de evaluaciones para la búsqueda local dentro de cada iteración).
- `metaheuristics/ag/`: migración del Algoritmo Genético desde el
  repositorio anterior (`AG/fjsp_ag/ag_fjsp.py`), adaptada al contrato de
  `core.metaheuristic.Metaheuristica`. Conserva la codificación de dos
  vectores, cruce POX sobre `OS` + cruce uniforme sobre `MS`, mutaciones,
  selección por torneo, elitismo e inmigrantes por estancamiento del
  original; ya no trae decodificador propio y mide el presupuesto en
  evaluaciones (D8) en vez de segundos de reloj. `tam_poblacion` y
  `estancamiento_max` se recalibraron a mano (no con Optuna todavía) porque
  dependían implícitamente de un presupuesto de tiempo — ver
  `metaheuristics/ag/README.md` y el docstring de `algorithm.py`. Pasa
  V1–V8 (`tests/test_ag.py`, 8 pruebas). Corrida de humo sobre mk01
  (semilla 1000, presupuesto por defecto): makespan 41 (BKS 40, gap 2.5 %);
  sobre mk10: makespan 244 (BKS 193, gap 26.4 %) — parámetros sin calibrar
  todavía.
- `metaheuristics/tabu/`: migración de Búsqueda Tabú desde el repositorio
  anterior (`Tabú/taboo_search.py`), adaptada al contrato de
  `core.metaheuristic.Metaheuristica`. Conserva el vecindario original
  (reasignación N1 + intercambio adyacente N2 + reubicación N3 sobre el
  camino crítico, criterio de aspiración, diversificación) pero ya no trae
  decodificador propio, mide el presupuesto en evaluaciones (D8) y ata la
  tenencia tabú y la diversificación a evaluaciones consumidas en vez de a
  un contador de iteraciones. Ver `metaheuristics/tabu/README.md` y el
  docstring de `algorithm.py` para el detalle de las diferencias. Pasa
  V1–V8 (`tests/test_tabu.py`, 8 pruebas). Corrida de humo sobre mk01
  (semilla 1000, presupuesto por defecto): makespan 42 (BKS 40, gap 5 %);
  sobre mk10: makespan 248 (BKS 193, gap 28.5 %) — parámetros sin calibrar
  todavía (`metaheuristics/tabu/params.yaml`).

### Corregido
- `tests/test_validator.py::test_duracion_cero_no_se_solapa` fallaba porque
  buscaba, dentro de "orb7_vdata", dos operaciones de trabajos distintos con
  tiempo de proceso 0 en la misma máquina. Se revisó el catálogo completo
  (297 instancias) y ninguna contiene ese patrón: "orb7_vdata" solo tiene una
  operación con alternativas de duración 0, repartidas en 6 máquinas, nunca
  dos operaciones compitiendo por la misma máquina. La prueba dependía de una
  coincidencia en datos reales para verificar una propiedad puntual del
  validador. Se reemplazó por una instancia sintética mínima construida a
  propósito para el caso. No afecta a `core/` ni invalida resultados: el
  validador nunca estuvo mal, la prueba estaba mal planteada.

### Pendiente
- D1–D3: selección del subconjunto de instancias, partición
  calibración/evaluación y calibración del presupuesto (Frente D).
- Calibración de parámetros con Optuna (punto 7 del acta 2026-08-25).
