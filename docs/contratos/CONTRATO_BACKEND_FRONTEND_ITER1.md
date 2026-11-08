# Contrato Backend → Frontend — Iteración 1

Este documento especifica la respuesta que consume el frontend para las cuatro consultas de Iteración 1. El backend puede consultar un grafo RDF, pero debe entregar JSON de aplicación: el frontend no necesita ejecutar SPARQL ni recorrer triples.

## Alcance e integración

El contrato lógico ya está reflejado en `clean_process/contracts.py` y `clean_process/schemas/output.schema.json`. El resultado completo usa `contract_version: "1.0"`; la proyección orientada a presentación usa `contract_version: "1.0"` y reúne cada respuesta en `questions`, indexada por `question_id`.

Si el endpoint devuelve el resultado completo, las cuatro respuestas se encuentran en `data.question_results` (lista). Si devuelve la proyección de presentación, se encuentran en `questions` (objeto). Se recomienda que el endpoint de consulta use la proyección de presentación y que no obligue al frontend a reconstruir grupos desde `knowledge.assertions`.

Cada respuesta tiene esta envoltura:

```json
{
  "question_id": "price_range",
  "subject_ref": null,
  "status": "answered",
  "values": {},
  "supporting_assertion_ids": [],
  "exclusions": []
}
```

- `question_id`: identificador estable descrito abajo.
- `subject_ref`: URI/ID RDF de la entidad consultada cuando hay un único sujeto; `null` si el resultado cubre varios sujetos o el sujeto no se pudo resolver.
- `status`: `answered`, `partial` o `not_answerable`. `partial` señala que hay resultados utilizables junto con omisiones o datos incompletos. `not_answerable` significa que no se pudo producir ningún resultado utilizable; no significa lista vacía de productos.
- `values`: objeto con forma específica de la consulta. Las colecciones se devuelven como `[]`, nunca como `null`.
- `supporting_assertion_ids`: IDs de las aserciones RDF que sostienen los resultados.
- `exclusions`: elementos omitidos y razón legible por máquina. Puede estar vacío.

Los identificadores `*_ref` son referencias estables a entidades del grafo dentro del resultado, no etiquetas para mostrar. Para UI, usar `name`, `label`, `quotes` u otros campos textuales proporcionados. Importes se transportan como cadenas decimales para evitar pérdida de precisión; no combinar monedas, unidades, condiciones ni períodos diferentes.

## 1. ¿Qué rango de precio maneja el producto? — `price_range`

`values.groups` contiene un grupo por variante, moneda, condiciones y período de comparación. Solo precios exactos comparables participan en `average`, `minimum` y `maximum`; ofertas “desde”, “hasta”, cuotas y precio anterior siguen disponibles en `offers`, pero no se tratan como precios exactos. `average` se calcula al procesar la consulta: media aritmética redondeada a dos decimales con regla half-up. Si no hay precios exactos, vale `null`.

```json
{
  "question_id": "price_range",
  "subject_ref": null,
  "status": "answered",
  "values": {
    "groups": [
      {
        "variant_ref": "urn:webir:variant:123",
        "currency": "UYU",
        "conditions": {"membership_required": false},
        "comparison_time": ["sample", "sample-1"],
        "offers": [
          {
            "offer_ref": "urn:webir:offer:456",
            "amount": "1200.00",
            "kind": "exact",
            "seller": "Comercio A",
            "valid_period": null,
            "discount_status": "unknown",
            "discount_percent": null,
            "discount_amount": null,
            "previous_amount": null,
            "currency_symbol": "$",
            "assertion_refs": ["assertion-1"]
          }
        ],
        "price_observed": "1200.00",
        "average": "1200.00",
        "minimum": null,
        "maximum": null,
        "range_basis": "no_observed_range"
      }
    ]
  },
  "supporting_assertion_ids": ["assertion-1"],
  "exclusions": []
}
```

Campos de grupo: `variant_ref`, `currency` (código ISO 4217), `conditions` (JSON), `comparison_time` (período explícito o muestra de captura), `offers`, `price_observed`, `average`, `minimum`, `maximum`, `range_basis`. Si hay un solo precio exacto comparable, `price_observed` y `average` llevan ese importe. Con dos o más, `average` lleva la media aritmética redondeada a dos decimales (half-up), `minimum`/`maximum` llevan el rango y `price_observed` es `null`. `average` se calcula por grupo; nunca se combinan monedas, variantes, condiciones ni períodos. `range_basis` es `exact_comparable_offers` o `no_observed_range`.

Cada oferta expone `offer_ref`, `amount`, `kind` (`exact`, `from`, `until`, `previous`, `installment`), `seller`, `valid_period`, `discount_status` (`discount`, `no_discount`, `unknown`, `conflict`), campos de descuento opcionales y `assertion_refs`.

El frontend debe mostrar el promedio recibido y no recalcularlo a partir de las ofertas. El backend aplica la regla de cálculo y redondeo anterior.

## 2. ¿Cómo manejan la presentación de los productos en la página? — `visual_presentation`

