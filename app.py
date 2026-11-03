"""
Interfaz web (Streamlit) de la mesa de ayuda de TI.

Permite cambiar los parámetros del problema desde el navegador, re-resolver el
modelo MIP, ver las colas M/M/c, simular la semana con SimPy y comparar los
escenarios predefinidos. No repite cálculos: usa las mismas funciones de src/
que main.py, y los gráficos son los de src/reportes.py dibujados en memoria
(la interfaz no escribe archivos en resultados/).

Uso (desde la carpeta del proyecto, con el entorno activado):
    streamlit run app.py
"""
from dataclasses import replace
from io import BytesIO
import math

import streamlit as st

from main import asegurar_datos
from src import config
from src.datos import cargar_instancia, con_demanda
from src.escenarios import (aplicar_ausentismo, barrido_meta_espera, cambiar_carga,
                            cambiar_recargos, correr_escenarios, escalar_demanda,
                            indicadores, usar_regla_carga)
from src.modelo import resolver, verificar_solucion
from src.reportes import (grafico_barrido_meta, grafico_cdf_espera, grafico_cobertura,
                          grafico_cronograma, grafico_escenarios, grafico_espera,
                          grafico_mmc_vs_simulacion, grafico_tecnicos)
from src.simulacion import N_REPLICAS, comparar_por_cola, resumir, simular_plan

REGLA_MMC = "M/M/c (meta de espera)"
REGLA_85 = "Regla 85 % de utilización (sin colas)"

# Valores de los controles que reproducen el escenario base (ver src/config.py y data/)
VALORES_BASE = {
    "meta": int(config.META_ESPERA_MIN),
    "demanda_pct": 100,
    "ausentismo_pct": 0,
    "carga": (3, 5),
    "nocturno_pct": round(config.RECARGO_NOCTURNO * 100),
    "dominical_pct": round(config.RECARGO_DOMINICAL * 100),
    "regla": REGLA_MMC,
    "replicas": N_REPLICAS,
}


# --- Cálculos (en caché: solo se repiten si cambian los parámetros) ------------
def parametros_de(valores: dict) -> tuple:
    """Convierte los valores de los controles en los argumentos de `resolver_plan`."""
    return (valores["meta"], valores["demanda_pct"] / 100, valores["ausentismo_pct"] / 100,
            *valores["carga"], valores["nocturno_pct"] / 100, valores["dominical_pct"] / 100,
            valores["regla"] == REGLA_85)


@st.cache_data(show_spinner="Resolviendo el modelo MIP con CBC...")
def resolver_plan(meta, factor_demanda, ausentismo, hmin, hmax, nocturno, dominical, regla_85):
    """Arma la instancia con los parámetros elegidos (mismas transformaciones que los
    escenarios de src/escenarios.py) y la resuelve. Devuelve (instancia, resultado)."""
    asegurar_datos()
    inst = escalar_demanda(cargar_instancia(), factor_demanda)
    inst = con_demanda(inst, meta_espera_min=meta)
    inst = aplicar_ausentismo(inst, ausentismo)        # con 0 no cambia nada
    inst = cambiar_recargos(inst, nocturno, dominical)
    inst = cambiar_carga(inst, hmin, hmax)
    if regla_85:
        inst = usar_regla_carga(inst)
    inst = replace(inst, nombre="interfaz")
    return inst, resolver(inst)


@st.cache_data(show_spinner="Simulando la semana con SimPy...")
def simular(parametros: tuple, n_replicas: int):
    """Tickets simulados con el plan óptimo de esos parámetros (semilla fija)."""
    inst, res = resolver_plan(*parametros)
    return simular_plan(inst, res, n_replicas)


@st.cache_data(show_spinner="Re-resolviendo los escenarios predefinidos...")
def escenarios_predefinidos():
    """Tabla de los 8 escenarios y barrido de la meta de espera sobre los datos base."""
    asegurar_datos()
    base = cargar_instancia()
    tabla, _ = correr_escenarios(base)
    return tabla, barrido_meta_espera(base)


# --- Ayudas de presentación ----------------------------------------------------
def mostrar_figura(dibujar) -> None:
    """Dibuja un gráfico de src/reportes.py en memoria (PNG) y lo muestra."""
    buf = BytesIO()
    dibujar(buf)
    st.image(buf.getvalue(), width="stretch")


def cop(valor: float) -> str:
    """Pesos colombianos con separador de miles, p. ej. 16 645 750."""
    return f"{valor:,.0f}".replace(",", " ")


def minutos(valor: float) -> str:
    return "inestable" if math.isinf(valor) else f"{valor:.1f}"


