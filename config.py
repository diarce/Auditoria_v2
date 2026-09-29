"""
config.py — Configuración central del instrumento de auditoría
===============================================================
Proyecto : AuditMayorista — auditoría digital automatizada del desarrollo
           funcional de plataformas de comercio electrónico mayorista
Contexto : Tesis de Maestría en Administración Estratégica de Negocios
           (UNaM, FCE). Ver capítulo 7 y anexos B y C.
Versión  : 6.0.0

Correspondencia con la tesis
----------------------------
- 32 indicadores en 8 dimensiones, con los identificadores del Anexo C.
- 25 indicadores de relevamiento automático (A) y 7 de verificación manual (M),
  según la Tabla B.2.
- Escala 0-3: 3 cumple plenamente, 2 cumple parcialmente, 1 no cumple,
  0 no aplica o no verificable (sección 7.4).
- Sin índice agregado ni ponderaciones (sección 7.4.2): el análisis compara
  perfiles por dimensión.

Datos identificatorios
----------------------
Este archivo no contiene URL ni nombres de organizaciones. Los sitios a
auditar se leen en tiempo de ejecución desde data/privado/universo.csv,
carpeta excluida del control de versiones (.gitignore).
"""

import os
from pathlib import Path

VERSION = "6.0.0"

# ── Directorios ────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
OUTPUT_DIR    = BASE_DIR / "outputs"          # excluido del repositorio
LOGS_DIR      = OUTPUT_DIR / "logs"
CSV_DIR       = OUTPUT_DIR / "csv"
REPORTS_DIR   = OUTPUT_DIR / "reports"
SNAPSHOTS_DIR = OUTPUT_DIR / "snapshots"
DB_PATH       = OUTPUT_DIR / "auditoria_v6.db"   # datos observados
DB_DEMO_PATH  = OUTPUT_DIR / "demo_simulada.db"  # datos simulados (nunca se mezclan)

PRIVATE_DIR      = BASE_DIR / "data" / "privado"   # excluido del repositorio
UNIVERSO_PRIVADO = PRIVATE_DIR / "universo.csv"
UNIVERSO_EJEMPLO = BASE_DIR / "data" / "universo_ejemplo.csv"

