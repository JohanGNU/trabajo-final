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

from src import config
from src.datos import Instancia
from src.modelo import Resultado, construir_modelo

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
    _, x, w, v, pen = construir_modelo(inst)  # mismas variables y coeficientes que PuLP
    wb = Workbook()
    ws = wb.active
    ws.title = "Modelo"
    ws["A1"] = "Verificación en Excel Solver: instancia reducida de la mesa de ayuda"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (f"{len(inst.tecnicos)} técnicos · día {', '.join(inst.dias)} · tipos "
                f"{', '.join(inst.tipos)} · meta Wq <= {inst.meta_espera_min:g} min. "
                "Celdas amarillas = variables de decisión.")

    # --- Valores de la solución de Python ---
    x_py = {(a.tecnico, a.turno, a.tipo) for a in res.asignacion.itertuples()}
    cob_py = res.cobertura.set_index(["turno", "tipo"])

    def w_python(s, k, j):
        """En Python faltan los niveles más altos: j > asignados + v."""
        fila = cob_py.loc[(s, k)]
        return int(j > fila.asignados + fila.deficit_estable)

    # --- Variables: x (asignación), w (déficit por nivel), v (estabilidad) ---
    _encabezado(ws, FILA_ENCABEZADO, 1, ["Variable", "Técnico / nivel", "Turno", "Tipo",
                                         "Coeficiente FO (COP)", "Valor (Solver)", "Valor Python"])
    fila = FILA_ENCABEZADO + 1
    x_ini = fila
    for (t, s, k) in x:
        ws.append([f"x[{t},{s},{k}]", t, s, k, inst.costo[t, s], 0, int((t, s, k) in x_py)])
        fila += 1
    x_fin, w_ini = fila - 1, fila
    for (s, k, j) in w:
        ws.append([f"w[{s},{k},{j}]", f"falta el técnico {j}", s, k, round(pen[s, k, j], 2),
                   0, w_python(s, k, j)])
        fila += 1
    w_fin, v_ini = fila - 1, fila
    for (s, k) in v:
        ws.append([f"v[{s},{k}]", "(estabilidad)", s, k, config.PENALIZACION_ESTABILIDAD,
                   0, int(cob_py.loc[(s, k)].deficit_estable)])
        fila += 1
    v_fin = fila - 1
    for r in range(x_ini, v_fin + 1):
        ws.cell(r, 5).number_format = FMT_COP
        ws.cell(r, 6).fill = RELLENO_DECISION

    # --- Función objetivo ---
    ws["B4"] = "Función objetivo: costo + penalizaciones (COP)"
    ws["C4"] = f"=SUMPRODUCT(E{x_ini}:E{v_fin},F{x_ini}:F{v_fin})"
    ws["B5"] = "Función objetivo según Python (COP)"
    ws["C5"] = round(res.costo_total, 2)
    ws["B6"] = "Penalización de w: P + Ce · λ · 8 h · (Wq(j-1) - Wq(j)), con Wq de M/M/c"
    for c in ("C4", "C5"):
        ws[c].number_format = FMT_COP
    ws["B4"].font = ws["C4"].font = NEGRITA
    ws["C4"].fill = RELLENO_OBJETIVO

    rng = lambda col, a, b: f"${col}${a}:${col}${b}"
    rx, rw, rv = (lambda col: rng(col, x_ini, x_fin), lambda col: rng(col, w_ini, w_fin),
                  lambda col: rng(col, v_ini, v_fin))

    # --- Restricciones (1) cobertura de la meta y (1b) estabilidad ---
    _encabezado(ws, FILA_ENCABEZADO, 9, [
        "Turno", "Tipo", "λ (tickets/h)", "μ (tickets/h)", "Asignados", "Déficit estab. v",
        "Déficit meta Σw", "Para estabilidad", "", "Mínimo m", "Para meta", "", "Requeridos r"])
    cob_ini = FILA_ENCABEZADO + 1
    claves = list(v)  # pares (turno, tipo) con demanda
    for i, (s, k) in enumerate(claves):
        r = cob_ini + i
        ws.cell(r, 9, s), ws.cell(r, 10, k)
        ws.cell(r, 11, inst.lam[s, k]), ws.cell(r, 12, inst.mu[k])
        ws.cell(r, 13, f"=SUMIFS({rx('F')},{rx('C')},I{r},{rx('D')},J{r})")
        ws.cell(r, 14, f"=SUMIFS({rv('F')},{rv('C')},I{r},{rv('D')},J{r})")
        ws.cell(r, 15, f"=SUMIFS({rw('F')},{rw('C')},I{r},{rw('D')},J{r})" if w else 0)
        ws.cell(r, 16, f"=M{r}+N{r}"), ws.cell(r, 17, ">="), ws.cell(r, 18, inst.minimos[s, k])
        ws.cell(r, 19, f"=M{r}+N{r}+O{r}"), ws.cell(r, 20, ">="), ws.cell(r, 21, inst.requeridos[s, k])
    cob_fin = cob_ini + len(claves) - 1

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

    anchos = {"A": 34, "B": 44, "C": 16, "D": 11, "E": 14, "F": 12, "G": 12, "H": 3, "I": 14,
              "J": 14, "K": 11, "L": 11, "M": 10, "N": 11, "O": 11, "P": 11, "Q": 4, "R": 10,
              "S": 10, "T": 4, "U": 11}
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
        ("Función objetivo (COP)", round(res.costo_total, 2), f"={m}C4"),
        ("Costo de personal (COP)", res.costo_personal,
         f"=SUMPRODUCT({m}E{x_ini}:E{x_fin},{m}F{x_ini}:F{x_fin})"),
        ("Técnico-turnos asignados", int(res.cobertura["asignados"].sum()),
         f"=SUM({m}F{x_ini}:F{x_fin})"),
        ("Déficit frente a la meta (técnicos)", int(res.cobertura["deficit"].sum()),
         f"=SUM({m}F{w_ini}:F{w_fin})" if w else 0),
        ("Déficit de estabilidad (técnicos)", int(res.cobertura["deficit_estable"].sum()),
         f"=SUM({m}F{v_ini}:F{v_fin})"),
    ]
    for i, (nombre, v_py, f_solver) in enumerate(filas_comp):
        r = 4 + i
        wc.cell(r, 1, nombre), wc.cell(r, 2, v_py), wc.cell(r, 3, f_solver)
        wc.cell(r, 4, f"=C{r}-B{r}")
        for c in (2, 3, 4):
            wc.cell(r, c).number_format = FMT_COP
    r = 4 + len(filas_comp)
    wc.cell(r, 1, "Variables con valor distinto")
    wc.cell(r, 3, f"=SUMPRODUCT(--(ROUND({m}F{x_ini}:F{v_fin},6)<>{m}G{x_ini}:G{v_fin}))")
    wc.cell(r + 2, 1, "Si la diferencia en la función objetivo es 0, ambos métodos llegan al mismo "
                      "óptimo. Algunas variables pueden diferir si hay óptimos alternativos "
                      "(mismo costo con otra asignación).")
    wc.cell(r + 3, 1, f"Tamaño: {len(x) + len(w) + len(v)} variables ({len(x)} binarias x, "
                      f"{len(w)} continuas w en [0,1], {len(v)} enteras v); límite de Solver: 200.")
    wc.column_dimensions["A"].width = 40
    for col in "BCD":
        wc.column_dimensions[col].width = 16

    # --- Rangos para Solver e instrucciones ---
    rangos = {
        "objetivo": "$C$4",
        "variables": f"$F${x_ini}:$F${v_fin}",
        "x": f"$F${x_ini}:$F${x_fin}",
        "w": f"$F${w_ini}:$F${w_fin}" if w else None,
        "v": f"$F${v_ini}:$F${v_fin}",
        "estabilidad_lhs": f"$P${cob_ini}:$P${cob_fin}", "estabilidad_rhs": f"$R${cob_ini}:$R${cob_fin}",
        "meta_lhs": f"$S${cob_ini}:$S${cob_fin}", "meta_rhs": f"$U${cob_ini}:$U${cob_fin}",
        "turnos": f"$J${tec_ini}:$J${tec_fin}",
        "minimo": f"$K${tec_ini}:$K${tec_fin}", "maximo": f"$L${tec_ini}:$L${tec_fin}",
    }
    wi = wb.create_sheet("Instrucciones")
    pasos = [
        "Cómo resolver el modelo con Solver (Datos > Solver):",
        "",
        f"1. Establecer objetivo: Modelo!{rangos['objetivo']}  ->  Mín.",
        f"2. Cambiando las celdas de variables: Modelo!{rangos['variables']}",
        "3. Sujeto a las restricciones:",
        f"   a) Estabilidad: Modelo!{rangos['estabilidad_lhs']} >= Modelo!{rangos['estabilidad_rhs']}",
        f"   b) Meta de espera: Modelo!{rangos['meta_lhs']} >= Modelo!{rangos['meta_rhs']}",
        f"   c) Máximo de turnos: Modelo!{rangos['turnos']} <= Modelo!{rangos['maximo']}",
        f"   d) Mínimo de turnos: Modelo!{rangos['turnos']} >= Modelo!{rangos['minimo']}",
        f"   e) Asignación binaria: Modelo!{rangos['x']} = binario",
        f"   f) Déficit por nivel: Modelo!{rangos['w']} <= 1" if w else "   f) (sin variables w)",
        f"   g) Déficit de estabilidad entero: Modelo!{rangos['v']} = entero",
        "4. Marcar 'Convertir variables sin restricciones en no negativas'.",
        "5. Método de resolución: Simplex LP.",
        "6. Opciones > 'Ignorar restricciones de enteros' desmarcado y Optimalidad de enteros (%) = 0.",
        "7. Resolver y comparar el resultado en la hoja Comparacion.",
        "",
        "Notas: en una instancia de un solo día, 'un turno por día' y 'máximo de turnos' coinciden",
        "(máximo 1) y no aplica el descanso entre días. Los coeficientes de w vienen de M/M/c:",
        "faltar el técnico j cuesta la penalización base más la espera adicional que causa.",
    ]
    for i, texto in enumerate(pasos, start=1):
        wi.cell(i, 1, texto)
    wi["A1"].font = NEGRITA
    wi.column_dimensions["A"].width = 100

    wb.save(ruta)
    return rangos
