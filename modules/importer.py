"""
modules/importer.py — Carga de la verificación manual (Tabla B.2, indicadores M)
================================================================================
Los siete indicadores que requieren interactuar con la plataforma
(D2.4, D4.3, D4.4, D5.1, D5.4, D7.1, D7.2) se verifican manualmente y se
cargan con este módulo. Cada valor queda registrado con método «M», el
nombre del auditor y la fecha.

Reglas de validación:
  - el indicador debe existir en el Anexo C;
  - el valor debe estar en la escala 0-3;
  - por defecto solo se aceptan indicadores manuales; los automáticos se
    rechazan salvo `permitir_automaticos=True` (y entonces quedan como «M»);
  - no se aceptan valores de plataformas excluidas (criterio de la sección 7.4).

Columnas requeridas: site_id, test_case_id, compliance
Columnas opcionales: auditor, fecha_auditoria, notas, site_name, site_url
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from config import INDICADORES, INDICADORES_MANUALES, PRIVATE_DIR
from modules.storage import AuditResult, DatabaseManager

COLUMNAS_REQUERIDAS = ["site_id", "test_case_id", "compliance"]


class AuditImporter:

    def __init__(self, db: DatabaseManager, log_fn=None, permitir_automaticos: bool = False):
        self.db = db
        self.permitir_automaticos = permitir_automaticos
        self._log = log_fn or (lambda msg, nivel="INFO": print(f"[{nivel}] {msg}"))

    def from_csv(self, path, encoding: str = "utf-8-sig", delimiter: str = ",") -> dict:
        df = pd.read_csv(path, encoding=encoding, delimiter=delimiter, dtype=str, keep_default_na=False)
        return self._importar(df, Path(path).name)

    def from_excel(self, path, sheet=0) -> dict:
        df = pd.read_excel(path, sheet_name=sheet, dtype=str).fillna("")
        return self._importar(df, Path(path).name)

    def from_dataframe(self, df: pd.DataFrame, fuente: str = "dataframe") -> dict:
        return self._importar(df.astype(str).fillna(""), fuente)

    def _importar(self, df: pd.DataFrame, fuente: str) -> dict:
        res = {"fuente": fuente, "total_filas": len(df), "insertadas": 0, "omitidas": 0,
               "errores": [], "sitios_nuevos": []}
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        faltan = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
        if faltan:
            res["errores"].append(f"Columnas faltantes: {faltan}")
            self._log(res["errores"][-1], "ERR")
            return res

        excluidas = {e["site_id"] for e in self.db.get_exclusiones()}
        registros: list[AuditResult] = []
        for idx, fila in df.iterrows():
            n_fila = idx + 2
            sid = str(fila.get("site_id", "")).strip()
            ind = str(fila.get("test_case_id", "")).strip().upper()
            val = str(fila.get("compliance", "")).strip()
            if not sid or not ind or val == "":
                res["omitidas"] += 1
                continue                      # fila sin completar: se omite sin error
            if ind not in INDICADORES:
                res["omitidas"] += 1
                res["errores"].append(f"Fila {n_fila}: indicador desconocido «{ind}»")
                continue
            if ind not in INDICADORES_MANUALES and not self.permitir_automaticos:
                res["omitidas"] += 1
                res["errores"].append(f"Fila {n_fila}: {ind} es de relevamiento automático")
                continue
            try:
                valor = int(float(val))
                assert valor in (0, 1, 2, 3)
            except (ValueError, AssertionError):
                res["omitidas"] += 1
                res["errores"].append(f"Fila {n_fila}: valor «{val}» fuera de la escala 0-3")
                continue
            if sid in excluidas:
                res["omitidas"] += 1
                res["errores"].append(f"Fila {n_fila}: la plataforma {sid} está excluida (sección 7.4)")
                continue
            if self.db.get_site(sid) is None:
                self.db.upsert_site({"id": sid, "name": str(fila.get("site_name", "") or sid),
                                     "base_url": str(fila.get("site_url", "") or "")})
                res["sitios_nuevos"].append(sid)
            fecha = str(fila.get("fecha_auditoria", "") or datetime.now().date().isoformat())
            registros.append(AuditResult(
                site_id=sid, test_case_id=ind, compliance=valor, metodo="M", pagina="manual",
                notes=str(fila.get("notas", "")), auditor=str(fila.get("auditor", "")),
                evidence=f"verificación manual {fecha}"))
        if registros:
            self.db.guardar_resultados(registros)
        res["insertadas"] = len(registros)
        res["sitios_nuevos"] = sorted(set(res["sitios_nuevos"]))
        self._log(f"Importación: {res['insertadas']} valores cargados, {res['omitidas']} filas omitidas.", "OK")
        return res


def generar_plantilla_csv(site_ids: list[str] | None = None,
                          destino: Path | None = None) -> Path:
    """Plantilla con los 7 indicadores manuales por plataforma (se guarda en data/privado/)."""
    destino = Path(destino or (PRIVATE_DIR / "plantilla_verificacion_manual.csv"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    filas = []
    for sid in (site_ids or [""]):
        for ind in INDICADORES_MANUALES:
            tc = INDICADORES[ind]
            filas.append({"site_id": sid, "test_case_id": ind, "indicador": tc["name"],
                          "regla": tc["regla"], "compliance": "", "auditor": "",
                          "fecha_auditoria": "", "notas": ""})
    pd.DataFrame(filas).to_csv(destino, index=False, encoding="utf-8-sig")
    return destino
