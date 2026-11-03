"""
Mesa de ayuda de TI: asignación de turnos y dimensionamiento.
Proyecto final de Investigación de Operaciones.

Uso:
    python main.py          -> menú interactivo
    python main.py --todo   -> ejecuta todo de principio a fin (sin preguntas)
"""
import argparse
from dataclasses import replace

import pandas as pd

from data.generar_datos import generar_datos
from src import config
from src.datos import Instancia, cargar_instancia, subinstancia
from src.escenarios import ESCENARIOS, barrido_meta_espera, correr_escenarios, indicadores
from src.excel_solver import crear_libro_solver
from src.modelo import Resultado, resolver, verificar_solucion
from src.reportes import (exportar_instancia, generar_graficos, guardar_escenarios,
                          guardar_simulacion, guardar_tablas)
from src.simulacion import (N_REPLICAS, comparar_por_cola, resumir, simular_plan,
                            validar_contra_mmc)

# Instancia reducida que se verifica en Excel Solver (máximo 200 variables)
REDUCIDA = {"dias": ["Sab"], "tipos": ["Redes", "Software"], "n_tecnicos": 9}
LIBRO_SOLVER = config.RAIZ / "verificacion_solver.xlsx"
# Planes que se prueban en la simulación: el base, la mejor alternativa y la regla sin colas
PLANES_SIMULADOS = ["Base", "E3 Hasta 6 turnos", "E7 Regla 85% (sin colas)"]
# Cola con la que se valida el simulador frente a M/M/c (el ejemplo del informe, con r = 3)
COLA_VALIDACION = ("Lun-Mañana", "Software", 3)


def mostrar_resultado(inst: Instancia, res: Resultado) -> None:
    """Imprime el resumen de una solución y el chequeo de restricciones."""
    print(f"\n=== Instancia '{res.instancia}' ===")
    print(f"Técnicos: {len(inst.tecnicos)} | Turnos: {len(inst.turnos)} | Tipos: {len(inst.tipos)}")
    print(f"Variables: {res.n_variables} | Restricciones: {res.n_restricciones}")
    print(f"Estado del solver: {res.estado} (tiempo {res.tiempo_s:.2f} s)")
    print(f"Costo de personal:  {res.costo_personal:>14,.0f} COP")
    print(f"Penalización déficit:{res.costo_deficit:>14,.0f} COP")
    print(f"Función objetivo:   {res.costo_total:>14,.0f} COP")
    ind = indicadores(inst, res)
    print(f"Técnico-turnos requeridos (M/M/c, Wq <= {inst.meta_espera_min:g} min): "
          f"{ind['requeridos']} | asignados: {ind['asignados']} | déficit: {ind['deficit']} "
          f"(~{ind['tecnicos_faltantes']} técnicos)")
    print(f"Colas que cumplen la meta: {ind['colas_cumplen_meta_pct']} % | "
          f"espera media: {ind['wq_promedio_min']} min | colas inestables: {ind['colas_inestables']}")
    errores = verificar_solucion(inst, res)
    if errores:
        print(f"ATENCIÓN: {len(errores)} restricciones violadas:")
        for e in errores[:10]:
            print("  -", e)
    else:
        print("Todas las restricciones verificadas.")


def asegurar_datos() -> None:
    """Genera los datos si todavía no existen."""
    if not (config.DIR_DATOS / "tecnicos.csv").exists():
        opcion_generar()


def opcion_generar() -> None:
    generar_datos()
    print(f"Datos generados en {config.DIR_DATOS} (semilla {config.SEMILLA}).")


def opcion_modelo_base() -> None:
    asegurar_datos()
    inst = cargar_instancia()
    res = resolver(inst)
    mostrar_resultado(inst, res)
    rutas = guardar_tablas(res) + generar_graficos(inst, res)
    print("Archivos generados:")
    for r in rutas:
        print("  -", r.relative_to(config.RAIZ))


