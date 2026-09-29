# Registro de cambios

## 6.0.0 — 2026-09-29

Versión que alinea el instrumento con lo descripto en la tesis (capítulo 7, anexos B y C). Rompe la compatibilidad con la base de datos de la 5.0: la nueva base es `outputs/auditoria_v6.db`.

### Correspondencia con la tesis

- 32 indicadores con los identificadores y nombres del Anexo C. Se retiraron el D3.6 (atributo alt, duplicaba D8.4) y el D6.3 anterior (HTTPS, duplicaba D8.3); la factura A pasa a ser D6.3.
- Cada indicador declara su tipo de relevamiento (25 automáticos y 7 manuales, Tabla B.2) y la página donde se mide.
- Los indicadores se miden en la página que indica la Tabla B.2 (listado, ficha, registro, páginas informativas, ruta inexistente), descubierta a partir de la página de inicio. Antes casi todos se medían en la página de inicio.
- Los siete indicadores manuales ya no se valoran automáticamente.
- Se eliminó el índice agregado ponderado (ICC) de informes, cuaderno, interfaz, README y `CITATION.cff`, en coherencia con la sección 7.4.2. El informe sigue el procedimiento de esa sección: distribución de frecuencias, puntaje por dimensión y comparación de perfiles.
- Se eliminó la frase de resultado fija del informe («Ninguna plataforma alcanza cumplimiento pleno»).
- Ámbito limitado al municipio de Posadas (incluye Itaembé Guazú; excluye Garupá).
- Nombre de D5 unificado como «Proceso de checkout», como en la Tabla B.1 y el Anexo C.

### Escala y exclusión

- El valor 0 se asigna cuando la página no puede observarse: no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. Antes esos casos se registraban como «No cumple».
- Criterio de exclusión (sección 7.4): la plataforma se excluye si robots.txt no autoriza la página de inicio, el listado o la ficha, si robots.txt no puede leerse o si la página de inicio no responde. La exclusión se registra con su motivo y se informa como resultado.
- Cada valor registra el método (A o M), la página y el auditor. Un nuevo relevamiento reemplaza los valores automáticos sin duplicarlos y conserva los manuales.

### Reglas de valoración

- D8.1: umbral de 4,0 s (antes 5,0 s) y sin categoría parcial, según Franco Ruiz (2017). Se mide el tiempo de respuesta del servidor.
- D8.3: se verifica la conexión HTTPS real con certificado válido y la redirección de HTTP a HTTPS. Antes se comprobaba solo el texto de la URL configurada.
- Factura A: solo «factura A» (distinguiendo mayúscula) da cumplimiento pleno; la mención de IVA discriminado da cumplimiento parcial; «factura B» ya no cuenta.
- D3.2 ya no acepta «por unidad»; D3.5 exige una escala por cantidad (las promociones NxM son cumplimiento parcial y las ofertas genéricas ya no cuentan).
- D6.1 cuenta los medios de pago nombrados; D6.2 ya no acepta la palabra «banco».
- D7.3 evalúa el código HTTP y la navegación de la página de error.
- Se leen datos estructurados schema.org (JSON-LD y microdatos) en la ficha de producto.
- Las reglas están en `docs/reglas_de_valoracion.md`, generado desde `config.py`.

### Protocolo ético

- robots.txt se descarga con el user-agent del estudio y con tiempo límite.
- Se respeta el `Crawl-delay`, con un limitador de demora por sitio.
- Las redirecciones se siguen una por una y se verifica robots.txt en cada destino.
- Todas las solicitudes, incluida la lectura de robots.txt, quedan en el registro de transparencia.
- El user-agent informa un contacto real (configurable con `AUDIT_CONTACTO`).

### Datos identificatorios

- Se retiraron del repositorio las URL reales, el universo con datos de contacto, los informes generados y la sección del cuaderno que mostraba nombres de empresas.
- El universo se lee de `data/privado/universo.csv`, excluido del control de versiones. Se incluye un universo de ejemplo ficticio.
- Los informes y los CSV anonimizados no incluyen URL, nombres ni evidencias textuales.

### Verificación manual y concordancia

- `importer.py` reescrito: funcionaba contra métodos y columnas inexistentes. Ahora valida indicador, escala, método y exclusión.
- Nuevo `modules/concordancia.py`: muestra aleatoria estratificada con semilla fija para codificación manual ciega, acuerdo porcentual y kappa de Cohen sin ponderar y con ponderación cuadrática.

### Modo demostración

- Escribe en una base separada, usa plataformas ficticias (`.example`), fija la semilla y aplica los perfiles simulados (antes no se aplicaban por un error de identificadores). Todo informe generado con esa base se rotula «DATOS SIMULADOS».
- El cuaderno de Colab ya no ejecuta la demostración en el flujo principal.

### Otros

- Se retiraron Playwright de las dependencias y la afirmación de que se renderizaba JavaScript: el instrumento analiza HTML (ver limitación en `docs/INSTALACION.md`).
- Licencia: GPL-3.0 o posterior para el código y CC BY-SA 4.0 para documentación y datos de ejemplo (antes CC BY-SA 2.5, no recomendada para software).
- Pruebas automáticas en `tests/` con un sitio ficticio local.
- Se retiró `docs_guia_instalacion.html` (versión 3.0, desactualizada); la instalación está en `docs/INSTALACION.md`.
