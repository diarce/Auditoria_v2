"""
modules/paginas.py — Obtención ética de páginas y descubrimiento de secciones
============================================================================
PageFetcher obtiene páginas aplicando el protocolo ético (robots.txt,
demora por sitio con Crawl-delay, registro de transparencia).

El descubrimiento de secciones localiza, a partir de la página de inicio,
las páginas donde la Tabla B.2 indica que se relevan los indicadores:
listado de categorías, ficha de producto, formulario de registro y páginas
informativas (envíos, medios de pago, condiciones comerciales).
Solo se siguen enlaces del mismo dominio y solo mediante GET.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import LOGS_DIR, SCRAPING_CONFIG
from modules.ethics import (EthicsLogger, RateLimiter, RobotsChecker, base_de,
                            solicitud_etica)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Pagina:
    """Resultado de solicitar una página."""
    seccion: str
    url: str
    final_url: str = ""
    status: int = 0
    soup: BeautifulSoup | None = None
    html: str = ""
    elapsed_s: float | None = None     # tiempo hasta recibir la respuesta (requests .elapsed)
    bloqueada_por_robots: bool = False
    error: str = ""
    error_ssl: bool = False
    historial: list[int] = field(default_factory=list)   # códigos de redirección previos
    location: str = ""         # cabecera Location (solicitudes sin seguir redirecciones)

    @property
    def redirige_a_https(self) -> bool:
        return self.status in (301, 302, 303, 307, 308) and self.location.lower().startswith("https://")

    @property
    def ok(self) -> bool:
        return self.soup is not None and 200 <= self.status < 400

    @property
    def muro_de_sesion(self) -> bool:
        """La solicitud terminó en una página de inicio de sesión."""
        destino = urlparse(self.final_url or self.url).path.lower()
        return bool(re.search(r"(login|signin|sign-in|iniciar-sesion|ingresar|account/login|"
                              r"customer/account/login|/auth)", destino)) and \
            urlparse(self.final_url).path != urlparse(self.url).path

    def motivo_no_verificable(self) -> str:
        if self.muro_de_sesion:
            return f"{self.seccion}: redirige a inicio de sesión (el protocolo no inicia sesión)"
        if self.bloqueada_por_robots:
            return f"{self.seccion}: bloqueada por robots.txt"
        if self.error_ssl:
            return f"{self.seccion}: error de certificado TLS"
        if self.error:
            return f"{self.seccion}: sin respuesta ({self.error})"
        if self.status >= 400:
            return f"{self.seccion}: HTTP {self.status}"
        if self.soup is None:
            return f"{self.seccion}: sin contenido"
        return ""


# ─────────────────────────────────────────────────────────────────────────────
class PageFetcher:
    """Obtiene páginas de forma ética; un limitador de cadencia por sitio."""

    def __init__(self, cfg: dict = SCRAPING_CONFIG):
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": cfg["user_agent"], **cfg.get("headers", {})})
        self.ethics_log = EthicsLogger(
            LOGS_DIR / f"access_log_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.csv")
        self.robots_checker = RobotsChecker(cfg["user_agent"], session=self.session,
                                            timeout=cfg["timeout_seconds"],
                                            ethics_logger=self.ethics_log)
        self._limitadores: dict[str, RateLimiter] = {}

    def _limitador(self, url: str) -> RateLimiter:
        base = base_de(url)
        if base not in self._limitadores:
            self._limitadores[base] = RateLimiter(
                base_delay=self.cfg["rate_limit_seconds"],
                jitter=self.cfg["rate_limit_jitter"],
                crawl_delay=self.robots_checker.get_crawl_delay(base),
            )
        return self._limitadores[base]

    def obtener(self, url: str, seccion: str = "", allow_redirects: bool = True,
                max_redirecciones: int = 5) -> Pagina:
        """
        GET ético. Las redirecciones se siguen una a una para verificar
        robots.txt también en cada destino (requests no lo haría).
        """
        pag = Pagina(seccion=seccion, url=url)
        actual, tiempo = url, 0.0
        for _ in range(max_redirecciones + 1):
            r = solicitud_etica(actual, self.robots_checker, self._limitador(actual), self.ethics_log,
                                self.session, timeout=self.cfg["timeout_seconds"], allow_redirects=False)
            pag.final_url = actual
            if r.response is None:
                pag.bloqueada_por_robots, pag.error, pag.error_ssl = r.bloqueada_por_robots, r.error, r.error_ssl
                return pag
            resp = r.response
            tiempo += resp.elapsed.total_seconds()
            location = resp.headers.get("Location", "")
            if allow_redirects and resp.status_code in (301, 302, 303, 307, 308) and location:
                pag.historial.append(resp.status_code)
                actual = urljoin(actual, location)
                continue
            pag.status = resp.status_code
            pag.location = location
            pag.elapsed_s = tiempo
            ctype = resp.headers.get("Content-Type", "")
            if "html" in ctype or not ctype:
                if "charset" in ctype.lower():
                    pag.soup = BeautifulSoup(resp.text, "lxml")
                else:   # sin charset declarado: se respeta el <meta charset> del documento
                    pag.soup = BeautifulSoup(resp.content, "lxml")
                pag.html = str(pag.soup)
            return pag
        pag.error = "demasiadas redirecciones"
        return pag

    # Compatibilidad con el scraper de catálogo
    def get(self, url: str) -> BeautifulSoup | None:
        pag = self.obtener(url, "catalogo")
        return pag.soup if pag.ok else None

    def is_allowed(self, url: str) -> bool:
        return self.robots_checker.is_allowed(url)

    def ethics_summary(self) -> dict:
        return self.ethics_log.summary()


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de análisis de HTML
# ─────────────────────────────────────────────────────────────────────────────

def texto(soup: BeautifulSoup | None, incluir_atributos: bool = False) -> str:
    """Texto visible de la página; opcionalmente con alt y title de imágenes y enlaces."""
    if soup is None:
        return ""
    s = BeautifulSoup(str(soup), "lxml")
    for t in s(["script", "style", "noscript", "template"]):
        t.decompose()
    partes = [s.get_text(" ", strip=True)]
    if incluir_atributos:
        for t in s.find_all(["img", "a", "svg"]):
            for attr in ("alt", "title", "aria-label"):
                v = t.get(attr)
                if v:
                    partes.append(str(v))
    return re.sub(r"\s+", " ", " ".join(partes))


def jsonld(soup: BeautifulSoup | None) -> list[dict]:
    """Objetos schema.org declarados en JSON-LD (aplanando @graph y listas)."""
    if soup is None:
        return []
    objetos: list[dict] = []

    def _agregar(o):
        if isinstance(o, list):
            for x in o:
                _agregar(x)
        elif isinstance(o, dict):
            if "@graph" in o:
                _agregar(o["@graph"])
            objetos.append(o)

    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        try:
            _agregar(json.loads(tag.string or tag.get_text() or ""))
        except (json.JSONDecodeError, TypeError):
            continue
    return objetos


def jsonld_tipo(soup: BeautifulSoup | None, tipo: str) -> list[dict]:
    res = []
    for o in jsonld(soup):
        t = o.get("@type")
        tipos = t if isinstance(t, list) else [t]
        if tipo in tipos:
            res.append(o)
    return res


def ofertas_jsonld(soup: BeautifulSoup | None) -> list[dict]:
    res = []
    for prod in jsonld_tipo(soup, "Product"):
        off = prod.get("offers")
        for o in (off if isinstance(off, list) else [off]):
            if isinstance(o, dict):
                res.append(o)
                inner = o.get("offers")
                if isinstance(inner, list):
                    res.extend(x for x in inner if isinstance(x, dict))
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Descubrimiento de secciones
# ─────────────────────────────────────────────────────────────────────────────

_UTILIDAD = re.compile(r"(login|logout|signin|cuenta|account|carrito|cart|checkout|contacto|"
                       r"blog|ayuda|help|wishlist|favoritos|mailto:|tel:|whatsapp|javascript:|"
                       r"facebook|instagram|twitter|tiktok|youtube|linkedin)", re.I)
_CATEGORIA = re.compile(r"/(categorias?|category|categories|c|departamentos?|productos|catalogo|"
                        r"catalog|tienda|shop|rubros?|secci[oó]n|seccion|almacen|bebidas|limpieza|"
                        r"perfumeria|lacteos)(/|$|\?|-)", re.I)
_PRODUCTO = re.compile(r"(/(producto|product|p|articulo|item)/|/p/?$|/p\?|-p\d+|/prod/|\.html$)", re.I)
_REGISTRO_HREF = re.compile(r"(registro|registrar|register|registrate|crear-cuenta|create-account|"
                            r"account/create|signup|sign-up|alta-cliente|nuevo-cliente)", re.I)
_REGISTRO_TXT = re.compile(r"(registr(ate|arse|o)|crear (una )?cuenta|alta de cliente|"
                           r"soy nuevo|quiero ser cliente|nuevo cliente)", re.I)
_CUENTA = re.compile(r"(mi cuenta|ingresar|iniciar sesi[oó]n|login|account|acceder)", re.I)
_INFORMATIVA = re.compile(r"(env[ií]os?|entregas?|despachos?|c[oó]mo[- ]comprar|como-comprar|"
                          r"preguntas|faq|t[eé]rminos|terminos|condiciones|formas?[- ]de[- ]pago|"
                          r"medios?[- ]de[- ]pago|pagos|facturaci[oó]n|facturacion|pol[ií]ticas?|"
                          r"politica|retiro|sucursales|preguntas-frecuentes)", re.I)


def _mismo_dominio(url: str, base: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc


def enlaces(soup: BeautifulSoup | None, base_url: str) -> list[tuple[str, str, object]]:
    """(url absoluta, texto, tag) de enlaces del mismo dominio, sin duplicados."""
    if soup is None:
        return []
    vistos, res = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        url = urljoin(base_url, href).split("#")[0]
        if not url.startswith("http") or not _mismo_dominio(url, base_url):
            continue
        if url in vistos:
            continue
        vistos.add(url)
        res.append((url, a.get_text(" ", strip=True), a))
    return res


def candidatos_listado(inicio: BeautifulSoup | None, base_url: str,
                       selector: str = "") -> tuple[list[str], list[str]]:
    """
    (enlaces que por su forma apuntan a categorías o listados, enlaces de respaldo del menú).
    Los primeros definen si robots.txt bloquea el catálogo; los segundos solo se prueban
    cuando no hay enlaces del primer tipo.
    """
    raiz = urlparse(base_url)._replace(path="/", query="", fragment="").geturl()
    fuertes: list[str] = []
    if selector and inicio is not None:
        for a in inicio.select(selector):
            if a.get("href"):
                fuertes.append(urljoin(base_url, a["href"]).split("#")[0])
    for url, txt, a in enlaces(inicio, base_url):
        if _UTILIDAD.search(url) or url.rstrip("/") == raiz.rstrip("/"):
            continue
        if _CATEGORIA.search(urlparse(url).path):
            fuertes.append(url)
    respaldo: list[str] = []
    if inicio is not None:
        for a in inicio.select("nav a[href], header a[href], [class*='menu'] a[href], "
                               "[class*='categor'] a[href], [class*='department'] a[href]"):
            url = urljoin(base_url, a["href"]).split("#")[0]
            ruta = urlparse(url).path
            if (url.startswith("http") and _mismo_dominio(url, base_url)
                    and not _UTILIDAD.search(url) and url.rstrip("/") != raiz.rstrip("/")
                    and not _PRODUCTO.search(ruta) and not _REGISTRO_HREF.search(url)
                    and not _INFORMATIVA.search(ruta) and not _REGISTRO_TXT.search(a.get_text(" ", strip=True))):
                respaldo.append(url)
    fuertes = list(dict.fromkeys(fuertes))
    return fuertes, [u for u in dict.fromkeys(respaldo) if u not in fuertes]


def candidatos_ficha(listado: BeautifulSoup | None, base_url: str, selector: str = "") -> list[str]:
    res: list[str] = []
    if listado is None:
        return res
    for lista in jsonld_tipo(listado, "ItemList"):
        for el in lista.get("itemListElement") or []:
            u = None
            if isinstance(el, str):
                u = el
            elif isinstance(el, dict):
                u = el.get("url")
                item = el.get("item")
                if not u and isinstance(item, dict):
                    u = item.get("url") or item.get("@id")
                elif not u and isinstance(item, str):
                    u = item
            if isinstance(u, str):
                url = urljoin(base_url, u)
                if _mismo_dominio(url, base_url):
                    res.append(url)
    sel = selector or ("[itemtype*='Product'] a[href], [class*='product'] a[href], "
                       "[class*='Product'] a[href], .product-item a[href], li.item a[href]")
    for a in listado.select(sel):
        url = urljoin(base_url, a["href"]).split("#")[0]
        if url.startswith("http") and _mismo_dominio(url, base_url) and not _UTILIDAD.search(url):
            res.append(url)
    for url, txt, a in enlaces(listado, base_url):
        if _PRODUCTO.search(urlparse(url).path) and not _UTILIDAD.search(url):
            res.append(url)
    return list(dict.fromkeys(res))


def candidatos_registro(inicio: BeautifulSoup | None, base_url: str) -> tuple[list[str], list[str]]:
    """(enlaces explícitos de registro, enlaces de cuenta o ingreso)."""
    registro, cuenta = [], []
    for url, txt, a in enlaces(inicio, base_url):
        etiqueta = " ".join([txt, a.get("title", ""), a.get("aria-label", "")])
        if _REGISTRO_HREF.search(url) or _REGISTRO_TXT.search(etiqueta):
            registro.append(url)
        elif _CUENTA.search(url) or _CUENTA.search(etiqueta):
            cuenta.append(url)
    return list(dict.fromkeys(registro)), list(dict.fromkeys(cuenta))


def candidatos_informativas(inicio: BeautifulSoup | None, base_url: str) -> list[str]:
    res = []
    for url, txt, a in enlaces(inicio, base_url):
        if _INFORMATIVA.search(urlparse(url).path) or _INFORMATIVA.search(txt):
            if not re.search(r"(mailto:|tel:|whatsapp)", url, re.I):
                res.append(url)
    return list(dict.fromkeys(res))


def es_listado(soup: BeautifulSoup | None, base_url: str) -> bool:
    return len(candidatos_ficha(soup, base_url)) >= 3


def es_ficha(soup: BeautifulSoup | None) -> bool:
    if soup is None:
        return False
    if jsonld_tipo(soup, "Product") or soup.select_one("[itemtype*='schema.org/Product']"):
        return True
    t = texto(soup).lower()
    tiene_h1 = soup.find("h1") is not None
    tiene_compra = bool(re.search(r"(agregar al carrito|añadir al carrito|agregar al pedido|comprar)", t))
    tiene_precio = bool(re.search(r"\$\s?\d", t))
    return tiene_h1 and (tiene_compra or tiene_precio)


def es_formulario_registro(soup: BeautifulSoup | None) -> bool:
    """Un formulario con al menos 3 campos visibles de datos personales o comerciales."""
    if soup is None:
        return False
    for form in soup.find_all("form"):
        campos = [i for i in form.find_all(["input", "select"])
                  if (i.get("type") or "text").lower() not in
                  ("hidden", "submit", "button", "image", "reset", "search")]
        if len(campos) >= 3:
            return True
    return False
