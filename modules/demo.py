"""
modules/demo.py — Modo de demostración con DATOS SIMULADOS
=========================================================
Sirve solo para verificar que el sistema funciona (almacenamiento, informes,
gráficos) sin acceder a sitios reales. Salvaguardas:

  - escribe en una base separada (config.DB_DEMO_PATH), nunca en la de datos
    observados;
  - las plataformas son ficticias (dominios reservados .example);
  - cada plataforma se registra con origen «simulado» y todo informe generado
    sobre esta base lo declara en el título y en un aviso destacado;
  - la semilla es fija, por lo que la simulación es reproducible.

Los datos simulados NO deben citarse como resultados de la investigación.
"""

from __future__ import annotations

import logging
import random

from config import DB_DEMO_PATH, INDICADORES
from modules.storage import (ORIGEN_SIMULADO, AuditResult, DatabaseManager, ProductData,
                             SnapshotRecord)

logger = logging.getLogger(__name__)

SEMILLA_DEMO = 2026

_SIMULATED_SITES = [
    {"id": "DEMO01", "name": "Plataforma simulada 1", "base_url": "https://plataforma-1.example",
     "platform": "simulada", "region": "simulada", "origen": ORIGEN_SIMULADO},
    {"id": "DEMO02", "name": "Plataforma simulada 2", "base_url": "https://plataforma-2.example",
     "platform": "simulada", "region": "simulada", "origen": ORIGEN_SIMULADO},
    {"id": "DEMO03", "name": "Plataforma simulada 3", "base_url": "https://plataforma-3.example",
     "platform": "simulada", "region": "simulada", "origen": ORIGEN_SIMULADO},
]
_SITIO_EXCLUIDO = {"id": "DEMO04", "name": "Plataforma simulada 4", "base_url": "https://plataforma-4.example",
                   "platform": "simulada", "region": "simulada", "origen": ORIGEN_SIMULADO}

# Media simulada por dimensión (escala 1-3) para cada plataforma ficticia
_SITE_PROFILES = {
    "DEMO01": {"D1": 2.8, "D2": 2.4, "D3": 2.6, "D4": 2.2, "D5": 2.5, "D6": 2.0, "D7": 1.8, "D8": 2.7},
    "DEMO02": {"D1": 2.2, "D2": 1.6, "D3": 2.0, "D4": 2.4, "D5": 1.8, "D6": 2.6, "D7": 2.2, "D8": 2.0},
    "DEMO03": {"D1": 1.8, "D2": 1.2, "D3": 1.5, "D4": 1.8, "D5": 1.4, "D6": 1.6, "D7": 1.0, "D8": 1.6},
}
_PROB_NO_VERIFICABLE = 0.08

_CATEGORIAS = ["Bebidas", "Almacén", "Limpieza", "Perfumería", "Lácteos"]


def _resultados(site_id: str, rng: random.Random) -> list[AuditResult]:
    perfil = _SITE_PROFILES[site_id]           # KeyError si falta: no se simula con valores por defecto
    res = []
    for ind, tc in INDICADORES.items():
        if rng.random() < _PROB_NO_VERIFICABLE:
            valor, nota = 0, "simulado: no verificable"
        else:
            valor = min(3, max(1, round(perfil[tc["dimension_id"]] + rng.gauss(0, 0.4))))
            nota = "simulado"
        res.append(AuditResult(site_id=site_id, test_case_id=ind, compliance=valor,
                               metodo=tc["relevamiento"], pagina=tc["pagina"],
                               evidence="DATO SIMULADO", notes=nota, auditor="demo"))
    return res


def _productos(site_id: str, snap_id: int, rng: random.Random) -> list[ProductData]:
    prods = []
    for i in range(rng.randint(20, 40)):
        pu = round(rng.uniform(300, 3000), 2)
        prods.append(ProductData(
            site_id=site_id, snapshot_id=snap_id,
            product_url=f"https://{site_id.lower()}.example/producto-simulado-{i}",
            name=f"Producto simulado {i}", category=rng.choice(_CATEGORIAS),
            price_unit=pu, price_bulk=round(pu * rng.choice([6, 12, 24]), 2),
            unit_measure=rng.choice(["kg", "lt", "g", "ml"]), quantity_per_bulk=rng.choice([6, 12, 24]),
            stock_status=rng.choice(["disponible"] * 4 + ["sin stock"]),
            has_discount=rng.random() < 0.2))
    return prods


def run_demo(db: DatabaseManager | None = None) -> DatabaseManager:
    """Puebla la base de demostración con datos simulados reproducibles."""
    db = db or DatabaseManager(DB_DEMO_PATH)
    if db.db_path.resolve() != DB_DEMO_PATH.resolve() and "demo" not in db.db_path.name:
        raise ValueError("El modo demo solo escribe en la base de demostración (config.DB_DEMO_PATH).")
    rng = random.Random(SEMILLA_DEMO)
    print("\n  MODO DEMOSTRACIÓN — DATOS SIMULADOS (no son observaciones reales)\n")
    for site in _SIMULATED_SITES + [_SITIO_EXCLUIDO]:
        db.clear_site_results(site["id"])
        db.upsert_site(site, origen=ORIGEN_SIMULADO)
    for site in _SIMULATED_SITES:
        db.guardar_resultados(_resultados(site["id"], rng))
        snap_id = db.insert_snapshot(SnapshotRecord(site_id=site["id"], snapshot_number=1,
                                                    notes="DATOS SIMULADOS"))
        prods = _productos(site["id"], snap_id, rng)
        db.insert_products_bulk(prods)
        db.update_snapshot_count(snap_id, len(prods), len({p.category for p in prods}))
    db.registrar_exclusion(_SITIO_EXCLUIDO["id"], "robots_bloquea_inicio", "simulado")
    print(f"  ✓ {len(_SIMULATED_SITES)} plataformas simuladas y 1 exclusión simulada "
          f"(semilla {SEMILLA_DEMO}); base: {db.db_path.name}\n")
    return db
