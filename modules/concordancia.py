"""
modules/concordancia.py — Concordancia entre codificación automática y manual
=============================================================================
Procedimiento:
  1. `generar_muestra_control` selecciona al azar (semilla fija) un conjunto de
     pares plataforma × indicador automático, estratificado por dimensión, y
     escribe una planilla para codificación manual CIEGA (sin el valor
     automático). La planilla contiene URL y se guarda en data/privado/.
  2. El codificador valora cada par con las mismas reglas del instrumento
     (docs/reglas_de_valoracion.md) y completa la columna «valor_manual».
  3. `importar_control` carga la planilla; `calcular_concordancia` compara
     ambos valores: acuerdo porcentual, kappa de Cohen y kappa con ponderación
     cuadrática (adecuada para categorías ordenadas), en total y por dimensión.

El criterio para interpretar los coeficientes debe fijarse y citarse en la
tesis antes de conocer los resultados.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path

from config import INDICADORES, PRIVATE_DIR
from modules.storage import DatabaseManager

CATEGORIAS = (0, 1, 2, 3)


# ─────────────────────────────────────────────────────────────────────────────
def kappa_cohen(a: list[int], b: list[int], ponderacion: str | None = None) -> float | None:
    """
    Kappa de Cohen para dos codificaciones de los mismos casos.
    ponderacion=None → kappa sin ponderar; "cuadratica" → pesos 1-(i-j)²/(k-1)².
    Devuelve None si no está definido (acuerdo esperado igual a 1).
    """
    if len(a) != len(b) or not a:
        return None
    k = len(CATEGORIAS)
    idx = {c: i for i, c in enumerate(CATEGORIAS)}
    n = len(a)
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    fila = [sum(obs[i]) for i in range(k)]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    def peso(i, j):
        if ponderacion == "cuadratica":
            return 1 - ((i - j) ** 2) / ((k - 1) ** 2)
        return 1.0 if i == j else 0.0

    po = sum(peso(i, j) * obs[i][j] for i in range(k) for j in range(k)) / n
    pe = sum(peso(i, j) * fila[i] * col[j] for i in range(k) for j in range(k)) / (n * n)
    if abs(1 - pe) < 1e-12:
        return None
    return (po - pe) / (1 - pe)


def _resumen(pares: list[tuple[int, int]]) -> dict:
    a = [p[0] for p in pares]
    b = [p[1] for p in pares]
    n = len(pares)
    return {
        "n": n,
        "acuerdo": (sum(1 for x, y in pares if x == y) / n) if n else 0.0,
        "kappa": kappa_cohen(a, b),
        "kappa_ponderado": kappa_cohen(a, b, "cuadratica"),
    }


# ─────────────────────────────────────────────────────────────────────────────
def generar_muestra_control(db: DatabaseManager, n: int = 40, semilla: int = 2026,
                            destino: Path | None = None) -> Path:
    """Muestra aleatoria estratificada por dimensión de valores automáticos."""
    auto = [r for r in db.get_audit_results() if r["metodo"] == "A"]
    if not auto:
        raise ValueError("No hay valores automáticos para muestrear.")
    por_dim: dict[str, list[dict]] = defaultdict(list)
    for r in auto:
        por_dim[r["dimension_id"]].append(r)
    rng = random.Random(semilla)
    n = min(n, len(auto))
    # Asignación proporcional con al menos 1 caso por dimensión presente
    cuota = {d: max(1, round(n * len(v) / len(auto))) for d, v in por_dim.items()}
    muestra = []
    for d in sorted(por_dim):
        casos = sorted(por_dim[d], key=lambda r: (r["site_id"], r["test_case_id"]))
        muestra.extend(rng.sample(casos, min(cuota[d], len(casos))))
    rng.shuffle(muestra)

    destino = destino or (PRIVATE_DIR / f"muestra_control_semilla{semilla}.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["site_id", "test_case_id", "indicador", "regla", "url_evaluada",
                    "valor_manual", "codificador", "notas"])
        for r in muestra:
            tc = INDICADORES[r["test_case_id"]]
            w.writerow([r["site_id"], r["test_case_id"], tc["name"], tc["regla"],
                        r["url_evaluada"], "", "", ""])
    return destino


def importar_control(db: DatabaseManager, ruta: Path, codificador: str = "") -> int:
    n = 0
    with Path(ruta).open(encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            valor = (fila.get("valor_manual") or "").strip()
            if valor == "":
                continue
            db.guardar_control(fila["site_id"].strip(), fila["test_case_id"].strip(), int(valor),
                               codificador or (fila.get("codificador") or "").strip(),
                               (fila.get("notas") or "").strip())
            n += 1
    return n


def calcular_concordancia(db: DatabaseManager, codificador: str | None = None) -> dict:
    auto = {(r["site_id"], r["test_case_id"]): r["compliance"]
            for r in db.get_audit_results() if r["metodo"] == "A"}
    pares_total, por_dim = [], defaultdict(list)
    for c in db.get_control():
        if codificador and c["codificador"] != codificador:
            continue
        clave = (c["site_id"], c["test_case_id"])
        if clave in auto:
            par = (auto[clave], c["valor_manual"])
            pares_total.append(par)
            por_dim[INDICADORES[c["test_case_id"]]["dimension_id"]].append(par)
    res = _resumen(pares_total)
    res["por_dimension"] = {d: _resumen(p) for d, p in por_dim.items()}
    matriz = [[0] * 4 for _ in range(4)]
    for x, y in pares_total:
        matriz[x][y] += 1
    res["matriz"] = matriz          # filas: automático; columnas: manual
    return res
