"""
Mesa de ayuda de TI: asignación de turnos y dimensionamiento.
Proyecto final de Investigación de Operaciones.

Uso:
    python main.py          -> menú interactivo
    python main.py --todo   -> ejecuta todo de principio a fin (sin preguntas)
"""
import argparse

from data.generar_datos import generar_datos
from src import config
from src.datos import Instancia, cargar_instancia, subinstancia
from src.escenarios import barrido_demanda, correr_escenarios
from src.excel_solver import crear_libro_solver
from src.modelo import Resultado, resolver, verificar_solucion
from src.reportes import (exportar_instancia, generar_graficos, guardar_escenarios,
                          guardar_tablas)

# Instancia reducida que se verifica en Excel Solver (máximo 200 variables)
REDUCIDA = {"dias": ["Sab"], "tipos": ["Redes", "Software"], "n_tecnicos": 10}
LIBRO_SOLVER = config.RAIZ / "verificacion_solver.xlsx"


def mostrar_resultado(inst: Instancia, res: Resultado) -> None:
    """Imprime el resumen de una solución y el chequeo de restricciones."""
    print(f"\n=== Instancia '{res.instancia}' ===")
    print(f"Técnicos: {len(inst.tecnicos)} | Turnos: {len(inst.turnos)} | Tipos: {len(inst.tipos)}")
    print(f"Variables: {res.n_variables} | Restricciones: {res.n_restricciones}")
    print(f"Estado del solver: {res.estado} (tiempo {res.tiempo_s:.2f} s)")
    print(f"Costo de personal:  {res.costo_personal:>14,.0f} COP")
    print(f"Penalización déficit:{res.costo_deficit:>14,.0f} COP")
    print(f"Costo total:        {res.costo_total:>14,.0f} COP")
    req, asig = res.cobertura["requeridos"].sum(), res.cobertura["asignados"].sum()
    print(f"Técnico-turnos requeridos: {req} | asignados: {asig} | "
          f"déficit: {res.cobertura['deficit'].sum()}")
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
    barrido = barrido_demanda(base)
    print("\n=== Escenarios ===")
    columnas = ["escenario", "estado", "requeridos", "asignados", "deficit",
                "costo_total_cop", "var_vs_base_pct", "restricciones_ok"]
    print(tabla[columnas].to_string(index=False, formatters={"costo_total_cop": "{:,.0f}".format}))
    print("\n=== Barrido de demanda ===")
    print(barrido.to_string(index=False, formatters={"costo_personal_cop": "{:,.0f}".format}))
    print("Archivos generados:")
    for r in guardar_escenarios(tabla, barrido):
        print("  -", r.relative_to(config.RAIZ))


def ejecutar_todo() -> None:
    opcion_generar()
    opcion_modelo_base()
    opcion_reducida()
    opcion_escenarios()


OPCIONES = {
    "1": ("Generar datos simulados", opcion_generar),
    "2": ("Resolver modelo base (semana completa)", opcion_modelo_base),
    "3": ("Resolver instancia reducida (para Excel Solver)", opcion_reducida),
    "4": ("Analizar escenarios", opcion_escenarios),
    "5": ("Ejecutar todo", ejecutar_todo),
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
