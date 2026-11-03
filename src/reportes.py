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
          "mu_tickets_hora": inst.mu[k], "minimos": inst.minimos[s, k],
          "requeridos": inst.requeridos[s, k]}
         for s in inst.turnos for k in inst.tipos])
    rutas = [destino / f"{prefijo}variables.csv", destino / f"{prefijo}requeridos.csv"]
    variables.to_csv(rutas[0], index=False, encoding="utf-8-sig")
    requeridos.to_csv(rutas[1], index=False, encoding="utf-8-sig")
    return rutas


def grafico_cobertura(inst: Instancia, res: Resultado, ruta: Path,
                      plan: str = "modelo base") -> None:
    """Barras agrupadas: técnicos requeridos vs. asignados en cada turno."""
    por_turno = res.cobertura.groupby("turno", sort=False)[["requeridos", "asignados"]].sum()
    por_turno = por_turno.reindex(inst.turnos)
    pos = np.arange(len(por_turno))

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(pos - 0.2, por_turno["requeridos"], width=0.4, label="Requeridos", color="#9aa5b1")
    ax.bar(pos + 0.2, por_turno["asignados"], width=0.4, label="Asignados", color="#2a78b8")
    ax.set_xticks(pos, por_turno.index, rotation=60, ha="right")
    ax.set_title(f"Técnicos requeridos vs. asignados por turno ({plan})")
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


