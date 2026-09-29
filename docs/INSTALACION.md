# Instalación

## Requisitos

- Python 3.10 o superior.
- Conexión a internet para instalar paquetes y para relevar los sitios.

## Pasos

```bash
git clone https://github.com/diarce/Auditoria.git
cd Auditoria
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # instrumento
pip install -r requirements-app.txt  # opcional: interfaz Streamlit
pip install -r requirements-dev.txt  # opcional: pruebas
```

## Universo privado

Copie el universo real a `data/privado/universo.csv` con las columnas de `data/universo_ejemplo.csv`. Esa carpeta no se sube al repositorio. Sin ese archivo, el sistema solo muestra el universo de ejemplo y no audita.

El user-agent informa un contacto a los sitios auditados. Por defecto es el de `CITATION.cff`; puede cambiarse sin editar el código:

```bash
export AUDIT_CONTACTO="nombre@institucion.edu.ar"
```

## Verificación

```bash
python -m pytest -q
python main.py demo      # informe de demostración con DATOS SIMULADOS
```

## Limitación conocida

El instrumento analiza el HTML que entregan los servidores, como indica la Tabla B.2. No ejecuta JavaScript. En plataformas que construyen la página en el navegador, algunos elementos pueden no estar en ese HTML; en ese caso el indicador puede resultar 1 o 0 por limitación técnica y no por ausencia de la función. La muestra de control de concordancia permite estimar ese efecto.