`values.appearances` agrupa los usos de imagen por aparición/contexto de página; `subject_refs` identifica los productos o entidades representadas. Una imagen es un recurso asociado a un uso, no necesariamente una imagen principal.

```json
{
  "question_id": "visual_presentation",
  "subject_ref": null,
  "status": "partial",
  "values": {
    "appearances": [
      {
        "appearance_ref": "urn:webir:appearance:1",
        "subject_refs": ["urn:webir:product:123"],
        "image_uses": [
          {
            "usage_ref": "urn:webir:image-use:1",
            "image_refs": ["urn:webir:image:1"],
            "resources": ["https://example.test/image.jpg"],
            "order": 1,
            "context": "product_gallery",
            "visibility": "visible",
            "functions": ["product_image"],
            "function_status": "declared"
          }
        ]
      }
    ]
  },
  "supporting_assertion_ids": ["assertion-image-1"],
  "exclusions": []
}
```

`image_uses` incluye `usage_ref`, `image_refs`, `resources` (URL correspondiente por posición; puede contener `null`), `order` (entero o `null`), `context` (JSON o `null`), `visibility` (`visible`, `hidden`, `unknown` o `null`), `functions` (lista) y `function_status` (`declared`, `not_interpreted`). La función solo describe lo declarado o interpretado por el backend; el cliente no debe etiquetar por su cuenta una imagen como portada, envase o banner.

## 3. ¿Qué palabras se usan más al hablar del producto? — `keywords`

`values.groups` contiene términos o temas agrupados por sujeto, voz e idioma. En el contrato vigente `definition` indica cómo se obtuvieron. `expression_occurrences` es frecuencia de expresiones contabilizada por la lógica del backend; `unique_content_units` es cantidad de unidades de contenido distintas consideradas. `independent_authors` puede ser `null` cuando no se puede establecer independencia.

```json
{
  "question_id": "keywords",
  "subject_ref": null,
  "status": "answered",
  "values": {
    "groups": [
      {
        "subject_ref": "urn:webir:product:123",
        "corpus_id": null,
        "kind": "keyword",
        "label": "hidratación",
        "voice": "consumer",
        "language": "es",
        "expressions": ["hidratación", "hidrata"],
        "assertion_refs": ["assertion-keyword-1"],
        "unique_content_units": 12,
        "expression_occurrences": 18,
        "independent_authors": null
      }
    ],
    "definition": "description_words_v1"
  },
  "supporting_assertion_ids": ["assertion-keyword-1"],
  "exclusions": []
}
```

Campos: `subject_ref` (puede ser `null`), `corpus_id` (puede ser `null`), `kind` (`keyword` o `topic`), `label`, `voice` (`brand`, `seller`, `consumer`, `unknown`), `language`, `expressions`, `assertion_refs`, `unique_content_units`, `expression_occurrences`, `independent_authors`. `definition` puede ser `description_words_v1` o `legacy_expressions`. No comparar frecuencias entre definiciones, corpus o idiomas sin normalización explícita.

## 4. ¿Qué opiniones tienen sobre esa categoría de productos? — `category_opinions`

La respuesta separa opiniones agrupadas por aspecto/sentimiento de puntuaciones agregadas publicadas por la fuente. No convierte una valoración agregada en reseñas individuales ni deduce una opinión de categoría si la relación con la categoría es ambigua.

```json
{
  "question_id": "category_opinions",
  "subject_ref": "urn:webir:category:facial-moisturizers",
  "status": "partial",
  "values": {
    "groups": [
      {
        "category_ref": "urn:webir:category:facial-moisturizers",
        "basis": "product_reviews_in_category",
        "aspect": "texture",
        "sentiment": "favorable",
        "voice": "consumer",
        "review_refs": ["urn:webir:review:789"],
        "assertion_refs": ["assertion-opinion-1"],
        "quotes": ["Se absorbe rápido."],
        "unique_opinions": 1,
        "independence": "unknown"
      }
    ],
    "published_aggregates": [
      {
        "aggregate_ref": "urn:webir:rating:321",
        "subject_refs": ["urn:webir:product:123"],
        "rating": 4.5,
        "scale": {"min": 1, "max": 5},
        "published_count": 83,
        "count_kind": "reviews",
        "assertion_refs": ["assertion-rating-1"]
      }
    ]
  },
  "supporting_assertion_ids": ["assertion-opinion-1", "assertion-rating-1"],
  "exclusions": []
}
```

Cada grupo incluye `category_ref`, `basis` (`explicit_category_opinion` o `product_reviews_in_category`), `aspect`, `sentiment` (`favorable`, `unfavorable`, `mixed`, `neutral`, `indeterminate`), `voice`, `review_refs`, `assertion_refs`, `quotes`, `unique_opinions` e `independence` (`unknown`). Cada agregado incluye `aggregate_ref`, `subject_refs`, `rating`, `scale`, `published_count`, `count_kind` (`ratings`, `reviews`, `unspecified`) y `assertion_refs`. Los valores de escala y conteo conservan lo publicado por la fuente; no se asume que distintas escalas sean comparables.

## Visualizaciones

