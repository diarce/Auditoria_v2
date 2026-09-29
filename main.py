#!/usr/bin/env python3
"""
main.py — Punto de entrada por consola de AuditMayorista
========================================================
Uso:
  python main.py universo                       Resumen del universo (sin datos identificatorios)
  python main.py audit [--site ID] [--dimension D3]
                                                Auditoría automatizada (25 indicadores A)
  python main.py plantilla-manual               Planilla para los 7 indicadores manuales
  python main.py importar-manual ARCHIVO.csv    Carga la verificación manual
  python main.py muestra-control [--n 40] [--semilla 2026]
                                                Muestra para codificación manual de control
  python main.py importar-control ARCHIVO.csv --codificador NOMBRE
  python main.py concordancia                   Acuerdo y kappa automático vs. manual
  python main.py scrape [--snapshot 1|2|3]      Relevamiento de productos del catálogo
  python main.py report [--format all|console|csv|html]
  python main.py demo                           Demostración con DATOS SIMULADOS (base separada)

Los sitios se leen de data/privado/universo.csv (no publicado).
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DB_DEMO_PATH, DB_PATH, LOGS_DIR, VERSION  # noqa: E402
from modules.storage import DatabaseManager  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="auditmayorista",
                                description=f"AuditMayorista {VERSION} — auditoría digital académica")
    p.add_argument("--verbose", "-v", action="store_true")
    sub = p.add_subparsers(dest="command", metavar="COMANDO")
    sub.add_parser("universo", help="Resumen del universo del estudio")
    a = sub.add_parser("audit", help="Auditoría automatizada")
    a.add_argument("--site", "-s", metavar="ID")
    a.add_argument("--dimension", "-d", metavar="D1..D8")
    sub.add_parser("plantilla-manual", help="Planilla de verificación manual")
    im = sub.add_parser("importar-manual", help="Cargar verificación manual")
    im.add_argument("archivo")
    mc = sub.add_parser("muestra-control", help="Muestra para control de concordancia")
    mc.add_argument("--n", type=int, default=40)
    mc.add_argument("--semilla", type=int, default=2026)
    ic = sub.add_parser("importar-control", help="Cargar codificación manual de control")
    ic.add_argument("archivo")
    ic.add_argument("--codificador", default="")
    sub.add_parser("concordancia", help="Calcular concordancia")
    s = sub.add_parser("scrape", help="Relevamiento de productos del catálogo")
    s.add_argument("--site", "-s", metavar="ID")
    s.add_argument("--snapshot", type=int, choices=[1, 2, 3], default=1)
    r = sub.add_parser("report", help="Generar informes")
    r.add_argument("--format", "-f", choices=["all", "console", "csv", "html"], default="all")
    r.add_argument("--demo", action="store_true", help="Informe de la base de demostración (simulada)")
    sub.add_parser("demo", help="Demostración con datos simulados")
    return p


def setup_logging(verbose: bool) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(LOGS_DIR / f"run_{ts}.log", encoding="utf-8")])
    for ruidoso in ("urllib3", "requests", "charset_normalizer", "bs4"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def main() -> None:
    args = build_parser().parse_args()
    if args.command is None:
        build_parser().print_help()
        return
    setup_logging(args.verbose)

    if args.command == "demo":
        from modules.demo import run_demo
        from modules.reporter import ReportEngine
        ReportEngine(run_demo()).generate("all")
        return

    db = DatabaseManager(DB_DEMO_PATH if getattr(args, "demo", False) else DB_PATH)

    if args.command == "universo":
        from modules.universo import cargar_universo, resumen_universo, ruta_universo, usa_datos_de_ejemplo
        u = cargar_universo()
        print(f"\n  Universo: {len(u)} registros ({'EJEMPLO ficticio' if usa_datos_de_ejemplo() else ruta_universo().name})")
        for estado, n in resumen_universo(u).most_common():
            print(f"    {estado:<45} {n}")
        print()

    elif args.command == "audit":
        from modules.auditor import DESCRIPCION_EXCLUSION, AuditEngine
        from modules.universo import sitios_para_auditar, usa_datos_de_ejemplo
        if usa_datos_de_ejemplo():
            print("  [!] No existe data/privado/universo.csv; no se audita el universo de ejemplo.")
            return
        res = AuditEngine(db).run(site_filter=args.site, dimension_filter=args.dimension,
                                  sites_override=sitios_para_auditar())
        for sid, r in res.items():
            estado = f"EXCLUIDA — {DESCRIPCION_EXCLUSION[r.codigo_exclusion]}" if r.excluida \
                else f"{len(r.resultados)} indicadores valorados"
            print(f"  {sid}: {estado}")

    elif args.command == "plantilla-manual":
        from modules.importer import generar_plantilla_csv
        ids = sorted({r["site_id"] for r in db.get_audit_results()})
        print(f"  Plantilla: {generar_plantilla_csv(ids)}")

    elif args.command == "importar-manual":
        from modules.importer import AuditImporter
        res = AuditImporter(db).from_csv(args.archivo)
        for e in res["errores"]:
            print(f"  ! {e}")

    elif args.command == "muestra-control":
        from modules.concordancia import generar_muestra_control
        print(f"  Muestra de control: {generar_muestra_control(db, n=args.n, semilla=args.semilla)}")

    elif args.command == "importar-control":
        from modules.concordancia import importar_control
        print(f"  {importar_control(db, Path(args.archivo), args.codificador)} valores de control cargados.")

    elif args.command == "concordancia":
        from modules.concordancia import calcular_concordancia
        r = calcular_concordancia(db)
        fk = lambda k: "—" if k is None else f"{k:.3f}"  # noqa: E731
        print(f"\n  n = {r['n']} · acuerdo = {r['acuerdo']:.1%} · kappa = {fk(r['kappa'])} · "
              f"kappa ponderado = {fk(r['kappa_ponderado'])}")
        for d, v in sorted(r["por_dimension"].items()):
            print(f"    {d}: n={v['n']} acuerdo={v['acuerdo']:.1%} kappa={fk(v['kappa'])}")
        print()

    elif args.command == "scrape":
        from modules.scraper import ScrapingEngine
        from modules.universo import sitios_para_auditar
        ScrapingEngine(db).run(site_filter=args.site, snapshot_number=args.snapshot,
                               sites_override=sitios_para_auditar())

    elif args.command == "report":
        from modules.reporter import ReportEngine
        ReportEngine(db).generate(fmt=args.format)


if __name__ == "__main__":
    main()
