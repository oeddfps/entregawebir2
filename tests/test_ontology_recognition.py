from copy import deepcopy
import json

import pytest

from clean_process import Output, process
from clean_process.contracts import Input
from clean_process.ontology_recognition import OntologyRecognizer, vocabulary
from clean_process.presentation import present
from clean_process.commerce import money
from src.integrations.clean_process import from_scraper


def raw(name, value):
    return {'property': 'raw_field', 'value': {'name': name, 'value': value}}


def unit(uid, kind, text='', **fields):
    return {'unit_id': uid, 'classification': 'other', 'text': text,
            'locator': {'source_type_names': [kind]},
            'fields': [{'property': p, 'value': v} for p, v in fields.items()]}


def run(units, relations=(), recognizer=None):
    return process({'samples': [{'sample_id': 's', 'source_ref': 'document:neutral',
        'content_units': units, 'relations': list(relations)}]},
        ontology_recognizer=recognizer or OntologyRecognizer())


def relation(subject, predicate, target):
    return {'subject_unit': subject, 'predicate': predicate, 'object_unit': target}


def test_all_diagram_classes_and_relations_have_vocabularies_and_supported_recognition():
    units = [unit('page', 'Página', url='https://neutral.example/'),
             unit('list', 'collection'), unit('appearance', 'card'),
             unit('p', 'product', name='Item', url='https://neutral.example/p'),
             unit('c', 'category', name='Category'), unit('v', 'variant', size='50 ml'),
             unit('o', 'offer', amount='100', currency='UYU'),
             unit('i', 'image', url='https://neutral.example/image'),
             unit('use', 'image usage'), unit('text', 'text', text='A relevant description.'),
             unit('review', 'reseña', review_body='My own experience with this item.'),
             unit('agg', 'aggregate rating', rating='4.7', rating_count='10')]
    edges = [relation('page', 'contains', 'list'), relation('list', 'member', 'appearance'),
             relation('appearance', 'represents', 'p'), relation('p', 'belongs_to', 'c'),
             relation('p', 'has_variant', 'v'), relation('o', 'offers', 'v'),
             relation('appearance', 'presents', 'use'), relation('use', 'uses', 'i'),
             relation('text', 'mentions', 'p'), relation('review', 'evaluates', 'p'),
             relation('agg', 'summarizes', 'p')]
    original = deepcopy(units)
    out = run(units, edges)
    types = {a.value for a in out.knowledge.assertions if a.predicate == 'type'}
    expected = {'Pagina','Coleccion','Aparicion','Producto','Categoria','Variante','Oferta',
                'Imagen','UsoDeImagen','Texto','Resena','ValoracionAgregada'}
    assert expected <= types
    assert len([key for key in vocabulary()['concepts'] if key.startswith('entity.')]) == 12
    assert len([key for key in vocabulary()['concepts'] if key.startswith('relation.')]) == 11
    assert {r['predicate'] for r in edges} <= {a.predicate for a in out.knowledge.assertions}
    assert units == original
    assert out.ontology_version == '0.3'
    Output.model_validate_json(out.model_dump_json())


def test_producer_class_and_field_names_are_read_without_scraper_changes():
    payload = [{'url': 'https://neutral.example/', 'result': {'entities': [
        {'class': 'product', 'parts': [{'class': 'productName', 'values': [{'text': 'Example'}]},
                                     {'class': 'productUrl', 'values': [{'text': 'https://neutral.example/item'}]}]},
        {'class': 'price', 'text': '$100'},
        {'class': 'discount', 'value': '%20'}]}}]
    original = deepcopy(payload)
    out = process(from_scraper(payload), ontology_recognizer=OntologyRecognizer())
    assert payload == original
    assert out.data.products[0].name == 'Example'
    assert len(out.data.offers) == 2
    price = next(o for o in out.data.offers if o.amount is not None)
    discount = next(o for o in out.data.offers if o.discount_percent is not None)
    assert price.amount == '100' and price.currency_symbol == '$' and price.currency is None
    assert price.discount_status == 'unknown'
    assert discount.discount_percent == '20' and discount.discount_status == 'discount'


@pytest.mark.parametrize('value', ['%20', '20%', '20% de descuento'])
def test_discount_percent_signs_are_supported_but_not_product_concentration(value):
    offer = unit('offer', 'offer')
    offer['fields'] = [raw('price', '$100'), raw('descuento', value)]
    ingredient = unit('ingredient', 'other')
    ingredient['fields'] = [raw('niacinamida', value)]
    out = run([offer, ingredient])
    assert out.data.offers[0].discount_status == 'discount'
    assert out.data.offers[0].discount_percent == '20'
    assert sum(a.predicate == 'discount_percent' for a in out.knowledge.assertions) == 1


