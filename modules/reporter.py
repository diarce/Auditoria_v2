"""
modules/reporter.py — Informes de la auditoría digital (sección 7.4.2)
======================================================================
El informe sigue el procedimiento de análisis de la tesis:
  1. Distribución de frecuencias de las cuatro categorías, total y por dimensión.
  2. Puntaje por dimensión S_ik (Anexo B.4.1), como medida exploratoria ordinal.
  3. Comparación de perfiles por dimensión entre plataformas.
No se calcula índice agregado alguno, ponderado ni simple (sección 7.4.2).

Además informa las plataformas excluidas y su motivo (sección 7.4), la
cobertura por método (automático / manual) y, si existe, la concordancia
entre la codificación automática y una codificación manual de control.

Anonimización: las plataformas se identifican con el alias «Sitio Auditado N».
Los informes no incluyen URL, nombres ni evidencias textuales.
Si la base contiene datos simulados, todas las salidas lo declaran.
"""

from __future__ import annotations

import html
import logging
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from config import (BASE_DIR, COMPLIANCE_SCALE, CSV_DIR, INDICADORES, INDICADORES_MANUALES,
                    QA_DIMENSIONS, REPORTS_DIR, VERSION)
from modules.storage import ORIGEN_SIMULADO, DatabaseManager, build_anon_map

logger = logging.getLogger(__name__)

DIMS = sorted(QA_DIMENSIONS)
ETIQUETA_CORTA = {3: "Pleno", 2: "Parcial", 1: "No cumple", 0: "N/A"}


def _e(x) -> str:
    return html.escape(str(x))


def _num(x: float, dec: int = 2) -> str:
    """Número con coma decimal (convención del español rioplatense)."""
    return f"{x:.{dec}f}".replace(".", ",")


