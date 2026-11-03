"""
Simulación de eventos discretos (SimPy) de la semana completa con un plan de turnos.

A diferencia del modelo M/M/c, que analiza cada turno por separado y en estado
estable, aquí la semana corre de forma continua (21 turnos de 8 h, 168 h):
    - por cada tipo de ticket hay una cola FIFO compartida entre turnos;
    - los tickets llegan según un proceso de Poisson con la tasa lambda del turno;
    - cada técnico del plan atiende durante su turno con tiempos exponenciales
      (tasa mu); al terminar el turno acaba el ticket que tiene y se retira;
    - los tickets que no alcanzan a atenderse pasan al turno siguiente.
Así se mide el efecto de los traspasos entre turnos (por ejemplo, Hardware, que
no opera de noche) y la variabilidad entre semanas (réplicas con semilla fija).

El simulador se valida con `validar_contra_mmc`: una cola con tasa constante y
técnicos que atienden toda la semana sin cambios de turno es una M/M/c, así que
la espera simulada debe coincidir con la fórmula de Erlang C.
"""
import numpy as np
import pandas as pd
import simpy

from src import config
from src.colas import metricas_mmc
from src.datos import Instancia
from src.modelo import Resultado

N_REPLICAS = 30
N_REPLICAS_VALIDACION = 300


def _llegadas(env, cola, tipo, lam_turno, turnos, rng, registros):
    """Genera los tickets de un tipo, con tasa constante dentro de cada turno."""
    for j, s in enumerate(turnos):
        inicio, fin = j * config.HORAS_TURNO, (j + 1) * config.HORAS_TURNO
        lam = lam_turno[s]
        if lam <= 0:
            continue
        if env.now < inicio:
            yield env.timeout(inicio - env.now)
        t = inicio + rng.exponential(1 / lam)  # Poisson: tiempos entre llegadas exponenciales
        while t < fin:
            yield env.timeout(t - env.now)
            ticket = {"tipo": tipo, "turno": s, "llegada_h": env.now, "inicio_h": None}
            registros.append(ticket)
            yield cola.put(ticket)
            t += rng.exponential(1 / lam)


def _tecnico(env, cola, inicio, fin, mu, rng):
    """Un técnico atiende la cola de su tipo durante [inicio, fin)."""
    if env.now < inicio:
        yield env.timeout(inicio - env.now)
    while env.now < fin:
        pedido = cola.get()
        listo = yield pedido | env.timeout(fin - env.now)
        if pedido not in listo:  # terminó el turno sin tickets en cola
            pedido.cancel()
            return
        ticket = listo[pedido]
        ticket["inicio_h"] = env.now
        yield env.timeout(rng.exponential(1 / mu))


def simular_semana(inst: Instancia, res: Resultado, semilla: int) -> list[dict]:
    """Una réplica de la semana con los técnicos asignados en `res`."""
    rng = np.random.default_rng(semilla)
    env = simpy.Environment()
    asignados = res.cobertura.set_index(["turno", "tipo"])["asignados"]
    registros = []
    for k in inst.tipos:
        cola = simpy.Store(env)
        env.process(_llegadas(env, cola, k, {s: inst.lam[s, k] for s in inst.turnos},
                              inst.turnos, rng, registros))
        for j, s in enumerate(inst.turnos):
            for _ in range(int(asignados[s, k])):
                env.process(_tecnico(env, cola, j * config.HORAS_TURNO,
                                     (j + 1) * config.HORAS_TURNO, inst.mu[k], rng))
    env.run(until=len(inst.turnos) * config.HORAS_TURNO)
    return registros


def _filas_tickets(registros: list[dict], replica: int, fin_h: float) -> list[dict]:
    """Una fila por ticket de una réplica, con su espera en cola en minutos."""
    filas = []
    for t in registros:
        atendido = t["inicio_h"] is not None
        # Un ticket sin atender al cierre de la semana cuenta con la espera que lleva
        espera_h = (t["inicio_h"] if atendido else fin_h) - t["llegada_h"]
        filas.append({"replica": replica, "tipo": t["tipo"], "turno": t["turno"],
                      "espera_min": espera_h * 60, "atendido": atendido})
    return filas


