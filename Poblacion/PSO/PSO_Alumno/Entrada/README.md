# Entrada/

Instancias disponibles para probar PSO_IA. `instances/` contiene las 297
instancias del benchmark FJSPLib (Brandimarte, Hurink, Dauzère-Pérès — ver
`PROCEDENCIA.md`). `bks.json` trae las cotas de referencia de cada una,
para comparar a mano el makespan obtenido — `algorithm.py` no las usa
internamente.

Mismo catálogo que `data/instances/` en la raíz del repositorio, duplicado
acá a propósito para que `PSO_IA/` se pueda usar de forma completamente
autónoma, igual que `AG_IA/` y `ACO_IA/`.

Cada corrida real, además, deja su propia copia de la instancia usada en
`../Salida/dd_mm_aaaa_hh_mm_ss/forma1.txt`.
