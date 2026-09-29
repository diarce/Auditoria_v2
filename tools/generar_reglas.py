"""Genera docs/reglas_de_valoracion.md a partir de config.py (fuente única de las reglas)."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from config import COMPLIANCE_SCALE, QA_DIMENSIONS, QA_TEST_CASES, SECCIONES_REQUERIDAS, VERSION  # noqa: E402

PAGINAS = {
    "inicio": "página de inicio", "listado": "listado de productos de una categoría",
    "ficha": "ficha de producto", "registro": "formulario público de registro",
    "informativas": "páginas informativas (envíos, pagos, condiciones) y pie de la página de inicio",
    "inexistente": "ruta inexistente generada por el instrumento", "manual": "verificación manual",
}


def generar() -> str:
    lineas = [
        f"# Reglas de valoración — AuditMayorista {VERSION}",
        "",
        "Documento generado desde `config.py` con `python tools/generar_reglas.py`. No editar a mano.",
        "",
        "## Escala (sección 7.4)",
        "",
        *[f"- **{v}**: {t}" for v, t in COMPLIANCE_SCALE.items()],
        "",
        "## Reglas generales",
        "",
        "- Cada indicador se releva en la página que indica la Tabla B.2 (columna «Página»).",
        "- Si esa página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión, "
        "el valor es 0 (no verificable) y se registra el motivo. El 0 se excluye del puntaje por dimensión.",
        f"- Una plataforma se excluye del relevamiento si robots.txt no autoriza alguna de las secciones "
        f"requeridas ({', '.join(SECCIONES_REQUERIDAS)}), si robots.txt no puede leerse o si la página de "
        "inicio no responde. La exclusión se informa como resultado.",
        "- Los indicadores manuales (M) se cargan con `main.py importar-manual` y quedan registrados "
        "con método «M».",
        "",
    ]
    for dim, casos in QA_TEST_CASES.items():
        lineas += [f"## {dim} — {QA_DIMENSIONS[dim]['name']}", "",
                   "| ID | Indicador | Rel. | Página | Fund. | Regla de valoración |",
                   "| --- | --- | --- | --- | --- | --- |"]
        for tc in casos:
            lineas.append(f"| {tc['id']} | {tc['name']} | {tc['relevamiento']} | {PAGINAS[tc['pagina']]} | "
                          f"{tc['fundamentacion']} | {tc['regla']} |")
        lineas.append("")
    return "\n".join(lineas)


if __name__ == "__main__":
    destino = RAIZ / "docs" / "reglas_de_valoracion.md"
    destino.write_text(generar(), encoding="utf-8")
    print(f"Escrito: {destino}")