def version_codigo() -> str:
    """Versión del instrumento y commit, para citar en la tesis."""
    try:
        commit = subprocess.run(["git", "-C", str(BASE_DIR), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        commit = ""
    return f"{VERSION}" + (f" (commit {commit})" if commit else "")


# ─────────────────────────────────────────────────────────────────────────────
# Datos del informe
# ─────────────────────────────────────────────────────────────────────────────
class DatosInforme:
    def __init__(self, db: DatabaseManager):
        self.sites = db.get_sites()
        self.results = db.get_audit_results()
        self.scores = db.get_dimension_scores()
        self.exclusiones = db.get_exclusiones()
        self.control = db.get_control()
        self.simulado = ORIGEN_SIMULADO in db.origenes()
        auditados = sorted({r["site_id"] for r in self.results})
        self.alias = build_anon_map(auditados)
        self.alias_excl = {e["site_id"]: f"Plataforma excluida {i}"
                           for i, e in enumerate(self.exclusiones, start=1)}
        self.por_sitio: dict[str, dict] = defaultdict(dict)
        for s in self.scores:
            self.por_sitio[s["site_id"]][s["dimension_id"]] = s

    @property
    def auditados(self) -> list[str]:
        return list(self.alias)


# ─────────────────────────────────────────────────────────────────────────────
# Visualizaciones (SVG / HTML autocontenidos, reutilizados por app y notebook)
# ─────────────────────────────────────────────────────────────────────────────
CSS = """
<style>
.viz-root{color-scheme:light;
  --surface-1:#fcfcfb;--page:#f9f9f7;--text-primary:#0b0b0b;--text-secondary:#52514e;--muted:#6b6a66;
  --grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);
  --v0:#d6d5cf;--v1:#86b6ef;--v2:#3987e5;--v3:#184f95;--v0-ink:#0b0b0b;--v1-ink:#0b0b0b;--v2-ink:#ffffff;--v3-ink:#ffffff;
  --s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#4a3aa7;--s8:#e34948;
  --critical:#d03b3b;--critical-bg:#fbeaea;
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--text-primary);background:var(--page)}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;
  --surface-1:#1a1a19;--page:#0d0d0d;--text-primary:#fff;--text-secondary:#c3c2b7;--muted:#a3a29c;
  --grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);
  --v0:#4a4945;--v1:#1c5cab;--v2:#3987e5;--v3:#9ec5f4;--v0-ink:#fff;--v1-ink:#fff;--v2-ink:#0b0b0b;--v3-ink:#0b0b0b;
  --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;
  --critical-bg:#3a1c1c}}
:root[data-theme="dark"] .viz-root{color-scheme:dark;
  --surface-1:#1a1a19;--page:#0d0d0d;--text-primary:#fff;--text-secondary:#c3c2b7;--muted:#a3a29c;
  --grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);
  --v0:#4a4945;--v1:#1c5cab;--v2:#3987e5;--v3:#9ec5f4;--v0-ink:#fff;--v1-ink:#fff;--v2-ink:#0b0b0b;--v3-ink:#0b0b0b;
  --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;
  --critical-bg:#3a1c1c}
.viz-root{margin:0;padding:0;line-height:1.45;font-size:14px}
.viz-root .contenido{max-width:980px;margin:0 auto;padding:24px 16px 48px}
.viz-root h1{font-size:22px;margin:0 0 4px}
.viz-root h2{font-size:17px;margin:32px 0 6px;padding-bottom:4px;border-bottom:1px solid var(--axis)}
.viz-root p,.viz-root li{color:var(--text-secondary);max-width:75ch}
.viz-root .meta{color:var(--text-secondary);font-size:13px}
.viz-root .tarjeta{background:var(--surface-1);border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin:10px 0;overflow-x:auto}
.viz-root table{border-collapse:collapse;font-size:13px;width:100%}
.viz-root th,.viz-root td{padding:5px 8px;border-bottom:1px solid var(--grid);text-align:left;vertical-align:top}
.viz-root th{color:var(--text-secondary);font-weight:600}
.viz-root td.num,.viz-root th.num{text-align:right;font-variant-numeric:tabular-nums}
.viz-root .celda{text-align:center;font-variant-numeric:tabular-nums;font-weight:600;border:2px solid var(--surface-1);min-width:34px}
.viz-root .c0{background:var(--v0);color:var(--v0-ink)}.viz-root .c1{background:var(--v1);color:var(--v1-ink)}
.viz-root .c2{background:var(--v2);color:var(--v2-ink)}.viz-root .c3{background:var(--v3);color:var(--v3-ink)}
.viz-root .leyenda{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12px;color:var(--text-secondary);margin:6px 0}
.viz-root .leyenda span.sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:5px}
.viz-root .aviso{border-left:4px solid var(--critical);background:var(--critical-bg);padding:10px 12px;border-radius:4px;margin:12px 0;font-weight:600}
.viz-root .nota{font-size:12px;color:var(--muted)}
.viz-root svg text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
</style>"""


def _leyenda_categorias() -> str:
    items = "".join(f'<span><span class="sw c{v}"></span>{v} = {ETIQUETA_CORTA[v]}</span>' for v in (3, 2, 1, 0))
    return f'<div class="leyenda">{items}</div>'


def svg_distribucion(results: list[dict]) -> str:
    """Barras apiladas horizontales: composición de las cuatro categorías por dimensión."""
    if not results:
        return ""
    cuenta = {d: Counter(r["compliance"] for r in results if r["dimension_id"] == d) for d in DIMS}
    filas = [d for d in DIMS if sum(cuenta[d].values())]
    W, pad_l, pad_r, h_bar, gap = 640, 190, 16, 22, 12
    ancho = W - pad_l - pad_r
    H = 30 + len(filas) * (h_bar + gap)
    partes = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
              f'aria-label="Distribución de categorías de cumplimiento por dimensión">']
    for x_pct in (0, 25, 50, 75, 100):
        x = pad_l + ancho * x_pct / 100
        partes.append(f'<line x1="{x:.1f}" y1="18" x2="{x:.1f}" y2="{H - 6}" stroke="var(--grid)" stroke-width="1"/>'
                      f'<text x="{x:.1f}" y="12" font-size="10" fill="var(--muted)" text-anchor="middle">{x_pct} %</text>')
    for i, d in enumerate(filas):
        y = 24 + i * (h_bar + gap)
        total = sum(cuenta[d].values())
        partes.append(f'<text x="{pad_l - 8}" y="{y + h_bar / 2 + 4}" font-size="12" fill="var(--text-primary)" '
                      f'text-anchor="end">{d} {_e(QA_DIMENSIONS[d]["name"][:24])}</text>')
        x = pad_l
        for v in (3, 2, 1, 0):
            n = cuenta[d].get(v, 0)
            if not n:
                continue
            w = ancho * n / total
            partes.append(
                f'<rect x="{x:.1f}" y="{y}" width="{max(w - 2, 1):.1f}" height="{h_bar}" rx="3" '
                f'fill="var(--v{v})"><title>{d} · {ETIQUETA_CORTA[v]}: {n} de {total} ({_num(100 * n / total, 0)} %)'
                f'</title></rect>')
            if w >= 26:
                partes.append(f'<text x="{x + w / 2 - 1:.1f}" y="{y + h_bar / 2 + 4}" font-size="11" '
                              f'font-weight="600" fill="var(--v{v}-ink)" text-anchor="middle">{n}</text>')
            x += w
    partes.append("</svg>")
    return "".join(partes)


def svg_perfiles(por_sitio: dict[str, dict], alias: dict[str, str]) -> str:
    """Perfil S_ik por dimensión, una línea por plataforma; huecos donde no hay dato."""
    sitios = [s for s in alias if s in por_sitio]
    if not sitios:
        return ""
    if len(sitios) > 8:
        return "".join(svg_perfiles({s: por_sitio[s]}, {s: alias[s]}) for s in sitios)
    W, H, pl, pr, pt, pb = 680, 300, 44, 150, 16, 44
    aw, ah = W - pl - pr, H - pt - pb
    xs = {d: pl + aw * i / (len(DIMS) - 1) for i, d in enumerate(DIMS)}

    def y(v):
        return pt + ah * (3 - v) / 2        # escala 1..3

    partes = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
              f'aria-label="Perfiles de puntaje por dimensión de las plataformas auditadas">']
    for v in (1, 1.5, 2, 2.5, 3):
        partes.append(f'<line x1="{pl}" y1="{y(v):.1f}" x2="{pl + aw}" y2="{y(v):.1f}" stroke="var(--grid)"/>'
                      f'<text x="{pl - 8}" y="{y(v) + 4:.1f}" font-size="10" fill="var(--muted)" '
                      f'text-anchor="end">{str(v).replace(".", ",")}</text>')
    for d in DIMS:
        partes.append(f'<text x="{xs[d]:.1f}" y="{H - pb + 18}" font-size="11" fill="var(--text-secondary)" '
                      f'text-anchor="middle">{d}</text>')
    etiquetas_fin = []
    for k, sid in enumerate(sitios):
        color = f"var(--s{k % 8 + 1})"
        puntos = [(d, por_sitio[sid].get(d, {}).get("avg_compliance")) for d in DIMS]
        tramo: list[str] = []
        for d, v in puntos + [(None, None)]:
            if v is not None:
                tramo.append(f"{xs[d]:.1f},{y(v):.1f}")
            else:
                if len(tramo) > 1:
                    partes.append(f'<polyline points="{" ".join(tramo)}" fill="none" stroke="{color}" '
                                  f'stroke-width="2" stroke-linejoin="round"/>')
                tramo = []
        for d, v in puntos:
            if v is not None:
                partes.append(f'<circle cx="{xs[d]:.1f}" cy="{y(v):.1f}" r="4.5" fill="{color}" '
                              f'stroke="var(--surface-1)" stroke-width="2"><title>{_e(alias[sid])} · {d} '
                              f'{_e(QA_DIMENSIONS[d]["name"])}: {_num(v)}</title></circle>')
        ultimo = next(((d, v) for d, v in reversed(puntos) if v is not None), None)
        if ultimo:
            etiquetas_fin.append([y(ultimo[1]), alias[sid], color])
    etiquetas_fin.sort()
    for i in range(1, len(etiquetas_fin)):          # evitar superposición de etiquetas
        etiquetas_fin[i][0] = max(etiquetas_fin[i][0], etiquetas_fin[i - 1][0] + 14)
    for yy, nombre, color in etiquetas_fin:
        partes.append(f'<circle cx="{pl + aw + 14}" cy="{yy - 4:.1f}" r="4" fill="{color}"/>'
                      f'<text x="{pl + aw + 22}" y="{yy:.1f}" font-size="11" fill="var(--text-primary)">'
                      f'{_e(nombre)}</text>')
    partes.append(f'<text x="{pl}" y="{H - 6}" font-size="10" fill="var(--muted)">Eje vertical: puntaje '
                  f'S_ik (1 a 3). Los huecos indican dimensiones sin valores válidos.</text></svg>')
    return "".join(partes)


