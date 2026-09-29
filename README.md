# AuditMayorista

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/diarce/Auditoria/blob/main/AuditMayorista_Colab.ipynb)

Instrumento de auditoría digital automatizada del desarrollo funcional de plataformas de comercio electrónico mayorista. Es el instrumento metodológico de la tesis *Factores estratégicos asociados al desarrollo del comercio electrónico en tiendas mayoristas de bienes de consumo masivo de Posadas, Misiones* (Maestría en Administración Estratégica de Negocios, UNaM, FCE). El software no es objeto de estudio de la tesis: es un medio de recolección de datos.

**Versión 6.0.0.** Los cambios respecto de la 5.0 están en [CHANGELOG.md](CHANGELOG.md).

## Correspondencia con la tesis

| Elemento | Tesis | Implementación |
| --- | --- | --- |
| Indicadores | 32 en 8 dimensiones (Anexo C) | `config.QA_TEST_CASES`, mismos identificadores |
| Relevamiento | 25 automáticos, 7 manuales (Tablas B.2 y B.3) | campo `relevamiento`; los manuales se cargan con `importar-manual` |
| Página de medición | Tabla B.2 | campo `pagina`: inicio, listado, ficha, registro, informativas, ruta inexistente |
| Escala | 3 pleno, 2 parcial, 1 no cumple, 0 no aplica o no verificable (7.4) | `config.COMPLIANCE_SCALE`; 0 cuando la página no puede observarse |
| Puntaje por dimensión | Promedio de valores mayores que 0 (B.4.1) | `DatabaseManager.get_dimension_scores` |
| Índice agregado | Descartado (7.4.2) | no existe; el análisis compara perfiles por dimensión |
| Criterio de exclusión | robots.txt no autoriza las secciones requeridas (7.4) | la plataforma se excluye y el motivo se informa como resultado |
| Protocolo ético | robots.txt, demora con variación aleatoria, solo GET (7.4.1) | `modules/ethics.py`; también respeta `Crawl-delay` |
| Ámbito | Municipio de Posadas (7.3) | `config.RESEARCH_CONTEXT`; otras localidades quedan fuera de ámbito |
| Anonimización | Alias por plataforma (B.5) | «Sitio Auditado N»; la tabla de correspondencia vive fuera del repositorio |

Las reglas de valoración de cada indicador están en [docs/reglas_de_valoracion.md](docs/reglas_de_valoracion.md). Las reglas de los siete indicadores manuales están marcadas como propuesta.

## Datos identificatorios

El repositorio no contiene URL ni nombres de organizaciones. El universo real se guarda en `data/privado/universo.csv`, con el formato de [data/universo_ejemplo.csv](data/universo_ejemplo.csv). La carpeta `data/privado/` y las salidas (`outputs/`) están excluidas del control de versiones.

## Instalación y uso

Requiere Python 3.10 o superior. Ver [docs/INSTALACION.md](docs/INSTALACION.md).

```bash
pip install -r requirements.txt
python main.py universo                      # resumen del universo
python main.py audit                         # 25 indicadores automáticos
python main.py plantilla-manual              # planilla de los 7 indicadores manuales
python main.py importar-manual data/privado/plantilla_verificacion_manual.csv
python main.py muestra-control --n 40        # muestra para el control de concordancia
python main.py importar-control data/privado/muestra_control_semilla2026.csv --codificador "Codificador 1"
python main.py concordancia                  # acuerdo y kappa (sin ponderar y cuadrático)
python main.py report                        # informe HTML y CSV anonimizados
```

Interfaz gráfica local: `pip install -r requirements-app.txt` y luego `streamlit run app.py`.

### Modo demostración

`python main.py demo` genera **datos simulados** para verificar el funcionamiento sin acceder a sitios reales. Escribe en una base separada, usa plataformas ficticias con semilla fija y todo informe que produce lo declara en el título y en un aviso. Esos datos no deben citarse como resultados.

## Pruebas

```bash
pip install pytest
python -m pytest -q
```

Las pruebas usan un sitio ficticio servido en la propia máquina. Verifican, entre otras cosas, los 32 indicadores del Anexo C, la exclusión por robots.txt, el valor 0 para páginas no observables, la ausencia de índice agregado y la ausencia de dominios de organizaciones en los archivos publicables.

## Cita

```bibtex
@software{AuditMayorista2026,
  author  = {Arce, Diego Enrique},
  title   = {{AuditMayorista}: instrumento de auditoría digital automatizada del desarrollo
             funcional de plataformas de comercio electrónico mayorista},
  year    = {2026},
  version = {6.0.0},
  url     = {https://github.com/diarce/Auditoria}
}
```

Cite también el identificador del commit usado para relevar los datos; el informe HTML lo incluye en su encabezado.

## Licencia

Código: GNU GPL v3 o posterior ([LICENSE](LICENSE)). Documentación y datos de ejemplo: CC BY-SA 4.0 ([LICENSE-DOCS.md](LICENSE-DOCS.md)).

**Autor:** Diego Enrique Arce · **Director:** Dr. Carlos Roberto Brys · Universidad Nacional de Misiones, Facultad de Ciencias Económicas