for d in [OUTPUT_DIR, LOGS_DIR, CSV_DIR, REPORTS_DIR, SNAPSHOTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# ÁMBITO DEL ESTUDIO (sección 7.3)
# ══════════════════════════════════════════════════════════════════════════════
# Tiendas mayoristas de bienes de consumo masivo radicadas en el municipio de
# Posadas (totalidad del ejido municipal). Itaembé Guazú es un barrio de Posadas
# con delegación municipal propia; Garupá es un municipio distinto y queda fuera.
RESEARCH_CONTEXT = {
    "provincia"             : "Misiones",
    "ambito"                : "Municipio de Posadas (totalidad del ejido municipal)",
    "localidades_admitidas" : ["Posadas", "Itaembé Guazú"],
    "mercado"               : "Tiendas mayoristas de bienes de consumo masivo",
    "region"                : "NEA — Nordeste Argentino",
}

# Sitios a auditar: se completan en tiempo de ejecución (modules/universo.py).
SITES: list[dict] = []


# ══════════════════════════════════════════════════════════════════════════════
# PROTOCOLO ÉTICO (sección 7.4.1)
# ══════════════════════════════════════════════════════════════════════════════
# Contacto que se informa a los sitios en el user-agent. Puede cambiarse con la
# variable de entorno AUDIT_CONTACTO sin editar el código.
CONTACTO_INVESTIGADOR = os.environ.get("AUDIT_CONTACTO", "diarce@fce.unam.edu.ar")

SCRAPING_CONFIG = {
    # Identificación transparente del agente. El primer token ("AuditMayorista")
    # es el que se compara con las reglas User-agent de robots.txt.
    "user_agent": (
        f"AuditMayorista/{VERSION} "
        "(investigacion academica no comercial; UNaM-FCE; "
        f"+https://github.com/diarce/Auditoria; contacto: {CONTACTO_INVESTIGADOR})"
    ),
    # Cadencia entre solicitudes a un mismo sitio: base + variación aleatoria en
    # [-jitter/2, +jitter], con mínimo de 1 s. Si robots.txt declara un
    # Crawl-delay mayor, se usa ese valor como base.
    "rate_limit_seconds"        : 3.0,
    "rate_limit_jitter"         : 1.5,
    "timeout_seconds"           : 30,
    # Límites de relevamiento
    "max_candidatos_por_seccion": 3,    # enlaces probados para hallar listado/ficha/registro
    "max_paginas_informativas"  : 4,
    "max_products_per_site"     : 200,  # scraping de catálogo (relevamiento de productos)
    "max_products_per_category" : 50,
    "snapshot_intervals_days"   : [0, 7, 14],
    "respect_robots_txt"        : True,  # obligatorio en este protocolo
    "headers": {
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.5",
        "Accept"         : "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "DNT"            : "1",
    },
}

# Secciones cuyo bloqueo por robots.txt excluye a la plataforma del relevamiento
# (sección 7.4, criterio de exclusión). El bloqueo de otras secciones no excluye:
# los indicadores afectados se valoran 0 (no verificable).
SECCIONES_REQUERIDAS = ("inicio", "listado", "ficha")

# Umbral de tiempo de respuesta (D8.1; Franco Ruiz, 2017: más de 4 s es falla)
UMBRAL_TIEMPO_RESPUESTA_S = 4.0


# ══════════════════════════════════════════════════════════════════════════════
# ESCALA DE VALORACIÓN (sección 7.4)
# ══════════════════════════════════════════════════════════════════════════════
COMPLIANCE_SCALE = {
    3: "Cumple plenamente",
    2: "Cumple parcialmente",
    1: "No cumple",
    0: "No aplica / No verificable",
}


# ══════════════════════════════════════════════════════════════════════════════
# DIMENSIONES (Tabla B.1) — sin ponderaciones (sección 7.4.2)
# ══════════════════════════════════════════════════════════════════════════════
QA_DIMENSIONS = {
    "D1": {"name": "Estructura y navegación",
           "description": "Arquitectura de navegación: menú, buscador, categorías, migas de pan y ordenamiento."},
    "D2": {"name": "Registro y autenticación",
           "description": "Alta de clientes: acceso al registro, identificación fiscal y tipo de cuenta."},
    "D3": {"name": "Ficha de producto",
           "description": "Información comercial del producto: precio, bulto, unidad, stock y escalas."},
    "D4": {"name": "Carrito de compras",
           "description": "Mecanismos de compra: control de compra, mínimo, cantidades y subtotal."},
    "D5": {"name": "Proceso de checkout",
           "description": "Etapas de compra y condiciones de entrega informadas."},
    "D6": {"name": "Medios de pago",
           "description": "Medios de pago y condiciones fiscales informados."},
    "D7": {"name": "Comunicación de errores y retroalimentación",
           "description": "Confirmaciones, validación de formularios y página de error."},
    "D8": {"name": "Desempeño técnico",
           "description": "Tiempo de respuesta, adaptación móvil, HTTPS y texto alternativo."},
}


# ══════════════════════════════════════════════════════════════════════════════
# INDICADORES (Anexo C) — 32 en total: 25 automáticos (A) y 7 manuales (M)
# ══════════════════════════════════════════════════════════════════════════════
# pagina: sección del sitio donde se releva el indicador (Tabla B.2)
#   inicio | listado | ficha | registro | informativas | inexistente | manual
# fundamentacion: Dire. (concordancia directa), Parc. (parcial), Cont. (contextual)
# regla: regla de valoración aplicada (documentada en docs/reglas_de_valoracion.md)
def _ind(id_, nombre, relevamiento, pagina, fundamentacion, fuente, regla):
    return {"id": id_, "name": nombre, "relevamiento": relevamiento, "pagina": pagina,
            "fundamentacion": fundamentacion, "fuente": fuente, "regla": regla}

_SIN = "0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión."

QA_TEST_CASES = {
    "D1": [
        _ind("D1.1", "Menú de navegación principal visible en cabecera", "A", "inicio", "Dire.",
             "Franco Ruiz (2017)", "3 si hay un elemento de navegación principal; 1 si no. " + _SIN),
        _ind("D1.2", "Buscador interno de productos presente", "A", "inicio", "Dire.",
             "Pedraza Jiménez et al. (2016)", "3 si hay un campo de búsqueda; 1 si no. " + _SIN),
        _ind("D1.3", "Árbol de categorías accesible desde la página de inicio", "A", "inicio", "Dire.",
             "Pedraza Jiménez et al. (2016)",
             "3 con menú de categorías o 3 o más enlaces a categorías; 2 con 1 o 2 enlaces; 1 sin enlaces. " + _SIN),
        _ind("D1.4", "Breadcrumbs presentes en páginas de producto", "A", "ficha", "Dire.",
             "Franco Ruiz (2017)", "3 si la ficha muestra migas de pan (HTML o schema.org BreadcrumbList); 1 si no. " + _SIN),
        _ind("D1.5", "Filtros de ordenamiento en resultados de búsqueda", "A", "listado", "Dire.",
             "Pedraza Jiménez et al. (2016)",
             "3 con control de ordenamiento y filtros; 2 con solo uno de ellos; 1 sin ninguno. " + _SIN),
    ],
    "D2": [
        _ind("D2.1", "Enlace o botón de registro de cuenta visible", "A", "inicio", "Dire.",
             "Pedraza Jiménez et al. (2016)",
             "3 con enlace explícito de registro; 2 si solo hay acceso a cuenta o ingreso; 1 sin acceso. " + _SIN),
        _ind("D2.2", "Campo CUIT/CUIL en formulario de alta", "A", "registro", "Cont.",
             "Elaboración propia",
             "3 si el formulario de registro pide CUIT o CUIL; 1 si no. 0 si no hay formulario de registro público. " + _SIN),
        _ind("D2.3", "Diferenciación de tipo de cuenta (mayorista/minorista)", "A", "registro", "Parc.",
             "Pedraza Jiménez et al. (2016)",
             "3 con un control que ofrece 2 o más tipos de cliente; 2 si el texto del registro alude a un tipo de "
             "cliente sin control; 1 si no. 0 si no hay formulario de registro público. " + _SIN),
        _ind("D2.4", "Formulario de inicio de sesión funcional", "M", "manual", "Parc.",
             "Franco Ruiz (2017)", 
             "Propuesta: 3 si hay formulario de ingreso con usuario, contraseña y recuperación de contraseña; 2 si falta la recuperación; 1 si no hay formulario de ingreso. No se envían credenciales."),
    ],
    "D3": [
        _ind("D3.1", "Precio de venta visible en ficha de producto", "A", "ficha", "Parc.",
             "Pedraza Jiménez et al. (2016)",
             "3 si la ficha muestra precio (schema.org o texto); 1 si no. 0 si el precio exige iniciar sesión. " + _SIN),
        _ind("D3.2", "Precio por bulto, pack o caja indicado", "A", "ficha", "Cont.",
             "Elaboración propia",
             "3 si se informa precio o contenido por bulto, caja, pack, fardo o display; 1 si no. "
             "0 si el precio exige iniciar sesión. " + _SIN),
        _ind("D3.3", "Unidad de medida especificada", "A", "ficha", "Cont.",
             "Elaboración propia", "3 si se informa contenido neto (peso, volumen o unidades); 1 si no. " + _SIN),
        _ind("D3.4", "Indicador de disponibilidad de stock", "A", "ficha", "Dire.",
             "Pedraza Jiménez et al. (2016)",
             "3 si se informa disponibilidad (schema.org availability o texto específico); 1 si no. " + _SIN),
        _ind("D3.5", "Descuento por volumen o escala visible", "A", "ficha", "Cont.",
             "Elaboración propia",
             "3 si se informa una escala de precio según cantidad; 2 si solo hay promociones del tipo NxM; 1 si no. "
             "0 si el precio exige iniciar sesión. " + _SIN),
    ],
    "D4": [
        _ind("D4.1", "Botón de agregar al carrito presente y visible", "A", "ficha", "Dire.",
             "Pedraza Jiménez et al. (2016)",
             "3 si hay control de compra en la ficha; 1 si no. 0 si la compra exige iniciar sesión. " + _SIN),
        _ind("D4.2", "Cantidad mínima de compra comunicada", "A", "ficha", "Cont.",
             "Elaboración propia",
             "3 si la ficha comunica una cantidad o monto mínimo; 1 si no. " + _SIN),
        _ind("D4.3", "Selector de cantidad de unidades en carrito", "M", "manual", "Parc.",
             "Franco Ruiz (2017)", 
             "Propuesta: 3 si en el carrito se puede cambiar la cantidad de cada ítem y quitarlo; 2 si solo una de las dos; 1 si ninguna. 0 si el carrito exige iniciar sesión."),
        _ind("D4.4", "Subtotal actualizado visible en carrito", "M", "manual", "Dire.",
             "Pedraza Jiménez et al. (2016)", 
             "Propuesta: 3 si el carrito muestra el subtotal y lo actualiza al cambiar cantidades; 2 si lo muestra sin actualizarlo; 1 si no lo muestra. 0 si el carrito exige iniciar sesión."),
    ],
    "D5": [
        _ind("D5.1", "Indicador de etapas de progreso en checkout", "M", "manual", "Dire.",
             "Pedraza Jiménez et al. (2016)", 
             "Propuesta: 3 si el checkout muestra las etapas y señala la actual; 2 si muestra etapas sin señalar la actual; 1 si no hay indicador. 0 si el checkout exige iniciar sesión."),
        _ind("D5.2", "Opción de envío a domicilio disponible", "A", "informativas", "Parc.",
             "Pedraza Jiménez et al. (2016)",
             "3 si las páginas informativas o el pie del sitio informan envío o entrega a domicilio; 1 si no. "
             "0 si no hay páginas informativas accesibles."),
        _ind("D5.3", "Opción de retiro en sucursal disponible", "A", "informativas", "Dire.",
             "Pedraza Jiménez et al. (2016)",
             "3 si las páginas informativas o el pie del sitio informan retiro en local, sucursal o depósito; 1 si no. "
             "0 si no hay páginas informativas accesibles."),
        _ind("D5.4", "Formulario de dirección de entrega presente", "M", "manual", "Parc.",
             "Pedraza Jiménez et al. (2016)", 
             "Propuesta: 3 si el checkout pide la dirección de entrega en un formulario; 1 si no. 0 si el checkout exige iniciar sesión."),
    ],
    "D6": [
        _ind("D6.1", "Medios de pago listados en el sitio", "A", "informativas", "Dire.",
             "Pedraza Jiménez et al. (2016)",
             "3 si se nombran 2 o más medios de pago; 2 si se nombra 1; 1 si ninguno. "
             "0 si no hay páginas informativas accesibles."),
        _ind("D6.2", "Opción de transferencia bancaria disponible", "A", "informativas", "Dire.",
             "Pedraza Jiménez et al. (2016)",
             "3 si se informa pago por transferencia o depósito bancario; 1 si no. "
             "0 si no hay páginas informativas accesibles."),
        _ind("D6.3", "Factura tipo A disponible para revendedores", "A", "informativas", "Cont.",
             "Elaboración propia",
             "3 si se informa emisión de factura A; 2 si solo se menciona IVA discriminado o responsables "
             "inscriptos; 1 si no. 0 si no hay páginas informativas accesibles."),
    ],
    "D7": [
        _ind("D7.1", "Confirmación visual al agregar producto al carrito", "M", "manual", "Parc.",
             "Pedraza Jiménez et al. (2016)", 
             "Propuesta: 3 si al agregar un producto aparece un mensaje o panel de confirmación; 2 si solo cambia el contador del carrito; 1 sin confirmación. 0 si agregar exige iniciar sesión."),
        _ind("D7.2", "Mensajes de error en formularios (validación)", "M", "manual", "Dire.",
             "Pedraza Jiménez et al. (2016)", 
             "Propuesta: 3 si un formulario enviado con datos inválidos muestra el error junto al campo; 2 si el mensaje es genérico; 1 sin mensaje. 0 si no hay formulario accesible sin sesión."),
        _ind("D7.3", "Página de error 404 con navegación útil", "A", "inexistente", "Parc.",
             "Franco Ruiz (2017)",
             "3 si una ruta inexistente responde 404 o 410 y ofrece navegación; 2 si cumple solo una de las dos "
             "condiciones; 1 si ninguna. " + _SIN),
    ],
    "D8": [
        _ind("D8.1", "Tiempo de respuesta del servidor inferior al umbral", "A", "inicio", "Dire.",
             "Franco Ruiz (2017)",
             "3 si la página de inicio responde en 4,0 s o menos; 1 si tarda más. " + _SIN),
        _ind("D8.2", "Meta viewport para adaptación móvil presente", "A", "inicio", "Dire.",
             "Pedraza Jiménez et al. (2016)",
             "3 con meta viewport width=device-width; 2 con meta viewport sin ese valor; 1 sin meta viewport. " + _SIN),
        _ind("D8.3", "Conexión segura HTTPS", "A", "inicio", "Dire.",
             "Franco Ruiz (2017)",
             "3 si el sitio responde por HTTPS con certificado válido y HTTP redirige a HTTPS; 2 si responde por "
             "HTTPS pero la redirección no se verifica; 1 sin HTTPS válido. " + _SIN),
        _ind("D8.4", "Imágenes del catálogo con atributo alt", "A", "listado", "Dire.",
             "Franco Ruiz (2017)",
             "3 si todas las imágenes del listado tienen alt; 2 si al menos la mitad; 1 si menos. "
             "0 si el listado no tiene imágenes. " + _SIN),
    ],
}

INDICADORES = {tc["id"]: {**tc, "dimension_id": dim}
               for dim, casos in QA_TEST_CASES.items() for tc in casos}
INDICADORES_AUTOMATICOS = [i for i, tc in INDICADORES.items() if tc["relevamiento"] == "A"]
INDICADORES_MANUALES    = [i for i, tc in INDICADORES.items() if tc["relevamiento"] == "M"]

assert len(INDICADORES) == 32, "El instrumento debe tener 32 indicadores (Anexo C)."
assert len(INDICADORES_AUTOMATICOS) == 25 and len(INDICADORES_MANUALES) == 7, "Tabla B.3: 25 A / 7 M."
