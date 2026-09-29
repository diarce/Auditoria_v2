"""
modules/ethics.py — Resguardos éticos para el relevamiento automatizado
=======================================================================
Implementa el protocolo de la sección 7.4.1 de la tesis:
 - RobotsChecker : descarga robots.txt con el user-agent del estudio y
                   verifica cada URL antes de solicitarla.
 - RateLimiter   : demora entre solicitudes a un mismo sitio, con variación
                   aleatoria y respeto del Crawl-delay declarado.
 - EthicsLogger  : registro de transparencia de todas las solicitudes.
 - solicitud_etica: única vía para hacer una petición GET al sitio auditado.

Referencia metodológica: el protocolo de este módulo sigue los principios
de scraping ético descriptos en Hirano et al. (2019) y en las
directrices de la ACM sobre investigación con datos web.
"""

from __future__ import annotations

import csv
import logging
import random
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


def base_de(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


# ─────────────────────────────────────────────────────────────────────────────
class _RestrictiveRobotParser:
    """Stub que deniega todo acceso (fallback conservador)."""
    def can_fetch(self, *args) -> bool:
        return False

    def crawl_delay(self, *args):
        return None


class RobotsChecker:
    """
    Verifica si una URL está permitida para el agente del estudio.

    Lectura de robots.txt (con el user-agent del estudio y tiempo límite):
    - 200            → se aplican sus reglas.
    - 401 o 403      → se deniega todo (convención de urllib.robotparser).
    - otro 4xx       → no hay robots.txt: se permite el acceso.
    - 5xx o error de red → se deniega todo por precaución.
    El estado de lectura queda disponible en `estado(base_url)`.
    """

    def __init__(self, user_agent: str, session: requests.Session | None = None,
                 timeout: int = 30, ethics_logger: "EthicsLogger | None" = None):
        self.user_agent = user_agent
        self.session = session or requests.Session()
        self.timeout = timeout
        self.ethics_logger = ethics_logger
        self._cache: dict[str, object] = {}
        self._estado: dict[str, str] = {}

    def _get_parser(self, base_url: str):
        if base_url in self._cache:
            return self._cache[base_url]
        robots_url = f"{base_url.rstrip('/')}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        t0 = time.monotonic()
        try:
            resp = self.session.get(robots_url, timeout=self.timeout,
                                    headers={"User-Agent": self.user_agent})
            ms = (time.monotonic() - t0) * 1000
            if self.ethics_logger:
                self.ethics_logger.record(robots_url, status_code=resp.status_code,
                                          robots_allowed=True, response_time_ms=ms,
                                          notes="lectura de robots.txt")
            if resp.status_code in (401, 403):
                rp.disallow_all = True
                self._estado[base_url] = f"robots.txt respondió {resp.status_code}: acceso denegado"
            elif 400 <= resp.status_code < 500:
                rp.allow_all = True
                self._estado[base_url] = "sin robots.txt (acceso permitido)"
            elif resp.status_code >= 500:
                rp = _RestrictiveRobotParser()
                self._estado[base_url] = f"robots.txt inaccesible (HTTP {resp.status_code})"
            else:
                rp.parse(resp.text.splitlines())
                self._estado[base_url] = "robots.txt leído"
            logger.info(f"[ÉTICA] {self._estado[base_url]}: {robots_url}")
        except requests.RequestException as exc:
            rp = _RestrictiveRobotParser()
            self._estado[base_url] = "robots.txt inaccesible (error de red)"
            logger.warning(f"[ÉTICA] No se pudo leer {robots_url}: {exc}. Se deniega el acceso.")
            if self.ethics_logger:
                self.ethics_logger.record(robots_url, status_code=0, robots_allowed=False,
                                          notes=f"robots.txt inaccesible: {type(exc).__name__}")
        self._cache[base_url] = rp
        return rp

    def estado(self, base_url: str) -> str:
        self._get_parser(base_url)
        return self._estado.get(base_url, "")

    def is_allowed(self, url: str) -> bool:
        rp = self._get_parser(base_de(url))
        allowed = rp.can_fetch(self.user_agent, url)
        if not allowed:
            logger.warning(f"[ÉTICA] Acceso no permitido ({self._estado.get(base_de(url), '')}): {url}")
        return allowed

    def get_crawl_delay(self, base_url: str) -> float | None:
        rp = self._get_parser(base_url)
        try:
            delay = rp.crawl_delay(self.user_agent)
        except Exception:
            delay = None
        return float(delay) if delay else None


# ─────────────────────────────────────────────────────────────────────────────
class RateLimiter:
    """
    Demora entre solicitudes a un mismo sitio.

    demora = max(base, Crawl-delay, 1 s) + U(-jitter/2, +jitter), con mínimo de 1 s.
    """

    def __init__(self, base_delay: float = 3.0, jitter: float = 1.5,
                 crawl_delay: float | None = None):
        self.base_delay = base_delay
        self.jitter = jitter
        self.crawl_delay = crawl_delay
        self._last_request: float = 0.0

    def demora_base(self) -> float:
        return max(self.base_delay, self.crawl_delay or 0.0, 1.0)

    def wait(self) -> None:
        delay = max(self.demora_base() + random.uniform(-self.jitter / 2, self.jitter), 1.0)
        elapsed = time.monotonic() - self._last_request
        sleep_for = max(0.0, delay - elapsed)
        if sleep_for > 0 and self._last_request > 0:
            logger.debug(f"[RATE LIMIT] Esperando {sleep_for:.2f}s.")
            time.sleep(sleep_for)
        self._last_request = time.monotonic()


# ─────────────────────────────────────────────────────────────────────────────
class EthicsLogger:
    """Registro CSV de transparencia: una fila por solicitud realizada o bloqueada."""

    CAMPOS = ["timestamp", "url", "method", "status_code", "robots_allowed",
              "response_time_ms", "notes"]

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._entries: list[dict] = []
        if not log_path.exists():
            with log_path.open("w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(self.CAMPOS)

    def record(self, url: str, method: str = "GET", status_code: int = 0,
               robots_allowed: bool = True, response_time_ms: float = 0.0,
               notes: str = "") -> None:
        entry = {
            "timestamp": datetime.now().isoformat(), "url": url, "method": method,
            "status_code": status_code, "robots_allowed": robots_allowed,
            "response_time_ms": round(response_time_ms, 2), "notes": notes,
        }
        self._entries.append(entry)
        with self.log_path.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([entry[c] for c in self.CAMPOS])

    def summary(self) -> dict:
        if not self._entries:
            return {"total": 0}
        total = len(self._entries)
        return {
            "total": total,
            "blocked_by_robots": sum(1 for e in self._entries if not e["robots_allowed"]),
            "http_errors": sum(1 for e in self._entries if e["status_code"] >= 400),
            "avg_response_ms": round(sum(e["response_time_ms"] for e in self._entries) / total, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class ResultadoSolicitud:
    url: str
    response: requests.Response | None = None
    bloqueada_por_robots: bool = False
    error: str = ""            # nombre de la excepción, si hubo
    error_ssl: bool = False


def solicitud_etica(url: str, robots_checker: RobotsChecker, rate_limiter: RateLimiter,
                    ethics_logger: EthicsLogger, session: requests.Session,
                    timeout: int = 30, allow_redirects: bool = True) -> ResultadoSolicitud:
    """GET ético: robots.txt → demora → solicitud → registro. Nunca otro método HTTP."""
    if not robots_checker.is_allowed(url):
        ethics_logger.record(url=url, robots_allowed=False, notes="Bloqueado por robots.txt")
        return ResultadoSolicitud(url=url, bloqueada_por_robots=True)

    rate_limiter.wait()
    t0 = time.monotonic()
    try:
        response = session.get(url, timeout=timeout, allow_redirects=allow_redirects)
        ms = (time.monotonic() - t0) * 1000
        ethics_logger.record(url=url, status_code=response.status_code,
                             robots_allowed=True, response_time_ms=ms)
        logger.info(f"[GET] {response.status_code} | {url} | {ms:.0f}ms")
        return ResultadoSolicitud(url=url, response=response)
    except requests.exceptions.SSLError as exc:
        ms = (time.monotonic() - t0) * 1000
        ethics_logger.record(url=url, status_code=0, response_time_ms=ms, notes="Error TLS/SSL")
        return ResultadoSolicitud(url=url, error=type(exc).__name__, error_ssl=True)
    except requests.RequestException as exc:
        ms = (time.monotonic() - t0) * 1000
        ethics_logger.record(url=url, status_code=0, response_time_ms=ms, notes=type(exc).__name__)
        logger.error(f"[ERROR] {url}: {exc}")
        return ResultadoSolicitud(url=url, error=type(exc).__name__)


def ethical_request(url: str, robots_checker: RobotsChecker, rate_limiter: RateLimiter,
                    ethics_logger: EthicsLogger, session: requests.Session,
                    timeout: int = 30) -> requests.Response | None:
    """Compatibilidad con versiones anteriores: devuelve solo la respuesta."""
    return solicitud_etica(url, robots_checker, rate_limiter, ethics_logger,
                           session, timeout).response
