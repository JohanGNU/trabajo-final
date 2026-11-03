"""
Análisis de escenarios.

El modelo es entero (MIP), así que sus precios sombra no son válidos: la
sensibilidad se mide re-resolviendo el modelo con datos modificados y
comparando costo, cobertura y mezcla de personal frente al escenario base.
"""
from dataclasses import dataclass, replace
from typing import Callable

import numpy as np
import pandas as pd

from src import config
from src.datos import Instancia, costo_turno
from src.demanda import calcular_requeridos
from src.modelo import Resultado, resolver, verificar_solucion


# --- Transformaciones de la instancia -------------------------------------
def escalar_demanda(inst: Instancia, factor: float) -> Instancia:
    """Multiplica las llegadas de tickets y recalcula los técnicos requeridos."""
    lam = {key: l * factor for key, l in inst.lam.items()}
    return replace(inst, lam=lam, requeridos=calcular_requeridos(lam, inst.mu))


def aplicar_ausentismo(inst: Instancia, prob: float, semilla: int = config.SEMILLA) -> Instancia:
    """Cada turno disponible se pierde con probabilidad `prob` (semilla fija)."""
    rng = np.random.default_rng(semilla)
    disponible = {(t, s): int(inst.disponible[t, s] == 1 and rng.random() >= prob)
                  for t in inst.tecnicos for s in inst.turnos}
    return replace(inst, disponible=disponible)


def cambiar_recargos(inst: Instancia, nocturno: float = config.RECARGO_NOCTURNO,
                     dominical: float = config.RECARGO_DOMINICAL) -> Instancia:
    """Recalcula el costo de cada turno con otros recargos."""
    costo = {(t, s): costo_turno(inst.costo_base[t], *inst.info_turno[s], nocturno, dominical)
             for t in inst.tecnicos for s in inst.turnos}
    return replace(inst, costo=costo)


def cambiar_carga(inst: Instancia, hmin: int | None = None, hmax: int | None = None) -> Instancia:
    """Cambia el mínimo y/o máximo de turnos semanales de todos los técnicos."""
    return replace(inst,
                   hmin={t: inst.hmin[t] if hmin is None else hmin for t in inst.tecnicos},
                   hmax={t: inst.hmax[t] if hmax is None else hmax for t in inst.tecnicos})


# --- Definición de escenarios ---------------------------------------------
@dataclass
class Escenario:
    nombre: str
    descripcion: str
    transformar: Callable[[Instancia], Instancia]


ESCENARIOS = [
    Escenario("Base", "Datos originales", lambda i: i),
    Escenario("E1 Demanda +20%", "Temporada alta: llegadas de tickets 20 % mayores",
              lambda i: escalar_demanda(i, 1.20)),
    Escenario("E2 Demanda +40%", "Pico de demanda: llegadas 40 % mayores",
              lambda i: escalar_demanda(i, 1.40)),
    Escenario("E3 Demanda +40% y 6 turnos", "Pico de demanda cubierto con un turno extra por técnico",
              lambda i: cambiar_carga(escalar_demanda(i, 1.40), hmax=6)),
    Escenario("E4 Ausentismo 30%", "Cada turno disponible se pierde con probabilidad 0,30",
              lambda i: aplicar_ausentismo(i, 0.30)),
    Escenario("E5 Dominical 100%", "Recargo dominical sube de 75 % a 100 %",
              lambda i: cambiar_recargos(i, dominical=1.00)),
    Escenario("E6 Sin mínimo semanal", "Se elimina el mínimo contractual de 3 turnos",
              lambda i: cambiar_carga(i, hmin=0)),
]

FACTORES_DEMANDA = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6]


def correr_escenarios(base: Instancia, escenarios: list = ESCENARIOS):
    """Resuelve cada escenario. Devuelve (tabla resumen, {nombre: Resultado})."""
    filas, resultados = [], {}
    for esc in escenarios:
        inst = replace(esc.transformar(base), nombre=esc.nombre)
        res = resolver(inst)
        resultados[esc.nombre] = res
        por_nivel = res.asignacion.groupby("nivel").size()
        filas.append({
            "escenario": esc.nombre,
            "descripcion": esc.descripcion,
            "estado": res.estado,
            "requeridos": int(res.cobertura["requeridos"].sum()),
            "asignados": int(res.cobertura["asignados"].sum()),
            "deficit": int(res.cobertura["deficit"].sum()),
            "turnos_junior": int(por_nivel.get("Junior", 0)),
            "turnos_senior": int(por_nivel.get("Senior", 0)),
            "costo_personal_cop": res.costo_personal,
            "penalizacion_cop": res.costo_deficit,
            "costo_total_cop": res.costo_total,
            "restricciones_ok": not verificar_solucion(inst, res),
        })
    tabla = pd.DataFrame(filas)
    costo_base = tabla.loc[0, "costo_total_cop"]
    tabla["var_vs_base_pct"] = ((tabla["costo_total_cop"] / costo_base - 1) * 100).round(2)
    return tabla, resultados


def barrido_demanda(base: Instancia, factores: list = FACTORES_DEMANDA) -> pd.DataFrame:
    """Re-resuelve el modelo para varios niveles de demanda (punto de quiebre)."""
    capacidad = sum(base.hmax.values())  # técnico-turnos máximos por semana
    filas = []
    for f in factores:
        res = resolver(replace(escalar_demanda(base, f), nombre=f"demanda_{f}"))
        filas.append({
            "factor_demanda": f,
            "requeridos": int(res.cobertura["requeridos"].sum()),
            "asignados": int(res.cobertura["asignados"].sum()),
            "deficit": int(res.cobertura["deficit"].sum()),
            "capacidad_max": capacidad,
            "costo_personal_cop": res.costo_personal,
            "costo_total_cop": res.costo_total,  # incluye penalización por déficit
        })
    return pd.DataFrame(filas)
