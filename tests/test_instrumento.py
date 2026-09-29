"""
Pruebas del instrumento AuditMayorista 6.0.0 contra lo que describe la tesis.
Se ejecutan sin acceder a sitios reales: usan un sitio ficticio servido en 127.0.0.1.

    python -m pytest -q
"""

from __future__ import annotations

import csv
import functools
import http.server
import re
import subprocess
import threading
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import config
from modules import ethics
from modules.indicadores import REGLAS, Contexto
from modules.paginas import Pagina
from modules.storage import AuditResult, DatabaseManager

RAIZ = Path(__file__).resolve().parent.parent
SITIO = Path(__file__).resolve().parent / "sitio_ficticio"

ANEXO_C = ["D1.1", "D1.2", "D1.3", "D1.4", "D1.5", "D2.1", "D2.2", "D2.3", "D2.4",
           "D3.1", "D3.2", "D3.3", "D3.4", "D3.5", "D4.1", "D4.2", "D4.3", "D4.4",
           "D5.1", "D5.2", "D5.3", "D5.4", "D6.1", "D6.2", "D6.3", "D7.1", "D7.2", "D7.3",
           "D8.1", "D8.2", "D8.3", "D8.4"]
MANUALES_B2 = {"D2.4", "D4.3", "D4.4", "D5.1", "D5.4", "D7.1", "D7.2"}
POR_DIMENSION_B1 = {"D1": 5, "D2": 4, "D3": 5, "D4": 4, "D5": 4, "D6": 3, "D7": 3, "D8": 4}


# ─────────────────────────────────────────────────────────────────────────────
# Servidor del sitio ficticio
# ─────────────────────────────────────────────────────────────────────────────
class _Handler(http.server.SimpleHTTPRequestHandler):
    robots = None           # texto alternativo de robots.txt
    redirecciones: dict = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/robots.txt" and self.robots is not None:
            cuerpo = self.robots.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        for prefijo, destino in self.redirecciones.items():
            if self.path.startswith(prefijo):
                self.send_response(302)
                self.send_header("Location", destino)
                self.end_headers()
                return
        super().do_GET()

    def send_error(self, code, message=None, explain=None):
        if code == 404:
            cuerpo = (SITIO / "404.html").read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        super().send_error(code, message, explain)


