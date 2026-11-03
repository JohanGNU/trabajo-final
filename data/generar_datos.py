"""
Generador de datos simulados para la mesa de ayuda de TI.

Los datos se generan con una semilla fija (src/config.py -> SEMILLA), por lo que
cualquier persona obtiene exactamente los mismos archivos CSV. Las distribuciones
y los supuestos están documentados en data/README.md.

Uso:  python data/generar_datos.py
"""
from pathlib import Path
import sys

# Permite ejecutar este archivo directamente (python data/generar_datos.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from src.config import (DIAS, DIR_DATOS, FIN_DE_SEMANA, FRANJAS, SEMILLA,
                        TIPOS, nombre_turno, turnos_semana)

# --- Supuestos de generación ----------------------------------------------
N_TECNICOS = 28
PROP_SENIOR = 0.35                                  # P(técnico es senior)
COSTO_BASE = {"Junior": 95_000, "Senior": 150_000}  # COP por turno de 8 h
HMIN, HMAX = 3, 5                                   # turnos por semana
P_CERTIFICACION = {"Junior": 0.45, "Senior": 0.75}  # P(certificado en un tipo)
P_DISPONIBLE = 0.85                                 # P(disponible en un turno)

# Llegadas de tickets (tickets/hora) en la franja de la mañana de un día hábil
LAMBDA_BASE = {"Redes": 2.0, "Software": 3.5, "Hardware": 1.5, "Accesos": 2.5}
FACTOR_FRANJA = {"Mañana": 1.0, "Tarde": 0.8, "Noche": 0.2}
FACTOR_FIN_SEMANA = 0.5
SIN_SERVICIO_NOCTURNO = {"Hardware"}  # soporte en sitio no opera de noche
VARIACION = 0.10                      # lambda * Uniforme(0.9, 1.1)

# Tasa de servicio por técnico (tickets/hora); tiempo medio = 60/mu minutos
MU = {"Redes": 1.5, "Software": 2.0, "Hardware": 1.0, "Accesos": 3.0}


def generar_datos(destino: Path = DIR_DATOS, semilla: int = SEMILLA) -> dict:
    """Genera los CSV de entrada en `destino` y los devuelve como DataFrames."""
    rng = np.random.default_rng(semilla)
    ids = [f"T{i:02d}" for i in range(1, N_TECNICOS + 1)]

    # 1. Técnicos: nivel, costo base y carga semanal permitida
    niveles = np.where(rng.random(N_TECNICOS) < PROP_SENIOR, "Senior", "Junior")
    tecnicos = pd.DataFrame({
        "tecnico": ids,
        "nivel": niveles,
        "costo_base_cop": [COSTO_BASE[n] for n in niveles],
        "hmin": HMIN,
        "hmax": HMAX,
    })

    # 2. Certificaciones (Bernoulli); cada técnico tiene al menos una
    filas = []
    for t, nivel in zip(ids, niveles):
        cert = rng.random(len(TIPOS)) < P_CERTIFICACION[nivel]
        if not cert.any():
            cert[rng.integers(len(TIPOS))] = True
        filas.append({"tecnico": t, **dict(zip(TIPOS, cert.astype(int)))})
    certificaciones = pd.DataFrame(filas)

    # 3. Disponibilidad por turno (Bernoulli)
    turnos = turnos_semana()
    disp = (rng.random((N_TECNICOS, len(turnos))) < P_DISPONIBLE).astype(int)
    disponibilidad = pd.DataFrame(disp, columns=turnos)
    disponibilidad.insert(0, "tecnico", ids)

    # 4. Demanda: tasa de llegada lambda por turno y tipo de ticket
    filas = []
    for dia in DIAS:
        f_dia = FACTOR_FIN_SEMANA if dia in FIN_DE_SEMANA else 1.0
        for franja in FRANJAS:
            for tipo in TIPOS:
                if franja == "Noche" and tipo in SIN_SERVICIO_NOCTURNO:
                    lam = 0.0
                else:
                    ruido = rng.uniform(1 - VARIACION, 1 + VARIACION)
                    lam = LAMBDA_BASE[tipo] * FACTOR_FRANJA[franja] * f_dia * ruido
                filas.append({"dia": dia, "franja": franja,
                              "turno": nombre_turno(dia, franja), "tipo": tipo,
                              "lambda_tickets_hora": round(lam, 3)})
    demanda = pd.DataFrame(filas)

    # 5. Tasa de servicio por tipo de ticket
    servicio = pd.DataFrame({"tipo": list(MU), "mu_tickets_hora": list(MU.values())})

    datos = {"tecnicos": tecnicos, "certificaciones": certificaciones,
             "disponibilidad": disponibilidad, "demanda": demanda,
             "servicio": servicio}
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, df in datos.items():
        df.to_csv(destino / f"{nombre}.csv", index=False, encoding="utf-8")
    return datos


if __name__ == "__main__":
    generar_datos()
    print(f"Datos generados en {DIR_DATOS} (semilla {SEMILLA}).")
