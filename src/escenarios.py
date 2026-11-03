"""
Análisis de escenarios.

El modelo es entero (MIP), así que sus precios sombra no son válidos: la
sensibilidad se mide re-resolviendo el modelo con datos modificados y
comparando costo, cobertura, déficit y espera frente al escenario base.
"""
from dataclasses import dataclass, replace
from typing import Callable
import math

import numpy as np
import pandas as pd

from src import config
from src.datos import Instancia, con_demanda, costo_turno
from src.demanda import calcular_requeridos_carga
from src.modelo import Resultado, resolver, verificar_solucion


# --- Transformaciones de la instancia -------------------------------------
def escalar_demanda(inst: Instancia, factor: float) -> Instancia:
    """Multiplica las llegadas de tickets y recalcula los técnicos requeridos."""
    return con_demanda(inst, lam={key: l * factor for key, l in inst.lam.items()})


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


def usar_regla_carga(inst: Instancia) -> Instancia:
    """Requeridos con la regla anterior (utilización <= 85 %), sin colas."""
    return replace(inst, requeridos=calcular_requeridos_carga(inst.lam, inst.mu))


# --- Definición de escenarios ---------------------------------------------
@dataclass
class Escenario:
    nombre: str
    descripcion: str
    transformar: Callable[[Instancia], Instancia]


ESCENARIOS = [
    Escenario("Base", f"28 técnicos, meta Wq <= {config.META_ESPERA_MIN} min", lambda i: i),
    Escenario("E1 Demanda +20%", "Temporada alta: llegadas de tickets 20 % mayores",
              lambda i: escalar_demanda(i, 1.20)),
    Escenario("E2 Ausentismo 30%", "Cada turno disponible se pierde con probabilidad 0,30",
              lambda i: aplicar_ausentismo(i, 0.30)),
    Escenario("E3 Hasta 6 turnos", "Un turno extra por técnico (máximo 6 por semana)",
              lambda i: cambiar_carga(i, hmax=6)),
    Escenario("E4 Meta 30 min", "Servicio menos exigente: espera media de hasta 30 min",
              lambda i: con_demanda(i, meta_espera_min=30)),
    Escenario("E5 Dominical 100%", "Recargo dominical sube de 75 % a 100 %",
              lambda i: cambiar_recargos(i, dominical=1.00)),
    Escenario("E6 Sin mínimo semanal", "Se elimina el mínimo contractual de 3 turnos",
              lambda i: cambiar_carga(i, hmin=0)),
    Escenario("E7 Regla 85% (sin colas)", "Requeridos con utilización <= 85 %, sin M/M/c",
              usar_regla_carga),
]

METAS_ESPERA_MIN = [5, 10, 15, 20, 30, 45, 60]


def indicadores(inst: Instancia, res: Resultado) -> dict:
    """Indicadores de servicio y costo de una solución."""
    cob = res.cobertura[res.cobertura["lambda_tickets_hora"] > 0]
    capacidad = sum(inst.hmax.values())
    deficit = int(cob["deficit"].sum())
    # Espera media ponderada por las llegadas; infinita si alguna cola es inestable
    wq = cob["wq_min"]
    wq_prom = (float((cob["lambda_tickets_hora"] * wq).sum() / cob["lambda_tickets_hora"].sum())
               if np.isfinite(wq).all() else math.inf)
    return {
        "requeridos": int(cob["requeridos"].sum()),
        "asignados": int(cob["asignados"].sum()),
        "capacidad_max": capacidad,
        "deficit": deficit,
        # técnicos adicionales equivalentes, cada uno trabajando su máximo semanal
        "tecnicos_faltantes": math.ceil(deficit / max(inst.hmax.values())),
        "colas_inestables": int((cob["wq_min"] == math.inf).sum()),
        "colas_cumplen_meta_pct": round(100 * cob["cumple_meta"].mean(), 1),
        "wq_promedio_min": round(wq_prom, 2),
        "costo_personal_cop": res.costo_personal,
    }


def correr_escenarios(base: Instancia, escenarios: list = ESCENARIOS):
    """Resuelve cada escenario. Devuelve (tabla resumen, {nombre: Resultado})."""
    filas, resultados = [], {}
    for esc in escenarios:
        inst = replace(esc.transformar(base), nombre=esc.nombre)
        res = resolver(inst)
        resultados[esc.nombre] = res
        filas.append({"escenario": esc.nombre, "descripcion": esc.descripcion,
                      "estado": res.estado, **indicadores(inst, res),
                      "restricciones_ok": not verificar_solucion(inst, res)})
    tabla = pd.DataFrame(filas)
    costo_base = tabla.loc[0, "costo_personal_cop"]
    tabla["var_costo_vs_base_pct"] = ((tabla["costo_personal_cop"] / costo_base - 1) * 100).round(2)
    return tabla, resultados


def barrido_meta_espera(base: Instancia, metas: list = METAS_ESPERA_MIN) -> pd.DataFrame:
    """Re-resuelve el modelo para varias metas de espera (servicio vs. costo)."""
    filas = []
    for meta in metas:
        inst = replace(con_demanda(base, meta_espera_min=meta), nombre=f"meta_{meta}")
        filas.append({"meta_espera_min": meta, **indicadores(inst, resolver(inst))})
    return pd.DataFrame(filas)
