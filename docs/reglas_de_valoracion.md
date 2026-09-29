# Reglas de valoración — AuditMayorista 6.0.0

Documento generado desde `config.py` con `python tools/generar_reglas.py`. No editar a mano.

## Escala (sección 7.4)

- **3**: Cumple plenamente
- **2**: Cumple parcialmente
- **1**: No cumple
- **0**: No aplica / No verificable

## Reglas generales

- Cada indicador se releva en la página que indica la Tabla B.2 (columna «Página»).
- Si esa página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión, el valor es 0 (no verificable) y se registra el motivo. El 0 se excluye del puntaje por dimensión.
- Una plataforma se excluye del relevamiento si robots.txt no autoriza alguna de las secciones requeridas (inicio, listado, ficha), si robots.txt no puede leerse o si la página de inicio no responde. La exclusión se informa como resultado.
- Los indicadores manuales (M) se cargan con `main.py importar-manual` y quedan registrados con método «M».

## D1 — Estructura y navegación

| ID | Indicador | Rel. | Página | Fund. | Regla de valoración |
| --- | --- | --- | --- | --- | --- |
| D1.1 | Menú de navegación principal visible en cabecera | A | página de inicio | Dire. | 3 si hay un elemento de navegación principal; 1 si no. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D1.2 | Buscador interno de productos presente | A | página de inicio | Dire. | 3 si hay un campo de búsqueda; 1 si no. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D1.3 | Árbol de categorías accesible desde la página de inicio | A | página de inicio | Dire. | 3 con menú de categorías o 3 o más enlaces a categorías; 2 con 1 o 2 enlaces; 1 sin enlaces. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D1.4 | Breadcrumbs presentes en páginas de producto | A | ficha de producto | Dire. | 3 si la ficha muestra migas de pan (HTML o schema.org BreadcrumbList); 1 si no. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D1.5 | Filtros de ordenamiento en resultados de búsqueda | A | listado de productos de una categoría | Dire. | 3 con control de ordenamiento y filtros; 2 con solo uno de ellos; 1 sin ninguno. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |

## D2 — Registro y autenticación

| ID | Indicador | Rel. | Página | Fund. | Regla de valoración |
| --- | --- | --- | --- | --- | --- |
| D2.1 | Enlace o botón de registro de cuenta visible | A | página de inicio | Dire. | 3 con enlace explícito de registro; 2 si solo hay acceso a cuenta o ingreso; 1 sin acceso. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D2.2 | Campo CUIT/CUIL en formulario de alta | A | formulario público de registro | Cont. | 3 si el formulario de registro pide CUIT o CUIL; 1 si no. 0 si no hay formulario de registro público. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D2.3 | Diferenciación de tipo de cuenta (mayorista/minorista) | A | formulario público de registro | Parc. | 3 con un control que ofrece 2 o más tipos de cliente; 2 si el texto del registro alude a un tipo de cliente sin control; 1 si no. 0 si no hay formulario de registro público. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D2.4 | Formulario de inicio de sesión funcional | M | verificación manual | Parc. | Propuesta: 3 si hay formulario de ingreso con usuario, contraseña y recuperación de contraseña; 2 si falta la recuperación; 1 si no hay formulario de ingreso. No se envían credenciales. |

## D3 — Ficha de producto

| ID | Indicador | Rel. | Página | Fund. | Regla de valoración |
| --- | --- | --- | --- | --- | --- |
| D3.1 | Precio de venta visible en ficha de producto | A | ficha de producto | Parc. | 3 si la ficha muestra precio (schema.org o texto); 1 si no. 0 si el precio exige iniciar sesión. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D3.2 | Precio por bulto, pack o caja indicado | A | ficha de producto | Cont. | 3 si se informa precio o contenido por bulto, caja, pack, fardo o display; 1 si no. 0 si el precio exige iniciar sesión. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D3.3 | Unidad de medida especificada | A | ficha de producto | Cont. | 3 si se informa contenido neto (peso, volumen o unidades); 1 si no. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D3.4 | Indicador de disponibilidad de stock | A | ficha de producto | Dire. | 3 si se informa disponibilidad (schema.org availability o texto específico); 1 si no. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D3.5 | Descuento por volumen o escala visible | A | ficha de producto | Cont. | 3 si se informa una escala de precio según cantidad; 2 si solo hay promociones del tipo NxM; 1 si no. 0 si el precio exige iniciar sesión. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |

## D4 — Carrito de compras

| ID | Indicador | Rel. | Página | Fund. | Regla de valoración |
| --- | --- | --- | --- | --- | --- |
| D4.1 | Botón de agregar al carrito presente y visible | A | ficha de producto | Dire. | 3 si hay control de compra en la ficha; 1 si no. 0 si la compra exige iniciar sesión. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D4.2 | Cantidad mínima de compra comunicada | A | ficha de producto | Cont. | 3 si la ficha comunica una cantidad o monto mínimo; 1 si no. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D4.3 | Selector de cantidad de unidades en carrito | M | verificación manual | Parc. | Propuesta: 3 si en el carrito se puede cambiar la cantidad de cada ítem y quitarlo; 2 si solo una de las dos; 1 si ninguna. 0 si el carrito exige iniciar sesión. |
| D4.4 | Subtotal actualizado visible en carrito | M | verificación manual | Dire. | Propuesta: 3 si el carrito muestra el subtotal y lo actualiza al cambiar cantidades; 2 si lo muestra sin actualizarlo; 1 si no lo muestra. 0 si el carrito exige iniciar sesión. |

