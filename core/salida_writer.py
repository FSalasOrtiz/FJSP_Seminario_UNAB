"""core.salida_writer
====================
Escribe el contrato de salida `Salida/dd_mm_aaaa_hh_mm_ss/` (acordado en
`experimento_humano_ia/README.md`, extendido acá a las metaheurísticas del
núcleo) a partir de un `core.metaheuristic.Resultado`.

Se centraliza acá, en `core/`, para que las cuatro metaheurísticas
(`Trayectoria/sa`, `Trayectoria/tabu`, `Poblacion/AG`, `Poblacion/ACO`) — y
las que vengan después — no reimplementen cada una su propia escritura de
archivos. Es infraestructura compartida, no parte del algoritmo: no viola
D2/D5 (esas reglas son sobre parsear/decodificar/evaluar/validar, no sobre
cómo se vuelca un resultado ya calculado a disco).

Nota importante, para que quede registrada: `Resultado.traza` está indexada
por EVALUACIONES consumidas (D8), no por tiempo de reloj — es la unidad
válida de presupuesto en este repositorio. El acta de reunión (07-09-2026,
observación 3 sobre el SA) pide comparar "makespan con el tiempo" en los
gráficos; tal como está hoy el núcleo, el gráfico de convergencia que se
genera acá usa evaluaciones en el eje X, no segundos. Registrar el tiempo
de reloj en cada punto de la traza (no solo el total) requeriría modificar
`core.objective.evaluar` o el bucle de cada `algorithm.py` para tomar el
tiempo en cada evaluación — un cambio no trivial al núcleo, pendiente de
decidir con el equipo, no algo que este escritor deba resolver por su
cuenta. Mientras tanto, `tiempos.txt` sí registra el tiempo total de la
corrida completa (inicio a fin), aunque no un desglose punto por punto.
"""

import csv
import os
import platform
from datetime import datetime


def detectar_hardware():
    return {
        "sistema": f"{platform.system()} {platform.release()}",
        "procesador": platform.processor() or "no disponible",
        "nucleos_logicos": os.cpu_count() or "no disponible",
        "python": platform.python_version(),
        "passmark_cpu": "PENDIENTE - medir con https://www.cpubenchmark.net/ y completar a mano",
        "id_equipo": "PENDIENTE - asignar un identificador fijo por equipo fisico usado",
    }


def escribir_salida(directorio_base, nombre_mh, instancia, ruta_instancia,
                     resultado, parametros, semilla, tiempo_total_s,
                     evaluaciones_usadas, evaluaciones_maximas):
    """Escribe Salida/dd_mm_aaaa_hh_mm_ss/ con los 7 archivos del contrato.

    Parámetros
    ----------
    directorio_base : carpeta donde crear la subcarpeta con marca de tiempo
                       (normalmente "Salida" dentro de la carpeta de la
                       metaheurística, p.ej. Trayectoria/sa/Salida).
    nombre_mh        : nombre corto de la metaheurística (p.ej. "sa").
    instancia        : objeto core.instance.Instancia ya parseado.
    ruta_instancia   : ruta al archivo .fjs original, para copiarlo a forma1.txt.
    resultado        : core.metaheuristic.Resultado devuelto por resolver().
    parametros       : dict de hiperparámetros usados en esta corrida.
    semilla          : semilla usada.
    tiempo_total_s   : tiempo de reloj de la corrida completa (medido por
                        quien llama, envolviendo resolver() con time.time()).
    evaluaciones_usadas, evaluaciones_maximas : de core.evaluation_budget.Presupuesto.

    Devuelve la ruta de la carpeta creada.
    """
    marca_tiempo = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    directorio = os.path.join(directorio_base, marca_tiempo)
    os.makedirs(directorio, exist_ok=True)

    # forma1.txt
    with open(ruta_instancia, "r") as f_in:
        contenido = f_in.read()
    with open(os.path.join(directorio, "forma1.txt"), "w") as f_out:
        f_out.write(contenido)

    # parametros.txt
    with open(os.path.join(directorio, "parametros.txt"), "w") as f:
        f.write(f"metaheuristica: {nombre_mh}\n")
        f.write(f"semilla: {semilla}\n")
        for clave, valor in parametros.items():
            f.write(f"{clave}: {valor}\n")

    # salida1.txt -- makespan + horario. Se recalcula el horario acá mismo
    # (una sola evaluación extra, fuera del presupuesto de búsqueda, igual
    # que hace tests/test_*.py al validar el resultado final) para no
    # depender de que Resultado cargue el horario completo.
    from core.objective import evaluar
    makespan_confirmado, horario = evaluar(instancia, resultado.ms, resultado.os)
    with open(os.path.join(directorio, "salida1.txt"), "w") as f:
        f.write(f"instancia: {instancia.nombre}\n")
        f.write(f"makespan: {makespan_confirmado}\n")
        f.write("# horario: trabajo operacion maquina inicio fin\n")
        for (j, o, m, inicio, fin) in sorted(horario, key=lambda x: x[3]):
            f.write(f"{j} {o} {m} {inicio} {fin}\n")

    # representacion1.txt -- codificación interna (OS/MS)
    with open(os.path.join(directorio, "representacion1.txt"), "w") as f:
        f.write("OS: " + " ".join(str(x) for x in resultado.os) + "\n")
        f.write("MS: " + " ".join(str(x) for x in resultado.ms) + "\n")

    # tiempos.txt -- separado de salida1.txt (acta, punto 6)
    with open(os.path.join(directorio, "tiempos.txt"), "w") as f:
        f.write(f"tiempo_total_s: {tiempo_total_s:.4f}\n")
        f.write(f"evaluaciones_usadas: {evaluaciones_usadas}\n")
        f.write(f"evaluaciones_maximas: {evaluaciones_maximas}\n")

    # hardware.txt
    with open(os.path.join(directorio, "hardware.txt"), "w") as f:
        for clave, valor in detectar_hardware().items():
            f.write(f"{clave}: {valor}\n")

    # g1.csv + g1.png -- convergencia. Eje X en EVALUACIONES, no en tiempo
    # (ver nota del módulo, arriba).
    ruta_csv = os.path.join(directorio, "g1.csv")
    with open(ruta_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["evaluaciones", "mejor_makespan"])
        for ev, mk in resultado.traza:
            w.writerow([ev, mk])

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        evaluaciones = [ev for ev, _ in resultado.traza]
        makespans = [mk for _, mk in resultado.traza]
        plt.figure(figsize=(6, 4))
        plt.step(evaluaciones, makespans, where="post")
        plt.xlabel("Evaluaciones consumidas")
        plt.ylabel("Mejor makespan")
        plt.title(f"Convergencia — {nombre_mh} — {instancia.nombre}")
        plt.tight_layout()
        plt.savefig(os.path.join(directorio, "g1.png"), dpi=120)
        plt.close()
    except ImportError:
        pass

    return directorio