def html_detalle(results: list[dict], alias: dict[str, str]) -> str:
    """Tabla indicador × plataforma con el valor en cada celda (color + número)."""
    if not results:
        return ""
    val = {(r["site_id"], r["test_case_id"]): r for r in results}
    sitios = list(alias)
    cab = "".join(f'<th class="num">{_e(alias[s])}</th>' for s in sitios)
    filas = []
    for d in DIMS:
        filas.append(f'<tr><th colspan="{3 + len(sitios)}">{d} — {_e(QA_DIMENSIONS[d]["name"])}</th></tr>')
        for tc in [t for t in INDICADORES.values() if t["dimension_id"] == d]:
            celdas = ""
            for s in sitios:
                r = val.get((s, tc["id"]))
                if r is None:
                    celdas += '<td class="num nota" title="Sin valor cargado">—</td>'
                else:
                    v = r["compliance"]
                    celdas += (f'<td class="celda c{v}" title="{_e(COMPLIANCE_SCALE[v])} · '
                               f'método {r["metodo"]}">{v}</td>')
            filas.append(f'<tr><td>{tc["id"]}</td><td>{_e(tc["name"])}</td><td>{tc["relevamiento"]}</td>{celdas}</tr>')
    return (f'{_leyenda_categorias()}<table><thead><tr><th>ID</th><th>Indicador</th><th>Rel.</th>{cab}</tr>'
            f'</thead><tbody>{"".join(filas)}</tbody></table>'
            f'<p class="nota">Rel.: A = relevamiento automático, M = verificación manual. '
            f'«—» = valor manual aún no cargado.</p>')


