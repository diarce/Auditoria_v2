"""
modules/auditor.py — Motor de auditoría digital automatizada
============================================================
Releva los 25 indicadores automáticos del Anexo C en la página que indica
la Tabla B.2 para cada uno. Los 7 indicadores manuales se cargan aparte
(modules/importer.py) y quedan registrados con método «M».

Criterio de exclusión (sección 7.4): una plataforma se excluye del
relevamiento cuando su robots.txt no autoriza al agente del estudio a
acceder a alguna de las secciones requeridas (página de inicio, listado de
productos o ficha de producto), cuando robots.txt no puede leerse o cuando
la página de inicio no responde. La exclusión se registra con su motivo y
se informa como resultado.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

from config import (INDICADORES, INDICADORES_AUTOMATICOS, QA_DIMENSIONS, SCRAPING_CONFIG,
                    SECCIONES_REQUERIDAS, SITES)
from modules.indicadores import REGLAS, Contexto, Resultado
from modules.paginas import (PageFetcher, Pagina, candidatos_ficha, candidatos_informativas,
                             candidatos_listado, candidatos_registro, es_ficha, es_formulario_registro,
                             es_listado)
from modules.storage import AuditResult, DatabaseManager

logger = logging.getLogger(__name__)

# Códigos de exclusión
EXCL_ROBOTS_INACCESIBLE = "robots_inaccesible"
EXCL_ROBOTS_INICIO = "robots_bloquea_inicio"
EXCL_ROBOTS_CATALOGO = "robots_bloquea_catalogo"
EXCL_INICIO_INACCESIBLE = "inicio_inaccesible"

DESCRIPCION_EXCLUSION = {
    EXCL_ROBOTS_INACCESIBLE: "robots.txt no pudo leerse; se deniega el acceso por precaución",
    EXCL_ROBOTS_INICIO: "robots.txt no autoriza la página de inicio",
    EXCL_ROBOTS_CATALOGO: "robots.txt no autoriza el listado o la ficha de producto",
    EXCL_INICIO_INACCESIBLE: "la página de inicio no responde o no es accesible",
}


@dataclass
class ResultadoSitio:
    site_id: str
    excluida: bool = False
    codigo_exclusion: str = ""
    detalle_exclusion: str = ""
    resultados: dict[str, Resultado] = field(default_factory=dict)
    paginas: dict[str, str] = field(default_factory=dict)   # sección → URL (uso interno)


class _Exclusion(Exception):
    def __init__(self, codigo: str, detalle: str = ""):
        super().__init__(codigo)
        self.codigo, self.detalle = codigo, detalle


class AuditEngine:

    def __init__(self, db: DatabaseManager, cfg: dict = SCRAPING_CONFIG,
                 fetcher: PageFetcher | None = None):
        self.db = db
        self.cfg = cfg
        self.fetcher = fetcher or PageFetcher(cfg)
        self.max_cand = cfg.get("max_candidatos_por_seccion", 3)

    # ── API ────────────────────────────────────────────────────────────────────
    def run(self, site_filter: str | None = None, dimension_filter=None,
            sites_override: list[dict] | None = None) -> dict[str, ResultadoSitio]:
        fuente = sites_override if sites_override is not None else SITES
        sitios = [s for s in fuente if site_filter is None or s["id"].lower() == site_filter.lower()]
        if not sitios:
            logger.error("[AUDIT] No hay sitios para auditar. Revise data/privado/universo.csv.")
            return {}
        if dimension_filter is None:
            dims = set(QA_DIMENSIONS)
        elif isinstance(dimension_filter, str):
            dims = {dimension_filter.upper()}
        else:
            dims = {d.upper() for d in dimension_filter}
        indicadores = [i for i in INDICADORES_AUTOMATICOS if INDICADORES[i]["dimension_id"] in dims]

        salida = {}
        for site in sitios:
            self.db.upsert_site(site)
            logger.info(f"[AUDIT] ══ {site['id']} ══")
            res = self.auditar_sitio(site, indicadores)
            self._persistir(site, res)
            salida[site["id"]] = res
        return salida

    # ── Relevamiento de una plataforma ─────────────────────────────────────────
    def auditar_sitio(self, site: dict, indicadores: list[str] | None = None) -> ResultadoSitio:
        indicadores = indicadores or INDICADORES_AUTOMATICOS
        res = ResultadoSitio(site_id=site["id"])
        try:
            ctx = self._relevar_paginas(site, res)
        except _Exclusion as e:
            res.excluida, res.codigo_exclusion, res.detalle_exclusion = True, e.codigo, e.detalle
            logger.warning(f"[AUDIT] {site['id']} excluida: {DESCRIPCION_EXCLUSION[e.codigo]}")
            return res
        for ind in indicadores:
            try:
                res.resultados[ind] = REGLAS[ind](ctx)
            except Exception as exc:   # un error de análisis no es un incumplimiento
                logger.exception(f"[AUDIT] Error al valorar {ind}")
                res.resultados[ind] = Resultado(0, nota=f"error de análisis ({type(exc).__name__})")
        return res

    def _relevar_paginas(self, site: dict, res: ResultadoSitio) -> Contexto:
        f = self.fetcher
        base = site["base_url"].strip().rstrip("/")
        p = urlparse(base)
        raiz = f"{p.scheme}://{p.netloc}"

        # Preferir HTTPS si el sitio fue cargado con http://
        if p.scheme == "http":
            https_raiz = f"https://{p.netloc}"
            if f.is_allowed(https_raiz + "/"):
                prueba = f.obtener(https_raiz + "/", "inicio")
                if prueba.ok:
                    base, raiz = https_raiz + p.path, https_raiz

        # 1. Página de inicio (sección requerida)
        inicio_url = base + "/"
        if not f.is_allowed(inicio_url):
            estado = f.robots_checker.estado(raiz)
            if "inaccesible" in estado:
                raise _Exclusion(EXCL_ROBOTS_INACCESIBLE, estado)
            raise _Exclusion(EXCL_ROBOTS_INICIO, estado)
        inicio = f.obtener(inicio_url, "inicio")
        if not inicio.ok:
            raise _Exclusion(EXCL_INICIO_INACCESIBLE, inicio.motivo_no_verificable())
        ctx = Contexto(base_url=raiz, inicio=inicio)
        res.paginas["inicio"] = inicio.final_url or inicio_url
        sel = site.get("selectors", {}) or {}

        # 2. Listado de productos (sección requerida)
        fuertes, respaldo = candidatos_listado(inicio.soup, inicio.final_url or inicio_url,
                                               sel.get("category_links", ""))
        if fuertes and not any(f.is_allowed(u) for u in fuertes):
            raise _Exclusion(EXCL_ROBOTS_CATALOGO, f"listado: {len(fuertes)} enlace(s) a categorías bloqueados")
        ctx.listado = self._primera_valida([u for u in fuertes if f.is_allowed(u)] + respaldo, "listado",
                                           lambda pg: es_listado(pg.soup, raiz), ctx)
        if ctx.listado is None and es_listado(inicio.soup, raiz):
            ctx.listado = inicio
            ctx.notas.pop("listado", None)
            res.paginas["listado"] = res.paginas["inicio"] + " (la página de inicio lista productos)"
        elif ctx.listado is not None:
            res.paginas["listado"] = ctx.listado.final_url

        # 3. Ficha de producto (sección requerida)
        origen_fichas = ctx.listado.soup if ctx.listado is not None else inicio.soup
        cands = candidatos_ficha(origen_fichas, raiz, sel.get("product_link", ""))
        ctx.ficha = self._primera_valida(cands, "ficha", lambda pg: es_ficha(pg.soup), ctx)
        if ctx.ficha is not None:
            res.paginas["ficha"] = ctx.ficha.final_url

        # 4. Registro
        explicitos, cuenta = candidatos_registro(inicio.soup, raiz)
        ctx.registro_explicito, ctx.hay_acceso_cuenta = bool(explicitos), bool(cuenta)
        ctx.registro = self._primera_valida(explicitos + cuenta, "registro",
                                            lambda pg: es_formulario_registro(pg.soup), ctx,
                                            excluir_si_bloqueado=False)
        if ctx.registro is not None:
            res.paginas["registro"] = ctx.registro.final_url

        # 5. Páginas informativas
        infos = [u for u in candidatos_informativas(inicio.soup, raiz) if f.is_allowed(u)]
        for u in infos[: self.cfg.get("max_paginas_informativas", 4)]:
            pg = f.obtener(u, "informativas")
            ctx.informativas.append(pg)
        if not infos:
            ctx.notas["informativas"] = "informativas: no se hallaron enlaces a páginas informativas accesibles"
        res.paginas["informativas"] = "; ".join(pg.final_url or pg.url for pg in ctx.informativas)

        # 6. Ruta inexistente (D7.3)
        sufijo = hashlib.sha1(raiz.encode()).hexdigest()[:10]
        ctx.inexistente = f.obtener(f"{raiz}/pagina-inexistente-auditoria-{sufijo}", "inexistente")

        # 7. Redirección HTTP → HTTPS (D8.3), sin seguir redirecciones
        if raiz.startswith("https://"):
            http_url = "http://" + urlparse(raiz).netloc + "/"
            ctx.http_inicio = f.obtener(http_url, "http", allow_redirects=False)
        return ctx

    def _primera_valida(self, candidatos: list[str], seccion: str, es_valida, ctx: Contexto,
                        excluir_si_bloqueado: bool = True) -> Pagina | None:
        """
        Primer candidato permitido por robots.txt que cumple `es_valida`.
        Si todos los candidatos están bloqueados y la sección es requerida,
        la plataforma se excluye.
        """
        if not candidatos:
            ctx.notas[seccion] = f"{seccion}: no se identificaron enlaces a esta sección"
            return None
        permitidos = [u for u in candidatos if self.fetcher.is_allowed(u)]
        if not permitidos:
            if excluir_si_bloqueado and seccion in SECCIONES_REQUERIDAS:
                raise _Exclusion(EXCL_ROBOTS_CATALOGO, f"{seccion}: {len(candidatos)} enlace(s) bloqueados")
            ctx.notas[seccion] = f"{seccion}: bloqueada por robots.txt"
            return None
        ultimo_motivo = ""
        for u in permitidos[: self.max_cand]:
            pg = self.fetcher.obtener(u, seccion)
            if pg.muro_de_sesion:
                ultimo_motivo = pg.motivo_no_verificable()
                continue
            if pg.ok and es_valida(pg):
                return pg
            ultimo_motivo = pg.motivo_no_verificable() or f"{seccion}: la página no tiene la estructura esperada"
        ctx.notas[seccion] = ultimo_motivo or f"{seccion}: no se identificó la página"
        return None

    # ── Persistencia ───────────────────────────────────────────────────────────
    def _persistir(self, site: dict, res: ResultadoSitio) -> None:
        # Se reemplazan solo los valores automáticos; los manuales se conservan.
        self.db.borrar_resultados(site["id"], metodo="A")
        if res.excluida:
            self.db.registrar_exclusion(site["id"], res.codigo_exclusion, res.detalle_exclusion)
            return
        self.db.quitar_exclusion(site["id"])
        registros = []
        for ind, r in res.resultados.items():
            pagina = INDICADORES[ind]["pagina"]
            registros.append(AuditResult(
                site_id=site["id"], test_case_id=ind, compliance=r.valor, metodo="A",
                pagina=pagina, url_evaluada=res.paginas.get(pagina, ""),
                evidence=r.evidencia, notes=r.nota, auditor="AuditMayorista"))
        self.db.guardar_resultados(registros)
