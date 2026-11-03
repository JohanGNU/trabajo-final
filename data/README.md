# Datos y supuestos

Los datos son **simulados**. Los genera `generar_datos.py` con
`numpy.random.default_rng(42)`, así que cualquier persona obtiene exactamente los
mismos archivos. Los valores y las distribuciones se definen como constantes al
inicio de `generar_datos.py`.

## Archivos

| Archivo | Contenido |
|---|---|
| `tecnicos.csv` | Técnico, nivel (Junior/Senior), costo base por turno (COP), turnos mínimos y máximos por semana |
| `certificaciones.csv` | 1 si el técnico está certificado en el tipo de ticket |
| `disponibilidad.csv` | 1 si el técnico está disponible en el turno (21 turnos) |
| `demanda.csv` | Tasa de llegada λ (tickets/hora) por turno y tipo |
| `servicio.csv` | Tasa de servicio μ (tickets/hora que atiende un técnico) por tipo |

## Supuestos de generación

| Elemento | Supuesto |
|---|---|
| Técnicos | 28. Cada uno es Senior con probabilidad 0.35 |
| Costo base por turno de 8 h | Junior 95 000 COP, Senior 150 000 COP |
| Recargos (`src/config.py`) | Nocturno +35 %, dominical +75 % (se suman) |
| Carga semanal | Entre 3 y 5 turnos por técnico |
| Certificaciones | Bernoulli(0.45) para Junior y Bernoulli(0.75) para Senior en cada tipo; si no sale ninguna, se asigna una al azar |
| Disponibilidad | Bernoulli(0.85) por técnico y turno |
| Turnos | 7 días × 3 franjas (Mañana, Tarde, Noche) = 21 turnos |
| Tipos de ticket | Redes, Software, Hardware, Accesos |
| λ en la mañana de un día hábil | Redes 2.0, Software 3.5, Hardware 1.5, Accesos 2.5 tickets/h |
| Factor por franja | Mañana 1.0, Tarde 0.8, Noche 0.2 |
| Factor fin de semana | 0.5 (sábado y domingo) |
| Variación aleatoria | λ se multiplica por Uniforme(0.9, 1.1) |
| Hardware de noche | λ = 0: el soporte en sitio no opera de noche |
| μ por técnico | Redes 1.5, Software 2.0, Hardware 1.0, Accesos 3.0 tickets/h |
| Penalización por déficit | 1 000 000 COP por técnico faltante en un turno |

## Técnicos requeridos

`r[s,k] = ceil(λ / (μ · 0.85))`: se necesitan suficientes técnicos para que cada uno no
supere el 85 % de utilización. Más adelante se reemplazará por el modelo de colas
M/M/c (menor número de técnicos que cumpla una meta de tiempo de espera).

## Limitaciones

- Los valores son realistas pero inventados. Si el equipo consigue datos reales de una
  mesa de ayuda, basta con reemplazar los CSV conservando las mismas columnas.
- Se planea una sola semana, sin enlazar el domingo con el lunes siguiente.