# ─────────────────────────────────────────────────────────────────────────────
class HTMLReporter:

    def __init__(self, db: DatabaseManager, output_dir: Path = REPORTS_DIR):
        self.db = db
        self.output_dir = output_dir

    def generate(self) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        datos = DatosInforme(self.db)
        prefijo = "informe_SIMULADO" if datos.simulado else "informe_auditoria"
        out = self.output_dir / f"{prefijo}_{ts}.html"
        out.write_text(self.build_html(datos), encoding="utf-8")
        logger.info(f"[HTML] Informe generado: {out}")
        return out

    def build_html(self, datos: DatosInforme | None = None) -> str:
        d = datos or DatosInforme(self.db)
        titulo = "Informe de la auditoría digital" + (" — DATOS SIMULADOS" if d.simulado else "")
        aviso = ('<div class="aviso">⚠ DATOS SIMULADOS. Este informe fue generado con el modo de '
                 'demostración y no contiene observaciones de plataformas reales. No debe citarse '
                 'como resultado de la investigación.</div>') if d.simulado else ""
        secciones = [self._portada(d), aviso, self._exclusiones(d), self._cobertura(d),
                     self._distribucion(d), self._puntajes(d), self._perfiles(d),
                     self._detalle(d), self._concordancia(), self._nota_metodologica()]
        return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{_e(titulo)}</title>{CSS}</head><body class="viz-root"><div class="contenido">'
                + "".join(secciones) + "</div></body></html>")

    # ── Secciones ──────────────────────────────────────────────────────────────
    def _portada(self, d: DatosInforme) -> str:
        n_man_cargados = sum(1 for r in d.results if r["metodo"] == "M")
        return (f'<h1>Auditoría digital del desarrollo funcional del comercio electrónico</h1>'
                f'<p class="meta">Tiendas mayoristas de bienes de consumo masivo · Municipio de Posadas, '
                f'Misiones<br>Instrumento AuditMayorista {_e(version_codigo())} · generado el '
                f'{datetime.now().strftime("%d/%m/%Y %H:%M")}<br>'
                f'Plataformas auditadas: {len(d.auditados)} · plataformas excluidas: {len(d.exclusiones)} · '
                f'observaciones: {len(d.results)} ({n_man_cargados} de verificación manual)</p>'
                f'<p class="nota">Las plataformas se identifican con alias («Sitio Auditado N») asignados por el '
                f'orden de su identificador interno. La correspondencia entre identificadores y organizaciones '
                f'se conserva fuera del repositorio público, por lo que los alias no permiten identificar a las '
                f'organizaciones con la información publicada.</p>')

    def _exclusiones(self, d: DatosInforme) -> str:
        from modules.auditor import DESCRIPCION_EXCLUSION
        if not d.exclusiones:
            return ('<h2>1. Plataformas excluidas</h2><p>Ninguna plataforma fue excluida por el criterio '
                    'de robots.txt ni por inaccesibilidad.</p>')
        por_motivo = Counter(e["codigo"] for e in d.exclusiones)
        filas = "".join(f'<tr><td>{_e(DESCRIPCION_EXCLUSION.get(c, c))}</td><td class="num">{n}</td></tr>'
                        for c, n in por_motivo.most_common())
        total = len(d.exclusiones) + len(d.auditados)
        return (f'<h2>1. Plataformas excluidas</h2>'
                f'<p>{len(d.exclusiones)} de {total} plataformas con canal de venta en línea quedaron fuera del '
                f'relevamiento automatizado por el criterio de la sección 7.4. Este resultado forma parte de '
                f'los hallazgos: describe las condiciones de acceso público que fijan las propias plataformas.</p>'
                f'<div class="tarjeta"><table><thead><tr><th>Motivo</th><th class="num">Plataformas</th></tr>'
                f'</thead><tbody>{filas}</tbody></table></div>')

    def _cobertura(self, d: DatosInforme) -> str:
        if not d.auditados:
            return ""
        esperados_m = len(d.auditados) * len(INDICADORES_MANUALES)
        cargados_m = sum(1 for r in d.results if r["metodo"] == "M")
        auto = [r for r in d.results if r["metodo"] == "A"]
        n0 = sum(1 for r in auto if r["compliance"] == 0)
        return (f'<h2>2. Cobertura del relevamiento</h2>'
                f'<p>Valores automáticos: {len(auto)}; de ellos, {n0} no verificables (valor 0). '
                f'Valores manuales cargados: {cargados_m} de {esperados_m} previstos '
                f'({len(INDICADORES_MANUALES)} indicadores por plataforma).</p>')

    def _distribucion(self, d: DatosInforme) -> str:
        if not d.results:
            return '<h2>3. Distribución de frecuencias</h2><p>Sin observaciones registradas.</p>'
        c = Counter(r["compliance"] for r in d.results)
        total = len(d.results)
        filas = "".join(f'<tr><td><span class="celda c{v}" style="display:inline-block;padding:0 6px">{v}</span>'
                        f' {_e(COMPLIANCE_SCALE[v])}</td><td class="num">{c.get(v, 0)}</td>'
                        f'<td class="num">{_num(100 * c.get(v, 0) / total, 1)} %</td></tr>' for v in (3, 2, 1, 0))
        cab = "".join(f'<th class="num">{v}</th>' for v in (3, 2, 1, 0))
        por_dim = ""
        for dim in DIMS:
            cd = Counter(r["compliance"] for r in d.results if r["dimension_id"] == dim)
            if sum(cd.values()):
                por_dim += (f'<tr><td>{dim} {_e(QA_DIMENSIONS[dim]["name"])}</td>'
                            + "".join(f'<td class="num">{cd.get(v, 0)}</td>' for v in (3, 2, 1, 0))
                            + f'<td class="num">{sum(cd.values())}</td></tr>')
        return (f'<h2>3. Distribución de frecuencias</h2>'
                f'<p>{total} observaciones anidadas en {len(d.auditados)} plataformas. No son casos '
                f'independientes: cada plataforma aporta hasta 32 observaciones.</p>'
                f'<div class="tarjeta"><table><thead><tr><th>Categoría</th><th class="num">n</th>'
                f'<th class="num">%</th></tr></thead><tbody>{filas}</tbody></table></div>'
                f'<div class="tarjeta">{_leyenda_categorias()}{svg_distribucion(d.results)}</div>'
                f'<div class="tarjeta"><table><thead><tr><th>Dimensión</th>{cab}<th class="num">Total</th></tr>'
                f'</thead><tbody>{por_dim}</tbody></table></div>')

    def _puntajes(self, d: DatosInforme) -> str:
        if not d.por_sitio:
            return ""
        cab = "".join(f'<th class="num" title="{_e(QA_DIMENSIONS[x]["name"])}">{x}</th>' for x in DIMS)
        filas = ""
        for sid in d.auditados:
            celdas = ""
            for dim in DIMS:
                s = d.por_sitio[sid].get(dim)
                if not s or s["avg_compliance"] is None:
                    celdas += '<td class="num nota" title="Sin valores válidos">nd</td>'
                else:
                    celdas += (f'<td class="num" title="{s["n_validos"]} válidos, {s["n_na"]} N/A">'
                               f'{_num(s["avg_compliance"])}</td>')
            filas += f'<tr><td>{_e(d.alias[sid])}</td>{celdas}</tr>'
        return (f'<h2>4. Puntaje por dimensión (S<sub>i,k</sub>)</h2>'
                f'<p>Promedio de los indicadores con valor mayor que 0 (Anexo B.4.1). Por tratarse de una '
                f'escala ordinal, se usa como medida exploratoria de tendencia central, no como magnitud de '
                f'intervalo. «nd»: la dimensión no tiene valores válidos.</p>'
                f'<div class="tarjeta"><table><thead><tr><th>Plataforma</th>{cab}</tr></thead>'
                f'<tbody>{filas}</tbody></table></div>')

    def _perfiles(self, d: DatosInforme) -> str:
        if not d.por_sitio:
            return ""
        return (f'<h2>5. Comparación de perfiles</h2>'
                f'<p>Cada línea es el perfil de una plataforma en las ocho dimensiones. La comparación se '
                f'lee dimensión por dimensión; no se resume en un índice único (sección 7.4.2).</p>'
                f'<div class="tarjeta">{svg_perfiles(d.por_sitio, d.alias)}</div>')

    def _detalle(self, d: DatosInforme) -> str:
        if not d.results:
            return ""
        return (f'<h2>6. Detalle por indicador</h2>'
                f'<div class="tarjeta">{html_detalle(d.results, d.alias)}</div>')

    def _concordancia(self) -> str:
        from modules.concordancia import calcular_concordancia
        res = calcular_concordancia(self.db)
        if res["n"] == 0:
            return ""
        filas = "".join(
            f'<tr><td>{_e(k)}</td><td class="num">{v["n"]}</td><td class="num">{_num(100 * v["acuerdo"], 1)} %</td>'
            f'<td class="num">{_fmt_k(v["kappa"])}</td><td class="num">{_fmt_k(v["kappa_ponderado"])}</td></tr>'
            for k, v in [("Total", res)] + sorted(res["por_dimension"].items()))
        return (f'<h2>7. Concordancia entre codificación automática y manual</h2>'
                f'<p>Muestra de control codificada manualmente sin conocer el valor automático. '
                f'Kappa de Cohen sin ponderar y con ponderación cuadrática para escalas ordinales.</p>'
                f'<div class="tarjeta"><table><thead><tr><th>Ámbito</th><th class="num">n</th>'
                f'<th class="num">Acuerdo</th><th class="num">κ</th><th class="num">κ ponderado</th></tr>'
                f'</thead><tbody>{filas}</tbody></table></div>')

    def _nota_metodologica(self) -> str:
        return ('<h2>Nota metodológica</h2><ul>'
                '<li>Escala ordinal: 3 cumple plenamente, 2 parcialmente, 1 no cumple, 0 no aplica o no '
                'verificable. El valor 0 se asigna cuando la página no pudo observarse (inexistente, bloqueada '
                'por robots.txt, sin respuesta o detrás de un inicio de sesión) y se excluye del puntaje '
                'por dimensión.</li>'
                '<li>No se calcula un índice agregado: la ponderación entre dimensiones carece de sustento en '
                'la literatura de referencia y en el número de casos (sección 7.4.2).</li>'
                '<li>Las reglas de valoración de cada indicador están en docs/reglas_de_valoracion.md.</li>'
                '<li>La triangulación con la encuesta se realiza a nivel agregado (sección 7.6), fuera de '
                'este instrumento.</li></ul>')