def _servidor(robots=None, redirecciones=None):
    handler = type("H", (_Handler,), {"robots": robots, "redirecciones": redirecciones or {}})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                          functools.partial(handler, directory=str(SITIO)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


@pytest.fixture(autouse=True)
def _sin_espera_ni_proxy(monkeypatch):
    monkeypatch.setattr(ethics.RateLimiter, "wait", lambda self: None)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


def _auditar(tmp_path, robots=None, redirecciones=None):
    from modules.auditor import AuditEngine
    srv, url = _servidor(robots, redirecciones)
    try:
        db = DatabaseManager(tmp_path / "t.db")
        motor = AuditEngine(db)
        res = motor.run(sites_override=[{"id": "T01", "name": "ficticio", "base_url": url}])["T01"]
        return db, res, motor
    finally:
        srv.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# Correspondencia con el Anexo C y la Tabla B.2
# ─────────────────────────────────────────────────────────────────────────────
def test_32_indicadores_con_ids_del_anexo_c():
    assert list(config.INDICADORES) == ANEXO_C
    assert set(config.INDICADORES_MANUALES) == MANUALES_B2
    assert len(config.INDICADORES_AUTOMATICOS) == 25
    for dim, n in POR_DIMENSION_B1.items():
        assert len(config.QA_TEST_CASES[dim]) == n
    assert config.INDICADORES["D6.3"]["name"].startswith("Factura tipo A")
    assert set(REGLAS) == set(config.INDICADORES_AUTOMATICOS)


def test_fundamentacion_como_tabla_b3():
    from collections import Counter
    c = Counter(tc["fundamentacion"] for tc in config.INDICADORES.values())
    assert c == {"Dire.": 18, "Parc.": 8, "Cont.": 6}


def test_sin_ponderaciones_ni_icc():
    assert all("weight" not in d for d in config.QA_DIMENSIONS.values())
    codigo = "".join(p.read_text(encoding="utf-8") for p in RAIZ.rglob("*.py") if "tests" not in p.parts)
    assert "_calc_icc" not in codigo and "Indice de Calidad Compuesto" not in codigo
    assert config.UMBRAL_TIEMPO_RESPUESTA_S == 4.0


def test_ambito_posadas():
    from modules.universo import cargar_universo, sitios_para_auditar
    u = cargar_universo(RAIZ / "data" / "universo_ejemplo.csv")
    estados = {e.id: e.estado_efectivo for e in u}
    assert estados["EJ004"] == "FUERA_DE_AMBITO"          # Garupá
    assert {s["id"] for s in sitios_para_auditar(u)} == {"EJ001", "EJ002"}


# ─────────────────────────────────────────────────────────────────────────────
# Ausencia de datos identificatorios en el repositorio
# ─────────────────────────────────────────────────────────────────────────────
DOMINIOS_PERMITIDOS = {
    "github.com", "colab.research.google.com", "schema.org", "www.w3.org",
    "www.gnu.org", "gnu.org", "creativecommons.org", "fsf.org", "www.fsf.org", "doi.org",
    "misionesonline.net", "es.wikipedia.org", "streamlit.io", "docs.github.com", "zenodo.org",
    "pypi.org", "www.python.org", "python.org",
}


def _archivos_publicables():
    try:
        salida = subprocess.run(["git", "-C", str(RAIZ), "ls-files", "--cached", "--others",
                                 "--exclude-standard"], capture_output=True, text=True, check=True).stdout
        rutas = [RAIZ / r for r in salida.splitlines()]
    except Exception:
        rutas = [p for p in RAIZ.rglob("*") if p.is_file() and "privado" not in p.parts
                 and "outputs" not in p.parts and ".git" not in p.parts]
    return [p for p in rutas if p.suffix in {".py", ".md", ".csv", ".json", ".ipynb", ".cff",
                                            ".txt", ".html", ".sh", ""} and p.exists()]


def test_sin_urls_de_organizaciones():
    patron = re.compile(r"https?://([a-z0-9.\-]+)", re.I)
    for p in _archivos_publicables():
        if "sitio_ficticio" in p.parts:
            continue
        for dominio in patron.findall(p.read_text(encoding="utf-8", errors="ignore")):
            d = dominio.lower().rstrip(".")
            assert (d in DOMINIOS_PERMITIDOS or d.endswith(".example") or d.endswith(".streamlit.app")
                    or d in {"127.0.0.1", "localhost"}), \
                f"{p.relative_to(RAIZ)} contiene un dominio no permitido: {d}"


def test_documento_de_reglas_actualizado():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", RAIZ / "tools" / "generar_reglas.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert (RAIZ / "docs" / "reglas_de_valoracion.md").read_text(encoding="utf-8") == gen.generar()


def test_carpetas_privadas_ignoradas():
    gi = (RAIZ / ".gitignore").read_text()
    assert "data/privado/*" in gi and "outputs/" in gi


# ─────────────────────────────────────────────────────────────────────────────
# Relevamiento de extremo a extremo sobre el sitio ficticio
# ─────────────────────────────────────────────────────────────────────────────
ESPERADO = {
    "D1.1": 3, "D1.2": 3, "D1.3": 3, "D1.4": 3, "D1.5": 3, "D2.1": 3, "D2.2": 3, "D2.3": 3,
    "D3.1": 3, "D3.2": 3, "D3.3": 3, "D3.4": 3, "D3.5": 3, "D4.1": 3, "D4.2": 3,
    "D5.2": 3, "D5.3": 3, "D6.1": 3, "D6.2": 3, "D6.3": 3, "D7.3": 3,
    "D8.1": 3, "D8.2": 3, "D8.3": 1, "D8.4": 2,
}


def test_relevamiento_completo(tmp_path):
    db, res, motor = _auditar(tmp_path)
    assert not res.excluida
    obtenidos = {k: v.valor for k, v in res.resultados.items()}
    assert obtenidos == ESPERADO, {k: (v.valor, v.nota) for k, v in res.resultados.items()
                                   if ESPERADO.get(k) != v.valor}
    filas = db.get_audit_results("T01")
    assert len(filas) == 25 and all(f["metodo"] == "A" for f in filas)
    assert {f["pagina"] for f in filas} >= {"inicio", "listado", "ficha", "registro", "informativas"}
    # el Crawl-delay declarado (2 s) quedó registrado en el limitador del sitio
    assert any(l.crawl_delay == 2.0 for l in motor.fetcher._limitadores.values())


def test_exclusion_por_robots_en_inicio(tmp_path):
    db, res, _ = _auditar(tmp_path, robots="User-agent: *\nDisallow: /\n")
    assert res.excluida and res.codigo_exclusion == "robots_bloquea_inicio"
    assert db.get_audit_results("T01") == []
    assert db.get_exclusiones()[0]["codigo"] == "robots_bloquea_inicio"


def test_exclusion_por_robots_en_catalogo(tmp_path):
    db, res, _ = _auditar(tmp_path, robots="User-agent: *\nDisallow: /categoria/\nDisallow: /producto/\n")
    assert res.excluida and res.codigo_exclusion == "robots_bloquea_catalogo"


def test_seccion_secundaria_bloqueada_da_cero(tmp_path):
    db, res, _ = _auditar(tmp_path, robots="User-agent: *\nDisallow: /registro/\nDisallow: /cuenta/\n")
    assert not res.excluida
    assert res.resultados["D2.2"].valor == 0 and "robots" in res.resultados["D2.2"].nota


def test_muro_de_sesion_da_cero(tmp_path):
    db, res, _ = _auditar(tmp_path, redirecciones={"/producto/": "/cuenta/login"})
    assert not res.excluida
    for ind in ("D3.1", "D3.2", "D3.4", "D4.1"):
        assert res.resultados[ind].valor == 0, (ind, res.resultados[ind])


def test_relevamiento_reemplaza_solo_valores_automaticos(tmp_path):
    db = DatabaseManager(tmp_path / "t.db")
    db.upsert_site({"id": "T01", "name": "x", "base_url": "http://x.example"})
    db.guardar_resultados([AuditResult("T01", "D2.4", 3, "M")])
    from modules.auditor import AuditEngine
    srv, url = _servidor()
    try:
        AuditEngine(db).run(sites_override=[{"id": "T01", "name": "x", "base_url": url}])
        AuditEngine(db).run(sites_override=[{"id": "T01", "name": "x", "base_url": url}])
    finally:
        srv.shutdown()
    filas = db.get_audit_results("T01")
    assert len(filas) == 26                     # 25 automáticos sin duplicar + 1 manual conservado
    assert [f for f in filas if f["test_case_id"] == "D2.4"][0]["metodo"] == "M"


# ─────────────────────────────────────────────────────────────────────────────
# Reglas de valoración (casos negativos que antes daban «cumple plenamente»)
# ─────────────────────────────────────────────────────────────────────────────
def _pag(seccion, html_body, url="https://x.example/p", **kw):
    soup = BeautifulSoup(f"<html><body><main>{html_body}</main></body></html>", "lxml")
    return Pagina(seccion=seccion, url=url, final_url=kw.pop("final_url", url),
                  status=kw.pop("status", 200), soup=soup, **kw)


FORM = "<form><input name='a'><input name='b'><input name='c'></form>"


@pytest.mark.parametrize("ind,seccion,html_body,esperado", [
    ("D3.2", "ficha", "<h1>X</h1><p>Precio por unidad: $1.200</p>", 1),
    ("D3.5", "ficha", "<h1>X</h1><p>Oferta de la semana en yerba</p>", 1),
    ("D3.5", "ficha", "<h1>X</h1><p>Promo 3x2 en gaseosas</p>", 2),
    ("D2.3", "registro", FORM + "<p>Bienvenido a nuestra tienda mayorista</p>", 2),
    ("D2.3", "registro", FORM, 1),
    ("D6.3", "informativas", "<p>Emitimos factura B a consumidor final</p>", 1),
    ("D6.3", "informativas", "<p>Enviamos la factura a nombre de la empresa</p>", 1),
    ("D6.3", "informativas", "<p>Emitimos Factura «A» y B</p>", 3),
    ("D6.3", "informativas", "<p>Precios con IVA discriminado</p>", 2),
    ("D6.1", "informativas", "<p>Formas de pago</p>", 1),
    ("D6.1", "informativas", "<p>Pagá con Mercado Pago</p>", 2),
    ("D6.2", "informativas", "<p>Colaboramos con el banco de alimentos</p>", 1),
])
def test_reglas_casos_puntuales(ind, seccion, html_body, esperado):
    ctx = Contexto(base_url="https://x.example")
    pag = _pag(seccion, html_body)
    if seccion == "informativas":
        ctx.informativas = [pag]
    else:
        setattr(ctx, seccion, pag)
    assert REGLAS[ind](ctx).valor == esperado


def test_pagina_no_observada_da_cero():
    ctx = Contexto(base_url="https://x.example")
    for ind in ("D1.4", "D3.1", "D3.5", "D4.1", "D8.4", "D2.2"):
        r = REGLAS[ind](ctx)
        assert r.valor == 0 and r.nota
    bloqueada = Pagina(seccion="ficha", url="https://x.example/p", bloqueada_por_robots=True)
    ctx.ficha = bloqueada
    assert REGLAS["D3.1"](ctx).valor == 0
    ctx.informativas = []
    assert REGLAS["D6.1"](ctx).valor == 0


def test_precio_detras_de_sesion_da_cero():
    ctx = Contexto(base_url="https://x.example",
                   ficha=_pag("ficha", "<h1>Yerba</h1><p>Iniciá sesión para ver los precios</p>"))
    assert REGLAS["D3.1"](ctx).valor == 0


def test_umbral_tiempo_respuesta():
    ctx = Contexto(base_url="https://x.example", inicio=_pag("inicio", "<nav></nav>", elapsed_s=4.0))
    assert REGLAS["D8.1"](ctx).valor == 3
    ctx.inicio.elapsed_s = 4.01
    assert REGLAS["D8.1"](ctx).valor == 1


def test_https_con_redireccion_real():
    ctx = Contexto(base_url="https://x.example", inicio=_pag("inicio", "", url="https://x.example/"))
    ctx.http_inicio = Pagina(seccion="http", url="http://x.example/", status=301,
                             location="https://x.example/")
    assert REGLAS["D8.3"](ctx).valor == 3
    ctx.http_inicio = Pagina(seccion="http", url="http://x.example/", status=200)
    assert REGLAS["D8.3"](ctx).valor == 2
    ctx.inicio = Pagina(seccion="inicio", url="https://x.example/", error="SSLError", error_ssl=True)
    assert REGLAS["D8.3"](ctx).valor == 1


# ─────────────────────────────────────────────────────────────────────────────
# Verificación manual, concordancia, informes y demo
# ─────────────────────────────────────────────────────────────────────────────
def test_importador_manual(tmp_path):
    import pandas as pd
    from modules.importer import AuditImporter
    db = DatabaseManager(tmp_path / "t.db")
    db.upsert_site({"id": "S1", "name": "x", "base_url": ""})
    db.upsert_site({"id": "S2", "name": "y", "base_url": ""})
    db.registrar_exclusion("S2", "robots_bloquea_inicio")
    df = pd.DataFrame([
        {"site_id": "S1", "test_case_id": "D4.3", "compliance": "3", "auditor": "DA"},
        {"site_id": "S1", "test_case_id": "D7.2", "compliance": "0"},
        {"site_id": "S1", "test_case_id": "D3.1", "compliance": "3"},    # automático: rechazado
        {"site_id": "S1", "test_case_id": "D9.9", "compliance": "3"},    # inexistente
        {"site_id": "S1", "test_case_id": "D5.1", "compliance": "5"},    # fuera de escala
        {"site_id": "S2", "test_case_id": "D4.3", "compliance": "2"},    # plataforma excluida
    ])
    res = AuditImporter(db, log_fn=lambda *a, **k: None).from_dataframe(df)
    assert res["insertadas"] == 2 and res["omitidas"] == 4
    filas = db.get_audit_results()
    assert {f["test_case_id"] for f in filas} == {"D4.3", "D7.2"} and all(f["metodo"] == "M" for f in filas)


def test_kappa_coincide_con_scikit_learn():
    sk = pytest.importorskip("sklearn.metrics")
    from modules.concordancia import kappa_cohen
    a = [3, 3, 2, 1, 0, 3, 2, 2, 1, 3, 1, 2, 3, 0, 2]
    b = [3, 2, 2, 1, 0, 3, 2, 3, 1, 3, 2, 2, 3, 1, 2]
    assert abs(kappa_cohen(a, b) - sk.cohen_kappa_score(a, b)) < 1e-9
    assert abs(kappa_cohen(a, b, "cuadratica")
               - sk.cohen_kappa_score(a, b, weights="quadratic", labels=[0, 1, 2, 3])) < 1e-9


def test_flujo_de_concordancia(tmp_path):
    from modules.concordancia import calcular_concordancia, generar_muestra_control, importar_control
    db, res, _ = _auditar(tmp_path)
    ruta = generar_muestra_control(db, n=10, semilla=1, destino=tmp_path / "m.csv")
    filas = list(csv.DictReader(ruta.open(encoding="utf-8-sig")))
    assert "compliance" not in filas[0]                  # codificación ciega
    auto = {(r["site_id"], r["test_case_id"]): r["compliance"] for r in db.get_audit_results()}
    for f in filas:
        f["valor_manual"] = auto[(f["site_id"], f["test_case_id"])]
    with ruta.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    assert importar_control(db, ruta, "codificador 1") == len(filas)
    assert calcular_concordancia(db)["acuerdo"] == 1.0


def test_informe_y_exportacion_anonimos(tmp_path):
    from modules.reporter import HTMLReporter
    db, res, _ = _auditar(tmp_path)
    html = HTMLReporter(db, output_dir=tmp_path).build_html()
    assert "Sitio Auditado 1" in html
    assert "127.0.0.1" not in html and "ficticio" not in html
    assert "ICC" not in html and "Índice de Calidad" not in html
    assert "DATOS SIMULADOS" not in html
    for p in db.export_anonimizado(tmp_path / "csv"):
        texto = p.read_text(encoding="utf-8")
        assert "127.0.0.1" not in texto and "ficticio" not in texto and "T01" not in texto


def test_demo_rotulada_separada_y_reproducible(tmp_path, monkeypatch):
    from modules import demo
    from modules.reporter import HTMLReporter
    monkeypatch.setattr(demo, "DB_DEMO_PATH", tmp_path / "demo_simulada.db")
    db1 = demo.run_demo(DatabaseManager(tmp_path / "demo_simulada.db"))
    v1 = [(r["site_id"], r["test_case_id"], r["compliance"]) for r in db1.get_audit_results()]
    db2 = demo.run_demo(DatabaseManager(tmp_path / "demo_simulada.db"))
    v2 = [(r["site_id"], r["test_case_id"], r["compliance"]) for r in db2.get_audit_results()]
    assert v1 == v2 and len(v1) == 3 * 32
    assert db1.origenes() == {"simulado"}
    html = HTMLReporter(db1, output_dir=tmp_path).build_html()
    assert "DATOS SIMULADOS" in html
    with pytest.raises(ValueError):
        demo.run_demo(DatabaseManager(tmp_path / "observados.db"))


def test_relevamiento_de_productos(tmp_path):
    from modules.scraper import ScrapingEngine
    srv, url = _servidor()
    try:
        db = DatabaseManager(tmp_path / "s.db")
        ScrapingEngine(db).run(sites_override=[{"id": "T01", "name": "t", "base_url": url, "selectors": {}}])
    finally:
        srv.shutdown()
    assert {p["name"] for p in db.get_products()} == {"Yerba 1 kg", "Fideos 500 g"}
