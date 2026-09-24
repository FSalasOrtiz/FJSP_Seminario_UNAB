# Entrada/

Instancias disponibles para probar AG_IA, y trazabilidad de cuáles se han
corrido. `instances/` contiene las 297 instancias del benchmark FJSPLib
(Brandimarte, Hurink, Dauzère-Pérès — ver `PROCEDENCIA.md` para la fuente
exacta y la licencia CC-BY-SA-4.0 del benchmark). `bks.json` trae las cotas
de referencia (lower/upper bound) de cada una, para comparar a mano el
makespan obtenido — `algorithm.py` no las lee ni las usa internamente, son
solo para tu propia referencia al revisar resultados.

Estas son las MISMAS instancias que `data/instances/` en la raíz del
repositorio (mismo contenido; estas venían con saltos de línea de Windows,
pero el parser las lee igual). Se duplican acá a propósito, para que
`AG_IA/` se pueda usar de forma completamente autónoma — sin necesitar el
resto del repositorio clonado — igual que ya es autónomo de `core/`.

Cada corrida real, además, deja su propia copia de la instancia usada en
`../Salida/dd_mm_aaaa_hh_mm_ss/forma1.txt` — esa es la copia con validez
para trazabilidad de una corrida puntual; esta carpeta es solo el catálogo
disponible para elegir de dónde correr.

## Ejemplos de instancias por tamaño, para partir

| Instancia | Tamaño | BKS (upper bound) |
|---|---|---|
| `ft06_edata.fjs` | 6×6, chica | ver bks.json |
| `mk01.fjs` | 10×6 | 40 |
| `mk07.fjs` | 20×5 | ver bks.json |
| `la40_vdata.fjs` | 15×15 | ver bks.json |
