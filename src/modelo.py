"""
Modelo de Programación Entera (MIP) para asignar técnicos a turnos y tipos de ticket.

Conjuntos
    T técnicos, S turnos (día d + franja h), K tipos de ticket.
Parámetros
    c_ts  costo del técnico t en el turno s (COP, con recargos)
    a_ts  1 si t está disponible en s
    q_tk  1 si t está certificado en k
    r_sk  técnicos requeridos en s para k (M/M/c con Wq <= meta)
    m_sk  técnicos mínimos para que la cola de s, k sea estable (m_sk <= r_sk)
    Hmin_t, Hmax_t  turnos mínimos y máximos por semana
    J_sk  niveles j = m_sk+1 .. r_sk: el j-ésimo técnico del turno s, tipo k
    p_skj penalización si falta el técnico j: P + Ce * lambda * 8 h * (Wq(j-1) - Wq(j)),
          es decir, una base P más el costo de la espera adicional que causa su ausencia
          (Ce = costo por hora de espera de un ticket; Wq de M/M/c, convexa en c)
    Q     penalización por técnico faltante para la estabilidad (Q = 10 P)
Variables
    x_tsk en {0,1}  1 si t trabaja el turno s atendiendo tickets tipo k
                    (solo existe si a_ts = 1 y q_tk = 1)
    w_skj en [0,1]  1 si falta el técnico j (déficit frente a la meta de espera)
    v_sk  >= 0 entera  técnicos que faltan en s, k para que la cola sea estable
Función objetivo
    min  sum c_ts * x_tsk  +  sum p_skj * w_skj  +  sum Q * v_sk
Restricciones
    (1) Cobertura:      sum_t x_tsk + v_sk + sum_j w_skj >= r_sk    para todo s, k
    (1b) Estabilidad:   sum_t x_tsk + v_sk >= m_sk                 para todo s, k
    (2) Un turno/día:   sum_{h,k} x_t(d,h)k <= 1                   para todo t, d
        (implica que en cada turno se atiende un solo tipo de ticket)
    (3) Descanso:       sum_k x_t(d,Noche)k + sum_k x_t(d+1,Mañana)k <= 1
    (4) Carga semanal:  Hmin_t <= sum_{s,k} x_tsk <= Hmax_t        para todo t

Si la plantilla no alcanza para cumplir r, el modelo deja sin cubrir primero los
técnicos que menos reducen la espera (p_skj decrece con j porque Wq es convexa),
y (1b) con su penalización Q evita dejar colas inestables.
"""
from dataclasses import dataclass
import re
import time

import pandas as pd
import pulp

from src import config
from src.colas import metricas_mmc
from src.datos import Instancia


@dataclass
class Resultado:
    """Solución de una instancia y sus indicadores."""
    instancia: str
    estado: str
    costo_total: float
    costo_personal: float
    costo_deficit: float
    tiempo_s: float
    n_variables: int
    n_restricciones: int
    asignacion: pd.DataFrame   # una fila por (técnico, turno, tipo) asignado
    cobertura: pd.DataFrame    # requeridos vs. asignados por (turno, tipo)
    por_tecnico: pd.DataFrame  # turnos y costo por técnico


def penalizacion_niveles(inst: Instancia, s: str, k: str) -> dict:
    """p_skj de cada técnico j entre el mínimo estable y el requerido (COP)."""
    lam, mu = inst.lam[s, k], inst.mu[k]
    wq_h = lambda c: metricas_mmc(lam, mu, c)["wq_min"] / 60
    return {j: config.PENALIZACION_DEFICIT
               + config.COSTO_ESPERA_HORA * lam * config.HORAS_TURNO * (wq_h(j - 1) - wq_h(j))
            for j in range(inst.minimos[s, k] + 1, inst.requeridos[s, k] + 1)}


