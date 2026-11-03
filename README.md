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
instancia reducida para Excel Solver, analiza los escenarios y guarda las tablas y los
gráficos en `resultados/`. Si `verificacion_solver.xlsx` no existe, también lo crea
(si ya existe no se toca, porque guarda la configuración de Solver).

Para usar el menú interactivo, ejecuta `python main.py`.

## Estructura

```text
README.md                 este archivo
requirements.txt          librerías con versiones fijas
main.py                   menú de consola y ejecución completa (--todo)
data/
  generar_datos.py        genera los CSV de entrada (semilla fija)
  README.md               supuestos y distribuciones de los datos
  *.csv                   datos generados
src/
  config.py               rutas, conjuntos y parámetros globales
  datos.py                carga los CSV como una Instancia; crea la instancia reducida
  demanda.py              técnicos requeridos r[s,k] por turno y tipo
  modelo.py               modelo MIP (PuLP), resolución y verificación de restricciones
  escenarios.py           escenarios y barrido de demanda (re-resolución del MIP)
  excel_solver.py         crea el libro de verificación en Excel Solver
  reportes.py             tablas CSV y gráficos matplotlib
resultados/               salidas generadas
verificacion_solver.xlsx  instancia reducida con Solver configurado y comparación con Python
```

## Modelo matemático (resumen)

- **Variables:** `x[t,s,k] = 1` si el técnico *t* trabaja el turno *s* atendiendo tickets
  del tipo *k*; `u[s,k]` = técnicos que faltan (déficit, penalizado).
- **Objetivo:** minimizar el costo de los turnos (con recargo nocturno y dominical) más la
  penalización por déficit.
- **Restricciones:** cobertura de los técnicos requeridos, a lo sumo un turno por día,
  descanso entre la noche y la mañana siguiente, y entre 3 y 5 turnos por semana por técnico.

La formulación completa está en el encabezado de `src/modelo.py`.

## Salidas en `resultados/`

| Archivo | Contenido |
|---|---|
| `asignacion_optima.csv` | Qué técnico trabaja en qué turno y tipo, con su costo |
| `cobertura.csv` | Técnicos requeridos vs. asignados por turno y tipo |
| `resumen_tecnicos.csv` | Turnos y costo semanal por técnico |
| `fig1_cobertura_por_turno.png` | Requeridos vs. asignados por turno |
| `fig2_carga_costo_tecnicos.png` | Carga y costo por técnico |
| `fig3_cronograma.png` | Cronograma semanal óptimo |
| `escenarios_resumen.csv`, `fig4_escenarios_costo.png` | Costo, cobertura y déficit de 6 escenarios frente al base |
| `barrido_demanda.csv`, `fig5_barrido_demanda.png` | Cobertura y costo con la demanda de +0 % a +60 % |
| `reducida_*.csv` | Instancia reducida (sábado, Redes y Software, 10 técnicos) y su solución, para verificarla en Excel Solver |
