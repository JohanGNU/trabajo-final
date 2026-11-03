"""
Reportes: tablas CSV y gráficos (matplotlib) en la carpeta resultados/.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # genera archivos PNG sin abrir ventanas
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from src import config
from src.datos import Instancia
from src.modelo import Resultado

COLORES_TIPO = ["#2a78b8", "#e08a1e", "#3a9a5b", "#9b59b6"]
COLOR_LIBRE = "#e6e6e6"


def guardar_tablas(res: Resultado, destino: Path = config.DIR_RESULTADOS,
                   prefijo: str = "") -> list[Path]:
    """Guarda asignación, cobertura y resumen por técnico en CSV."""
    destino.mkdir(parents=True, exist_ok=True)
    tablas = {"asignacion_optima": res.asignacion, "cobertura": res.cobertura,
              "resumen_tecnicos": res.por_tecnico}
    rutas = []
    for nombre, df in tablas.items():
        ruta = destino / f"{prefijo}{nombre}.csv"
        df.to_csv(ruta, index=False, encoding="utf-8-sig")  # -sig: Excel muestra bien las tildes
        rutas.append(ruta)
    return rutas


def exportar_instancia(inst: Instancia, destino: Path = config.DIR_RESULTADOS,
                       prefijo: str = "reducida_") -> list[Path]:
    """
    Exporta los parámetros de una instancia (variables posibles con su costo y
    técnicos requeridos) para construir el modelo en Excel Solver.
    """
    destino.mkdir(parents=True, exist_ok=True)
    variables = pd.DataFrame(
        [{"tecnico": t, "turno": s, "tipo": k, "costo_cop": inst.costo[t, s]}
         for t in inst.tecnicos for s in inst.turnos for k in inst.tipos
         if inst.puede_atender(t, s, k)])
    requeridos = pd.DataFrame(
        [{"turno": s, "tipo": k, "lambda_tickets_hora": inst.lam[s, k],
          "mu_tickets_hora": inst.mu[k], "requeridos": inst.requeridos[s, k]}
         for s in inst.turnos for k in inst.tipos])
    rutas = [destino / f"{prefijo}variables.csv", destino / f"{prefijo}requeridos.csv"]
    variables.to_csv(rutas[0], index=False, encoding="utf-8-sig")
    requeridos.to_csv(rutas[1], index=False, encoding="utf-8-sig")
    return rutas


def grafico_cobertura(inst: Instancia, res: Resultado, ruta: Path) -> None:
    """Barras agrupadas: técnicos requeridos vs. asignados en cada turno."""
    por_turno = res.cobertura.groupby("turno", sort=False)[["requeridos", "asignados"]].sum()
    por_turno = por_turno.reindex(inst.turnos)
    pos = np.arange(len(por_turno))

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(pos - 0.2, por_turno["requeridos"], width=0.4, label="Requeridos", color="#9aa5b1")
    ax.bar(pos + 0.2, por_turno["asignados"], width=0.4, label="Asignados", color="#2a78b8")
    ax.set_xticks(pos, por_turno.index, rotation=60, ha="right")
    ax.set_title("Técnicos requeridos vs. asignados por turno (modelo base)")
    ax.set_xlabel("Turno (día - franja de 8 h)")
    ax.set_ylabel("Técnicos (personas)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def grafico_tecnicos(res: Resultado, ruta: Path) -> None:
    """Turnos asignados y costo semanal por técnico."""
    df = res.por_tecnico
    colores = ["#e08a1e" if n == "Senior" else "#2a78b8" for n in df["nivel"]]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    ax1.bar(df["tecnico"], df["turnos"], color=colores)
    ax1.set_title("Carga y costo semanal por técnico")
    ax1.set_ylabel("Turnos asignados (turnos/semana)")
    ax1.grid(axis="y", alpha=0.3)
    ax2.bar(df["tecnico"], df["costo_cop"] / 1e6, color=colores)
    ax2.set_ylabel("Costo semanal (millones de COP)")
    ax2.set_xlabel("Técnico")
    ax2.tick_params(axis="x", rotation=90)
    ax2.grid(axis="y", alpha=0.3)
    ax1.legend(handles=[Patch(color="#2a78b8", label="Junior"),
                        Patch(color="#e08a1e", label="Senior")])
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def grafico_cronograma(inst: Instancia, res: Resultado, ruta: Path) -> None:
    """Mapa de calor técnico x turno coloreado por el tipo de ticket asignado."""
    matriz = np.full((len(inst.tecnicos), len(inst.turnos)), -1)
    fila = {t: i for i, t in enumerate(inst.tecnicos)}
    col = {s: j for j, s in enumerate(inst.turnos)}
    tipo_idx = {k: i for i, k in enumerate(inst.tipos)}
    for a in res.asignacion.itertuples():
        matriz[fila[a.tecnico], col[a.turno]] = tipo_idx[a.tipo]

    cmap = ListedColormap([COLOR_LIBRE] + COLORES_TIPO[:len(inst.tipos)])
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.imshow(matriz, cmap=cmap, vmin=-1, vmax=len(inst.tipos) - 1, aspect="auto")
    ax.set_xticks(range(len(inst.turnos)), inst.turnos, rotation=60, ha="right")
    ax.set_yticks(range(len(inst.tecnicos)), inst.tecnicos)
    ax.set_title("Cronograma semanal óptimo: tipo de ticket atendido por técnico y turno")
    ax.set_xlabel("Turno (día - franja de 8 h)")
    ax.set_ylabel("Técnico")
    leyenda = [Patch(color=COLOR_LIBRE, label="Libre")] + [
        Patch(color=COLORES_TIPO[i], label=k) for i, k in enumerate(inst.tipos)]
    ax.legend(handles=leyenda, bbox_to_anchor=(1.01, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def grafico_escenarios(tabla: pd.DataFrame, ruta: Path) -> None:
    """Barras horizontales apiladas: costo de personal + penalización por escenario."""
    df = tabla.iloc[::-1]  # el escenario base queda arriba
    personal = df["costo_personal_cop"] / 1e6
    penal = df["penalizacion_cop"] / 1e6

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.barh(df["escenario"], personal, color="#2a78b8", label="Costo de personal")
    ax.barh(df["escenario"], penal, left=personal, color="#d1495b",
            label="Penalización por déficit")
    costo_base = personal.iloc[-1]
    for y, (total, var, deficit) in enumerate(zip(
            personal + penal, df["var_vs_base_pct"], df["deficit"])):
        texto = f"{total:.2f} M ({var:+.1f} %)" + (f"  déficit {deficit}" if deficit else "")
        ax.text(max(total, costo_base) + 0.2, y, texto, va="center", fontsize=9)
    ax.axvline(costo_base, color="#555", ls="--", lw=1, label="Costo base")
    ax.set_title("Costo semanal por escenario (re-resolviendo el MIP)")
    ax.set_xlabel("Costo semanal (millones de COP)")
    ax.set_xlim(0, (personal + penal).max() * 1.3)
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def grafico_barrido_demanda(barrido: pd.DataFrame, ruta: Path) -> None:
    """Técnico-turnos requeridos vs. capacidad y costo al crecer la demanda."""
    x = (barrido["factor_demanda"] - 1) * 100

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.plot(x, barrido["requeridos"], "o-", color="#e08a1e", label="Requeridos")
    ax1.plot(x, barrido["asignados"], "s-", color="#2a78b8", label="Asignados")
    ax1.plot(x, barrido["capacidad_max"], "--", color="#555", label="Capacidad máxima (suma de Hmax)")
    ax1.fill_between(x, barrido["asignados"], barrido["requeridos"], color="#d1495b",
                     alpha=0.25, label="Déficit")
    ax1.set_title("Cobertura al aumentar la demanda")
    ax1.set_xlabel("Aumento de la demanda (%)")
    ax1.set_ylabel("Técnico-turnos por semana")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2.plot(x, barrido["costo_total_cop"] / 1e6, "s-", color="#d1495b",
             label="Costo total (con penalización)")
    ax2.plot(x, barrido["costo_personal_cop"] / 1e6, "o-", color="#2a78b8",
             label="Costo de personal")
    ax2.set_title("Costo semanal al aumentar la demanda")
    ax2.set_xlabel("Aumento de la demanda (%)")
    ax2.set_ylabel("Costo semanal (millones de COP)")
    ax2.legend()
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def guardar_escenarios(tabla: pd.DataFrame, barrido: pd.DataFrame,
                       destino: Path = config.DIR_RESULTADOS) -> list[Path]:
    """Guarda las tablas y los gráficos del análisis de escenarios."""
    destino.mkdir(parents=True, exist_ok=True)
    rutas = [destino / "escenarios_resumen.csv", destino / "barrido_demanda.csv",
             destino / "fig4_escenarios_costo.png", destino / "fig5_barrido_demanda.png"]
    tabla.to_csv(rutas[0], index=False, encoding="utf-8-sig")
    barrido.to_csv(rutas[1], index=False, encoding="utf-8-sig")
    grafico_escenarios(tabla, rutas[2])
    grafico_barrido_demanda(barrido, rutas[3])
    return rutas


def generar_graficos(inst: Instancia, res: Resultado,
                     destino: Path = config.DIR_RESULTADOS) -> list[Path]:
    """Genera los gráficos del modelo base."""
    destino.mkdir(parents=True, exist_ok=True)
    rutas = [destino / "fig1_cobertura_por_turno.png",
             destino / "fig2_carga_costo_tecnicos.png",
             destino / "fig3_cronograma.png"]
    grafico_cobertura(inst, res, rutas[0])
    grafico_tecnicos(res, rutas[1])
    grafico_cronograma(inst, res, rutas[2])
    return rutas
