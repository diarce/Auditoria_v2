"""
modules/universo.py — Universo de tiendas mayoristas del estudio
================================================================
Fuente: data/privado/universo.csv (excluido del repositorio público).
Si no existe, se usa data/universo_ejemplo.csv, con registros ficticios.

Columnas: id, nombre, ciudad, url_principal, url_alternativa, tipo_presencia,
plataforma_cms, nivel_digital, robots_permite, estado_auditoria, fuente,
notas_eticas, notas_metodologicas

estado_auditoria:
  AUDITAR                              plataforma propia con canal de venta en línea
  AUDITABLE_AUTOMATICO                 (valor anterior, equivale a AUDITAR)
  AUDITABLE_MANUAL_RECOMENDADO         (valor anterior, equivale a AUDITAR: la exclusión
                                        por robots.txt la decide el motor al relevar)
  EXCLUIR_QA_INCLUIR_ANALISIS_CUALITATIVO   sin canal de venta propio (solo redes sociales)
  PENDIENTE_TRABAJO_DE_CAMPO           sin URL verificada
  VERIFICAR                            datos incompletos

Ámbito (sección 7.3): solo se auditan registros cuya ciudad está en
config.RESEARCH_CONTEXT["localidades_admitidas"]; el resto se informa como
fuera de ámbito.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from config import RESEARCH_CONTEXT, UNIVERSO_EJEMPLO, UNIVERSO_PRIVADO

ESTADOS_A_AUDITAR = {"AUDITAR", "AUDITABLE_AUTOMATICO", "AUDITABLE_MANUAL_RECOMENDADO"}


@dataclass
class Empresa:
    id: str
    nombre: str
    ciudad: str
    url_principal: str
    url_alternativa: str
    tipo_presencia: str
    plataforma_cms: str
    nivel_digital: str
    robots_permite: str
    estado_auditoria: str
    fuente: str
    notas_eticas: str
    notas_metodologicas: str

    @property
    def en_ambito(self) -> bool:
        admitidas = {c.lower() for c in RESEARCH_CONTEXT["localidades_admitidas"]}
        return self.ciudad.strip().lower() in admitidas

    @property
    def estado_efectivo(self) -> str:
        if not self.en_ambito:
            return "FUERA_DE_AMBITO"
        if self.estado_auditoria in ESTADOS_A_AUDITAR:
            return "AUDITAR"
        return self.estado_auditoria


def ruta_universo() -> Path:
    return UNIVERSO_PRIVADO if UNIVERSO_PRIVADO.exists() else UNIVERSO_EJEMPLO


def usa_datos_de_ejemplo() -> bool:
    return not UNIVERSO_PRIVADO.exists()


def cargar_universo(csv_path: Path | None = None) -> list[Empresa]:
    csv_path = csv_path or ruta_universo()
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return [Empresa(**{k: (row.get(k) or "").strip() for k in Empresa.__dataclass_fields__})
                for row in csv.DictReader(f)]


def empresas_auditables(universo: list[Empresa]) -> list[Empresa]:
    return [e for e in universo if e.estado_efectivo == "AUDITAR" and e.url_principal.startswith("http")]


def empresas_excluidas(universo: list[Empresa]) -> list[Empresa]:
    """Sin canal de venta propio: se documentan como brecha digital, no se auditan."""
    return [e for e in universo if e.estado_efectivo == "EXCLUIR_QA_INCLUIR_ANALISIS_CUALITATIVO"]


def sitios_para_auditar(universo: list[Empresa] | None = None) -> list[dict]:
    universo = universo if universo is not None else cargar_universo()
    return [{"id": e.id, "name": e.nombre or e.id, "base_url": e.url_principal.rstrip("/"),
             "platform": e.plataforma_cms, "region": f"Misiones · {e.ciudad}", "selectors": {}}
            for e in empresas_auditables(universo)]


def registrar_en_db(universo: list[Empresa], db) -> int:
    sitios = sitios_para_auditar(universo)
    for s in sitios:
        db.upsert_site(s)
    return len(sitios)


def resumen_universo(universo: list[Empresa]) -> Counter:
    return Counter(e.estado_efectivo for e in universo)


def tabla_universo_html(universo: list[Empresa]) -> str:
    """Resumen por estado, sin nombres ni URL (apto para salidas que pueden publicarse)."""
    etiquetas = {
        "AUDITAR": "Canal de venta propio: se audita (sujeto al criterio de robots.txt)",
        "EXCLUIR_QA_INCLUIR_ANALISIS_CUALITATIVO": "Sin canal de venta propio: brecha digital",
        "PENDIENTE_TRABAJO_DE_CAMPO": "Pendiente de relevamiento de campo",
        "VERIFICAR": "Datos incompletos: por verificar",
        "FUERA_DE_AMBITO": "Fuera del municipio de Posadas",
    }
    c = resumen_universo(universo)
    filas = "".join(f"<tr><td>{etiquetas.get(k, k)}</td><td style='text-align:right'>{n}</td></tr>"
                    for k, n in c.most_common())
    origen = "datos de EJEMPLO ficticios" if usa_datos_de_ejemplo() else "universo privado del investigador"
    return (f"<table><thead><tr><th>Situación</th><th>Empresas</th></tr></thead><tbody>{filas}</tbody>"
            f"</table><p style='font-size:12px'>Fuente: {origen} · {len(universo)} registros.</p>")
