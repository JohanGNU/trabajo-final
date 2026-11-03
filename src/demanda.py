"""
Técnicos requeridos por turno y tipo de ticket.

    r[s,k]  requeridos: menor número de técnicos c que, en una cola M/M/c,
            deja la espera media en cola Wq <= META_ESPERA_MIN.
    m[s,k]  mínimo de estabilidad: menor c con lambda < c * mu. Con menos
            técnicos la cola crece sin límite.

La regla de carga anterior, r = ceil(lambda / (mu * RHO_MAX)), se conserva
solo para comparar (alternativa descartada: ignora el tiempo de espera).
"""
import math

from src.colas import servidores_minimos
from src.config import META_ESPERA_MIN, RHO_MAX


def tecnicos_estables(lam: float, mu: float) -> int:
    """Menor número de técnicos con utilización < 1 (cola estable)."""
    return 0 if lam <= 0 else math.floor(lam / mu) + 1


def tecnicos_regla_carga(lam: float, mu: float, rho_max: float = RHO_MAX) -> int:
    """Regla anterior: utilización por técnico <= rho_max."""
    if lam <= 0:
        return 0
    # El 1e-9 evita que errores de redondeo sumen un técnico de más
    return math.ceil(lam / (mu * rho_max) - 1e-9)


def calcular_requeridos(lam: dict, mu: dict, meta_min: float = META_ESPERA_MIN) -> dict:
    """r[(turno, tipo)] con el criterio M/M/c de espera máxima."""
    return {(s, k): servidores_minimos(l, mu[k], meta_min) for (s, k), l in lam.items()}


def calcular_minimos(lam: dict, mu: dict) -> dict:
    """m[(turno, tipo)]: técnicos mínimos para que cada cola sea estable."""
    return {(s, k): tecnicos_estables(l, mu[k]) for (s, k), l in lam.items()}


def calcular_requeridos_carga(lam: dict, mu: dict, rho_max: float = RHO_MAX) -> dict:
    """r[(turno, tipo)] con la regla de carga anterior (solo para comparar)."""
    return {(s, k): tecnicos_regla_carga(l, mu[k], rho_max) for (s, k), l in lam.items()}
