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
| Meta de espera (`src/config.py`) | Espera media en cola Wq ≤ 15 min |
| Costo de espera | 20 000 COP por hora que un ticket espera en cola |
| Penalización por déficit | 1 000 000 COP base por técnico faltante + su costo de espera; 10 000 000 COP si falta para la estabilidad |

## Técnicos requeridos (colas M/M/c)

Cada par (turno, tipo de ticket) es una cola M/M/c: llegadas Poisson (λ), servicio
exponencial (μ por técnico), c técnicos, disciplina FIFO y estado estable en el turno.

- `r[s,k]`: menor c con espera media en cola Wq ≤ 15 min (fórmula de Erlang C).
- `m[s,k]`: menor c con λ < c·μ; con menos técnicos la cola crece sin límite.

La regla anterior, `ceil(λ / (μ · 0.85))`, se conserva solo como comparación (escenario
E7): es más barata, pero deja una espera media de 43 min.

## Limitaciones

- Los valores son realistas pero inventados. Si el equipo consigue datos reales de una
  mesa de ayuda, basta con reemplazar los CSV conservando las mismas columnas.
- Se planea una sola semana, sin enlazar el domingo con el lunes siguiente.
- M/M/c supone estado estable dentro de cada turno y colas separadas por tipo de ticket.
  La simulación con SimPy (`src/simulacion.py`) corre la semana de forma continua: los
  tickets sin atender pasan al turno siguiente y el técnico saliente termina el ticket que
  tiene. Usa 30 réplicas con semillas 42 a 71.
