# Calibración de AG_IA con Optuna

`../params.yaml` trae valores por defecto sin calibrar (marcado
explícitamente ahí: "Sin calibrar con Optuna todavía"). Esta carpeta
cierra ese pendiente.

## Qué hace `calibrar_optuna.py`

Busca, dentro de los `rango_sugerido` de `params.yaml`, la combinación de
hiperparámetros que minimiza el gap %% promedio contra el BKS
(`upper_bound` en `../Entrada/bks.json`), usando TPE (el sampler
bayesiano por defecto de Optuna).

No corre las 297 instancias por cada intento — sería impracticable (297 ×
decenas de trials × varias semillas). En su lugar usa:

- **Un subconjunto curado de 10 instancias** (`INSTANCIAS_CALIBRACION` en
  el script) que cubre las 3 familias del benchmark (Brandimarte, Hurink,
  Dauzère-Pérès) y tamaños desde 6×6 hasta 30×15.
- **2 semillas por instancia** (1000, 2000), para que un trial no gane
  solo por suerte de semilla.
- **Un presupuesto reducido de generaciones por corrida** (60 en vez de
  las 200 de una corrida oficial) — dentro de un trial de calibración
  interesa comparar configuraciones rápido, no exprimir cada una al
  máximo.

El objetivo de cada trial es el promedio del gap %% sobre las 10
instancias × 2 semillas = 20 corridas.

## Uso

```bash
cd Poblacion/AG/AG_IA/calibracion
python calibrar_optuna.py                 # 40 trials, ~15-25 min según CPU
python calibrar_optuna.py --n-trials 100  # búsqueda más fina
```

El estudio se guarda en `calibracion.db` (sqlite): si se corta a la mitad
(Ctrl+C, se cae la sesión, etc.), correr el mismo comando de nuevo retoma
los trials ya hechos en vez de perderlos.

Al terminar escribe `mejores_parametros.json` con los mejores
hiperparámetros encontrados y metadata de cómo se calibraron (instancias,
semillas, generaciones por trial). Ese archivo es compatible directo con
`--parametros-json` de `../revision/sanity_check.py`:

```bash
cd ../revision
python sanity_check.py ../Entrada/instances/mk01.fjs \
    --parametros-json ../calibracion/mejores_parametros.json
```

(Un flag explícito en la línea de comandos de `sanity_check.py` sigue
ganándole al JSON — ver su `--help`.)

## Después de calibrar

Una vez que `mejores_parametros.json` exista con una calibración real
(no la del smoke test), conviene:

1. Actualizar `../params.yaml`: cambiar cada `valor:` por el encontrado, y
   la `justificacion:` de "sin calibrar" a algo como "calibrado con
   Optuna, N trials, gap promedio X%% sobre el subconjunto de
   calibración — ver `calibracion/mejores_parametros.json`".
2. Volver a correr las 297 instancias con los parámetros nuevos para la
   comparación final contra `AG_Alumno` (ver `../revision/sanity_check.py`
   y el runner batch usado para la corrida completa).
