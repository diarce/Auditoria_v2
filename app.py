"""
app.py — Interfaz Streamlit de AuditMayorista (uso local del investigador)
=========================================================================
  - Columna izquierda : selección de plataformas, parámetros y ejecución
  - Columna derecha   : resultados según la sección 7.4.2 (sin índice agregado)

Los sitios se toman de data/privado/universo.csv (no publicado). La base de
demostración (datos simulados) está separada de la base de datos observados.

Ejecución:  streamlit run app.py
"""

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Configuración de página ────────────────────────────────────────────────────
st.set_page_config(
    page_title = "AuditMayorista — Herramienta Académica",
    page_icon  = "📋",
    layout     = "wide",
    initial_sidebar_state = "collapsed",
)

# ── Estilos: presentación académica ───────────────────────────────────────────
st.markdown("""
<style>
/* Ocultar sidebar y botón de colapso */
section[data-testid="stSidebar"]        { display: none; }
[data-testid="collapsedControl"]        { display: none; }

/* Tipografía base */
html, body, [class*="css"] {
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 14px;
    color: #1a1a1a;
}

/* Contenedor principal */
.block-container {
    padding-top: 1.4rem !important;
    padding-bottom: 2rem !important;
    max-width: 1280px;
}

/* Encabezado de página */
.pag-titulo {
    border-bottom: 2px solid #1a1a2e;
    padding-bottom: 8px;
    margin-bottom: 4px;
    font-size: 18px;
    font-weight: bold;
    letter-spacing: .01em;
}
.pag-subtitulo {
    font-size: 12px;
    color: #555;
    font-style: italic;
    margin-bottom: 16px;
}

/* Encabezados de grupo en columna izquierda */
.grupo {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: .09em;
    text-transform: uppercase;
    color: #1a1a2e;
    border-bottom: 1px solid #1a1a2e;
    padding-bottom: 3px;
    margin: 18px 0 10px 0;
}

/* Línea divisoria de sección en columna derecha */
.res-seccion {
    font-size: 13px;
    font-weight: bold;
    border-bottom: 1px solid #888;
    padding-bottom: 3px;
    margin: 0 0 10px 0;
    color: #1a1a2e;
}

/* Estado del proceso */
.estado-ok  { color: #155724; font-size: 12px; font-family: monospace; }
.estado-pen { color: #856404; font-size: 12px; font-family: monospace; }

/* Empresa en lista */
.empresa-item {
    font-size: 12px;
    padding: 4px 0;
    border-bottom: 1px dotted #ccc;
    line-height: 1.4;
}
.empresa-url { color: #555; font-style: italic; font-size: 11px; }

/* Aviso de anonimización */
.aviso-anon {
    font-size: 11px;
    font-style: italic;
    color: #555;
    border-left: 3px solid #888;
    padding-left: 8px;
    margin: 8px 0;
}

/* Log monoespaciado */
.log-pre {
    font-family: monospace;
    font-size: 11px;
    background: #f5f5f5;
    border: 1px solid #ccc;
    padding: 10px;
    max-height: 340px;
    overflow-y: auto;
    white-space: pre-wrap;
    line-height: 1.5;
}

/* Nota metodológica */
.nota-met {
    font-size: 11px;
    color: #444;
    background: #f9f9f9;
    border: 1px solid #ddd;
    padding: 8px 10px;
    margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES Y ESTADO
# ══════════════════════════════════════════════════════════════════════════════
from config import (DB_DEMO_PATH, DB_PATH, INDICADORES, INDICADORES_MANUALES,  # noqa: E402
                    QA_DIMENSIONS, RESEARCH_CONTEXT, VERSION)

DIMS_LABEL = {d: f"{d} · {v['name']}" for d, v in QA_DIMENSIONS.items()}
COMPLIANCE_TEXTO = {3: "Pleno", 2: "Parcial", 1: "No cumple", 0: "N/A"}
BASES = {"Datos observados": "observada", "Demostración (DATOS SIMULADOS)": "demo"}


def init_state():
    defaults = {
        "companies": [], "audit_done": False, "audit_log": [],
        "selected_dims": list(DIMS_LABEL.keys()), "rate_limit": 3.0, "max_products": 50,
        "panel": "qa", "base": "observada",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


def db_activa():
    from modules.storage import DatabaseManager
    return DatabaseManager(DB_DEMO_PATH if st.session_state.base == "demo" else DB_PATH)


# ══════════════════════════════════════════════════════════════════════════════
# LOG
# ══════════════════════════════════════════════════════════════════════════════
class StreamlitLogHandler(logging.Handler):
    def emit(self, record):
        icons = {logging.DEBUG: "·", logging.INFO: "ℹ", logging.WARNING: "⚠", logging.ERROR: "✗"}
        st.session_state.audit_log.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] {icons.get(record.levelno, '·')} {self.format(record)}")


def install_log_handler():
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, StreamlitLogHandler)]
    h = StreamlitLogHandler()
    h.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root.addHandler(h)
    root.setLevel(logging.INFO)


def add_log(msg: str, level: str = "INFO"):
    icons = {"INFO": "ℹ", "OK": "✓", "WARN": "⚠", "ERR": "✗"}
    st.session_state.audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {icons.get(level, '·')} {msg}")
    st.session_state.audit_log = st.session_state.audit_log[-300:]


# ══════════════════════════════════════════════════════════════════════════════
# ACCIONES
# ══════════════════════════════════════════════════════════════════════════════
def build_runtime_sites() -> list:
    return [{"id": c["id"], "name": c["name"], "base_url": c["base_url"],
             "platform": c.get("platform", ""), "region": c.get("region", ""),
             "selectors": c.get("selectors", {})}
            for c in st.session_state.companies if c.get("base_url", "").startswith("http")]


def _aplicar_parametros():
    import config
    config.SCRAPING_CONFIG["rate_limit_seconds"] = max(1.0, float(st.session_state.rate_limit))
    config.SCRAPING_CONFIG["max_products_per_site"] = st.session_state.max_products


def _run_demo():
    st.session_state.audit_log = []
    install_log_handler()
    add_log("Modo demostración: se generan DATOS SIMULADOS en una base separada.", "WARN")
    try:
        from modules.demo import run_demo
        run_demo()
        st.session_state.base = "demo"
        st.session_state.audit_done = True
        st.session_state.panel = "qa"
        add_log("Base de demostración lista. Los informes la rotulan como simulada.", "OK")
    except Exception as exc:
        add_log(f"Error en demo: {exc}", "ERR")
        add_log(traceback.format_exc(), "ERR")
    st.rerun()


def _run_audit():
    sites = build_runtime_sites()
    if not sites:
        st.error("Agregue al menos una plataforma con URL válida.")
        return
    st.session_state.audit_log = []
    install_log_handler()
    _aplicar_parametros()
    st.session_state.base = "observada"
    add_log(f"Auditoría automatizada — {len(sites)} plataforma(s).", "INFO")
    try:
        from modules.auditor import DESCRIPCION_EXCLUSION, AuditEngine
        res = AuditEngine(db_activa()).run(dimension_filter=st.session_state.get("selected_dims") or None,
                                           sites_override=sites)
        for sid, r in res.items():
            if r.excluida:
                add_log(f"{sid}: EXCLUIDA — {DESCRIPCION_EXCLUSION[r.codigo_exclusion]}", "WARN")
            else:
                add_log(f"{sid}: {len(r.resultados)} indicadores automáticos valorados.", "OK")
        st.session_state.audit_done = True
        st.session_state.panel = "qa"
    except Exception as exc:
        add_log(f"Error: {exc}", "ERR")
        add_log(traceback.format_exc(), "ERR")
    st.rerun()


def _run_scraping():
    sites = build_runtime_sites()
    if not sites:
        st.error("Agregue al menos una plataforma con URL válida.")
        return
    st.session_state.audit_log = []
    install_log_handler()
    _aplicar_parametros()
    st.session_state.base = "observada"
    try:
        from modules.scraper import ScrapingEngine
        ScrapingEngine(db_activa()).run(snapshot_number=1, sites_override=sites)
        add_log("Relevamiento de productos finalizado. Las páginas bloqueadas por robots.txt no se consultan.", "OK")
    except Exception as exc:
        add_log(f"Error: {exc}", "ERR")
        add_log(traceback.format_exc(), "ERR")
    st.session_state.panel = "log"
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# COLUMNA IZQUIERDA
# ══════════════════════════════════════════════════════════════════════════════
def _grupo_muestra():
    st.markdown('<div class="grupo">1. Plataformas a auditar</div>', unsafe_allow_html=True)
    from modules.universo import cargar_universo, empresas_auditables, resumen_universo, usa_datos_de_ejemplo
    st.caption(f"Ámbito: {RESEARCH_CONTEXT['ambito']}.")
    universo = cargar_universo()
    if usa_datos_de_ejemplo():
        st.warning("No existe data/privado/universo.csv: se muestran registros de EJEMPLO ficticios.")
    c = resumen_universo(universo)
    st.caption(" · ".join(f"{k}: {n}" for k, n in c.most_common()))

    for e in empresas_auditables(universo):
        ya = any(x["id"] == e.id for x in st.session_state.companies)
        col_e, col_b = st.columns([4, 1])
        col_e.markdown(f'<div class="empresa-item"><b>{e.id}</b> · {e.nombre}'
                       f'<br><span class="empresa-url">{e.url_principal}</span></div>', unsafe_allow_html=True)
        if col_b.button("Agregar" if not ya else "(agregada)", key=f"add_{e.id}", disabled=ya):
            st.session_state.companies.append({"id": e.id, "name": e.nombre, "base_url": e.url_principal,
                                               "platform": e.plataforma_cms, "region": e.ciudad})
            st.rerun()

    with st.expander("Agregar una plataforma manualmente"):
        with st.form("form_manual", clear_on_submit=True):
            name = st.text_input("Nombre (uso interno)")
            base_url = st.text_input("URL del sitio", placeholder="https://")
            ok = st.form_submit_button("Agregar")
        if ok:
            if not base_url.startswith("http"):
                st.error("La URL debe comenzar con http:// o https://")
            else:
                st.session_state.companies.append({"id": f"USR{len(st.session_state.companies) + 1:03d}",
                                                   "name": name or base_url, "base_url": base_url.rstrip("/")})
                st.rerun()

    if st.session_state.companies:
        st.caption(f"Seleccionadas: {len(st.session_state.companies)}")
        for i, c in enumerate(st.session_state.companies):
            col_n, col_b = st.columns([5, 1])
            col_n.markdown(f'<div class="empresa-item"><b>{c["id"]}</b> · {c["name"]}</div>',
                           unsafe_allow_html=True)
            if col_b.button("X", key=f"rm_{i}"):
                st.session_state.companies.pop(i)
                st.rerun()


def _grupo_parametros():
    st.markdown('<div class="grupo">2. Parámetros</div>', unsafe_allow_html=True)
    st.session_state.selected_dims = st.multiselect(
        "Dimensiones a relevar", options=list(DIMS_LABEL), default=st.session_state.selected_dims,
        format_func=lambda d: DIMS_LABEL[d])
    st.session_state.rate_limit = st.slider(
        "Demora base entre solicitudes a un mismo sitio (s)", 1.0, 10.0, st.session_state.rate_limit, 0.5,
        help="Si robots.txt declara un Crawl-delay mayor, se usa ese valor.")
    st.session_state.max_products = st.slider("Máx. productos por sitio (relevamiento de productos)",
                                              10, 200, st.session_state.max_products, 10)
    st.markdown(
        '<div class="nota-met">El sistema consulta robots.txt antes de cada solicitud. Si robots.txt no '
        'autoriza la página de inicio, el listado o la ficha de producto, la plataforma se excluye y la '
        'exclusión se informa como resultado (sección 7.4). Las páginas secundarias bloqueadas y las que '
        'exigen iniciar sesión se valoran 0 (no verificable).</div>', unsafe_allow_html=True)


def _grupo_ejecucion():
    st.markdown('<div class="grupo">3. Ejecución</div>', unsafe_allow_html=True)
    ok = bool(st.session_state.companies)
    if st.button("Iniciar auditoría automatizada", type="primary", width="stretch", disabled=not ok):
        _run_audit()
    if st.button("Relevar productos del catálogo", width="stretch", disabled=not ok):
        _run_scraping()
    st.write("")
    if st.button("Generar demostración (DATOS SIMULADOS)", width="stretch"):
        _run_demo()
    st.caption("La demostración usa una base separada y plataformas ficticias. No produce resultados citables.")


# ══════════════════════════════════════════════════════════════════════════════
# COLUMNA DERECHA
# ══════════════════════════════════════════════════════════════════════════════
def _aviso_simulado(db):
    if "simulado" in db.origenes():
        st.error("⚠ DATOS SIMULADOS — esta base proviene del modo demostración. No son observaciones reales.")


def _panel_qa():
    st.markdown('<div class="res-seccion">Resultados de la auditoría</div>', unsafe_allow_html=True)
    from modules.auditor import DESCRIPCION_EXCLUSION
    from modules.reporter import DatosInforme
    db = db_activa()
    _aviso_simulado(db)
    d = DatosInforme(db)
    if not d.results and not d.exclusiones:
        st.info("Sin datos en esta base. Ejecute la auditoría.")
        return

    usar_anon = st.toggle("Presentación anónima (modo publicación)", value=True)
    nombres = {s["id"]: f'{s["id"]} · {s["name"]}' for s in d.sites}
    rotulo = (lambda sid: d.alias.get(sid, sid)) if usar_anon else (lambda sid: nombres.get(sid, sid))

    if d.exclusiones:
        st.markdown("**Plataformas excluidas (sección 7.4)**")
        st.dataframe(pd.DataFrame([{
            "Plataforma": d.alias_excl[e["site_id"]] if usar_anon else nombres.get(e["site_id"], e["site_id"]),
            "Motivo": DESCRIPCION_EXCLUSION.get(e["codigo"], e["codigo"])} for e in d.exclusiones]),
            hide_index=True, width="stretch")

    if d.por_sitio:
        st.markdown("**Puntaje por dimensión S<sub>i,k</sub>** (promedio de valores > 0; sin índice agregado)",
                    unsafe_allow_html=True)
        filas = []
        for sid in d.auditados:
            fila = {"Plataforma": rotulo(sid)}
            for dim in DIMS_LABEL:
                s = d.por_sitio[sid].get(dim)
                fila[dim] = s["avg_compliance"] if s and s["avg_compliance"] is not None else None
            filas.append(fila)
        st.dataframe(pd.DataFrame(filas).style.format({k: "{:.2f}" for k in DIMS_LABEL}, na_rep="nd"),
                     hide_index=True, width="stretch")
        st.markdown('<div class="nota-met">Escala ordinal: 3 pleno · 2 parcial · 1 no cumple · 0 no aplica o no '
                    'verificable (excluido del promedio). «nd»: sin valores válidos. La comparación entre '
                    'plataformas se hace por perfiles (sección 7.4.2).</div>', unsafe_allow_html=True)

        sid_sel = st.selectbox("Detalle de la plataforma", options=d.auditados, format_func=rotulo)
        filas = [{"ID": r["test_case_id"], "Indicador": r["test_case_name"], "Método": r["metodo"],
                  "Valor": r["compliance"], "Resultado": COMPLIANCE_TEXTO[r["compliance"]],
                  "Nota": r["notes"] or "", "Evidencia (uso interno)": "" if usar_anon else (r["evidence"] or "")}
                 for r in d.results if r["site_id"] == sid_sel]
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        faltan = [i for i in INDICADORES_MANUALES
                  if not any(r["site_id"] == sid_sel and r["test_case_id"] == i for r in d.results)]
        if faltan:
            st.caption(f"Indicadores manuales pendientes de carga: {', '.join(faltan)}")


def _panel_visualizaciones():
    import streamlit.components.v1 as components
    from modules.reporter import CSS, DatosInforme, html_detalle, svg_distribucion, svg_perfiles
    db = db_activa()
    _aviso_simulado(db)
    d = DatosInforme(db)
    if not d.results:
        st.info("Sin datos en esta base.")
        return

    def _render(titulo, cuerpo, alto):
        st.markdown(f'<div class="res-seccion">{titulo}</div>', unsafe_allow_html=True)
        pagina = (f"<!DOCTYPE html><html><head>{CSS}</head><body class='viz-root' "
                  f"style='background:transparent'>{cuerpo}</body></html>")
        if hasattr(st, "iframe"):          # Streamlit ≥ 1.5x
            st.iframe(pagina, height=alto)
        else:
            components.html(pagina, height=alto, scrolling=True)

    _render("Distribución de las cuatro categorías por dimensión", svg_distribucion(d.results), 320)
    _render("Comparación de perfiles por dimensión", svg_perfiles(d.por_sitio, d.alias), 340)
    _render("Detalle por indicador", html_detalle(d.results, d.alias), 900)


def _panel_log():
    st.markdown('<div class="res-seccion">Registro de ejecución</div>', unsafe_allow_html=True)
    if not st.session_state.audit_log:
        st.info("El registro se completa al ejecutar la auditoría.")
        return
    st.markdown(f'<div class="log-pre">{chr(10).join(st.session_state.audit_log[-120:])}</div>',
                unsafe_allow_html=True)


def _panel_manual():
    st.markdown('<div class="res-seccion">Verificación manual y concordancia</div>', unsafe_allow_html=True)
    from modules.concordancia import calcular_concordancia, generar_muestra_control, importar_control
    from modules.importer import AuditImporter, generar_plantilla_csv
    db = db_activa()
    _aviso_simulado(db)
    ids = sorted({r["site_id"] for r in db.get_audit_results()})
    st.markdown(f"**Indicadores manuales ({len(INDICADORES_MANUALES)})**: "
                + ", ".join(f"{i} {INDICADORES[i]['name']}" for i in INDICADORES_MANUALES))
    if st.button("Generar plantilla de verificación manual"):
        ruta = generar_plantilla_csv(ids)
        st.download_button("Descargar plantilla", ruta.read_bytes(), file_name=ruta.name, mime="text/csv")
    subido = st.file_uploader("Cargar verificación manual (CSV)", type=["csv"], key="up_manual")
    if subido is not None and st.button("Importar verificación manual"):
        res = AuditImporter(db, log_fn=lambda *a, **k: None).from_dataframe(
            pd.read_csv(subido, dtype=str, keep_default_na=False), subido.name)
        st.success(f"{res['insertadas']} valores cargados; {res['omitidas']} filas omitidas.")
        for e in res["errores"][:10]:
            st.caption(e)

    st.divider()
    st.markdown("**Control de concordancia** (codificación manual ciega de una muestra de valores automáticos)")
    col1, col2 = st.columns(2)
    n = col1.number_input("Tamaño de la muestra", 5, 200, 40)
    semilla = col2.number_input("Semilla", 0, 10**6, 2026)
    if st.button("Generar muestra de control"):
        try:
            ruta = generar_muestra_control(db, int(n), int(semilla))
            st.download_button("Descargar muestra", ruta.read_bytes(), file_name=ruta.name, mime="text/csv")
        except ValueError as exc:
            st.error(str(exc))
    control = st.file_uploader("Cargar codificación de control (CSV)", type=["csv"], key="up_control")
    codificador = st.text_input("Codificador")
    if control is not None and st.button("Importar codificación de control"):
        tmp = Path(DB_PATH).parent / f"_control_{datetime.now():%Y%m%d%H%M%S}.csv"
        tmp.write_bytes(control.getvalue())
        st.success(f"{importar_control(db, tmp, codificador)} valores de control cargados.")
        tmp.unlink(missing_ok=True)
    r = calcular_concordancia(db)
    if r["n"]:
        fk = lambda k: "—" if k is None else f"{k:.2f}"  # noqa: E731
        st.write(f"n = {r['n']} · acuerdo = {r['acuerdo']:.1%} · κ = {fk(r['kappa'])} · "
                 f"κ ponderado = {fk(r['kappa_ponderado'])}")


def _panel_exportar():
    st.markdown('<div class="res-seccion">Exportación</div>', unsafe_allow_html=True)
    from config import CSV_DIR
    from modules.reporter import HTMLReporter
    db = db_activa()
    _aviso_simulado(db)
    if st.button("Generar informe HTML", width="stretch"):
        ruta = HTMLReporter(db).generate()
        st.download_button("Descargar informe HTML", ruta.read_text(encoding="utf-8"), file_name=ruta.name,
                           mime="text/html", width="stretch")
    if st.button("Exportar CSV anonimizados", width="stretch"):
        for ruta in db.export_anonimizado(CSV_DIR):
            st.download_button(f"Descargar {ruta.name}", ruta.read_bytes(), file_name=ruta.name,
                               mime="text/csv", key=ruta.name)
    st.markdown('<div class="nota-met">El informe HTML y los CSV anonimizados usan alias y no incluyen URL, '
                'nombres ni evidencias. La base local conserva los datos identificatorios para uso interno y '
                'no debe publicarse.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# COMPOSICIÓN
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="pag-titulo">AuditMayorista — auditoría digital del desarrollo funcional del '
            'comercio electrónico mayorista</div>', unsafe_allow_html=True)
st.markdown(f'<div class="pag-subtitulo">Versión {VERSION} · {RESEARCH_CONTEXT["ambito"]} · '
            f'tiendas mayoristas de bienes de consumo masivo</div>', unsafe_allow_html=True)

col_izq, col_der = st.columns([2, 3], gap="large")
with col_izq:
    _grupo_muestra()
    _grupo_parametros()
    _grupo_ejecucion()

with col_der:
    etiqueta_base = st.radio("Base de datos", list(BASES), horizontal=True,
                             index=list(BASES.values()).index(st.session_state.base))
    st.session_state.base = BASES[etiqueta_base]
    vistas = {"Resultados": "qa", "Visualizaciones": "viz", "Manual y concordancia": "manual",
              "Registro": "log", "Exportar": "exportar"}
    actual = st.session_state.get("panel", "qa")
    sel = st.radio("Sección", list(vistas), index=list(vistas.values()).index(actual) if actual in
                   vistas.values() else 0, horizontal=True, label_visibility="collapsed")
    st.session_state.panel = vistas[sel]
    st.divider()
    {"qa": _panel_qa, "viz": _panel_visualizaciones, "manual": _panel_manual,
     "log": _panel_log, "exportar": _panel_exportar}[st.session_state.panel]()
