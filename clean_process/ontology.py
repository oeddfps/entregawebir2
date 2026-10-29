"""Closed core vocabulary; extensions require a versioned contract change."""
import hashlib
import json
import re
from urllib.parse import urlsplit, urlunsplit

# Labels describe meaning, never site selectors, domains or commercial phrases.
TAXONOMY = {
    'commerce.product': ('Producto', 'Identity of an individual commercial product, not a category or menu'),
    'commerce.variant': ('Variante', 'Explicit configuration or commercial presentation of a product'),
    'commerce.offer': ('Oferta', 'Conditions under which a particular variant is offered'),
    'content.collection': ('Coleccion', 'Grouping of identifiable members'),
    'content.appearance': ('Aparicion', 'Contextual appearance of an entity in content'),
    'content.category': ('Categoria', 'Conceptual category, not an individual product'),
    'opinion.review': ('Resena', 'An individual opinion or experience attributed to a subject'),
    'opinion.aggregate': ('ValoracionAgregada', 'Published aggregate rating; not an individual review'),
    'content.text': ('Texto', 'Text relevant to a question, with its original voice'),
    'other': ('other', 'Irrelevant, unknown, or insufficient evidence'),
}
PROPERTIES = {
    'name', 'description', 'url', 'brand', 'sku', 'gtin', 'size', 'quantity',
    'amount', 'currency', 'price_kind', 'seller', 'conditions', 'valid_period',
    'rating', 'rating_scale', 'rating_count', 'count_kind', 'review_body', 'author', 'date',
    'image', 'order', 'context', 'visibility', 'function', 'keyword', 'topic',
    'aspect_opinion', 'review_identity', 'presentation', 'other',
}
RELATIONS = {
    'contains': ({'Pagina', 'Coleccion'}, None),
    'member': ({'Coleccion'}, {'Aparicion'}),
    'represents': ({'Aparicion'}, {'Producto', 'Variante'}),
    'belongs_to': ({'Producto'}, {'Categoria'}),
    'has_variant': ({'Producto'}, {'Variante'}),
    'offers': ({'Oferta'}, {'Variante'}),
    'presents': ({'Aparicion'}, {'UsoDeImagen'}),
    'uses': ({'UsoDeImagen'}, {'Imagen'}),
    'mentions': ({'Texto'}, {'Producto', 'Variante', 'Categoria'}),
    'evaluates': ({'Resena'}, {'Producto', 'Variante', 'Categoria'}),
    'summarizes': ({'ValoracionAgregada'}, {'Producto', 'Variante', 'Categoria'}),
}


def identifier(prefix, *parts):
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return prefix + ':' + hashlib.sha256(raw.encode()).hexdigest()[:24]


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip()


def canonical_url(value):
    """Preserve query content, encoded paths and trailing slashes. Never fetch."""
    try:
        p = urlsplit(value)
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
            return None
        port = p.port
        host = p.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        if port and (p.scheme, port) not in {('http', 80), ('https', 443)}:
            host += ':' + str(port)
        return urlunsplit((p.scheme.lower(), host, p.path or '/', p.query, ''))
    except (ValueError, TypeError):
        return None
