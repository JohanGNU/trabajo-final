"""
Teoría de colas M/M/c (Erlang C).

Cada par (turno, tipo de ticket) se modela como una cola M/M/c independiente:
    - llegadas Poisson con tasa lambda (tickets/hora)
    - tiempos de servicio exponenciales con tasa mu (tickets/hora por técnico)
    - c servidores = técnicos asignados a ese tipo en ese turno
Supuestos: población infinita, capacidad infinita, disciplina FIFO y estado
estable dentro de cada turno de 8 horas.
"""
import math

INFINITO = math.inf


def erlang_c(c: int, a: float) -> float:
    """
    Probabilidad de que un ticket tenga que esperar, P(Wq > 0).
    `a` = lambda/mu es la carga ofrecida; requiere c > a (sistema estable).
    Se calcula con la recursión de Erlang B, que es numéricamente estable.
    """
    b = 1.0
    for n in range(1, c + 1):
        b = a * b / (n + a * b)
    rho = a / c
    return b / (1 - rho * (1 - b))


def metricas_mmc(lam: float, mu: float, c: int) -> dict:
    """Indicadores de una cola M/M/c. Tiempos en minutos."""
    if lam <= 0:
        return {"rho": 0.0, "p_espera": 0.0, "wq_min": 0.0, "w_min": 0.0, "lq": 0.0}
    if c <= 0 or lam >= c * mu:  # inestable: la cola crece sin límite
        return {"rho": lam / (c * mu) if c > 0 else INFINITO, "p_espera": 1.0,
                "wq_min": INFINITO, "w_min": INFINITO, "lq": INFINITO}
    pw = erlang_c(c, lam / mu)
    wq = pw / (c * mu - lam)                 # horas en cola
    return {"rho": lam / (c * mu), "p_espera": pw, "wq_min": wq * 60,
            "w_min": (wq + 1 / mu) * 60, "lq": lam * wq}


def servidores_minimos(lam: float, mu: float, meta_wq_min: float, c_max: int = 100) -> int:
    """Menor número de técnicos c con espera media en cola Wq <= meta (minutos)."""
    if lam <= 0:
        return 0
    c = math.floor(lam / mu) + 1  # mínimo para que el sistema sea estable
    while metricas_mmc(lam, mu, c)["wq_min"] > meta_wq_min:
        c += 1
        if c > c_max:
            raise ValueError(f"Meta de espera inalcanzable con {c_max} técnicos (lambda={lam})")
    return c
