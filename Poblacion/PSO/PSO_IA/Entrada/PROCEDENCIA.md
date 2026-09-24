# Procedencia de instancias y cotas

## Fuente

Todas las instancias y valores de referencia provienen de **FJSPLib**:
https://scheduleopt.github.io/benchmarks/fjsplib/

- Fecha de descarga: 2026-08-23
- Repositorio de origen: https://github.com/ScheduleOpt/benchmarks
- Carpeta: `flexible-jobshop`
- Hash SHA-256 de `solutions/bks.json` en origen: `PEGA_AQUI_EL_HASH`
- Instancias importadas: 297 (Brandimarte 15, Hurink 264, Dauzère-Pérès 18)
- Con cota conocida: 297 — 270 cerradas (óptimo probado), 27 abiertas

## Licencia del benchmark

La compilación FJSPLib se distribuye bajo **CC-BY-SA-4.0**, mantenida por
OptalCP. Al redistribuir estas instancias corresponde atribución y compartir
bajo la misma licencia. La licencia MIT de este repositorio cubre únicamente
el código propio.

## Verificación cruzada

Las 31 instancias del experimento previo fueron verificadas contra una segunda
fuente independiente (`HHS/resultados.csv` del repositorio original, que usaba
cotas correctas): **coincidencia exacta en LB y UB en las 31**, cero
discrepancias. Esto confirma que la columna `UB` de la Tabla III del paper
previo era errónea y no una fuente alternativa legítima.
## Regla de congelamiento (D1)

Los BKS se actualizan con el tiempo. Congelarlos en el repositorio hace el
experimento reproducible; citarlos sin congelarlos lo hace irreproducible seis
meses después.

**Prohibido escribir una cota a mano en cualquier archivo de código o de
resultados.** Toda cota se lee de `data/bks.json`.

Nota sobre los datos: cuatro instancias (orb7_sdata, orb7_edata, orb7_rdata,
orb7_vdata) contienen operaciones con tiempo de proceso 0, heredadas de la
instancia ORB7 del job shop clásico. Es un dato válido: la operación ocupa la
máquina durante un intervalo de duración nula. El decodificador y el validador
deben tratarlas con comparaciones no estrictas.

## Advertencia

En el experimento previo, las cotas de la Tabla III no correspondían a la
fuente citada: Brandimarte y Dauzère usaban cotas infladas, y Hurink edata
usaba los valores de rdata/vdata. Esto invalidó dos de las tres conclusiones
del análisis. Ver `docs/auditoria_experimento_previo.md`, sección 1.

## Autoría de los benchmarks

Las instancias pertenecen a sus autores originales:

- **Brandimarte (Mk01–Mk15)** — P. Brandimarte, "Routing and scheduling in a
  flexible job shop by tabu search", *Annals of Operations Research*, 41, 1993.
- **Hurink edata/rdata/vdata** — E. Hurink, B. Jurisch, M. Thole, "Tabu search
  for the job-shop scheduling problem with multi-purpose machines",
  *OR Spektrum*, 15, 1994.
- **Dauzère-Pérès y Paulli** — S. Dauzère-Pérès, J. Paulli, "An integrated
  approach for modeling and solving the general multiprocessor job-shop
  scheduling problem using tabu search", *Annals of Operations Research*, 70, 1997.
- **Barnes y Chambers** — J. W. Barnes, J. B. Chambers, "Flexible job shop
  scheduling by tabu search", Technical Report ORP96-09, Univ. of Texas, 1996.

La licencia MIT del repositorio cubre el código, no estas instancias.