def opcion_reducida() -> None:
    asegurar_datos()
    inst = subinstancia(cargar_instancia(), **REDUCIDA)
    res = resolver(inst)
    mostrar_resultado(inst, res)
    if res.n_variables > 200:
        print("ATENCIÓN: la instancia reducida supera el límite de 200 variables de Solver.")
    rutas = exportar_instancia(inst) + guardar_tablas(res, prefijo="reducida_")
    print("Archivos para la verificación en Excel Solver:")
    for r in rutas:
        print("  -", r.relative_to(config.RAIZ))
    # El libro guarda la configuración de Solver: no se sobrescribe si ya existe
    if LIBRO_SOLVER.exists():
        print(f"  - {LIBRO_SOLVER.name} ya existe (bórralo para regenerarlo).")
    else:
        crear_libro_solver(inst, res, LIBRO_SOLVER)
        print(f"  - {LIBRO_SOLVER.name} creado; configura Solver con la hoja 'Instrucciones'.")


def opcion_escenarios() -> None:
    asegurar_datos()
    base = cargar_instancia()
    tabla, _ = correr_escenarios(base)
    barrido = barrido_meta_espera(base)
    formato = {"costo_personal_cop": "{:,.0f}".format}
    print("\n=== Escenarios ===")
    columnas = ["escenario", "estado", "requeridos", "asignados", "deficit",
                "colas_cumplen_meta_pct", "wq_promedio_min", "costo_personal_cop",
                "var_costo_vs_base_pct", "restricciones_ok"]
    print(tabla[columnas].to_string(index=False, formatters=formato))
    print("\n=== Barrido de la meta de espera ===")
    print(barrido.to_string(index=False, formatters=formato))
    print("Archivos generados:")
    for r in guardar_escenarios(tabla, barrido, base.meta_espera_min):
        print("  -", r.relative_to(config.RAIZ))


def opcion_simulacion() -> None:
    asegurar_datos()
    base = cargar_instancia()
    escenarios = {e.nombre: e for e in ESCENARIOS}
    resumen, tickets_por_plan, por_cola = [], {}, None
    for nombre in PLANES_SIMULADOS:
        inst = replace(escenarios[nombre].transformar(base), nombre=nombre)
        res = resolver(inst)
        tickets = simular_plan(inst, res)
        tickets_por_plan[nombre] = tickets
        resumen.append(resumir(tickets, base.meta_espera_min, nombre))
        if nombre == "Base":
            por_cola = comparar_por_cola(tickets, res)
    resumen = pd.DataFrame(resumen)
    print(f"\n=== Simulación SimPy ({N_REPLICAS} réplicas de la semana) ===")
    print(resumen.to_string(index=False))
    validacion = pd.DataFrame([validar_contra_mmc(base, *COLA_VALIDACION)])
    print("\n=== Validación del simulador: técnicos toda la semana frente a M/M/c ===")
    print(validacion.to_string(index=False))
    print("Archivos generados:")
    for r in guardar_simulacion(resumen, por_cola, validacion, tickets_por_plan,
                                base.meta_espera_min):
        print("  -", r.relative_to(config.RAIZ))


def ejecutar_todo() -> None:
    opcion_generar()
    opcion_modelo_base()
    opcion_reducida()
    opcion_escenarios()
    opcion_simulacion()


OPCIONES = {
    "1": ("Generar datos simulados", opcion_generar),
    "2": ("Resolver modelo base (semana completa)", opcion_modelo_base),
    "3": ("Resolver instancia reducida (para Excel Solver)", opcion_reducida),
    "4": ("Analizar escenarios", opcion_escenarios),
    "5": ("Simular la semana con SimPy", opcion_simulacion),
    "6": ("Ejecutar todo", ejecutar_todo),
}


def menu() -> None:
    while True:
        print("\n--- Mesa de ayuda de TI: turnos y dimensionamiento ---")
        for clave, (texto, _) in OPCIONES.items():
            print(f"{clave}) {texto}")
        print("0) Salir")
        eleccion = input("Opción: ").strip()
        if eleccion == "0":
            break
        if eleccion in OPCIONES:
            OPCIONES[eleccion][1]()
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--todo", action="store_true",
                        help="ejecuta todo de principio a fin sin menú")
    if parser.parse_args().todo:
        ejecutar_todo()
    else:
        menu()
