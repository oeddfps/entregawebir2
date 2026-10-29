"""Words shared by distinct descriptions. No scraper or model dependency."""
from collections import defaultdict
import re
import unicodedata

from .ontology import identifier, normalized

# Deliberately small, auditable Spanish/English function-word lists. Preserve
# accents and inflections; no inferred language, stemming or synonym merging.
STOPWORDS = frozenset('''a al algo ante antes aquel aquella aquellas aquellos aquí así
bajo cada como con contra cual cuando de del desde donde durante e el ella ellas
ellos en entre era es esa esas ese eso esos esta estaba estas este esto estos fue
ha hasta hay la las le les lo los más me mi mis muy ni no nos o otra otras otro otros
para pero por porque que quien se ser si sin sobre son su sus también te tiene tu tus
un una unas uno unos y ya
the a an and or of to in on at for from with without by as is are was were be been
being it its this that these those you your we our they their he she his her not
but if so than then into through can may will has have had do does did'''.split())


def canonical(text):
    return normalized(unicodedata.normalize('NFC', text)).casefold()


def description_keywords(workspace):
    samples = {s.sample_id: s for s in workspace.request.samples}
    groups = {}
    corpus_words = defaultdict(lambda: defaultdict(set))
    for assertion in workspace.assertions:
        if assertion.status != 'accepted' or assertion.predicate != 'description':
            continue
        if not isinstance(assertion.value, str) or not assertion.value.strip():
            continue
        sample = samples.get(assertion.scope.get('sample_id'))
        if sample is None:
            continue
        # Producers can explicitly group multiple pages of the same capture.
        corpus = sample.context.get('keyword_corpus_ref') or sample.source_ref
        if not isinstance(corpus, str):
            corpus = sample.source_ref
        description = canonical(assertion.value)
        identity = identifier('description', corpus, description)
        words = set(re.findall(r'[^\W\d_]+', description, flags=re.UNICODE)) - STOPWORDS
        voice, language = assertion.scope.get('voice', 'unknown'), assertion.scope.get('language')
        for word in words:
            corpus_words[corpus][word].add(identity)
            key = (corpus, voice, language, word)
            group = groups.setdefault(key, {'subject_ref': None, 'corpus_id': corpus, 'kind': 'keyword',
                'label': word, 'voice': voice, 'language': language, 'expressions': [word],
                'descriptions': set(), 'assertion_refs': []})
            group['descriptions'].add(identity)
            group['assertion_refs'].append(assertion.assertion_id)
    result = []
    for (corpus, voice, language, word), group in groups.items():
        if len(corpus_words[corpus][word]) < 2:
            continue
        count = len(group.pop('descriptions'))
        group.update(unique_content_units=count, expression_occurrences=count,
                     independent_authors=None,
                     assertion_refs=list(dict.fromkeys(group['assertion_refs'])))
        result.append(group)
    return sorted(result, key=lambda g: (-g['unique_content_units'], g['label'],
                                         g['corpus_id'], g['voice'], g['language'] or ''))
