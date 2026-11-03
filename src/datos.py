"""
Carga de datos: convierte los CSV de data/ en una `Instancia` con los conjuntos
y parámetros del modelo matemático.
"""
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src import config
from src.demanda import calcular_requeridos


@dataclass
class Instancia:
    """Conjuntos y parámetros de una instancia del problema."""
    nombre: str
    tecnicos: list          # T
    dias: list
    franjas: list
    tipos: list             # K
    turnos: list            # S (cada turno = día + franja)
    info_turno: dict        # s -> (día, franja)
    nivel: dict             # t -> "Junior" / "Senior"
    costo_base: dict        # t -> COP por turno sin recargos
    costo: dict             # (t, s) -> c_ts, COP por turno (incluye recargos)
    disponible: dict        # (t, s) -> a_ts en {0, 1}
    certificado: dict       # (t, k) -> q_tk en {0, 1}
    lam: dict               # (s, k) -> tickets/hora que llegan
    mu: dict                # k -> tickets/hora que atiende un técnico
    requeridos: dict        # (s, k) -> r_sk, técnicos requeridos
    hmin: dict              # t -> turnos mínimos por semana
    hmax: dict              # t -> turnos máximos por semana

    def turnos_de(self, dia: str) -> list:
        """Turnos (franjas) de un día."""
        return [s for s in self.turnos if self.info_turno[s][0] == dia]

    def puede_atender(self, t: str, s: str, k: str) -> bool:
        """True si el técnico t está disponible en s y certificado en k."""
        return self.disponible[t, s] == 1 and self.certificado[t, k] == 1


def costo_turno(costo_base: float, dia: str, franja: str,
                recargo_nocturno: float = config.RECARGO_NOCTURNO,
                recargo_dominical: float = config.RECARGO_DOMINICAL) -> float:
    """Costo de un turno aplicando recargo nocturno y dominical."""
    factor = 1.0
    if franja == "Noche":
        factor += recargo_nocturno
    if dia == config.DIA_DOMINICAL:
        factor += recargo_dominical
    return round(costo_base * factor)


def cargar_instancia(directorio: Path = config.DIR_DATOS, nombre: str = "base") -> Instancia:
    """Lee los CSV generados por data/generar_datos.py."""
    leer = lambda archivo: pd.read_csv(directorio / archivo, encoding="utf-8")
    df_tec = leer("tecnicos.csv")
    df_cert = leer("certificaciones.csv").set_index("tecnico")
    df_disp = leer("disponibilidad.csv").set_index("tecnico")
    df_dem = leer("demanda.csv")
    df_serv = leer("servicio.csv")

    tecnicos = df_tec["tecnico"].tolist()
    info_turno = {config.nombre_turno(d, f): (d, f)
                  for d in config.DIAS for f in config.FRANJAS}
    turnos = list(info_turno)

    base = dict(zip(df_tec["tecnico"], df_tec["costo_base_cop"]))
    costo = {(t, s): costo_turno(base[t], *info_turno[s]) for t in tecnicos for s in turnos}
    disponible = {(t, s): int(df_disp.at[t, s]) for t in tecnicos for s in turnos}
    certificado = {(t, k): int(df_cert.at[t, k]) for t in tecnicos for k in config.TIPOS}
    lam = {(r.turno, r.tipo): r.lambda_tickets_hora for r in df_dem.itertuples()}
    mu = dict(zip(df_serv["tipo"], df_serv["mu_tickets_hora"]))

    return Instancia(
        nombre=nombre, tecnicos=tecnicos, dias=list(config.DIAS),
        franjas=list(config.FRANJAS), tipos=list(config.TIPOS), turnos=turnos,
        info_turno=info_turno, nivel=dict(zip(df_tec["tecnico"], df_tec["nivel"])),
        costo_base=base, costo=costo, disponible=disponible, certificado=certificado, lam=lam, mu=mu,
        requeridos=calcular_requeridos(lam, mu),
        hmin=dict(zip(df_tec["tecnico"], df_tec["hmin"])),
        hmax=dict(zip(df_tec["tecnico"], df_tec["hmax"])),
    )


def subinstancia(inst: Instancia, dias: list, tipos: list, n_tecnicos: int,
                 hmin: int = 0, nombre: str = "reducida") -> Instancia:
    """
    Versión reducida de una instancia (para verificarla en Excel Solver, que
    admite como máximo 200 variables). Toma los primeros `n_tecnicos` que estén
    certificados en alguno de los `tipos`. Como la instancia cubre pocos días, la
    carga mínima semanal se reemplaza por `hmin` y la máxima por el número de días.
    """
    tecnicos = [t for t in inst.tecnicos
                if any(inst.certificado[t, k] for k in tipos)][:n_tecnicos]
    turnos = [s for s in inst.turnos if inst.info_turno[s][0] in dias]
    lam = {(s, k): inst.lam[s, k] for s in turnos for k in tipos}
    return Instancia(
        nombre=nombre, tecnicos=tecnicos, dias=list(dias), franjas=inst.franjas,
        tipos=list(tipos), turnos=turnos,
        info_turno={s: inst.info_turno[s] for s in turnos},
        nivel={t: inst.nivel[t] for t in tecnicos},
        costo_base={t: inst.costo_base[t] for t in tecnicos},
        costo={(t, s): inst.costo[t, s] for t in tecnicos for s in turnos},
        disponible={(t, s): inst.disponible[t, s] for t in tecnicos for s in turnos},
        certificado={(t, k): inst.certificado[t, k] for t in tecnicos for k in tipos},
        lam=lam, mu={k: inst.mu[k] for k in tipos},
        requeridos={key: inst.requeridos[key] for key in lam},
        hmin={t: hmin for t in tecnicos},
        hmax={t: min(inst.hmax[t], len(dias)) for t in tecnicos},
    )