def simular_plan(inst: Instancia, res: Resultado, n_replicas: int = N_REPLICAS,
                 semilla: int = config.SEMILLA) -> pd.DataFrame:
    """Tickets de todas las réplicas, con su espera en cola en minutos."""
    fin_semana = len(inst.turnos) * config.HORAS_TURNO
    filas = []
    for r in range(n_replicas):
        filas += _filas_tickets(simular_semana(inst, res, semilla + r), r, fin_semana)
    return pd.DataFrame(filas)


def validar_contra_mmc(inst: Instancia, turno: str, tipo: str, tecnicos: int,
                       n_replicas: int = N_REPLICAS_VALIDACION,
                       semilla: int = config.SEMILLA) -> dict:
    """
    Valida el simulador frente a la fórmula M/M/c. Toma la tasa lambda de la cola
    (turno, tipo), la mantiene constante toda la semana y pone `tecnicos` técnicos que
    atienden las 168 h sin cambios de turno. Ese sistema es una cola M/M/c, así que la
    espera simulada debe coincidir con la fórmula, salvo el error de muestreo.
    """
    lam, mu = inst.lam[turno, tipo], inst.mu[tipo]
    fin_semana = len(inst.turnos) * config.HORAS_TURNO
    filas = []
    for r in range(n_replicas):
        rng = np.random.default_rng(semilla + r)
        env = simpy.Environment()
        cola, registros = simpy.Store(env), []
        env.process(_llegadas(env, cola, tipo, {s: lam for s in inst.turnos}, inst.turnos,
                              rng, registros))
        for _ in range(tecnicos):
            env.process(_tecnico(env, cola, 0, fin_semana, mu, rng))
        env.run(until=fin_semana)
        filas += _filas_tickets(registros, r, fin_semana)
    sim = resumir(pd.DataFrame(filas), inst.meta_espera_min, f"{turno} {tipo}")
    return {"cola": f"{turno} {tipo}", "lambda_tickets_hora": lam, "mu_tickets_hora": mu,
            "tecnicos": tecnicos, "replicas": n_replicas,
            "wq_simulada_min": sim["wq_media_min"], "ic95_inf_min": sim["ic95_inf_min"],
            "ic95_sup_min": sim["ic95_sup_min"],
            "wq_mmc_min": round(metricas_mmc(lam, mu, tecnicos)["wq_min"], 2)}


def resumir(tickets: pd.DataFrame, meta_min: float, nombre: str) -> dict:
    """Indicadores del plan simulado, con intervalo de confianza del 95 % entre réplicas."""
    por_replica = tickets.groupby("replica")["espera_min"].mean()
    media, error = por_replica.mean(), 1.96 * por_replica.std(ddof=1) / np.sqrt(len(por_replica))
    return {
        "plan": nombre,
        "replicas": int(tickets["replica"].nunique()),
        "tickets_por_semana": round(len(tickets) / tickets["replica"].nunique(), 1),
        "wq_media_min": round(media, 2),
        "ic95_inf_min": round(media - error, 2),
        "ic95_sup_min": round(media + error, 2),
        "wq_p90_min": round(tickets["espera_min"].quantile(0.9), 2),
        "pct_espera_mayor_meta": round(100 * (tickets["espera_min"] > meta_min).mean(), 2),
        "sin_atender_al_cierre": round((~tickets["atendido"]).sum() / tickets["replica"].nunique(), 2),
    }


def comparar_por_cola(tickets: pd.DataFrame, res: Resultado) -> pd.DataFrame:
    """Espera simulada vs. espera M/M/c por (turno, tipo), según el turno de llegada."""
    sim = (tickets.groupby(["turno", "tipo"])["espera_min"].mean()
           .rename("wq_simulada_min").reset_index())
    cob = res.cobertura[res.cobertura["lambda_tickets_hora"] > 0]
    tabla = cob[["turno", "dia", "franja", "tipo", "lambda_tickets_hora", "asignados", "wq_min"]]
    tabla = tabla.rename(columns={"wq_min": "wq_mmc_min"}).merge(sim, on=["turno", "tipo"], how="left")
    tabla["wq_simulada_min"] = tabla["wq_simulada_min"].round(2)
    return tabla
