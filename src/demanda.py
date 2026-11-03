"""
Cálculo de técnicos requeridos por turno y tipo de ticket (parámetro r[s,k]).

Versión actual: regla de carga. Se necesitan suficientes técnicos para que la
utilización de cada uno no supere RHO_MAX:

    r = ceil( lambda / (mu * RHO_MAX) )

Más adelante (semana 12) esta regla se reemplaza por el modelo de colas M/M/c:
r será el menor número de servidores c que cumpla la meta de tiempo de espera.
La firma de `calcular_requeridos` se mantiene para que el modelo no cambie.
"""
import math

from src.config import RHO_MAX


def tecnicos_requeridos(lam: float, mu: float, rho_max: float = RHO_MAX) -> int:
    """Técnicos necesarios para atender `lam` tickets/h con utilización <= rho_max."""
    if lam <= 0:
        return 0
    # El 1e-9 evita que errores de redondeo sumen un técnico de más
    return math.ceil(lam / (mu * rho_max) - 1e-9)


def calcular_requeridos(lam: dict, mu: dict, rho_max: float = RHO_MAX) -> dict:
    """Devuelve r[(turno, tipo)] para todos los pares de `lam`."""
    return {(s, k): tecnicos_requeridos(l, mu[k], rho_max) for (s, k), l in lam.items()}
