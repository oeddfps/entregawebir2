import json
from copy import deepcopy

from clean_process import Output, process
from clean_process.review_recognition import ReviewRecognizer, matches
from src.integrations.clean_process import from_scraper


def payload(*parts):
    return [{'url': 'https://neutral.example/item', 'result': {'entities': [
        {'role': 'product', 'attributes': {'source': 'jsonld'}, 'text': 'Example product',
         'parts': [{'class': 'name', 'values': [{'text': 'Example'}]},
                   {'class': 'product_link', 'values': [{'href': 'https://neutral.example/item'}]},
                   *[{'class': name, 'values': [{'text': value}]} for name, value in parts]]}]}}]


def recognize(raw, scorer=None, **options):
    return process(from_scraper(raw), review_recognizer=ReviewRecognizer(scorer, **options))


def values(output, prop):
    return [a.value for a in output.knowledge.assertions if a.predicate == prop]


def decisions(output):
    return [i.details for i in output.issues if i.code == 'review_recognition_decision']


def test_unknown_fields_preserved_and_count_alias_is_typed_with_evidence():
    raw = payload(('cantidadDeOpiniones', '285'))
    original = deepcopy(raw)
    adapted = from_scraper(raw)
    assert any(f.property == 'raw_field' for u in adapted.samples[0].content_units for f in u.fields)
    output = process(adapted, review_recognizer=ReviewRecognizer())
    assert values(output, 'rating_count') == ['285']
    assert values(output, 'count_kind') == ['reviews']
    assert raw == original
    assert any(d['status'] == 'accepted' for d in decisions(output))
    assert any(e.locator.get('original_block') == raw[0]['result']['entities'][0] for e in output.evidence)
    Output.model_validate_json(output.model_dump_json())


def test_counts_scores_and_scale_have_distinct_meanings():
    output = recognize(payload(('total_ratings', '9'), ('averageScore', '4,7'),
                               ('worstRating', '1'), ('bestRating', '5')))
    assert values(output, 'rating_count') == ['9']
    assert values(output, 'count_kind') == ['ratings']
    assert values(output, 'rating') == ['4.7']
    assert values(output, 'rating_scale') == [{'min': '1', 'max': '5'}]


def test_actions_links_collections_and_bare_numbers_do_not_become_reviews():
    output = recognize(payload(('review', 'Escribe tu opinión'),
                               ('reviews_url', 'https://neutral.example/reviews'),
                               ('reviews', [{'text': 'Nice product'}]), ('nota', '285'),
                               ('price', '285'), ('preview', 'Example product')))
    assert not values(output, 'rating_count')
    assert not values(output, 'review_body')
    assert not values(output, 'rating')
    assert not any(e.kind == 'Resena' for e in output.knowledge.entities)
    assert {'review_control', 'review_link', 'review_collection'} <= {d['concept'] for d in decisions(output)}
    assert not matches('preview')


def test_semantic_similarity_alone_is_only_a_candidate():
    class Scorer:
        def rank(self, texts):
            return [[('review_count', .99), ('other', .2)] for _ in texts]
    output = recognize(payload(('customerVoiceMetric', '285')), Scorer())
    assert not values(output, 'rating_count')
    decision = decisions(output)[0]
    assert decision['status'] == 'ambiguous'
    assert decision['semantic_ranking'][0]['cosine_similarity'] == .99


def test_disagreement_does_not_replace_existing_data_or_add_false_kind():
    output = recognize(payload(('rating_count', '12'), ('total_reviews', '15')))
    assert values(output, 'rating_count') == ['12']
    assert values(output, 'count_kind') == ['ratings']
    assert any(d['status'] == 'conflict' for d in decisions(output))


def test_unknown_model_failure_and_omissions_are_visible():
    class Broken:
        def rank(self, texts):
            raise RuntimeError('secret provider error')
    output = recognize(payload(('total_reviews', '2'), ('mystery', 'x')), Broken(), max_fields=1)
    summary = next(i.details for i in output.issues if i.code == 'review_recognition_summary')
    assert summary['model_available'] is False
    assert summary['omitted_fields'] == 1
    assert values(output, 'rating_count') == ['2']
    assert 'secret provider error' not in output.model_dump_json()


def test_multilingual_aliases_and_ambiguous_prose_count_abstain():
    assert 'review_count' in matches('QUANTIDADE_DE_AVALIAÇÕES')
    output = recognize(payload(('quantidade_de_avaliacoes', '18'), ('total_reviews', '1,234')))
    assert values(output, 'rating_count') == ['18']
    assert any(d['status'] == 'ambiguous' and d['field_name'] == 'total_reviews' for d in decisions(output))


def test_individual_review_requires_body_evidence_and_keeps_original_text():
    raw = payload(('review_body_text', 'I used it daily and liked the texture.'))
    raw[0]['result']['entities'][0]['role'] = 'semantic_article'
    raw[0]['result']['entities'][0]['parts'][-1]['class'] = 'reviewText'
    output = recognize(raw)
    assert values(output, 'review_body') == ['I used it daily and liked the texture.']
    assert any(e.kind == 'Resena' for e in output.knowledge.entities)


def test_invalid_counter_does_not_turn_into_review_text_even_with_author():
    raw = payload(('author', 'Example Person'), ('total_reviews', 'This number is unavailable'))
    output = recognize(raw)
    assert not values(output, 'review_body')
    assert not values(output, 'rating_count')


def test_semantic_budget_reuses_context_and_keeps_omissions_explicit():
    from clean_process.review_recognition import E5Scorer
    scorer = E5Scorer(max_new_texts=1)
    calls = []
    def encode(texts):
        calls.append(list(texts))
        return [[('review_text', .8)] for text in texts]
    scorer._rank = encode
    assert scorer.rank(['same', 'same', 'new']) == [[('review_text', .8)], [('review_text', .8)], []]
    assert scorer.last_omitted == 1
    scorer.rank(['same'])
    assert calls == [['same']]
    assert scorer.last_scored == 1


def test_original_label_can_disambiguate_an_unknown_producer_class():
    raw = payload(('metric', '7'))
    raw[0]['result']['entities'][0]['parts'][-1]['label'] = 'Cantidad de opiniones'
    assert values(recognize(raw), 'rating_count') == ['7']
    raw = payload(('unknown', '4.7'))
    raw[0]['result']['entities'][0]['parts'][-1]['values'][0]['property'] = 'ratingValue'
    assert values(recognize(raw), 'rating') == ['4.7']
