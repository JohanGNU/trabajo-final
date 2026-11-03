# Mesa de ayuda de TI: turnos y dimensionamiento

Proyecto final de Investigación de Operaciones (idea 5.1).

El aplicativo asigna técnicos a turnos y tipos de ticket al **menor costo**. Respeta
la disponibilidad de cada técnico, sus certificaciones, el descanso entre turnos y la
carga semanal, y cubre los técnicos que exige la demanda de tickets en cada turno.
El modelo es de Programación Entera (MIP) y se resuelve con PuLP + CBC.

## Requisitos

- **Python 3.13** (probado con 3.13.15; debería funcionar con 3.11 o posterior).
- Librerías con las versiones de `requirements.txt` (PuLP trae incluido el solver CBC,
  no hay que instalar nada más).

## Instalación (Windows, PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

En macOS/Linux, activa el entorno con `source .venv/bin/activate`.

## Ejecución

Desde la carpeta del proyecto, con el entorno activado:

```powershell
python main.py --todo
```

Esto genera los datos (semilla fija = 42), resuelve el modelo base, resuelve la
instancia reducida para Excel Solver, analiza los escenarios, simula la semana con SimPy
y guarda las tablas y los gráficos en `resultados/` (unos 15 segundos). Si `verificacion_solver.xlsx` no existe, también lo crea
(si ya existe no se toca, porque guarda la configuración de Solver).

Para usar el menú interactivo, ejecuta `python main.py`.

### Interfaz web (Streamlit)

```powershell
streamlit run app.py
```

Abre en el navegador (`http://localhost:8501`) un formulario para cambiar los parámetros:
meta de espera, demanda, ausentismo, turnos mínimos y máximos por técnico, recargos y
criterio de técnicos requeridos (M/M/c o regla del 85 %). Con cada cambio re-resuelve el
MIP y muestra los indicadores, el cronograma, las colas M/M/c, la simulación SimPy y los
escenarios predefinidos, con los mismos gráficos de `resultados/`. Usa las mismas
funciones de `src/` que `main.py` y no escribe archivos; el botón «Restablecer valores
base» vuelve a los parámetros del informe. La página solo se abre en este computador
(ver `.streamlit/config.toml`). Para cerrarla, presiona `Ctrl+C` en la terminal.

## Estructura

```text
README.md                 este archivo
requirements.txt          librerías con versiones fijas
main.py                   menú de consola y ejecución completa (--todo)
app.py                    interfaz web con Streamlit (streamlit run app.py)
.streamlit/config.toml    configuración de la interfaz (solo localhost, sin estadísticas)
data/
  generar_datos.py        genera los CSV de entrada (semilla fija)
  README.md               supuestos y distribuciones de los datos
  *.csv                   datos generados
src/
  config.py               rutas, conjuntos y parámetros globales
  datos.py                carga los CSV como una Instancia; crea la instancia reducida
  colas.py                fórmulas M/M/c (Erlang C): espera Wq y técnicos mínimos por meta
  demanda.py              técnicos requeridos r[s,k] (M/M/c) y mínimos estables m[s,k]
  modelo.py               modelo MIP (PuLP), resolución y verificación de restricciones
  escenarios.py           escenarios y barrido de la meta de espera (re-resolución del MIP)
  simulacion.py           simulación SimPy de la semana continua con un plan de turnos
  excel_solver.py         crea el libro de verificación en Excel Solver
  reportes.py             tablas CSV y gráficos matplotlib
resultados/               salidas generadas
verificacion_solver.xlsx  instancia reducida con Solver configurado y comparación con Python
```

## Modelo matemático (resumen)

- **Técnicos requeridos:** cada turno y tipo de ticket es una cola M/M/c; `r[s,k]` es el
  menor número de técnicos con espera media en cola Wq ≤ 15 min, y `m[s,k]` el mínimo para
  que la cola sea estable.
- **Variables:** `x[t,s,k] = 1` si el técnico *t* trabaja el turno *s* atendiendo tickets
  del tipo *k*; `w[s,k,j]` = falta el técnico *j* para cumplir la meta; `v[s,k]` = técnicos
  que faltan para la estabilidad.
- **Objetivo:** minimizar el costo de los turnos (con recargo nocturno y dominical) más las
  penalizaciones por déficit. Faltar el técnico *j* cuesta una base más la espera adicional
  que causa (20 000 COP por hora de espera de un ticket), así que si la plantilla no alcanza
  el déficit queda donde menos aumenta la espera.
- **Restricciones:** cobertura de la meta y de la estabilidad, a lo sumo un turno por día,
  descanso entre la noche y la mañana siguiente, y entre 3 y 5 turnos por semana por técnico.

La formulación completa está en el encabezado de `src/modelo.py`.

## Salidas en `resultados/`

| Archivo | Contenido |
|---|---|
| `asignacion_optima.csv` | Qué técnico trabaja en qué turno y tipo, con su costo |
| `cobertura.csv` | Por turno y tipo: requeridos, asignados, déficit, utilización y espera Wq (M/M/c) |
| `resumen_tecnicos.csv` | Turnos y costo semanal por técnico |
| `fig1_cobertura_por_turno.png` | Requeridos vs. asignados por turno |
| `fig2_carga_costo_tecnicos.png` | Carga y costo por técnico |
| `fig3_cronograma.png` | Cronograma semanal óptimo |
| `fig6_espera_por_turno.png` | Espera media Wq por turno y tipo con el plan óptimo |
| `escenarios_resumen.csv`, `fig4_escenarios.png` | Costo y nivel de servicio de 7 escenarios frente al base |
| `barrido_meta_espera.csv`, `fig5_barrido_meta_espera.png` | Técnicos requeridos y colas que cumplen, con metas de 5 a 60 min |
| `simulacion_resumen.csv`, `fig7_simulacion_espera.png` | Espera simulada (SimPy, 30 réplicas) de los planes Base, E3 y E7 |
| `simulacion_por_cola.csv`, `fig8_mmc_vs_simulacion.png` | Espera por turno y tipo: fórmula M/M/c frente a la simulación |
| `reducida_*.csv` | Instancia reducida (sábado, Redes y Software, 9 técnicos) y su solución, para verificarla en Excel Solver |