def _fmt_k(k) -> str:
    return "—" if k is None else f"{k:.2f}".replace(".", ",")


# ─────────────────────────────────────────────────────────────────────────────
class CSVReporter:
    def __init__(self, db: DatabaseManager, output_dir: Path = CSV_DIR):
        self.db, self.output_dir = db, output_dir

    def export_all(self) -> list[Path]:
        return self.db.export_anonimizado(self.output_dir)


class ConsoleReporter:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def print_audit_summary(self) -> None:
        d = DatosInforme(self.db)
        if d.simulado:
            print("\n  ⚠ DATOS SIMULADOS — no son observaciones reales.")
        if not d.por_sitio and not d.exclusiones:
            print("\n  [!] Sin datos de auditoría.\n")
            return
        print("\n  PUNTAJE POR DIMENSIÓN (S_ik) — sin índice agregado (sección 7.4.2)")
        print("  " + f"{'Plataforma':<20}" + "".join(f"{x:>7}" for x in DIMS))
        for sid in d.auditados:
            fila = f"  {d.alias[sid]:<20}"
            for dim in DIMS:
                s = d.por_sitio[sid].get(dim)
                fila += f"{(s['avg_compliance'] if s and s['avg_compliance'] is not None else 'nd'):>7}"
            print(fila)
        if d.exclusiones:
            print(f"\n  Plataformas excluidas: {len(d.exclusiones)}")
            for c, n in Counter(e["codigo"] for e in d.exclusiones).items():
                print(f"    {c}: {n}")
        print()


class ReportEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def generate(self, fmt: str = "all") -> None:
        if fmt in ("all", "console"):
            ConsoleReporter(self.db).print_audit_summary()
        if fmt in ("all", "csv"):
            for p in CSVReporter(self.db).export_all():
                print(f"  CSV anonimizado: {p}")
        if fmt in ("all", "html"):
            print(f"  Informe HTML: {HTMLReporter(self.db).generate()}")
