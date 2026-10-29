# Guía de Clean&Process

Clean&Process toma los datos capturados por el scraper, los revisa y los organiza
para mostrar productos, precios, imágenes y opiniones con su evidencia de origen.

El recorrido en la aplicación es:

**URL → Captura del scraper → Clean&Process → Resultados y gráficas**

La limpieza se aplica a los datos obtenidos. Clean&Process no vuelve a navegar
por las páginas ni modifica la captura original.

## 1. Recibir y validar la información

La aplicación puede trabajar con una captura nueva o con archivos compatibles.
El adaptador convierte la información del scraper al formato que entiende
Clean&Process.

Se comprueba que los datos tengan una estructura válida, identificadores únicos
y referencias a bloques existentes. Un archivo incompatible produce un error;
no se presenta como una importación correcta.

## 2. Guardar la evidencia original

Cada bloque conserva su procedencia: página de origen, texto, campos originales
y localización dentro de la captura.

Esto permite explicar de dónde salió un nombre, una imagen o una puntuación.
Excluir un producto del resultado no implica borrar su evidencia.

## 3. Reconocer qué representa cada bloque

Los bloques se organizan en tipos como producto, categoría, oferta, imagen,
descripción, reseña o valoración agregada.

Se utiliza la información declarada por la fuente y, cuando está habilitado,
el reconocimiento por vocabulario y el modelo local E5. La similitud ayuda a
encontrar candidatos, pero necesita respaldo en los datos para aceptarlos.

Si se elige Jev, también se interpreta texto libre. Las interpretaciones deben
apoyarse en fragmentos del texto original. Lo que no se puede identificar con
evidencia suficiente queda sin resolver y se registra en los diagnósticos.

## 4. Excluir productos relacionados con cookies por su nombre

La regla actual excluye los bloques clasificados como producto cuyo campo
`name` contenga `cookie`, sin distinguir mayúsculas y minúsculas. Esto también
cubre `cookies` y nombres como `Cookiebot`.

| Nombre del registro | Resultado |
| --- | --- |
| Cookie Consent | Se excluye. |
| Administrar COOKIES | Se excluye. |
| Cookie Consent · Products · OneTrust | Se excluye. |
| Loción hidratante facial | Se conserva, si cumple las demás validaciones. |

La comprobación se hace después del reconocimiento y antes de incorporar el
producto al catálogo procesado. El registro excluido no aporta sus propios
datos de producto, imágenes ni puntuaciones al resultado. Tampoco se crean
relaciones hacia el producto excluido.

Una mención a cookies en la descripción, en la URL o en un aviso de la página
no elimina por sí sola un producto legítimo. La regla comprueba el nombre del
producto, no todo el contenido de la página.

La exclusión se informa con el diagnóstico `product_excluded_cookie`, que
incluye el nombre y una referencia a la evidencia original.

**Alcance de la regla:** filtra nombres que contienen esa palabra. Otros servicios
ajenos al catálogo, con nombres diferentes, pueden seguir apareciendo; esta regla
no determina por sí sola si un producto pertenece a la categoría buscada.

## 5. Validar los campos y normalizar valores cuando hay respaldo

Se revisa que cada dato sea adecuado para su campo: por ejemplo, que un nombre
sea texto, una URL sea válida o un porcentaje esté entre 0 y 100.

Cuando el reconocimiento está habilitado, se normalizan importes y descuentos
que puedan interpretarse sin adivinar su significado.

| Dato encontrado | Tratamiento |
| --- | --- |
| `20%` con una indicación explícita de descuento | Puede registrarse como descuento del 20 %. |
| `20%` como concentración de un ingrediente | No se convierte automáticamente en descuento. |
| `$100` | El símbolo por sí solo no permite afirmar que la moneda sea USD. |
| `$1.234` | Si el separador es ambiguo, el importe queda sin resolver. |
| Precio anterior | Se mantiene separado del precio actual. |
| Sin información de descuento | Se muestra como desconocido, no como ausencia confirmada de descuento. |

Un valor inválido o no reconocido se conserva en la evidencia, pero no se acepta
como un dato tipado válido del resultado.

## 6. Evitar duplicaciones y asociaciones sin respaldo

Dos apariciones de un producto pueden agruparse cuando coinciden su URL y nombre
normalizado y sus identificadores son compatibles. Un nombre parecido no alcanza
para afirmar que son el mismo producto.

Las reseñas necesitan una identidad explícita y un contenido coincidente para
deduplicarse. Repetir el mismo texto no demuestra por sí solo que sea una única
reseña.

Las relaciones también se validan: un producto se vincula con una categoría,
variante, imagen o reseña solo cuando los datos permiten sostener esa asociación.

## 7. Señalar datos contradictorios o incompletos

Si una misma muestra aporta valores incompatibles para un campo que debe tener
un único valor, se registra un conflicto. No se elige uno de ellos al azar.

También se registran campos ambiguos, límites de muestreo, asociaciones pendientes
y fallos de reconocimiento. Si E5 no está disponible, el reconocimiento puede
continuar por vocabulario, dejando constancia de esa limitación.

## 8. Preparar las cuatro secciones del análisis

### Precios

Se agrupan ofertas comparables por variante, moneda y condiciones. Un precio
aislado no demuestra un rango. No se convierten monedas ni se inventan variantes,
vendedores o períodos de vigencia.

### Imágenes

Se muestran las imágenes que quedaron asociadas al producto y sus usos conocidos.
El orden, la visibilidad y la función se conservan por separado cuando hay datos.
El procesamiento actual no interpreta los píxeles para inventar funciones visuales.

Un producto sin imagen asociada en el resultado puede tener una imagen en la web
que la captura o la asociación no haya recuperado.

### Keywords

Se toman las descripciones aceptadas y se evitan duplicados normalizando espacios,
mayúsculas y la representación de los caracteres. Se separan las palabras y se
excluyen palabras funcionales frecuentes en español e inglés, como «de», «la» o
«the».

Una palabra se muestra cuando aparece en al menos dos descripciones distintas
del conjunto analizado. Repetirla varias veces dentro de una descripción cuenta
una sola vez para esa descripción. Los temas interpretados se mantienen separados
de estas palabras repetidas.

### Opiniones

Se distinguen los textos de reseñas de las puntuaciones y cantidades publicadas.
Por ejemplo, «200 valoraciones» no significa que se hayan capturado y leído
200 reseñas.

Las opiniones se agrupan por aspecto y valoración cuando hay evidencia suficiente.
Las puntuaciones solo se normalizan cuando se conocen los límites de su escala.

## 9. Presentar y permitir revisar el resultado

Clean&Process genera los datos para las fichas, las gráficas y las secciones del
análisis. La interfaz muestra esa información sin volver a clasificarla.

El mismo procesamiento se utiliza al analizar una URL y al comparar dos fuentes.
En una comparación, cada fuente se procesa por separado; no se asume que los
productos de ambas sean equivalentes.

Desde los resultados se puede consultar la evidencia y descargar los archivos
disponibles: captura, entrada de procesamiento, salida completa y datos de
presentación.

## Cuándo se aplican las reglas nuevas

Las reglas de limpieza se aplican al ejecutar un nuevo procesamiento.
Los resultados ya guardados no se reescriben automáticamente.

Para aplicar una regla nueva a una captura anterior, hay que volver a procesar
esa captura. La importación de una salida ya procesada se valida y presenta
directamente: no vuelve a ejecutar la limpieza.
