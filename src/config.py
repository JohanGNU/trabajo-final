"""
Configuración global del proyecto.

Todas las rutas son relativas a la carpeta del proyecto (se calculan a partir
de la ubicación de este archivo), así el código corre en cualquier computador
sin modificarlo.
"""
from pathlib import Path

# --- Rutas ---------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[1]
DIR_DATOS = RAIZ / "data"
DIR_RESULTADOS = RAIZ / "resultados"

# --- Reproducibilidad ----------------------------------------------------
SEMILLA = 42

# --- Conjuntos del problema ----------------------------------------------
DIAS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
FRANJAS = ["Mañana", "Tarde", "Noche"]          # turnos de 8 horas
TIPOS = ["Redes", "Software", "Hardware", "Accesos"]
FIN_DE_SEMANA = {"Sab", "Dom"}

# --- Parámetros económicos (supuestos, ver data/README.md) ----------------
RECARGO_NOCTURNO = 0.35      # +35 % sobre el valor del turno
RECARGO_DOMINICAL = 0.75     # +75 % sobre el valor del turno
DIA_DOMINICAL = "Dom"
PENALIZACION_DEFICIT = 1_000_000      # COP base por técnico que falte para cumplir la meta de espera
PENALIZACION_ESTABILIDAD = 10_000_000 # COP por técnico que falte para que la cola sea estable
COSTO_ESPERA_HORA = 20_000            # COP por cada hora que un ticket espera en cola
HORAS_TURNO = 8

# --- Parámetros de servicio ----------------------------------------------
META_ESPERA_MIN = 15         # espera media máxima en cola Wq (minutos), modelo M/M/c
RHO_MAX = 0.85               # regla de carga anterior (solo para comparar)

# --- Solver ---------------------------------------------------------------
TIEMPO_LIMITE_S = 120


def nombre_turno(dia: str, franja: str) -> str:
    """Nombre legible de un turno, p. ej. 'Lun-Mañana'."""
    return f"{dia}-{franja}"


def turnos_semana() -> list[str]:
    """Lista ordenada de los 21 turnos de la semana."""
    return [nombre_turno(d, f) for d in DIAS for f in FRANJAS]