Se propone que la proyección de presentación incluya un objeto `visualizations` con los datos preparados para representar el grafo RDF y una nube de palabras por categoría. Esta extensión debe incorporarse al modelo/schema de `Presentation` y al endpoint antes de que el frontend pueda consumirla. El backend entregará nodos, aristas y frecuencias; el frontend resolverá la disposición y el estilo visual.

```json
{
  "visualizations": {
    "graph": {
      "status": "ready",
      "root_refs": ["urn:webir:category:facial-moisturizers"],
      "depth": 2,
      "truncated": false,
      "nodes": [
        {
          "ref": "urn:webir:category:facial-moisturizers",
          "kind": "Categoria",
          "label": "Hidratantes faciales",
          "identity_status": "resolved",
          "properties": {}
        },
        {
          "ref": "urn:webir:product:123",
          "kind": "Producto",
          "label": "Crema hidratante",
          "identity_status": "resolved",
          "properties": {"brand": "Marca A"}
        }
      ],
      "edges": [
        {
          "source_ref": "urn:webir:product:123",
          "target_ref": "urn:webir:category:facial-moisturizers",
          "predicate": "belongs_to",
          "label": "pertenece a",
          "assertion_refs": ["assertion-22"]
        }
      ]
    },
    "category_word_cloud": {
      "status": "ready",
      "category_ref": "urn:webir:category:facial-moisturizers",
      "voice": "consumer",
      "language": "es",
      "count_basis": "expression_occurrences",
      "terms": [
        {"text": "hidratación", "frequency": 24, "content_units": 16},
        {"text": "textura ligera", "frequency": 11, "content_units": 9}
      ]
    }
  }
}
```

### Grafo RDF

- `status`: `ready`, `partial` o `not_available`.
- `root_refs`: entidad o entidades desde las que se pidió explorar el grafo.
- `depth`: profundidad máxima de relaciones incluida.
- `truncated`: indica que el backend limitó el subgrafo; si es `true`, la vista es incompleta.
- `nodes`: entidades con `ref`, `kind`, `label`, `identity_status` (`provisional`, `resolved`, `disputed`) y `properties` reducidas a datos útiles para mostrarlas.
- `edges`: relaciones con `source_ref`, `target_ref`, `predicate`, `label` y `assertion_refs` para trazabilidad. Ambos extremos deben estar incluidos en `nodes`.

La primera vista puede mostrar el vecindario de una categoría o producto hasta una profundidad configurable y con límite de nodos. El cliente puede pedir más información usando una nueva raíz o expandiendo los nodos frontera. El RDF puede incluir categorías, productos, variantes, ofertas, apariciones, usos e imágenes, textos, reseñas y valoraciones agregadas cuando existan. El cliente dibuja la disposición (por ejemplo, radial o dirigida) y permite seleccionar nodos para mostrar sus propiedades.

### Nube de palabras por categoría

- `status`: `ready`, `partial` o `not_available`.
- `category_ref`: categoría de los textos; incluir solo contenido con atribución respaldada en RDF.
- `voice`: voz incluida (`consumer`, `brand`, `seller`, `unknown` o `all`). Permitir separar voz de consumidor y texto comercial.
- `language`: idioma (`es`, `pt`, etc.). No mezclar idiomas en una misma nube.
- `count_basis`: métrica contada; en este contrato, `expression_occurrences`.
- `terms`: términos ordenados por `frequency` descendente; cada término informa `text`, `frequency` y `content_units` (unidades de contenido que lo contienen).

El backend agrega términos de productos pertenecientes a la categoría y textos atribuibles a ellos o a la categoría. Debe evitar contar dos veces la misma unidad de contenido si está vinculada a varios productos. El frontend usa `frequency` para dimensionar las palabras y no vuelve a sumar las filas de `questions.keywords`.

## Reglas de consumo para el frontend

1. Resolver la respuesta por `question_id`, no por posición dentro de una lista.
2. Renderizar `status` junto con los datos. Para `not_answerable`, mostrar un estado sin resultados; para `partial`, indicar que la cobertura es incompleta.
3. No reemplazar `null` por cero ni inventar agregaciones. Un `null` representa dato desconocido/no disponible.
4. Mostrar precios por grupo de variante, moneda, condiciones y período. No sumar ni promediar grupos distintos.
5. Usar los `*_ref` para enlazar entidades dentro del resultado; los IDs de aserción sirven para trazabilidad y no son texto de interfaz.
6. En el grafo, renderizar relaciones desde `edges`; no deducir vínculos por coincidencia de etiquetas.
7. En la nube, el tamaño visual representa `frequency`; ofrecer filtros por `voice` e `language` cuando haya datos.
8. La estructura de RDF (URI de predicados/clases, nombres de grafo, forma de consulta SPARQL y almacén) queda encapsulada en backend. Cambiarla no debe cambiar este JSON salvo que se incremente la versión del contrato.

## Fuente normativa

- `clean_process/contracts.py`: modelos tipados y enumeraciones.
- `clean_process/schemas/output.schema.json`: JSON Schema del resultado completo.
- `clean_process/schemas/presentation.schema.json`: JSON Schema de la proyección para UI.
- `clean_process/aggregates.py`: reglas actuales de cálculo y estado para estas preguntas.