## D5 — Proceso de checkout

| ID | Indicador | Rel. | Página | Fund. | Regla de valoración |
| --- | --- | --- | --- | --- | --- |
| D5.1 | Indicador de etapas de progreso en checkout | M | verificación manual | Dire. | Propuesta: 3 si el checkout muestra las etapas y señala la actual; 2 si muestra etapas sin señalar la actual; 1 si no hay indicador. 0 si el checkout exige iniciar sesión. |
| D5.2 | Opción de envío a domicilio disponible | A | páginas informativas (envíos, pagos, condiciones) y pie de la página de inicio | Parc. | 3 si las páginas informativas o el pie del sitio informan envío o entrega a domicilio; 1 si no. 0 si no hay páginas informativas accesibles. |
| D5.3 | Opción de retiro en sucursal disponible | A | páginas informativas (envíos, pagos, condiciones) y pie de la página de inicio | Dire. | 3 si las páginas informativas o el pie del sitio informan retiro en local, sucursal o depósito; 1 si no. 0 si no hay páginas informativas accesibles. |
| D5.4 | Formulario de dirección de entrega presente | M | verificación manual | Parc. | Propuesta: 3 si el checkout pide la dirección de entrega en un formulario; 1 si no. 0 si el checkout exige iniciar sesión. |

## D6 — Medios de pago

| ID | Indicador | Rel. | Página | Fund. | Regla de valoración |
| --- | --- | --- | --- | --- | --- |
| D6.1 | Medios de pago listados en el sitio | A | páginas informativas (envíos, pagos, condiciones) y pie de la página de inicio | Dire. | 3 si se nombran 2 o más medios de pago; 2 si se nombra 1; 1 si ninguno. 0 si no hay páginas informativas accesibles. |
| D6.2 | Opción de transferencia bancaria disponible | A | páginas informativas (envíos, pagos, condiciones) y pie de la página de inicio | Dire. | 3 si se informa pago por transferencia o depósito bancario; 1 si no. 0 si no hay páginas informativas accesibles. |
| D6.3 | Factura tipo A disponible para revendedores | A | páginas informativas (envíos, pagos, condiciones) y pie de la página de inicio | Cont. | 3 si se informa emisión de factura A; 2 si solo se menciona IVA discriminado o responsables inscriptos; 1 si no. 0 si no hay páginas informativas accesibles. |

## D7 — Comunicación de errores y retroalimentación

| ID | Indicador | Rel. | Página | Fund. | Regla de valoración |
| --- | --- | --- | --- | --- | --- |
| D7.1 | Confirmación visual al agregar producto al carrito | M | verificación manual | Parc. | Propuesta: 3 si al agregar un producto aparece un mensaje o panel de confirmación; 2 si solo cambia el contador del carrito; 1 sin confirmación. 0 si agregar exige iniciar sesión. |
| D7.2 | Mensajes de error en formularios (validación) | M | verificación manual | Dire. | Propuesta: 3 si un formulario enviado con datos inválidos muestra el error junto al campo; 2 si el mensaje es genérico; 1 sin mensaje. 0 si no hay formulario accesible sin sesión. |
| D7.3 | Página de error 404 con navegación útil | A | ruta inexistente generada por el instrumento | Parc. | 3 si una ruta inexistente responde 404 o 410 y ofrece navegación; 2 si cumple solo una de las dos condiciones; 1 si ninguna. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |

## D8 — Desempeño técnico

| ID | Indicador | Rel. | Página | Fund. | Regla de valoración |
| --- | --- | --- | --- | --- | --- |
| D8.1 | Tiempo de respuesta del servidor inferior al umbral | A | página de inicio | Dire. | 3 si la página de inicio responde en 4,0 s o menos; 1 si tarda más. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D8.2 | Meta viewport para adaptación móvil presente | A | página de inicio | Dire. | 3 con meta viewport width=device-width; 2 con meta viewport sin ese valor; 1 sin meta viewport. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D8.3 | Conexión segura HTTPS | A | página de inicio | Dire. | 3 si el sitio responde por HTTPS con certificado válido y HTTP redirige a HTTPS; 2 si responde por HTTPS pero la redirección no se verifica; 1 sin HTTPS válido. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
| D8.4 | Imágenes del catálogo con atributo alt | A | listado de productos de una categoría | Dire. | 3 si todas las imágenes del listado tienen alt; 2 si al menos la mitad; 1 si menos. 0 si el listado no tiene imágenes. 0 si la página no existe, está bloqueada por robots.txt, no responde o exige iniciar sesión. |