def test_explicit_no_discount_and_regular_price_are_distinct():
    a = unit('a', 'offer'); a['fields'] = [raw('price', '$100'), raw('has_discount', False)]
    b = unit('b', 'offer'); b['fields'] = [raw('price', '$100')]
    c = unit('c', 'offer'); c['fields'] = [raw('price', '$100'), raw('no_discount', True)]
    out = run([a,b,c])
    assert [o.discount_status for o in out.data.offers] == ['no_discount', 'unknown', 'no_discount']


def test_previous_price_and_discount_disagreement_are_not_silently_overwritten():
    offer = unit('a', 'offer', currency='UYU')
    offer['fields'] += [raw('current_price', '$80'), raw('previous_price', '$100'), raw('discount_percent', '10%')]
    out = run([offer])
    row = out.data.offers[0]
    assert row.amount == '80' and row.previous_amount == '100'
    assert row.discount_percent == '10' and row.discount_status == 'conflict'
    assert any(i.details.get('reason') == 'discount_percentage_disagrees_with_prices' for i in out.issues)
    assert present(out)['offers'][0]['discount_status'] == 'conflict'


def test_explicit_relation_labels_require_identified_compatible_endpoints():
    p = unit('p', 'product', name='Example', url='https://neutral.example/item')
    p['fields'] += [raw('belongsTo', 'cat'), raw('hasVariants', 'missing')]
    c = unit('cat', 'category', name='Category')
    out = run([p,c])
    assert any(a.predicate == 'belongs_to' for a in out.knowledge.assertions)
    assert not any(a.predicate == 'has_variant' for a in out.knowledge.assertions)
    assert any(i.details.get('reason') == 'unresolved_or_incompatible_endpoint' for i in out.issues)


def test_semantic_match_alone_does_not_reclassify_unrelated_content():
    class Scorer:
        def rank(self, texts):
            return [[('entity.Producto', .99)] for _ in texts]
    u = unit('x', 'unrecognized', text='Unknown editorial content.')
    out = run([u], recognizer=OntologyRecognizer(Scorer()))
    assert not out.data.products
    assert any(i.code == 'ontology_recognition_decision' and i.details['status'] == 'ambiguous' for i in out.issues)


def test_symbol_and_offer_word_do_not_override_missing_commercial_structure():
    u = unit('x', 'offer', text='This cream offers hydration.')
    u['fields'] = [raw('unknown', '$100'), raw('concentration', '%20')]
    out = run([u])
    # An explicit offer class and monetary value supports an offer, whereas
    # unlabelled percentage does not support a discount.
    assert out.data.offers[0].discount_status == 'unknown'
    assert out.data.offers[0].discount_percent is None
    out = run([unit('x', 'offer', text='Offers hydration with a pleasant texture.')])
    assert not out.data.offers


@pytest.mark.parametrize('value', ['$1.234', '$NaN', '$-10', '%10'])
def test_ambiguous_or_invalid_monetary_literals_abstain(value):
    assert money(value) is None


def test_keywords_definition_is_unchanged_when_new_recognition_runs():
    a = unit('a', 'text', description='Piel suave suave.')
    b = unit('b', 'text', description='Piel hidratada.')
    c = unit('c', 'text', description='PIEL suave suave.')
    out = run([a,b,c])
    q = next(q for q in out.data.question_results if q.question_id == 'keywords')
    assert q.values.definition == 'description_words_v1'
    assert [(g.label,g.unique_content_units) for g in q.values.groups] == [('piel',2)]


def test_reference_vector_cache_is_versioned_and_reused(tmp_path, monkeypatch):
    np = pytest.importorskip('numpy')
    from clean_process.embedding_cache import reference_vectors
    monkeypatch.setenv('CLEAN_PROCESS_CACHE', str(tmp_path))
    class Encoder:
        def __init__(self): self.calls = 0
        def encode(self, anchors, **kwargs):
            self.calls += 1
            return np.ones((len(anchors), 3))
    model = Encoder()
    assert reference_vectors(model, ['first'], 'model', 'rev')[1] is False
    assert reference_vectors(model, ['first'], 'model', 'rev')[1] is True
    assert reference_vectors(model, ['changed'], 'model', 'rev')[1] is False
    assert model.calls == 2