def variacion(actual: float, base: float) -> str | None:
    """Cambio porcentual frente a la base (None si no hay cambio o no se puede calcular)."""
    if not (math.isfinite(actual) and math.isfinite(base)) or base == 0 or actual == base:
        return None
    return f"{(actual / base - 1) * 100:+.1f} %"


def restablecer() -> None:
    for clave, valor in VALORES_BASE.items():
        st.session_state[clave] = valor


# --- Página ----------------------------------------------------------------------
st.set_page_config(page_title="Mesa de ayuda de TI", layout="wide")
for clave, valor in VALORES_BASE.items():
    st.session_state.setdefault(clave, valor)

st.title("Mesa de ayuda de TI: turnos y dimensionamiento")
st.caption("Proyecto final de Investigación de Operaciones · Modelo MIP (PuLP + CBC), "
           "colas M/M/c y simulación con SimPy. **Todos los datos son simulados o supuestos.**")

with st.sidebar:
    st.header("Parámetros")
    st.slider("Meta de espera media en cola Wq (min)", 5, 60, step=5, key="meta",
              help="Cada cola (turno, tipo) necesita el menor número de técnicos con Wq ≤ meta.")
    st.slider("Demanda de tickets (% de la base)", 50, 150, step=5, key="demanda_pct")
    st.slider("Ausentismo (% de turnos disponibles que se pierden)", 0, 50, step=5,
              key="ausentismo_pct", help="Se eligen al azar con la semilla fija 42.")
    st.slider("Turnos por técnico a la semana (mínimo y máximo)", 0, 7, key="carga",
              help="Máximo 7: cada técnico trabaja a lo sumo un turno por día.")
    st.number_input("Recargo nocturno (%)", 0, 200, step=5, key="nocturno_pct")
    st.number_input("Recargo dominical (%)", 0, 200, step=5, key="dominical_pct")
    st.radio("Criterio para los técnicos requeridos", [REGLA_MMC, REGLA_85], key="regla")
    st.divider()
    st.slider("Réplicas de la simulación SimPy", 5, 30, step=5, key="replicas")
    st.button("Restablecer valores base", on_click=restablecer, width="stretch")
    st.caption(f"Plantilla fija de 28 técnicos. Semilla {config.SEMILLA}. Los recargos "
               "son supuestos, no se verificaron en la norma vigente.")

valores = {clave: st.session_state[clave] for clave in VALORES_BASE}
parametros = parametros_de(valores)
parametros_base = parametros_de(VALORES_BASE)
es_base = parametros == parametros_base
nombre_plan = "escenario base" if es_base else "escenario elegido"

inst, res = resolver_plan(*parametros)
inst_base, res_base = resolver_plan(*parametros_base)
if res.estado != "Optimal":
    st.error(f"El solver terminó con estado **{res.estado}**: no hay un plan que cumpla las "
             "restricciones con estos parámetros. Prueba con menos ausentismo o con un mínimo "
             "de turnos semanales más bajo.")
    st.stop()
ind, ind_base = indicadores(inst, res), indicadores(inst_base, res_base)

tab_resumen, tab_colas, tab_cronograma, tab_sim, tab_esc = st.tabs(
    ["Resumen", "Cobertura y espera", "Cronograma", "Simulación SimPy", "Escenarios predefinidos"])

with tab_resumen:
    st.subheader(f"Plan óptimo del {nombre_plan}")
    if not es_base:
        st.caption("Las variaciones se miden frente al escenario base.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Costo de personal (COP/semana)", cop(res.costo_personal), border=True,
              delta=variacion(res.costo_personal, res_base.costo_personal), delta_color="inverse")
    dif_meta = ind["colas_cumplen_meta_pct"] - ind_base["colas_cumplen_meta_pct"]
    c2.metric("Colas que cumplen la meta", f"{ind['colas_cumplen_meta_pct']:.1f} %", border=True,
              delta=f"{dif_meta:+.1f} pp" if dif_meta else None,
              help="Variación en puntos porcentuales frente al escenario base.")
    c3.metric("Espera media en cola Wq (min)", minutos(ind["wq_promedio_min"]), border=True,
              delta=variacion(ind["wq_promedio_min"], ind_base["wq_promedio_min"]),
              delta_color="inverse", help="Promedio M/M/c ponderado por las llegadas de tickets.")
    c4, c5, c6 = st.columns(3)
    c4.metric("Técnico-turnos requeridos / asignados",
              f"{ind['requeridos']} / {ind['asignados']}", border=True,
              help=f"Capacidad máxima de la plantilla: {ind['capacidad_max']} técnico-turnos.")
    c5.metric("Déficit (técnico-turnos)", ind["deficit"], border=True,
              help="Técnico-turnos que faltan para que todas las colas cumplan la meta.")
    c6.metric("Función objetivo (COP)", cop(res.costo_total), border=True,
              help="Costo de personal + penalización por déficit.")

    if ind["deficit"]:
        st.warning(f"Con 28 técnicos faltan **{ind['deficit']} técnico-turnos** "
                   f"(unos **{ind['tecnicos_faltantes']} técnicos** más) para que todas las colas "
                   f"cumplan Wq ≤ {inst.meta_espera_min:g} min. El modelo deja el déficit donde "
                   "menos aumenta la espera.")
    else:
        st.success(f"La plantilla alcanza: todas las colas cumplen Wq ≤ {inst.meta_espera_min:g} min.")
    if ind["colas_inestables"]:
        st.error(f"{ind['colas_inestables']} colas quedan inestables (la espera crece sin límite).")

    errores = verificar_solucion(inst, res)
    if errores:
        st.error(f"{len(errores)} restricciones violadas: " + "; ".join(errores[:5]))
    else:
        st.success("Verificación independiente: la solución cumple todas las restricciones.")
    st.caption(f"Solver CBC: {res.estado} en {res.tiempo_s:.2f} s · {res.n_variables} variables · "
               f"{res.n_restricciones} restricciones.")