def construir_modelo(inst: Instancia,
                     penalizacion_estable: float = config.PENALIZACION_ESTABILIDAD):
    """Crea el problema PuLP. Devuelve (problema, x, w, v, penalizaciones de w)."""
    nombre = re.sub(r"\W", "_", inst.nombre)  # PuLP no acepta espacios ni símbolos
    prob = pulp.LpProblem(f"MesaAyuda_{nombre}", pulp.LpMinimize)

    # Nombres de variables con índices numéricos (evita caracteres especiales)
    it = {t: i for i, t in enumerate(inst.tecnicos)}
    js = {s: j for j, s in enumerate(inst.turnos)}
    lk = {k: l for l, k in enumerate(inst.tipos)}

    x = {(t, s, k): pulp.LpVariable(f"x_{it[t]}_{js[s]}_{lk[k]}", cat="Binary")
         for t in inst.tecnicos for s in inst.turnos for k in inst.tipos
         if inst.puede_atender(t, s, k)}
    pen = {(s, k, j): p for s in inst.turnos for k in inst.tipos
           for j, p in penalizacion_niveles(inst, s, k).items()}
    w = {(s, k, j): pulp.LpVariable(f"w_{js[s]}_{lk[k]}_{j}", lowBound=0, upBound=1)
         for (s, k, j) in pen}
    v = {(s, k): pulp.LpVariable(f"v_{js[s]}_{lk[k]}", lowBound=0, cat="Integer")
         for s in inst.turnos for k in inst.tipos if inst.minimos[s, k] > 0}

    # Función objetivo: costo de personal + penalizaciones por déficit
    prob += (pulp.lpSum(inst.costo[t, s] * var for (t, s, _), var in x.items())
             + pulp.lpSum(pen[key] * var for key, var in w.items())
             + pulp.lpSum(penalizacion_estable * var for var in v.values()))

    def asignados(s, k):
        """Expresión: técnicos asignados al turno s para el tipo k."""
        return pulp.lpSum(x[t, s, k] for t in inst.tecnicos if (t, s, k) in x)

    # (1) Cobertura de la meta de espera y (1b) estabilidad de cada cola
    for (s, k), m in inst.minimos.items():
        if m == 0:
            continue
        prob += asignados(s, k) + v[s, k] >= m, f"estabilidad_{js[s]}_{lk[k]}"
        niveles = [w[s, k, j] for j in range(m + 1, inst.requeridos[s, k] + 1)]
        if niveles:
            prob += (asignados(s, k) + v[s, k] + pulp.lpSum(niveles) >= inst.requeridos[s, k],
                     f"cobertura_{js[s]}_{lk[k]}")

    for t in inst.tecnicos:
        def trabaja(s):
            """Expresión: 1 si t trabaja el turno s (en cualquier tipo)."""
            return pulp.lpSum(x[t, s, k] for k in inst.tipos if (t, s, k) in x)

        # (2) A lo sumo un turno por día
        for d in inst.dias:
            prob += (pulp.lpSum(trabaja(s) for s in inst.turnos_de(d)) <= 1,
                     f"un_turno_dia_{it[t]}_{d}")

        # (3) Descanso: no trabajar la noche y la mañana siguiente
        for d, d_sig in zip(inst.dias, inst.dias[1:]):
            noche = config.nombre_turno(d, "Noche")
            manana = config.nombre_turno(d_sig, "Mañana")
            if noche in js and manana in js:
                prob += (trabaja(noche) + trabaja(manana) <= 1,
                         f"descanso_{it[t]}_{d}")

        # (4) Carga semanal mínima y máxima
        total = pulp.lpSum(trabaja(s) for s in inst.turnos)
        prob += total >= inst.hmin[t], f"carga_min_{it[t]}"
        prob += total <= inst.hmax[t], f"carga_max_{it[t]}"

    return prob, x, w, v, pen


