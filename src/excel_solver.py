"""
Construye `verificacion_solver.xlsx`: la instancia reducida del modelo lista para
resolverse con Excel Solver, junto con la solución de Python para compararlas.

Hojas:
    Modelo         variables de decisión, función objetivo y restricciones
    Comparacion    Python vs. Solver
    Instrucciones  cómo configurar Solver paso a paso
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src import config
from src.datos import Instancia
from src.modelo import Resultado

RELLENO_TITULO = PatternFill("solid", fgColor="1F4E78")
RELLENO_DECISION = PatternFill("solid", fgColor="FFF2CC")
RELLENO_OBJETIVO = PatternFill("solid", fgColor="C6EFCE")
NEGRITA = Font(bold=True)
BLANCO = Font(bold=True, color="FFFFFF")
FMT_COP = "#,##0"
FILA_ENCABEZADO = 8          # encabezados de las tablas de la hoja Modelo


def _encabezado(ws, fila: int, col: int, titulos: list) -> None:
    for j, titulo in enumerate(titulos):
        celda = ws.cell(fila, col + j, titulo)
        celda.font, celda.fill = BLANCO, RELLENO_TITULO
        celda.alignment = Alignment(horizontal="center", wrap_text=True)


def crear_libro_solver(inst: Instancia, res: Resultado,
                       ruta: Path = config.RAIZ / "verificacion_solver.xlsx") -> dict:
    """Crea el libro y devuelve las celdas/rangos que necesita Solver."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Modelo"
    ws["A1"] = "Verificación en Excel Solver: instancia reducida de la mesa de ayuda"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (f"{len(inst.tecnicos)} técnicos · día {', '.join(inst.dias)} · "
                f"tipos {', '.join(inst.tipos)}. Celdas amarillas = variables de decisión.")

    # --- Variables de decisión: x (asignación) y u (déficit) en una columna ---
    x_python = {(a.tecnico, a.turno, a.tipo) for a in res.asignacion.itertuples()}
    u_python = {(c.turno, c.tipo): c.deficit for c in res.cobertura.itertuples()}
    claves_x = [(t, s, k) for t in inst.tecnicos for s in inst.turnos for k in inst.tipos
                if inst.puede_atender(t, s, k)]
    claves_u = [(s, k) for s in inst.turnos for k in inst.tipos if inst.requeridos[s, k] > 0]

    _encabezado(ws, FILA_ENCABEZADO, 1, ["Variable", "Técnico", "Turno", "Tipo",
                                         "Coeficiente FO (COP)", "Valor (Solver)", "Valor Python"])
    fila = FILA_ENCABEZADO + 1
    x_ini = fila
    for t, s, k in claves_x:
        ws.append([f"x[{t},{s},{k}]", t, s, k, inst.costo[t, s], 0, int((t, s, k) in x_python)])
        fila += 1
    x_fin = fila - 1
    u_ini = fila
    fila_u = {}
    for s, k in claves_u:
        ws.append([f"u[{s},{k}]", "(déficit)", s, k, "=$C$4", 0, u_python[s, k]])
        fila_u[s, k] = fila
        fila += 1
    u_fin = fila - 1
    for r in range(x_ini, u_fin + 1):
        ws.cell(r, 5).number_format = FMT_COP
        ws.cell(r, 6).fill = RELLENO_DECISION

    # --- Parámetros y función objetivo ---
    ws["B4"], ws["C4"] = "Penalización por técnico faltante (COP)", config.PENALIZACION_DEFICIT
    ws["B5"] = "Función objetivo: costo total (COP)"
    ws["C5"] = f"=SUMPRODUCT(E{x_ini}:E{u_fin},F{x_ini}:F{u_fin})"
    ws["B6"] = "Costo total según Python (COP)"
    ws["C6"] = res.costo_total
    for c in ("C4", "C5", "C6"):
        ws[c].number_format = FMT_COP
    ws["B5"].font = ws["C5"].font = NEGRITA
    ws["C5"].fill = RELLENO_OBJETIVO

    rx = lambda col: f"${col}${x_ini}:${col}${x_fin}"  # columna de las variables x

    # --- Restricción (1): cobertura ---
    _encabezado(ws, FILA_ENCABEZADO, 9, ["Turno", "Tipo", "λ (tickets/h)", "μ (tickets/h)",
                                         "Asignados", "Déficit u", "Cubierto", "", "Requeridos r"])
    cob_ini = FILA_ENCABEZADO + 1
    for i, (s, k) in enumerate(claves_u):
        r = cob_ini + i
        ws.cell(r, 9, s), ws.cell(r, 10, k)
        ws.cell(r, 11, inst.lam[s, k]), ws.cell(r, 12, inst.mu[k])
        ws.cell(r, 13, f'=SUMIFS({rx("F")},{rx("C")},I{r},{rx("D")},J{r})')
        ws.cell(r, 14, f"=F{fila_u[s, k]}")
        ws.cell(r, 15, f"=M{r}+N{r}")
        ws.cell(r, 16, ">=")
        ws.cell(r, 17, inst.requeridos[s, k])
    cob_fin = cob_ini + len(claves_u) - 1

    # --- Restricciones (2) y (4): turnos por técnico ---
    tec_enc = cob_fin + 3
    ws.cell(tec_enc - 1, 9, "Un turno por día y carga semanal (en un día: mínimo 0, máximo 1)").font = NEGRITA
    _encabezado(ws, tec_enc, 9, ["Técnico", "Turnos asignados", "Mínimo", "Máximo"])
    tec_ini = tec_enc + 1
    for i, t in enumerate(inst.tecnicos):
        r = tec_ini + i
        ws.cell(r, 9, t)
        ws.cell(r, 10, f"=SUMIF({rx('B')},I{r},{rx('F')})")
        ws.cell(r, 11, inst.hmin[t])
        ws.cell(r, 12, min(inst.hmax[t], 1))
    tec_fin = tec_ini + len(inst.tecnicos) - 1

    anchos = {"A": 30, "B": 38, "C": 16, "D": 11, "E": 14, "F": 12, "G": 12, "H": 3,
              "I": 14, "J": 14, "K": 11, "L": 11, "M": 11, "N": 10, "O": 10, "P": 4, "Q": 12}
    for col, ancho in anchos.items():
        ws.column_dimensions[col].width = ancho
    ws.freeze_panes = f"A{FILA_ENCABEZADO + 1}"

    # --- Hoja de comparación ---
    wc = wb.create_sheet("Comparacion")
    wc["A1"] = "Comparación Python (PuLP + CBC) vs. Excel Solver (Simplex LP)"
    wc["A1"].font = Font(bold=True, size=14)
    _encabezado(wc, 3, 1, ["Indicador", "Python", "Excel Solver", "Diferencia"])
    m = "Modelo!"
    filas_comp = [
        ("Costo total, función objetivo (COP)", res.costo_total, f"={m}C5"),
        ("Costo de personal (COP)", res.costo_personal,
         f"=SUMPRODUCT({m}E{x_ini}:E{x_fin},{m}F{x_ini}:F{x_fin})"),
        ("Técnico-turnos asignados", int(res.cobertura["asignados"].sum()),
         f"=SUM({m}F{x_ini}:F{x_fin})"),
        ("Técnico-turnos de déficit", int(res.cobertura["deficit"].sum()),
         f"=SUM({m}F{u_ini}:F{u_fin})"),
    ]
    for i, (nombre, v_py, f_solver) in enumerate(filas_comp):
        r = 4 + i
        wc.cell(r, 1, nombre), wc.cell(r, 2, v_py), wc.cell(r, 3, f_solver)
        wc.cell(r, 4, f"=C{r}-B{r}")
        for c in (2, 3, 4):
            wc.cell(r, c).number_format = FMT_COP
    r = 4 + len(filas_comp)
    wc.cell(r, 1, "Variables con valor distinto")
    wc.cell(r, 3, f"=SUMPRODUCT(--({m}F{x_ini}:F{u_fin}<>{m}G{x_ini}:G{u_fin}))")
    wc.cell(r + 2, 1, "Si la diferencia en la función objetivo es 0, ambos métodos llegan al mismo "
                      "óptimo. Algunas variables pueden diferir si hay óptimos alternativos "
                      "(mismo costo con otra asignación).")
    wc.cell(r + 3, 1, f"Tamaño del modelo: {len(claves_x) + len(claves_u)} variables "
                      f"({len(claves_x)} binarias x, {len(claves_u)} enteras u), "
                      f"límite de Solver: 200.")
    wc.column_dimensions["A"].width = 40
    for col in "BCD":
        wc.column_dimensions[col].width = 16

    # --- Hoja de instrucciones ---
    rangos = {
        "objetivo": "$C$5",
        "variables": f"$F${x_ini}:$F${u_fin}",
        "x": f"$F${x_ini}:$F${x_fin}",
        "u": f"$F${u_ini}:$F${u_fin}",
        "cobertura_lhs": f"$O${cob_ini}:$O${cob_fin}",
        "cobertura_rhs": f"$Q${cob_ini}:$Q${cob_fin}",
        "turnos": f"$J${tec_ini}:$J${tec_fin}",
        "minimo": f"$K${tec_ini}:$K${tec_fin}",
        "maximo": f"$L${tec_ini}:$L${tec_fin}",
    }
    wi = wb.create_sheet("Instrucciones")
    pasos = [
        "Cómo resolver el modelo con Solver (Datos > Solver):",
        "",
        f"1. Establecer objetivo: Modelo!{rangos['objetivo']}  ->  Mín.",
        f"2. Cambiando las celdas de variables: Modelo!{rangos['variables']}",
        "3. Sujeto a las restricciones:",
        f"   a) Cobertura: Modelo!{rangos['cobertura_lhs']} >= Modelo!{rangos['cobertura_rhs']}",
        f"   b) Máximo de turnos: Modelo!{rangos['turnos']} <= Modelo!{rangos['maximo']}",
        f"   c) Mínimo de turnos: Modelo!{rangos['turnos']} >= Modelo!{rangos['minimo']}",
        f"   d) Asignación binaria: Modelo!{rangos['x']} = binario",
        f"   e) Déficit entero: Modelo!{rangos['u']} = entero",
        "4. Marcar 'Convertir variables sin restricciones en no negativas'.",
        "5. Método de resolución: Simplex LP.",
        "6. Opciones > 'Ignorar restricciones de enteros' desmarcado y Optimalidad de enteros (%) = 0.",
        "7. Resolver y comparar el resultado en la hoja Comparacion.",
        "",
        "Nota: en una instancia de un solo día, 'un turno por día' y 'máximo de turnos'",
        "coinciden (máximo 1), y no aplica la restricción de descanso entre días.",
    ]
    for i, texto in enumerate(pasos, start=1):
        wi.cell(i, 1, texto)
    wi["A1"].font = NEGRITA
    wi.column_dimensions["A"].width = 100

    wb.save(ruta)
    return rangos
