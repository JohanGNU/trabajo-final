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
PENALIZACION_DEFICIT = 1_000_000  # COP por cada técnico que falte en un turno

# --- Parámetros de servicio ----------------------------------------------
RHO_MAX = 0.85               # utilización máxima aceptada por técnico

# --- Solver ---------------------------------------------------------------
TIEMPO_LIMITE_S = 120


def nombre_turno(dia: str, franja: str) -> str:
    """Nombre legible de un turno, p. ej. 'Lun-Mañana'."""
    return f"{dia}-{franja}"


def turnos_semana() -> list[str]:
    """Lista ordenada de los 21 turnos de la semana."""
    return [nombre_turno(d, f) for d in DIAS for f in FRANJAS]
