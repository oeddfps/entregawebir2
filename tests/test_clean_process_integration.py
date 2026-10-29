import json
from pathlib import Path

import pytest

from clean_process import Output, process
from src.integrations.clean_process import from_scraper


def value(prop, text, **extra):
    return {'class': prop, 'values': [{'text': text, **extra}]}


def test_site_neutral_scraper_adapter_preserves_provenance_and_consumer_data():
    block = {'role': 'semantic_item', 'selector': 'main > section > div', 'text': 'Daily care',
             'attributes': {'source': 'collection_dom'}, 'parts': [
                 value('name', 'Example lotion', selector='main h2'),
                 value('product_link', 'https://neutral.example/p', href='https://neutral.example/p'),
                 value('image', 'https://neutral.example/i', src='https://neutral.example/i'),
                 value('description', 'Daily care')]}
    article = {'role': 'semantic_article', 'text': 'Example lotion. Daily care.',
               'parts': [value('name', 'Example lotion', selector='main h2')]}
    payload = [{'url': 'https://neutral.example/catalog', 'result': {'entities': [block, article]}}]
    before = json.dumps(payload)
    adapted = from_scraper(payload)
    out = process(adapted)
    assert json.dumps(payload) == before
    assert len(out.data.products) == 1
    assert out.data.products[0].name == 'Example lotion'
    assert len(out.data.products[0].appearance_refs) == 1
    assert any(a.predicate == 'mentions' for a in out.knowledge.assertions)
    assert any(e.locator.get('original_block') == block for e in out.evidence)
    assert out.data.products[0].field_assertion_refs['name']
    Output.model_validate_json(out.model_dump_json())


def test_scraper_product_and_member_merge_only_with_compatible_identity():
    parts = [value('name', 'Neutral'), value('product_link', 'https://neutral.example/p', href='https://neutral.example/p')]
    payload = [{'url': 'https://neutral.example/', 'result': {'entities': [
        {'role': 'product', 'attributes': {'source': 'jsonld'}, 'parts': parts},
        {'role': 'semantic_item', 'attributes': {'source': 'collection_dom'}, 'parts': parts}]}}]
    out = process(from_scraper(payload))
    assert len(out.data.products) == 1
    assert len(out.data.products[0].appearance_refs) == 2


@pytest.mark.parametrize('payload', [[], {}, [{'url': 'https://n.example', 'result': None}],
    [{'url': 'https://n.example', 'result': {'entities': 'bad'}}]])
def test_adapter_does_not_silently_accept_invalid_or_missing_results(payload):
    with pytest.raises(ValueError):
        from_scraper(payload)


def test_example_answers_four_questions_without_ui_semantic_work():
    path = Path(__file__).resolve().parents[1] / 'clean_process/examples/input.json'
    out = process(json.loads(path.read_text(encoding='utf-8')))
    assert len(out.data.products) == 1
    results = {q.question_id: q for q in out.data.question_results}
    prices = results['price_range'].values.groups[0]
    assert prices.minimum == '10.00' and prices.maximum == '12.00'
    assert results['visual_presentation'].values.appearances[0].image_uses[0].visibility == 'visible'
    assert results['keywords'].values.groups[0].expression_occurrences == 1
    assert results['category_opinions'].values.groups[0].unique_opinions == 1
    assert len(out.findings) == 1
    assert all(q.supporting_assertion_ids for q in results.values())
    assert results['visual_presentation'].status == 'partial'  # No inferred image function.
