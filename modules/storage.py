"""
modules/storage.py — Persistencia (SQLite + CSV)
================================================
Tablas:
  sites                 plataformas registradas (datos identificatorios: uso interno)
  audit_results         un valor por plataforma e indicador, con método A o M
  exclusiones           plataformas excluidas del relevamiento y motivo (sección 7.4)
  control_concordancia  codificación manual de control para medir concordancia
  snapshots, products, price_history   relevamiento de productos (scraping)

Las exportaciones anonimizadas reemplazan el identificador interno por el
alias «Sitio Auditado N» y omiten URL, nombres y evidencias textuales.
"""

from __future__ import annotations

import csv
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import COMPLIANCE_SCALE, INDICADORES

logger = logging.getLogger(__name__)

ORIGEN_OBSERVADO = "observado"
ORIGEN_SIMULADO = "simulado"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    base_url    TEXT NOT NULL,
    platform    TEXT,
    region      TEXT,
    origen      TEXT NOT NULL DEFAULT 'observado' CHECK (origen IN ('observado','simulado')),
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id          TEXT NOT NULL REFERENCES sites(id),
    dimension_id     TEXT NOT NULL,
    test_case_id     TEXT NOT NULL,
    test_case_name   TEXT NOT NULL,
    compliance       INTEGER NOT NULL CHECK (compliance BETWEEN 0 AND 3),
    compliance_label TEXT NOT NULL,
    metodo           TEXT NOT NULL CHECK (metodo IN ('A','M')),
    pagina           TEXT,
    url_evaluada     TEXT,
    evidence         TEXT,
    notes            TEXT,
    auditor          TEXT,
    audited_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (site_id, test_case_id)
);