with tab_colas:
    mostrar_figura(lambda buf: grafico_cobertura(inst, res, buf, plan=nombre_plan))
    mostrar_figura(lambda buf: grafico_espera(inst, res, buf))
    st.subheader("Cobertura por turno y tipo de ticket")
    st.dataframe(res.cobertura, hide_index=True)
    st.download_button("Descargar cobertura (CSV)", res.cobertura.to_csv(index=False),
                       "cobertura.csv", "text/csv")

with tab_cronograma:
    mostrar_figura(lambda buf: grafico_cronograma(inst, res, buf))
    mostrar_figura(lambda buf: grafico_tecnicos(res, buf))
    izq, der = st.columns([3, 2])
    with izq:
        st.subheader("Asignación óptima")
        st.dataframe(res.asignacion, hide_index=True)
        st.download_button("Descargar asignación (CSV)", res.asignacion.to_csv(index=False),
                           "asignacion_optima.csv", "text/csv")
    with der:
        st.subheader("Turnos y costo por técnico")
        st.dataframe(res.por_tecnico, hide_index=True)

with tab_sim:
    st.caption("La semana corre de forma continua: los tickets que no se atienden pasan al turno "
               "siguiente y el técnico saliente termina el ticket que tiene. Por eso la espera "
               "simulada puede diferir de la fórmula M/M/c, que analiza cada turno por separado.")
    tickets = simular(parametros, valores["replicas"])
    tickets_por_plan = {nombre_plan.capitalize(): tickets}
    if not es_base:  # se compara con el plan base simulado con las mismas réplicas
        tickets_por_plan["Escenario base"] = simular(parametros_base, valores["replicas"])
    r = resumir(tickets, inst.meta_espera_min, nombre_plan)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Espera media simulada (min)", f"{r['wq_media_min']:.1f}", border=True,
              help=f"IC 95 %: {r['ic95_inf_min']:.1f} a {r['ic95_sup_min']:.1f} min.")
    c2.metric(f"Tickets que esperan > {inst.meta_espera_min:g} min",
              f"{r['pct_espera_mayor_meta']:.1f} %", border=True)
    c3.metric("Percentil 90 de la espera (min)", f"{r['wq_p90_min']:.1f}", border=True)
    c4.metric("Tickets por semana", f"{r['tickets_por_semana']:.0f}", border=True,
              help=f"Sin atender al cierre de la semana: {r['sin_atender_al_cierre']:.1f} en promedio.")
    mostrar_figura(lambda buf: grafico_cdf_espera(tickets_por_plan, buf, inst.meta_espera_min))
    mostrar_figura(lambda buf: grafico_mmc_vs_simulacion(comparar_por_cola(tickets, res), buf,
                                                         plan=nombre_plan))

with tab_esc:
    st.caption("Escenarios fijos sobre los datos base (no dependen del panel lateral): cada uno "
               "re-resuelve el MIP con datos distintos. El modelo es entero, así que no se usan "
               "precios sombra.")
    tabla, barrido = escenarios_predefinidos()
    st.dataframe(tabla[["escenario", "descripcion", "requeridos", "asignados", "deficit",
                        "colas_cumplen_meta_pct", "wq_promedio_min", "costo_personal_cop",
                        "var_costo_vs_base_pct", "restricciones_ok"]], hide_index=True)
    mostrar_figura(lambda buf: grafico_escenarios(tabla, buf, config.META_ESPERA_MIN))
    st.subheader("Barrido de la meta de espera")
    mostrar_figura(lambda buf: grafico_barrido_meta(barrido, buf))