def grafico_escenarios(tabla: pd.DataFrame, ruta: Path, meta_min: float) -> None:
    """Costo de personal y espera media por escenario, lado a lado."""
    df = tabla.iloc[::-1]  # el escenario base queda arriba
    costo = df["costo_personal_cop"] / 1e6
    y = np.arange(len(df))
    colores = ["#2a78b8" if e == "Base" else "#9aa5b1" for e in df["escenario"]]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    ax1.barh(y, costo, color=colores)
    for i, (c, var) in enumerate(zip(costo, df["var_costo_vs_base_pct"])):
        ax1.text(c + 0.2, i, f"{c:.2f} M ({var:+.1f} %)", va="center", fontsize=9)
    ax1.set_yticks(y, df["escenario"])
    ax1.set_title("Costo de personal por semana")
    ax1.set_xlabel("Millones de COP por semana")
    ax1.set_xlim(0, costo.max() * 1.35)
    ax1.grid(axis="x", alpha=0.3)

    ax2.barh(y, df["wq_promedio_min"], color=colores)
    for i, (wq, pct, deficit) in enumerate(zip(df["wq_promedio_min"],
                                               df["colas_cumplen_meta_pct"], df["deficit"])):
        texto = f"{wq:.1f} min · {pct:.0f} % colas en meta" + (f" · faltan {deficit}" if deficit else "")
        ax2.text(max(wq, meta_min) + 0.8, i, texto, va="center", fontsize=9)
    ax2.axvline(meta_min, color="#d1495b", ls="--", lw=1, label=f"Meta Wq = {meta_min:g} min")
    ax2.set_title("Espera media en cola (ponderada por llegadas)")
    ax2.set_xlabel("Minutos (M/M/c con los técnicos asignados)")
    ax2.set_xlim(0, df["wq_promedio_min"].max() * 2.1)
    ax2.legend(loc="lower right")
    ax2.grid(axis="x", alpha=0.3)
    fig.suptitle("Escenarios: costo frente a nivel de servicio (re-resolviendo el MIP)")
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def grafico_espera(inst: Instancia, res: Resultado, ruta: Path) -> None:
    """Mapa de calor de la espera media Wq por turno y tipo con el plan óptimo."""
    cob = res.cobertura.set_index(["tipo", "turno"])
    matriz = np.array([[cob.loc[(k, s), "wq_min"] if cob.loc[(k, s), "lambda_tickets_hora"] > 0
                        else np.nan for s in inst.turnos] for k in inst.tipos])
    tope = 4 * inst.meta_espera_min  # escala de color: 0 a 4 veces la meta

    fig, ax = plt.subplots(figsize=(14, 4.2))
    im = ax.imshow(np.minimum(matriz, tope), cmap="RdYlGn_r", vmin=0, vmax=tope, aspect="auto")
    for i in range(len(inst.tipos)):
        for j in range(len(inst.turnos)):
            v = matriz[i, j]
            texto = "-" if np.isnan(v) else ("inest." if np.isinf(v) else f"{v:.0f}")
            ax.text(j, i, texto, ha="center", va="center", fontsize=8)
    ax.set_xticks(range(len(inst.turnos)), inst.turnos, rotation=60, ha="right")
    ax.set_yticks(range(len(inst.tipos)), inst.tipos)
    n_fuera = int((~res.cobertura.loc[res.cobertura["lambda_tickets_hora"] > 0, "cumple_meta"]).sum())
    ax.set_title(f"Espera media en cola Wq (min) con el plan óptimo: {n_fuera} colas superan "
                 f"la meta de {inst.meta_espera_min:g} min")
    ax.set_xlabel("Turno (día - franja de 8 h)")
    ax.set_ylabel("Tipo de ticket")
    fig.colorbar(im, ax=ax, label=f"Wq (min, recortado en {tope:g})")
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def grafico_barrido_meta(barrido: pd.DataFrame, ruta: Path) -> None:
    """Técnicos requeridos vs. capacidad y cumplimiento al variar la meta de espera."""
    x = barrido["meta_espera_min"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.plot(x, barrido["requeridos"], "o-", color="#e08a1e", label="Requeridos (M/M/c)")
    ax1.plot(x, barrido["asignados"], "s-", color="#2a78b8", label="Asignados")
    ax1.plot(x, barrido["capacidad_max"], "--", color="#555", label="Capacidad máxima (suma de Hmax)")
    ax1.fill_between(x, barrido["asignados"], barrido["requeridos"], color="#d1495b",
                     alpha=0.25, label="Déficit")
    ax1.set_title("Técnicos necesarios según la meta de espera")
    ax1.set_xlabel("Meta de espera media en cola Wq (min)")
    ax1.set_ylabel("Técnico-turnos por semana")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2.plot(x, barrido["colas_cumplen_meta_pct"], "o-", color="#2a78b8")
    for xi, pct, falt in zip(x, barrido["colas_cumplen_meta_pct"], barrido["tecnicos_faltantes"]):
        if falt:
            ax2.annotate(f"faltan ~{falt} téc.", (xi, pct), textcoords="offset points",
                         xytext=(6, -14), fontsize=8)
    ax2.set_ylim(0, 105)
    ax2.set_title("Colas que cumplen la meta con 28 técnicos")
    ax2.set_xlabel("Meta de espera media en cola Wq (min)")
    ax2.set_ylabel("Colas (turno, tipo) que cumplen (%)")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def guardar_escenarios(tabla: pd.DataFrame, barrido: pd.DataFrame, meta_min: float,
                       destino: Path = config.DIR_RESULTADOS) -> list[Path]:
    """Guarda las tablas y los gráficos del análisis de escenarios."""
    destino.mkdir(parents=True, exist_ok=True)
    rutas = [destino / "escenarios_resumen.csv", destino / "barrido_meta_espera.csv",
             destino / "fig4_escenarios.png", destino / "fig5_barrido_meta_espera.png"]
    tabla.to_csv(rutas[0], index=False, encoding="utf-8-sig")
    barrido.to_csv(rutas[1], index=False, encoding="utf-8-sig")
    grafico_escenarios(tabla, rutas[2], meta_min)
    grafico_barrido_meta(barrido, rutas[3])
    return rutas


def grafico_cdf_espera(tickets_por_plan: dict, ruta: Path, meta_min: float) -> None:
    """Distribución acumulada de la espera simulada de los tickets, por plan."""
    colores = ["#2a78b8", "#e08a1e", "#9aa5b1", "#3a9a5b"]
    n_replicas = next(iter(tickets_por_plan.values()))["replica"].nunique()
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for color, (plan, t) in zip(colores, tickets_por_plan.items()):
        esperas = np.sort(t["espera_min"].to_numpy())
        acumulada = np.arange(1, len(esperas) + 1) / len(esperas) * 100
        dentro = 100 * (esperas <= meta_min).mean()
        ax.plot(esperas, acumulada, color=color, lw=2,
                label=f"{plan}: {dentro:.0f} % de tickets esperan <= {meta_min:g} min")
    ax.axvline(meta_min, color="#d1495b", ls="--", lw=1)
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 101)
    ax.set_title(f"Espera de los tickets en la simulación de la semana (SimPy, {n_replicas} réplicas)")
    ax.set_xlabel("Espera en cola (min)")
    ax.set_ylabel("Tickets con esa espera o menos (%)")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def grafico_mmc_vs_simulacion(por_cola: pd.DataFrame, ruta: Path, plan: str = "plan base") -> None:
    """Espera media por cola: fórmula M/M/c frente a la simulación de la semana."""
    tope = float(np.nanmax(por_cola[["wq_mmc_min", "wq_simulada_min"]].to_numpy())) * 1.05
    fig, ax = plt.subplots(figsize=(8, 7))
    for color, (tipo, df) in zip(COLORES_TIPO, por_cola.groupby("tipo", sort=False)):
        ax.scatter(df["wq_mmc_min"], df["wq_simulada_min"], color=color, label=tipo, s=40)
    ax.plot([0, tope], [0, tope], color="#555", ls="--", lw=1, label="Igual espera")
    # Se rotulan las colas en las que la simulación se aleja más de la fórmula
    dif = (por_cola["wq_simulada_min"] - por_cola["wq_mmc_min"]).abs()
    for fila in por_cola.loc[dif.nlargest(4).index].itertuples():
        ax.annotate(f"{fila.turno} {fila.tipo}", (fila.wq_mmc_min, fila.wq_simulada_min),
                    textcoords="offset points", xytext=(6, 4), fontsize=8)
    ax.set_xlim(0, tope)
    ax.set_ylim(0, tope)
    ax.set_title(f"Espera media por turno y tipo: M/M/c frente a SimPy ({plan})")
    ax.set_xlabel("Wq según la fórmula M/M/c (min)")
    ax.set_ylabel("Wq simulada, semana continua (min)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def guardar_simulacion(resumen: pd.DataFrame, por_cola: pd.DataFrame, tickets_por_plan: dict,
                       meta_min: float, destino: Path = config.DIR_RESULTADOS) -> list[Path]:
    """Guarda las tablas y los gráficos de la simulación."""
    destino.mkdir(parents=True, exist_ok=True)
    rutas = [destino / "simulacion_resumen.csv", destino / "simulacion_por_cola.csv",
             destino / "fig7_simulacion_espera.png", destino / "fig8_mmc_vs_simulacion.png"]
    resumen.to_csv(rutas[0], index=False, encoding="utf-8-sig")
    por_cola.to_csv(rutas[1], index=False, encoding="utf-8-sig")
    grafico_cdf_espera(tickets_por_plan, rutas[2], meta_min)
    grafico_mmc_vs_simulacion(por_cola, rutas[3])
    return rutas


def generar_graficos(inst: Instancia, res: Resultado,
                     destino: Path = config.DIR_RESULTADOS) -> list[Path]:
    """Genera los gráficos del modelo base."""
    destino.mkdir(parents=True, exist_ok=True)
    rutas = [destino / "fig1_cobertura_por_turno.png",
             destino / "fig2_carga_costo_tecnicos.png",
             destino / "fig3_cronograma.png",
             destino / "fig6_espera_por_turno.png"]
    grafico_cobertura(inst, res, rutas[0])
    grafico_tecnicos(res, rutas[1])
    grafico_cronograma(inst, res, rutas[2])
    grafico_espera(inst, res, rutas[3])
    return rutas