def resolver(inst: Instancia, tiempo_limite: int = config.TIEMPO_LIMITE_S) -> Resultado:
    """Construye y resuelve el modelo con CBC; organiza la solución en tablas."""
    prob, x, w, v, pen = construir_modelo(inst)
    inicio = time.perf_counter()
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=tiempo_limite))
    tiempo = time.perf_counter() - inicio

    asignacion = pd.DataFrame(
        [{"tecnico": t, "nivel": inst.nivel[t], "dia": inst.info_turno[s][0],
          "franja": inst.info_turno[s][1], "turno": s, "tipo": k,
          "costo_cop": inst.costo[t, s]}
         for (t, s, k), var in x.items() if var.value() is not None and var.value() > 0.5],
        columns=["tecnico", "nivel", "dia", "franja", "turno", "tipo", "costo_cop"])

    asignados = asignacion.groupby(["turno", "tipo"]).size()
    val = lambda var: var.value() or 0
    deficit_meta = {}  # técnicos que faltan frente a r, sumando los niveles w
    for (s, k, _), var in w.items():
        deficit_meta[s, k] = deficit_meta.get((s, k), 0) + val(var)
    filas = []
    for s in inst.turnos:
        for k in inst.tipos:
            c = int(asignados.get((s, k), 0))
            # Desempeño de la cola M/M/c con los técnicos que asignó el modelo
            cola = metricas_mmc(inst.lam[s, k], inst.mu[k], c)
            filas.append({
                "turno": s, "dia": inst.info_turno[s][0], "franja": inst.info_turno[s][1],
                "tipo": k, "lambda_tickets_hora": inst.lam[s, k],
                "minimos": inst.minimos[s, k], "requeridos": inst.requeridos[s, k],
                "asignados": c, "deficit": int(round(deficit_meta.get((s, k), 0))),
                "deficit_estable": int(round(val(v[s, k]))) if (s, k) in v else 0,
                "utilizacion": round(cola["rho"], 4), "wq_min": round(cola["wq_min"], 2),
                "cumple_meta": cola["wq_min"] <= inst.meta_espera_min})
    cobertura = pd.DataFrame(filas)

    por_tecnico = (asignacion.groupby("tecnico")
                   .agg(turnos=("turno", "count"), costo_cop=("costo_cop", "sum"))
                   .reindex(inst.tecnicos, fill_value=0).reset_index())
    por_tecnico.insert(1, "nivel", por_tecnico["tecnico"].map(inst.nivel))

    costo_personal = float(asignacion["costo_cop"].sum())
    costo_deficit = float(sum(pen[key] * val(var) for key, var in w.items())
                          + sum(config.PENALIZACION_ESTABILIDAD * val(var) for var in v.values()))
    return Resultado(
        instancia=inst.nombre, estado=pulp.LpStatus[prob.status],
        costo_total=costo_personal + costo_deficit, costo_personal=costo_personal,
        costo_deficit=costo_deficit, tiempo_s=tiempo,
        n_variables=len(prob.variables()), n_restricciones=len(prob.constraints),
        asignacion=asignacion, cobertura=cobertura, por_tecnico=por_tecnico)


def verificar_solucion(inst: Instancia, res: Resultado) -> list[str]:
    """
    Revisa, de forma independiente al solver, que la solución cumpla todas las
    restricciones. Devuelve la lista de violaciones (vacía si todo está bien).
    """
    errores = []
    a = res.asignacion

    for fila in a.itertuples():
        if not inst.puede_atender(fila.tecnico, fila.turno, fila.tipo):
            errores.append(f"{fila.tecnico} no puede atender {fila.tipo} en {fila.turno}")

    for fila in res.cobertura.itertuples():
        if fila.asignados + fila.deficit_estable + fila.deficit < fila.requeridos:
            errores.append(f"Cobertura insuficiente en {fila.turno}/{fila.tipo}")
        if fila.asignados + fila.deficit_estable < fila.minimos:
            errores.append(f"Estabilidad insuficiente en {fila.turno}/{fila.tipo}")

    for t in inst.tecnicos:
        propios = a[a["tecnico"] == t]
        for d, n in propios.groupby("dia").size().items():
            if n > 1:
                errores.append(f"{t} trabaja {n} turnos el día {d}")
        turnos_t = set(propios["turno"])
        for d, d_sig in zip(inst.dias, inst.dias[1:]):
            if {config.nombre_turno(d, "Noche"), config.nombre_turno(d_sig, "Mañana")} <= turnos_t:
                errores.append(f"{t} no descansa entre {d}-Noche y {d_sig}-Mañana")
        if not inst.hmin[t] <= len(propios) <= inst.hmax[t]:
            errores.append(f"{t} trabaja {len(propios)} turnos (rango {inst.hmin[t]}-{inst.hmax[t]})")

    return errores
