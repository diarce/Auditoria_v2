# Makefile — AuditMayorista 6.0.0
.PHONY: help install install-app test web universo audit report demo reglas clean

PYTHON = python3

help:           ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install:        ## Instala las dependencias del instrumento
	$(PYTHON) -m pip install -r requirements.txt

install-app:    ## Instala además la interfaz Streamlit
	$(PYTHON) -m pip install -r requirements-app.txt

test:           ## Ejecuta las pruebas
	$(PYTHON) -m pytest -q

web:            ## Interfaz local en http://localhost:8501
	$(PYTHON) -m streamlit run app.py

universo:       ## Resumen del universo del estudio
	$(PYTHON) main.py universo

audit:          ## Auditoría automatizada del universo privado
	$(PYTHON) main.py audit

report:         ## Informe HTML y CSV anonimizados
	$(PYTHON) main.py report

demo:           ## Demostración con DATOS SIMULADOS (base separada)
	$(PYTHON) main.py demo

reglas:         ## Regenera docs/reglas_de_valoracion.md desde config.py
	$(PYTHON) tools/generar_reglas.py

clean:          ## Borra las salidas locales (no toca data/privado/)
	rm -rf outputs/