CREATE TABLE IF NOT EXISTS exclusiones (
    site_id      TEXT PRIMARY KEY REFERENCES sites(id),
    codigo       TEXT NOT NULL,
    detalle      TEXT,
    registrada_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS control_concordancia (
    site_id       TEXT NOT NULL REFERENCES sites(id),
    test_case_id  TEXT NOT NULL,
    valor_manual  INTEGER NOT NULL CHECK (valor_manual BETWEEN 0 AND 3),
    codificador   TEXT,
    notas         TEXT,
    registrada_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (site_id, test_case_id, codificador)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id          TEXT REFERENCES sites(id),
    snapshot_number  INTEGER NOT NULL CHECK(snapshot_number BETWEEN 1 AND 3),
    products_count   INTEGER DEFAULT 0,
    categories_count INTEGER DEFAULT 0,
    scraped_at       TEXT DEFAULT (datetime('now')),
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id           TEXT REFERENCES sites(id),
    snapshot_id       INTEGER REFERENCES snapshots(id),
    name TEXT, brand TEXT, category TEXT, subcategory TEXT,
    price_unit REAL, price_bulk REAL, unit_measure TEXT, quantity_per_bulk INTEGER,
    stock_status TEXT, has_discount INTEGER DEFAULT 0, discount_pct REAL,
    ean TEXT, image_url TEXT, product_url TEXT NOT NULL,
    scraped_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT REFERENCES sites(id), product_url TEXT NOT NULL, product_name TEXT,
    price_unit REAL, price_bulk REAL, has_discount INTEGER DEFAULT 0,
    snapshot_number INTEGER, recorded_at TEXT DEFAULT (datetime('now'))
);
"""


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class ProductData:
    site_id: str
    snapshot_id: int
    product_url: str
    name: str = ""
    brand: str = ""
    category: str = ""
    subcategory: str = ""
    price_unit: float = 0.0
    price_bulk: float = 0.0
    unit_measure: str = ""
    quantity_per_bulk: int = 0
    stock_status: str = "desconocido"
    has_discount: bool = False
    discount_pct: float = 0.0
    ean: str = ""
    image_url: str = ""


@dataclass
class AuditResult:
    site_id: str
    test_case_id: str
    compliance: int
    metodo: str                 # 'A' automático | 'M' manual
    pagina: str = ""
    url_evaluada: str = ""
    evidence: str = ""
    notes: str = ""
    auditor: str = ""

    def __post_init__(self):
        if self.test_case_id not in INDICADORES:
            raise ValueError(f"Indicador desconocido: {self.test_case_id}")
        if self.compliance not in (0, 1, 2, 3):
            raise ValueError(f"Valor fuera de escala: {self.compliance}")
        if self.metodo not in ("A", "M"):
            raise ValueError(f"Método inválido: {self.metodo}")

    @property
    def dimension_id(self) -> str:
        return INDICADORES[self.test_case_id]["dimension_id"]

    @property
    def test_case_name(self) -> str:
        return INDICADORES[self.test_case_id]["name"]


@dataclass
class SnapshotRecord:
    site_id: str
    snapshot_number: int
    products_count: int = 0
    categories_count: int = 0
    notes: str = ""


def build_anon_map(site_ids) -> dict:
    """
    Alias determinístico «Sitio Auditado N» por orden de identificador interno.
    La correspondencia identificador → organización se conserva fuera del
    repositorio público (data/privado/), por lo que el alias no es reversible
    con la información publicada.
    """
    ids = sorted({s["id"] if isinstance(s, dict) else s for s in site_ids})
    return {sid: f"Sitio Auditado {i}" for i, sid in enumerate(ids, start=1)}


# ── DatabaseManager ────────────────────────────────────────────────────────────

class DatabaseManager:

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ── Sitios ─────────────────────────────────────────────────────────────────
    def upsert_site(self, site: dict, origen: str = ORIGEN_OBSERVADO) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sites (id, name, base_url, platform, region, origen)
                   VALUES (:id, :name, :base_url, :platform, :region, :origen)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, base_url=excluded.base_url,
                     platform=excluded.platform, region=excluded.region, origen=excluded.origen""",
                {"id": site["id"], "name": site.get("name", site["id"]),
                 "base_url": site.get("base_url", ""), "platform": site.get("platform", ""),
                 "region": site.get("region", ""), "origen": site.get("origen", origen)})

    def get_site(self, site_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone()
        return dict(row) if row else None

    def get_sites(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM sites ORDER BY id")]

    def origenes(self) -> set[str]:
        with self._connect() as conn:
            return {r[0] for r in conn.execute("SELECT DISTINCT origen FROM sites")}

    # ── Resultados ─────────────────────────────────────────────────────────────
    def guardar_resultados(self, results: list[AuditResult]) -> None:
        """Inserta o reemplaza el valor de cada (plataforma, indicador)."""
        rows = [(r.site_id, r.dimension_id, r.test_case_id, r.test_case_name, r.compliance,
                 COMPLIANCE_SCALE[r.compliance], r.metodo, r.pagina, r.url_evaluada,
                 r.evidence, r.notes, r.auditor, datetime.now().isoformat(timespec="seconds"))
                for r in results]
        with self._connect() as conn:
            conn.executemany(
                """INSERT INTO audit_results (site_id, dimension_id, test_case_id, test_case_name,
                     compliance, compliance_label, metodo, pagina, url_evaluada, evidence, notes,
                     auditor, audited_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(site_id, test_case_id) DO UPDATE SET
                     compliance=excluded.compliance, compliance_label=excluded.compliance_label,
                     metodo=excluded.metodo, pagina=excluded.pagina, url_evaluada=excluded.url_evaluada,
                     evidence=excluded.evidence, notes=excluded.notes, auditor=excluded.auditor,
                     audited_at=excluded.audited_at""", rows)
        logger.info(f"[DB] {len(rows)} resultados guardados.")

    # Alias usado por versiones anteriores
    insert_audit_results_bulk = guardar_resultados

    def borrar_resultados(self, site_id: str, metodo: str | None = None) -> None:
        with self._connect() as conn:
            if metodo:
                conn.execute("DELETE FROM audit_results WHERE site_id=? AND metodo=?", (site_id, metodo))
            else:
                conn.execute("DELETE FROM audit_results WHERE site_id=?", (site_id,))

    def get_audit_results(self, site_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM audit_results"
        args: tuple = ()
        if site_id:
            sql += " WHERE site_id = ?"
            args = (site_id,)
        sql += " ORDER BY site_id, dimension_id, test_case_id"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, args)]

    def get_dimension_scores(self) -> list[dict]:
        """
        Puntaje por dimensión S_ik (Anexo B.4.1): promedio de los valores > 0.
        n_validos = indicadores con valor > 0; n_na = indicadores con valor 0.
        """
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT site_id, dimension_id,
                       ROUND(AVG(CASE WHEN compliance > 0 THEN compliance END), 2) AS avg_compliance,
                       SUM(CASE WHEN compliance > 0 THEN 1 ELSE 0 END) AS n_validos,
                       SUM(CASE WHEN compliance = 0 THEN 1 ELSE 0 END) AS n_na,
                       COUNT(*) AS total_cases
                FROM audit_results
                GROUP BY site_id, dimension_id
                ORDER BY site_id, dimension_id""").fetchall()
        return [dict(r) for r in rows]

    # ── Exclusiones ────────────────────────────────────────────────────────────
    def registrar_exclusion(self, site_id: str, codigo: str, detalle: str = "") -> None:
        with self._connect() as conn:
            conn.execute("""INSERT INTO exclusiones (site_id, codigo, detalle) VALUES (?,?,?)
                            ON CONFLICT(site_id) DO UPDATE SET codigo=excluded.codigo,
                              detalle=excluded.detalle, registrada_at=datetime('now')""",
                         (site_id, codigo, detalle))

    def quitar_exclusion(self, site_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM exclusiones WHERE site_id=?", (site_id,))

    def get_exclusiones(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM exclusiones ORDER BY site_id")]

    # ── Concordancia ───────────────────────────────────────────────────────────
    def guardar_control(self, site_id: str, test_case_id: str, valor: int,
                        codificador: str = "", notas: str = "") -> None:
        if test_case_id not in INDICADORES or valor not in (0, 1, 2, 3):
            raise ValueError(f"Registro de control inválido: {test_case_id}={valor}")
        with self._connect() as conn:
            conn.execute("""INSERT INTO control_concordancia (site_id, test_case_id, valor_manual,
                              codificador, notas) VALUES (?,?,?,?,?)
                            ON CONFLICT(site_id, test_case_id, codificador) DO UPDATE SET
                              valor_manual=excluded.valor_manual, notas=excluded.notas""",
                         (site_id, test_case_id, valor, codificador, notas))

    def get_control(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM control_concordancia")]

    # ── Limpieza ───────────────────────────────────────────────────────────────
    def clear_site_results(self, site_id: str) -> None:
        with self._connect() as conn:
            for tabla in ["audit_results", "exclusiones", "control_concordancia",
                          "price_history", "products", "snapshots"]:
                conn.execute(f"DELETE FROM {tabla} WHERE site_id = ?", (site_id,))

    # ── Productos (scraping) ───────────────────────────────────────────────────
    def insert_snapshot(self, snap: SnapshotRecord) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO snapshots (site_id, snapshot_number, products_count, categories_count, notes) "
                "VALUES (?,?,?,?,?)",
                (snap.site_id, snap.snapshot_number, snap.products_count, snap.categories_count, snap.notes))
            return cur.lastrowid

    def update_snapshot_count(self, snap_id: int, products_count: int, categories_count: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE snapshots SET products_count=?, categories_count=? WHERE id=?",
                         (products_count, categories_count, snap_id))

    def insert_products_bulk(self, products: list[ProductData]) -> None:
        rows = [(p.site_id, p.snapshot_id, p.name, p.brand, p.category, p.subcategory,
                 p.price_unit, p.price_bulk, p.unit_measure, p.quantity_per_bulk, p.stock_status,
                 int(p.has_discount), p.discount_pct, p.ean, p.image_url, p.product_url)
                for p in products]
        with self._connect() as conn:
            conn.executemany(
                """INSERT INTO products (site_id, snapshot_id, name, brand, category, subcategory,
                     price_unit, price_bulk, unit_measure, quantity_per_bulk, stock_status,
                     has_discount, discount_pct, ean, image_url, product_url)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)

    def record_price_history(self, p: ProductData, snapshot_number: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO price_history (site_id, product_url, product_name, price_unit,
                     price_bulk, has_discount, snapshot_number) VALUES (?,?,?,?,?,?,?)""",
                (p.site_id, p.product_url, p.name, p.price_unit, p.price_bulk,
                 int(p.has_discount), snapshot_number))

    def get_products(self, site_id: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM products", ()
        if site_id:
            sql, args = sql + " WHERE site_id = ?", (site_id,)
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql + " ORDER BY site_id, category, name", args)]

    def get_price_history(self, site_id: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM price_history", ()
        if site_id:
            sql, args = sql + " WHERE site_id = ?", (site_id,)
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql + " ORDER BY site_id, product_url, snapshot_number", args)]

    # ── Exportación ────────────────────────────────────────────────────────────
    def export_anonimizado(self, output_dir: Path) -> list[Path]:
        """Resultados y exclusiones con alias; sin URL, nombres ni evidencias."""
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        resultados = self.get_audit_results()
        alias = build_anon_map({r["site_id"] for r in resultados})
        origen = {s["id"]: s["origen"] for s in self.get_sites()}
        archivos = []

        f1 = output_dir / f"resultados_anonimizados_{ts}.csv"
        with f1.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["plataforma", "origen", "dimension_id", "indicador", "nombre_indicador",
                        "valor", "categoria", "metodo", "pagina", "nota"])
            for r in resultados:
                w.writerow([alias[r["site_id"]], origen.get(r["site_id"], ""), r["dimension_id"],
                            r["test_case_id"], r["test_case_name"], r["compliance"],
                            r["compliance_label"], r["metodo"], r["pagina"], r["notes"]])
        archivos.append(f1)

        excl = self.get_exclusiones()
        if excl:
            f2 = output_dir / f"exclusiones_anonimizadas_{ts}.csv"
            alias_ex = {e["site_id"]: f"Plataforma excluida {i}" for i, e in enumerate(excl, 1)}
            with f2.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["plataforma", "origen", "codigo_motivo"])
                for e in excl:
                    w.writerow([alias_ex[e["site_id"]], origen.get(e["site_id"], ""), e["codigo"]])
            archivos.append(f2)
        return archivos

    def export_csv(self, table: str, output_path: Path) -> Path:
        """Exportación completa de una tabla (uso interno: contiene datos identificatorios)."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = output_path / f"{table}_{ts}.csv"
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        if rows:
            with open(out_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows([dict(r) for r in rows])
        return out_file
