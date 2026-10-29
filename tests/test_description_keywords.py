from clean_process import process
from clean_process.presentation import present


def sample(identity, descriptions, source='document:a', corpus=None):
    return {'sample_id': identity, 'source_ref': source,
            'context': {'keyword_corpus_ref': corpus} if corpus else {},
            'content_units': [{'unit_id': str(i), 'classification': 'Producto',
                'text': description, 'fields': [{'property': 'description', 'value': description}]}
                for i, description in enumerate(descriptions)]}


def words(samples):
    output = process({'samples': samples, 'questions': ['keywords']})
    view = present(output)
    return view, {g['label']: g for g in view['questions']['keywords']['values']['groups']}


def test_distinct_descriptions_not_raw_occurrences_and_original_evidence():
    view, groups = words([sample('a', ['La piel suave, suave.', 'LA PIEL SUAVE, SUAVE.',
                                     'Para una piel hidratada.', 'Sólo una palabra.'])])
    assert set(groups) == {'piel'}
    assert groups['piel']['unique_content_units'] == 2
    assert groups['piel']['expression_occurrences'] == 2
    assert len(groups['piel']['assertion_refs']) == 3
    assert view['questions']['keywords']['values']['definition'] == 'description_words_v1'
    assert view['charts']['keyword_rows'][0]['label'] == 'piel'


def test_single_description_repetitions_do_not_qualify():
    view, groups = words([sample('a', ['Suave suave suave.'])])
    assert not groups
    assert view['questions']['keywords']['status'] == 'not_answerable'


def test_corpora_are_separate_and_explicit_grouping_combines_pages():
    _, separate = words([sample('a', ['Piel suave.']),
                         sample('b', ['Piel hidratada.'], source='document:b')])
    assert not separate
    _, grouped = words([sample('a', ['Piel suave.'], corpus='capture:a'),
                        sample('b', ['Piel hidratada.'], source='document:b', corpus='capture:a')])
    assert grouped['piel']['unique_content_units'] == 2


def test_accents_are_canonical_but_no_stemming_or_accent_removal():
    _, groups = words([sample('a', ['ÁCIDO para piel seca.', 'A\u0301cido con textura ligera.',
                                  'Acidos y crema.'])])
    assert set(groups) == {'ácido'}


def test_review_bodies_and_names_are_not_descriptions():
    s = sample('a', ['Crema suave.'])
    s['content_units'].append({'unit_id': 'review', 'classification': 'Resena',
                              'text': 'Crema suave.',
                              'fields': [{'property': 'review_body', 'value': 'Crema suave.'}]})
    _, groups = words([s])
    assert not groups
