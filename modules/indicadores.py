"""
modules/indicadores.py — Reglas de valoración de los 25 indicadores automáticos
===============================================================================
Cada función recibe el contexto de páginas relevadas de una plataforma y
devuelve un Resultado en la escala 0-3 de la sección 7.4:
  3 cumple plenamente · 2 cumple parcialmente · 1 no cumple ·
  0 no aplica o no verificable.

Regla general: si la página donde se releva el indicador (Tabla B.2) no se
pudo observar —no existe, está bloqueada por robots.txt, no responde o exige
iniciar sesión—, el valor es 0 y la nota registra el motivo. Nunca se
confunde la imposibilidad de observar con el incumplimiento.

Las reglas específicas están en config.QA_TEST_CASES[...]["regla"] y en
docs/reglas_de_valoracion.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from config import UMBRAL_TIEMPO_RESPUESTA_S
from modules.paginas import (Pagina, _CATEGORIA, enlaces, es_formulario_registro,
                             jsonld_tipo, ofertas_jsonld, texto)


# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Resultado:
    valor: int                 # 0..3
    evidencia: str = ""        # uso interno (no se publica)
    nota: str = ""             # motivo, en términos genéricos

    def __post_init__(self):
        assert self.valor in (0, 1, 2, 3)


@dataclass
class Contexto:
    base_url: str
    inicio: Pagina | None = None
    listado: Pagina | None = None
    ficha: Pagina | None = None
    registro: Pagina | None = None
    registro_explicito: bool = False
    hay_acceso_cuenta: bool = False
    informativas: list[Pagina] = field(default_factory=list)
    inexistente: Pagina | None = None
    http_inicio: Pagina | None = None
    notas: dict[str, str] = field(default_factory=dict)   # motivo por sección no observada


def _nv(ctx: Contexto, pag: Pagina | None, seccion: str) -> Resultado | None:
    """Devuelve 0 (no verificable) si la página de la sección no es observable."""
    if pag is None:
        return Resultado(0, nota=ctx.notas.get(seccion, f"{seccion}: no se identificó la página"))
    motivo = pag.motivo_no_verificable()
    if motivo:
        return Resultado(0, nota=motivo)
    return None


def _principal(soup: BeautifulSoup) -> BeautifulSoup:
    """Copia de la página sin cabecera, pie ni navegación (contenido principal)."""
    s = BeautifulSoup(str(soup), "lxml")
    for t in s.select("header, footer, nav, script, style, noscript, template"):
        t.decompose()
    return s


def _primero(soup: BeautifulSoup, selectores: list[str]):
    for sel in selectores:
        el = soup.select_one(sel)
        if el is not None:
            return sel, el
    return None, None


_PRECIO = re.compile(r"\$\s?\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?|\$\s?\d+")
_MURO_PRECIO = re.compile(
    r"((inici[aá]|ingres[aá]|logue[aá]|registr[aá])\w*\s+(sesi[oó]n\s+)?.{0,30}?(para|y)\s+"
    r"(ver|conocer|acceder\s+a)\s+(los\s+|el\s+|nuestros\s+)?precios?"
    r"|precios?\s+(s[oó]lo\s+)?(visibles?\s+)?(para|a)\s+(clientes|usuarios|comercios)\s+registrados"
    r"|(ver|conocer)\s+(los\s+)?precios?\s+(mayoristas\s+)?(requiere|exige)"
    r"|inici[aá]\s+sesi[oó]n\s+para\s+comprar)", re.I)


def _muro_precio(pag: Pagina) -> bool:
    return bool(_MURO_PRECIO.search(texto(pag.soup)))


# ═════════════════════════════════════════════════════════════════════════════
# D1 — Estructura y navegación
# ═════════════════════════════════════════════════════════════════════════════

def d1_1(ctx: Contexto) -> Resultado:
    if (r := _nv(ctx, ctx.inicio, "inicio")):
        return r
    sel, el = _primero(ctx.inicio.soup, ["header nav", "nav", "[role='navigation']",
                                         "header [class*='menu' i]", "#main-nav", ".nav-menu"])
    return Resultado(3, f"selector {sel}") if el else Resultado(1, nota="sin elemento de navegación")


def d1_2(ctx: Contexto) -> Resultado:
    if (r := _nv(ctx, ctx.inicio, "inicio")):
        return r
    sel, el = _primero(ctx.inicio.soup, [
        "input[type='search']", "form[role='search']", "input[name='q']", "input[name='s']",
        "input[name*='search' i]", "input[name*='buscar' i]", "input[name*='busca' i]",
        "input[placeholder*='busc' i]", "input[placeholder*='search' i]", "input[aria-label*='busc' i]",
    ])
    return Resultado(3, f"selector {sel}") if el else Resultado(1, nota="sin campo de búsqueda")


def d1_3(ctx: Contexto) -> Resultado:
    if (r := _nv(ctx, ctx.inicio, "inicio")):
        return r
    soup = ctx.inicio.soup
    sel, menu = _primero(soup, ["[class*='category-menu' i]", "[class*='categoryMenu' i]",
                                "[class*='category-tree' i]", "[class*='departments' i]",
                                "[class*='menu-categor' i]", "[class*='categorias' i]"])
    n_menu = len(menu.find_all("a", href=True)) if menu is not None else 0
    n_links = sum(1 for url, _, _ in enlaces(soup, ctx.base_url)
                  if _CATEGORIA.search(re.sub(r"^https?://[^/]+", "", url)))
    if (menu is not None and n_menu >= 3) or n_links >= 3:
        return Resultado(3, f"menú de categorías ({n_menu} enlaces) / {n_links} enlaces a categorías")
    if n_links >= 1 or n_menu >= 1:
        return Resultado(2, f"{max(n_links, n_menu)} enlace(s) a categorías")
    return Resultado(1, nota="sin enlaces a categorías")


def d1_4(ctx: Contexto) -> Resultado:
    if (r := _nv(ctx, ctx.ficha, "ficha")):
        return r
    soup = ctx.ficha.soup
    if jsonld_tipo(soup, "BreadcrumbList"):
        return Resultado(3, "schema.org BreadcrumbList")
    sel, el = _primero(soup, ["nav[aria-label*='breadcrumb' i]", "nav[aria-label*='miga' i]",
                              "[class*='breadcrumb' i]", "[itemtype*='BreadcrumbList']",
                              "[class*='migas' i]"])
    return Resultado(3, f"selector {sel}") if el else Resultado(1, nota="sin migas de pan")


_ORDEN_OPC = re.compile(r"(menor precio|mayor precio|precio (ascendente|descendente)|ordenar|"
                        r"relevancia|m[aá]s vendidos|nombre\s*(a-z|z-a)|novedades)", re.I)


def d1_5(ctx: Contexto) -> Resultado:
    if (r := _nv(ctx, ctx.listado, "listado")):
        return r
    soup = ctx.listado.soup
    _, orden = _primero(soup, ["select[name*='sort' i]", "select[name*='orden' i]",
                               "select[name*='order' i]", "[class*='orderBy' i]",
                               "[class*='sort' i]", "[class*='ordenar' i]"])
    if orden is None:
        for s in soup.find_all("select"):
            if _ORDEN_OPC.search(s.get_text(" ", strip=True)):
                orden = s
                break
    if orden is None and re.search(r"ordenar\s+por", texto(soup), re.I):
        orden = True
    _, filtro = _primero(soup, ["[class*='filter' i]", "[class*='filtro' i]", "[class*='facet' i]",
                                "[class*='refine' i]", "[class*='filtrar' i]"])
    if filtro is None and re.search(r"filtrar\s+por", texto(soup), re.I):
        filtro = True
    n = int(orden is not None) + int(filtro is not None)
    ev = f"ordenamiento={'sí' if orden is not None else 'no'}, filtros={'sí' if filtro is not None else 'no'}"
    return Resultado({2: 3, 1: 2, 0: 1}[n], ev, "" if n == 2 else ev)


# ═════════════════════════════════════════════════════════════════════════════
# D2 — Registro y autenticación
# ═════════════════════════════════════════════════════════════════════════════

def d2_1(ctx: Contexto) -> Resultado:
    if (r := _nv(ctx, ctx.inicio, "inicio")):
        return r
    if ctx.registro_explicito:
        return Resultado(3, "enlace explícito de registro")
    if ctx.hay_acceso_cuenta:
        return Resultado(2, "solo acceso a cuenta o ingreso", "sin enlace explícito de registro")
    return Resultado(1, nota="sin acceso a registro ni a cuenta")


def _registro_observable(ctx: Contexto) -> Resultado | None:
    if (r := _nv(ctx, ctx.registro, "registro")):
        return r
    if not es_formulario_registro(ctx.registro.soup):
        return Resultado(0, nota="registro: no se identificó un formulario de registro público")
    return None


_CUIT = re.compile(r"\bc\.?\s?u\.?\s?i\.?\s?[tl]\b|cuit|cuil", re.I)


def d2_2(ctx: Contexto) -> Resultado:
    if (r := _registro_observable(ctx)):
        return r
    soup = ctx.registro.soup
    for i in soup.find_all(["input", "select"]):
        atributos = " ".join(str(i.get(a, "")) for a in ("name", "id", "placeholder", "aria-label"))
        if _CUIT.search(atributos):
            return Resultado(3, "campo CUIT/CUIL en el formulario")
    for lab in soup.find_all("label"):
        if _CUIT.search(lab.get_text(" ", strip=True)):
            return Resultado(3, "etiqueta CUIT/CUIL en el formulario")
    return Resultado(1, nota="el formulario no pide CUIT/CUIL")


_TIPO_CLIENTE = re.compile(r"(mayorista|minorista|revendedor|comerciante|comercio|consumidor final|"
                           r"empresa|particular|persona jur[ií]dica|persona f[ií]sica)", re.I)


def d2_3(ctx: Contexto) -> Resultado:
    if (r := _registro_observable(ctx)):
        return r
    soup = ctx.registro.soup
    etiquetas = [o.get_text(" ", strip=True) for o in soup.select("select option")]
    for inp in soup.select("input[type='radio'], input[type='checkbox']"):
        lab = soup.find("label", attrs={"for": inp.get("id")}) if inp.get("id") else None
        etiquetas.append((lab.get_text(" ", strip=True) if lab else "") + " " + str(inp.get("value", "")))
    tipos = {m.group(1).lower() for e in etiquetas for m in [_TIPO_CLIENTE.search(e)] if m}
    if len(tipos) >= 2:
        return Resultado(3, f"control con tipos de cliente: {', '.join(sorted(tipos))}")
    if _TIPO_CLIENTE.search(texto(_principal(soup))):
        return Resultado(2, "el texto del registro alude a un tipo de cliente", "sin control de tipo de cuenta")
    return Resultado(1, nota="sin diferenciación de tipo de cuenta")


# ═════════════════════════════════════════════════════════════════════════════
# D3 — Ficha de producto
# ═════════════════════════════════════════════════════════════════════════════

def _ficha(ctx: Contexto) -> Resultado | None:
    return _nv(ctx, ctx.ficha, "ficha")


def d3_1(ctx: Contexto) -> Resultado:
    if (r := _ficha(ctx)):
        return r
    soup = ctx.ficha.soup
    for o in ofertas_jsonld(soup):
        if o.get("price") not in (None, "", 0, "0") or o.get("lowPrice"):
            return Resultado(3, "schema.org Offer.price")
    el = soup.select_one("[itemprop='price']")
    if el is not None and (el.get("content") or _PRECIO.search(el.get_text())):
        return Resultado(3, "microdatos itemprop=price")
    for el in _principal(soup).select("[class*='price' i], [class*='precio' i]"):
        if _PRECIO.search(el.get_text(" ", strip=True)):
            return Resultado(3, "elemento de precio con importe")
    if _muro_precio(ctx.ficha):
        return Resultado(0, nota="ficha: el precio exige iniciar sesión (el protocolo no inicia sesión)")
    return Resultado(1, nota="sin precio visible en la ficha")


_BULTO = re.compile(
    r"(precio\s+(por|x|del?)\s+(bulto|caja|pack|fardo|display|funda|blister)"
    r"|(bulto|caja|pack|fardo|display|funda|blister)\s*(cerrad[oa]\s*)?(x|de|por|c/|con)\s*\d+\s*"
    r"(u\b|un\b|unid\w*|uds?\b|botellas|latas|paquetes|sobres)"
    r"|\d+\s*(u\b|un\b|unid\w*|uds?\b)\s*(por|x)\s*(bulto|caja|pack|fardo|display))", re.I)


def d3_2(ctx: Contexto) -> Resultado:
    if (r := _ficha(ctx)):
        return r
    m = _BULTO.search(texto(_principal(ctx.ficha.soup)))
    if m:
        return Resultado(3, f"patrón «{m.group(0)[:60]}»")
    if _muro_precio(ctx.ficha):
        return Resultado(0, nota="ficha: el precio exige iniciar sesión (el protocolo no inicia sesión)")
    return Resultado(1, nota="sin precio o contenido por bulto, caja o pack")


_UNIDAD = re.compile(r"(\b\d+(?:[.,]\d+)?\s*(kg|kgs|g|gr|grs|gramos|l|lt|lts|litros?|ml|cc|cm3)\b"
                     r"|\bx\s*\d+\s*(u|un|unid\w*|uds?)\b)", re.I)


def d3_3(ctx: Contexto) -> Resultado:
    if (r := _ficha(ctx)):
        return r
    soup = ctx.ficha.soup
    for prod in jsonld_tipo(soup, "Product"):
        for k in ("weight", "size", "netContent", "height"):
            if prod.get(k):
                return Resultado(3, f"schema.org Product.{k}")
    h1 = soup.find("h1")
    m = _UNIDAD.search((h1.get_text(" ", strip=True) if h1 else "") + " " + texto(_principal(soup)))
    return Resultado(3, f"patrón «{m.group(0)}»") if m else Resultado(1, nota="sin contenido neto")


_STOCK = re.compile(r"(sin stock|agotado|en stock|stock disponible|hay stock|[uú]ltimas? unidades?|"
                    r"\d+\s+unidades disponibles|consultar stock|disponibilidad inmediata|no disponible)", re.I)


def d3_4(ctx: Contexto) -> Resultado:
    if (r := _ficha(ctx)):
        return r
    soup = ctx.ficha.soup
    for o in ofertas_jsonld(soup):
        if o.get("availability"):
            return Resultado(3, "schema.org Offer.availability")
    if soup.select_one("[itemprop='availability']") is not None:
        return Resultado(3, "microdatos itemprop=availability")
    principal = _principal(soup)
    for el in principal.select("[class*='stock' i], [class*='availability' i], [class*='disponib' i]"):
        if el.get_text(strip=True):
            return Resultado(3, "elemento de disponibilidad con texto")
    m = _STOCK.search(texto(principal))
    return Resultado(3, f"patrón «{m.group(0)}»") if m else Resultado(1, nota="sin información de stock")


_ESCALA = re.compile(
    r"((desde|a\s+partir\s+de|llevando|comprando|por\s+compras?\s+de|m[aá]s\s+de)\s+\d+\s*"
    r"(u\b|un\b|unid\w*|uds?\b|bultos?|cajas?|packs?|fardos?|kg)"
    r"|\d+\s*(u|unid\w*|uds?|bultos?|cajas?|packs?)\s*(o\s+m[aá]s|\+)"
    r"|(precio|descuento)s?\s+(por|seg[uú]n)\s+(cantidad|volumen|escala)"
    r"|escala\s+de\s+precios|precios?\s+escalonados?)", re.I)
_NXM = re.compile(r"\b\d\s*x\s*\d\b", re.I)


def d3_5(ctx: Contexto) -> Resultado:
    if (r := _ficha(ctx)):
        return r
    soup = ctx.ficha.soup
    for o in ofertas_jsonld(soup):
        especificacion = o.get("priceSpecification")
        candidatos = [o.get("eligibleQuantity")]
        for e in (especificacion if isinstance(especificacion, list) else [especificacion]):
            if isinstance(e, dict):
                candidatos.append(e.get("eligibleQuantity"))
        for eq in candidatos:
            if isinstance(eq, dict):
                try:
                    if float(eq.get("minValue", 0)) > 1:
                        return Resultado(3, "schema.org eligibleQuantity")
                except (TypeError, ValueError):
                    pass
    t = texto(_principal(soup))
    m = _ESCALA.search(t)
    if m:
        return Resultado(3, f"patrón «{m.group(0)[:60]}»")
    if _muro_precio(ctx.ficha):
        return Resultado(0, nota="ficha: el precio exige iniciar sesión (el protocolo no inicia sesión)")
    m = _NXM.search(t)
    if m:
        return Resultado(2, f"promoción «{m.group(0)}»", "solo promoción NxM, sin escala por cantidad")
    return Resultado(1, nota="sin escala de precio por cantidad")


# ═════════════════════════════════════════════════════════════════════════════
# D4 — Carrito de compras (automáticos)
# ═════════════════════════════════════════════════════════════════════════════

_COMPRAR = re.compile(r"((agregar|añadir|sumar)\s+(al\s+)?(carrito|pedido|changuito)|^\s*comprar\s*$|"
                      r"comprar ahora|^\s*agregar\s*$)", re.I)


def d4_1(ctx: Contexto) -> Resultado:
    if (r := _ficha(ctx)):
        return r
    principal = _principal(ctx.ficha.soup)
    for el in principal.find_all(["button", "a", "input"]):
        etiqueta = el.get_text(" ", strip=True) or str(el.get("value", "")) or str(el.get("aria-label", ""))
        if _COMPRAR.search(etiqueta):
            return Resultado(3, f"control «{etiqueta[:40]}»")
    sel, el = _primero(principal, ["[class*='buyButton' i]", "[class*='add-to-cart' i]",
                                   "[class*='addtocart' i]", "[class*='tocart' i]", "[class*='btn-comprar' i]"])
    if el is not None:
        return Resultado(3, f"selector {sel}")
    if re.search(r"inici[aá]\s+sesi[oó]n\s+para\s+comprar|ingres[aá]\s+para\s+comprar", texto(principal), re.I):
        return Resultado(0, nota="ficha: la compra exige iniciar sesión (el protocolo no inicia sesión)")
    return Resultado(1, nota="sin control de compra en la ficha")


_MINIMO = re.compile(
    r"((compra|pedido|monto|importe)\s+m[ií]nim[oa]|m[ií]nimo\s+de\s+(compra|pedido|\$?\s?\d+)|"
    r"cantidad\s+m[ií]nima|venta\s+m[ií]nima|m[ií]n\.?\s*(de\s*)?\d+\s*(u\b|un\b|unid\w*|bultos?|cajas?))", re.I)


def d4_2(ctx: Contexto) -> Resultado:
    if (r := _ficha(ctx)):
        return r
    principal = _principal(ctx.ficha.soup)
    m = _MINIMO.search(texto(principal))
    if m:
        return Resultado(3, f"patrón «{m.group(0)[:60]}»")
    for i in principal.select("input[type='number']"):
        try:
            if float(i.get("min", "0")) > 1:
                return Resultado(3, f"control de cantidad con mínimo {i.get('min')}")
        except ValueError:
            continue
    return Resultado(1, nota="sin cantidad ni monto mínimo informado en la ficha")


# ═════════════════════════════════════════════════════════════════════════════
# D5 y D6 — Páginas informativas (y pie de la página de inicio)
# ═════════════════════════════════════════════════════════════════════════════

def _corpus_informativo(ctx: Contexto) -> tuple[str, str, int]:
    """(texto, texto con mayúsculas originales, n.º de fuentes). Incluye alt/title (logos de pago)."""
    partes = [texto(p.soup, incluir_atributos=True) for p in ctx.informativas if not p.motivo_no_verificable()]
    if ctx.inicio is not None and ctx.inicio.soup is not None and not ctx.inicio.motivo_no_verificable():
        for pie in ctx.inicio.soup.select("footer"):
            partes.append(texto(pie, incluir_atributos=True))
    original = " ".join(partes)
    return original.lower(), original, len([p for p in partes if p])


def _nv_informativas(ctx: Contexto, n: int) -> Resultado | None:
    if n == 0:
        return Resultado(0, nota=ctx.notas.get("informativas", "informativas: no se hallaron páginas "
                                                                "informativas ni pie de página accesibles"))
    return None


_DOMICILIO = re.compile(r"(env[ií]os?\s+a\s+domicilio|entregas?\s+a\s+domicilio|despachos?\s+a\s+domicilio|"
                        r"env[ií]os?\s+a\s+tod[oa]|reparto|delivery|te\s+lo\s+llevamos|"
                        r"entregas?\s+en\s+(tu|su)\s+(comercio|local|negocio|domicilio)|"
                        r"env[ií]os?\s+sin\s+cargo|env[ií]o\s+gratis|costo\s+de\s+env[ií]o)", re.I)


def d5_2(ctx: Contexto) -> Resultado:
    t, _, n = _corpus_informativo(ctx)
    if (r := _nv_informativas(ctx, n)):
        return r
    m = _DOMICILIO.search(t)
    return Resultado(3, f"patrón «{m.group(0)}»") if m else Resultado(1, nota="sin envío a domicilio informado")


_RETIRO = re.compile(r"(retir(o|ar|á|a)\s+(en|por)\s+(el\s+|la\s+|nuestr[oa]s?\s+)?"
                     r"(local|sucursal|dep[oó]sito|tienda|sal[oó]n|punto)|"
                     r"pick\s*-?\s*up|take\s*away|click\s*(&|and|y)\s*collect|retiro\s+gratis|"
                     r"retiro\s+sin\s+cargo)", re.I)


def d5_3(ctx: Contexto) -> Resultado:
    t, _, n = _corpus_informativo(ctx)
    if (r := _nv_informativas(ctx, n)):
        return r
    m = _RETIRO.search(t)
    return Resultado(3, f"patrón «{m.group(0)}»") if m else Resultado(1, nota="sin retiro en local informado")


MEDIOS_DE_PAGO = [
    ("Visa", r"\bvisa\b", re.I), ("Mastercard", r"master\s?card", re.I),
    ("American Express", r"american\s+express|\bamex\b", re.I), ("Cabal", r"\bcabal\b", re.I),
    ("Naranja", r"tarjeta\s+naranja|naranja\s+x\b", re.I), ("Maestro", r"\bmaestro\b", re.I),
    ("Tarjeta de crédito", r"tarjetas?\s+de\s+cr[eé]dito", re.I),
    ("Tarjeta de débito", r"tarjetas?\s+de\s+d[eé]bito|\bd[eé]bito\b", re.I),
    ("Mercado Pago", r"mercado\s?pago", re.I), ("Transferencia", r"transferencias?", re.I),
    ("Efectivo", r"\befectivo\b", re.I), ("Rapipago", r"rapipago", re.I),
    ("Pago Fácil", r"pago\s?f[aá]cil", re.I), ("Cheque", r"\be?cheq(ue)?s?\b", re.I),
    ("Cuenta corriente", r"cuenta\s+corriente", re.I), ("MODO", r"\bMODO\b", 0),
    ("Contra entrega", r"contra\s?entrega|contrarre?embolso", re.I),
]


def d6_1(ctx: Contexto) -> Resultado:
    _, original, n = _corpus_informativo(ctx)
    if (r := _nv_informativas(ctx, n)):
        return r
    hallados = [nombre for nombre, pat, fl in MEDIOS_DE_PAGO if re.search(pat, original, fl)]
    ev = ", ".join(hallados)
    if len(hallados) >= 2:
        return Resultado(3, ev)
    if len(hallados) == 1:
        return Resultado(2, ev, "se nombra un solo medio de pago")
    return Resultado(1, nota="no se nombran medios de pago")


_TRANSFERENCIA = re.compile(r"(transferencias?(\s+bancarias?)?|dep[oó]sitos?\s+bancarios?|\bcbu\b|\bcvu\b)", re.I)


def d6_2(ctx: Contexto) -> Resultado:
    t, _, n = _corpus_informativo(ctx)
    if (r := _nv_informativas(ctx, n)):
        return r
    m = _TRANSFERENCIA.search(t)
    return Resultado(3, f"patrón «{m.group(0)}»") if m else Resultado(1, nota="sin pago por transferencia informado")


_FACTURA_A = re.compile(r"(?i:factura(?:s|ci[oó]n)?)\s+(?i:(?:tipo|clase)\s+)?[\"'«“]?A[\"'»”]?(?=[\s,.;:)!?/]|$)")
_IVA = re.compile(r"(iva\s+discriminado|discrimina\w*\s+(el\s+)?iva|responsables?\s+inscript[oa]s?|"
                  r"cr[eé]dito\s+fiscal)", re.I)


def d6_3(ctx: Contexto) -> Resultado:
    t, original, n = _corpus_informativo(ctx)
    if (r := _nv_informativas(ctx, n)):
        return r
    m = _FACTURA_A.search(original)
    if m:
        return Resultado(3, f"patrón «{m.group(0)}»")
    m = _IVA.search(t)
    if m:
        return Resultado(2, f"patrón «{m.group(0)}»", "menciona IVA discriminado sin nombrar factura A")
    return Resultado(1, nota="sin información sobre factura A")


# ═════════════════════════════════════════════════════════════════════════════
# D7 — Comunicación de errores (automático)
# ═════════════════════════════════════════════════════════════════════════════

def d7_3(ctx: Contexto) -> Resultado:
    p = ctx.inexistente
    if p is None:
        return Resultado(0, nota=ctx.notas.get("inexistente", "inexistente: no se solicitó"))
    if p.bloqueada_por_robots or p.error:
        return Resultado(0, nota=p.motivo_no_verificable())
    codigo_ok = p.status in (404, 410)
    navegacion = False
    if p.soup is not None:
        _, nav = _primero(p.soup, ["nav", "[role='navigation']", "input[type='search']", "input[name='q']"])
        al_inicio = any(re.sub(r"^https?://[^/]+", "", u).rstrip("/") == ""
                        for u, _, _ in enlaces(p.soup, ctx.base_url))
        navegacion = nav is not None or al_inicio
    ev = f"HTTP {p.status}; navegación={'sí' if navegacion else 'no'}" + \
         (f"; redirecciones {p.historial}" if p.historial else "")
    n = int(codigo_ok) + int(navegacion)
    return Resultado({2: 3, 1: 2, 0: 1}[n], ev, "" if n == 2 else ev)


# ═════════════════════════════════════════════════════════════════════════════
# D8 — Desempeño técnico
# ═════════════════════════════════════════════════════════════════════════════

def d8_1(ctx: Contexto) -> Resultado:
    if (r := _nv(ctx, ctx.inicio, "inicio")):
        return r
    t = ctx.inicio.elapsed_s
    if t is None:
        return Resultado(0, nota="inicio: tiempo de respuesta no medido")
    ev = f"{t:.2f} s (umbral {UMBRAL_TIEMPO_RESPUESTA_S:.1f} s)"
    return Resultado(3, ev) if t <= UMBRAL_TIEMPO_RESPUESTA_S else Resultado(1, ev, "supera el umbral")


def d8_2(ctx: Contexto) -> Resultado:
    if (r := _nv(ctx, ctx.inicio, "inicio")):
        return r
    meta = ctx.inicio.soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    if meta is None:
        return Resultado(1, nota="sin meta viewport")
    contenido = str(meta.get("content", ""))
    if "width=device-width" in contenido.replace(" ", "").lower():
        return Resultado(3, f"viewport «{contenido[:60]}»")
    return Resultado(2, f"viewport «{contenido[:60]}»", "meta viewport sin width=device-width")


def d8_3(ctx: Contexto) -> Resultado:
    p = ctx.inicio
    if p is None:
        return Resultado(0, nota=ctx.notas.get("inicio", "inicio: no observada"))
    if p.bloqueada_por_robots:
        return Resultado(0, nota=p.motivo_no_verificable())
    if p.error_ssl:
        return Resultado(1, nota="sin HTTPS válido (error de certificado)")
    if p.error or p.soup is None or p.status >= 400:
        return Resultado(0, nota=p.motivo_no_verificable() or "inicio: sin contenido")
    if not (p.final_url or p.url).lower().startswith("https://"):
        return Resultado(1, nota="el sitio no responde por HTTPS")
    h = ctx.http_inicio
    if h is not None and h.redirige_a_https:
        return Resultado(3, f"HTTPS válido; HTTP {h.status} redirige a HTTPS")
    if h is None or h.bloqueada_por_robots or h.error:
        motivo = "redirección HTTP→HTTPS no verificable"
        if h is not None:
            motivo += f" ({h.motivo_no_verificable()})"
        return Resultado(2, "HTTPS válido", motivo)
    return Resultado(2, f"HTTPS válido; HTTP respondió {h.status} sin redirigir a HTTPS",
                     "HTTP no redirige a HTTPS")


def d8_4(ctx: Contexto) -> Resultado:
    if (r := _nv(ctx, ctx.listado, "listado")):
        return r
    principal = _principal(ctx.listado.soup)
    imgs = principal.select("[class*='product' i] img, [itemtype*='Product'] img, li.item img, "
                            ".product-item img") or principal.find_all("img")
    if not imgs:
        return Resultado(0, nota="listado: sin imágenes de catálogo")
    con_alt = sum(1 for i in imgs if str(i.get("alt", "")).strip())
    pct = con_alt / len(imgs)
    ev = f"{con_alt}/{len(imgs)} imágenes con alt"
    if con_alt == len(imgs):
        return Resultado(3, ev)
    return Resultado(2 if pct >= 0.5 else 1, ev, f"{len(imgs) - con_alt} imágenes sin alt")


# ─────────────────────────────────────────────────────────────────────────────
REGLAS = {
    "D1.1": d1_1, "D1.2": d1_2, "D1.3": d1_3, "D1.4": d1_4, "D1.5": d1_5,
    "D2.1": d2_1, "D2.2": d2_2, "D2.3": d2_3,
    "D3.1": d3_1, "D3.2": d3_2, "D3.3": d3_3, "D3.4": d3_4, "D3.5": d3_5,
    "D4.1": d4_1, "D4.2": d4_2,
    "D5.2": d5_2, "D5.3": d5_3,
    "D6.1": d6_1, "D6.2": d6_2, "D6.3": d6_3,
    "D7.3": d7_3,
    "D8.1": d8_1, "D8.2": d8_2, "D8.3": d8_3, "D8.4": d8_4,
}
