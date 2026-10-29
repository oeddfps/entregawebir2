"""Source-neutral review recognition. Similarity retrieves; evidence validates.

Loading E5 is explicit and local-only. The core package remains usable without
torch or sentence-transformers. Unknown source content never becomes code.
"""
from functools import lru_cache
from importlib.resources import files
import json
import math
import re
import unicodedata

from .contracts import Datum
from .ontology import canonical_url

MODEL = 'intfloat/multilingual-e5-base'
REVISION = 'd128750597153bb5987e10b1c3493a34e5a4502a'


@lru_cache(maxsize=1)
def vocabulary():
    return json.loads(files('clean_process').joinpath('vocabularies/reviews.v1.json').read_text(encoding='utf-8'))


def normalize(value):
    value = re.sub(r'([a-z])([A-Z])', r'\1 \2', str(value))
    value = unicodedata.normalize('NFKD', value.casefold())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[^\W_]+', value, re.UNICODE))


def matches(value):
    normalized = normalize(value)
    return {concept: [term for term in item['terms']
                      if ' ' + normalize(term) + ' ' in ' ' + normalized + ' ']
            for concept, item in vocabulary()['concepts'].items()
            if any(' ' + normalize(term) + ' ' in ' ' + normalized + ' ' for term in item['terms'])}


class E5Scorer:
    """Local cached model; query prefixes on both sides for symmetric similarity."""
    def __init__(self, model_path=MODEL, *, max_new_texts=128):
        self.model_path = str(model_path)
        self.model = None
        self.anchor_vectors = None
        self.anchor_labels = []
        self.last_truncated = 0
        self.cache = {}
        self.max_new_texts = max_new_texts
        self.last_omitted = 0
        self.last_scored = 0

    def rank(self, texts):
        # Cache repeated blocks across pages and bound local inference work.
        # Vocabulary/structural validation still examines every selected field.
        pending = list(dict.fromkeys(t for t in texts if t not in self.cache))
        pending = pending[:max(0, self.max_new_texts-len(self.cache))]
        self.last_truncated = 0
        if pending:
            self.cache.update(zip(pending, self._rank(pending)))
        self.last_omitted = sum(t not in self.cache for t in texts)
        self.last_scored = len(texts)-self.last_omitted
        return [self.cache.get(t, []) for t in texts]

    def _rank(self, texts):
        import torch
        from sentence_transformers import SentenceTransformer
        if self.model is None:
            torch.set_num_threads(2)
            self.model = SentenceTransformer(self.model_path, device='cpu',
                                            revision=REVISION, local_files_only=True, trust_remote_code=False)
            self.model.max_seq_length = 512
            anchors = []
            for concept, item in vocabulary()['concepts'].items():
                for definition in item['definitions']:
                    anchors.append('query: ' + definition)
                    self.anchor_labels.append(concept)
            for negative in vocabulary()['negative_examples']:
                anchors.append('query: ' + negative['text'])
                self.anchor_labels.append(negative['concept'])
            self.anchor_vectors = self.model.encode(anchors, normalize_embeddings=True,
                                                     show_progress_bar=False, batch_size=16)
        prefixed = ['query: ' + text for text in texts]
        lengths = self.model.tokenizer(prefixed, truncation=False, verbose=False)['input_ids']
        self.last_truncated = sum(len(tokens) > 512 for tokens in lengths)
        vectors = self.model.encode(prefixed, normalize_embeddings=True,
                                    show_progress_bar=False, batch_size=16)
        scores = vectors @ self.anchor_vectors.T
        rankings = []
        for row in scores:
            concepts = {}
            for concept, value in zip(self.anchor_labels, row):
                score = float(value)
                if not math.isfinite(score):
                    raise ValueError('Invalid embedding score')
                concepts[concept] = max(score, concepts.get(concept, -1.0))
            rankings.append(sorted(concepts.items(), key=lambda item: -item[1])[:3])
        return rankings


def numeric(value, *, count=False):
    if isinstance(value, bool):
        return None
    text = str(value).strip()
    # Do not guess thousands separators or read a number out of prose.
    if not re.fullmatch(r'\d+' if count else r'\d+(?:[.,]\d+)?', text):
        return None
    if count:
        return str(int(text))
    result = float(text.replace(',', '.'))
    if not math.isfinite(result):
        return None
    return text.replace(',', '.')


class ReviewRecognizer:
    def __init__(self, scorer=None, *, max_fields=96):
        if type(max_fields) is not int or max_fields < 1:
            raise ValueError('max_fields must be a positive integer')
        self.scorer = scorer
        self.max_fields = max_fields

    def recognize(self, sample):
        records = []
        for unit in sample.content_units:
            for index, field in enumerate(unit.fields):
                if field.property != 'raw_field' or not isinstance(field.value, dict):
                    continue
                data = field.value
                name, value = str(data.get('name', '')), data.get('value')
                label = str(data.get('label') or name)
                context = ' '.join([name, label, str(value), unit.text])
                hits = matches(' '.join([name, label]))
                records.append({'unit': unit, 'field': field, 'index': index,
                    'name': name, 'label': label, 'value': value, 'hits': hits,
                    'text': f'Campo: {name[:180]}. Etiqueta: {label[:180]}. Valor: {str(value)[:600]}. Contexto: {unit.text[:800]}',
                    'context': context})
            if unit.classification in ('other', 'Texto') and unit.text.strip() and not any(f.property == 'raw_field' for f in unit.fields):
                records.append({'unit': unit, 'field': None, 'index': -1, 'name': '', 'label': '',
                    'value': unit.text, 'hits': matches(unit.text), 'text': unit.text[:1600], 'context': unit.text})
        records.sort(key=lambda r: (not bool(r['hits']), r['unit'].unit_id, r['index']))
        selected = records[:self.max_fields]
        rankings, model_error = [[] for _ in selected], False
        if self.scorer and selected:
            try:
                rankings = self.scorer.rank([r['text'] for r in selected])
                if len(rankings) != len(selected):
                    raise ValueError('Missing ranking')
            except Exception:
                rankings = [[] for _ in selected]
                model_error = True
        units = {u.unit_id: u.model_copy(deep=True) for u in sample.content_units}
        decisions = []
        for record, ranking in zip(selected, rankings):
            unit = units[record['unit'].unit_id]
            name, value, hits = normalize(record['name']), record['value'], record['hits']
            exact = {concept for concept, item in vocabulary()['concepts'].items()
                     if ({name, normalize(record['label'])} - {''}) & {normalize(t) for t in item['terms']}}
            concept, prop, mapped, reason = None, None, None, 'insufficient_context'
            contexts = matches(record['context'])
            if 'review_control' in contexts:
                concept, reason = 'review_control', 'invitation_or_submission_control'
            elif record['field'] and isinstance(value, str) and canonical_url(value) and any(k in hits for k in ('review_text', 'review_collection', 'review_link')):
                concept, reason = 'review_link', 'review_destination_not_review_text'
            elif isinstance(value, (list, dict)) and 'review_collection' in hits:
                concept, reason = 'review_collection', 'collection_not_individual_review'
            elif len(exact & {'review_count', 'rating_count'}) == 1 and numeric(value, count=True) is not None:
                concept = next(iter(exact & {'review_count', 'rating_count'}))
                prop, mapped, reason = 'rating_count', numeric(value, count=True), 'explicit_count_label_and_nonnegative_integer'
            elif len(exact & {'rating', 'aggregate_rating'}) >= 1 and numeric(value) is not None:
                # Legal notes and prices remain candidates, even when called nota/score.
                if name not in ('nota', 'note') or 'review_text' in contexts or 'review_collection' in contexts:
                    concept = 'aggregate_rating' if 'aggregate_rating' in exact else 'rating'
                    prop, mapped, reason = 'rating', numeric(value), 'explicit_score_label_and_numeric_value'
            elif record['field'] and 'review_text' in hits and not exact & {'review_count', 'rating_count', 'rating', 'aggregate_rating', 'review_author', 'rating_scale', 'review_collection', 'review_link'} and isinstance(value, str) and len(value.split()) >= 3:
                explicit = bool({name, normalize(record['label'])} & {normalize(t) for t in vocabulary()['concepts']['review_text']['explicit_fields']})
                attributed = unit.classification == 'Resena' or any(f.property == 'author' and f.value for f in unit.fields)
                if explicit or attributed:
                    concept, prop, mapped, reason = 'review_text', 'review_body', value, 'review_text_field_with_explicit_label_or_attribution'
            elif 'review_author' in exact and unit.classification == 'Resena' and isinstance(value, str) and value.strip():
                concept, prop, mapped, reason = 'review_author', 'author', value, 'author_inside_recognized_review'
            state = 'ambiguous'
            if prop:
                existing = [f.value for f in unit.fields if f.property == prop]
                kinds = [f.value for f in unit.fields if f.property == 'count_kind']
                expected_kind = 'reviews' if concept == 'review_count' else 'ratings' if concept == 'rating_count' else None
                if existing and not all(str(v) == str(mapped) for v in existing):
                    state, reason = 'conflict', 'existing_property_disagrees'
                elif expected_kind and any(kind != expected_kind for kind in kinds):
                    state, reason = 'conflict', 'existing_count_kind_disagrees'
                else:
                    state = 'accepted'
                    locator = {**record['field'].locator, 'recognition_rule': reason,
                               'vocabulary_version': vocabulary()['version']}
                    if not existing:
                        unit.fields.append(Datum(property=prop, value=mapped, method='interpretation', locator=locator))
                    if concept in ('review_count', 'rating_count'):
                        count_kind = 'reviews' if concept == 'review_count' else 'ratings'
                        if not kinds:
                            unit.fields.append(Datum(property='count_kind', value=count_kind, method='interpretation', locator=locator))
                    if unit.classification in ('other', 'Texto'):
                        unit.classification = 'Resena' if prop == 'review_body' else 'ValoracionAgregada' if prop in ('rating', 'rating_count') else unit.classification
                        unit.classification_method = 'interpretation'
            if concept is None and ranking and ranking[0][0] != 'other':
                concept = ranking[0][0]
            if concept is None and hits:
                concept = next(iter(hits))
            if concept is not None:
                decisions.append({'unit_id': unit.unit_id, 'field_name': record['name'],
                    'concept': concept, 'status': state, 'reason': reason,
                    'value': value, 'lexical_matches': hits,
                    'semantic_ranking': [{'concept': k, 'cosine_similarity': round(float(v), 6)} for k, v in ranking],
                    'locator': record['field'].locator if record['field'] else unit.locator})
        # Bounds require both ends explicitly; never assume a five-star scale.
        for unit in units.values():
            bounds = {}
            bound_records = [r for r in selected if r['unit'].unit_id == unit.unit_id]
            for record in bound_records:
                name = normalize(record['name'])
                side = 'min' if name in ('worst rating', 'minimum rating', 'min rating') else 'max' if name in ('best rating', 'maximum rating', 'max rating') else None
                value = numeric(record['value'])
                if side and value is not None:
                    bounds.setdefault(side, set()).add(value)
            if set(bounds) == {'min', 'max'} and all(len(values) == 1 for values in bounds.values()):
                scale = {side: next(iter(values)) for side, values in bounds.items()}
                if float(scale['min']) < float(scale['max']):
                    existing = [f.value for f in unit.fields if f.property == 'rating_scale']
                    state = 'conflict' if existing and any(v != scale for v in existing) else 'accepted'
                    if not existing:
                        unit.fields.append(Datum(property='rating_scale', value=scale, method='interpretation',
                            locator={'recognition_rule': 'both_explicit_scale_bounds', 'vocabulary_version': vocabulary()['version']}))
                    decisions.append({'unit_id': unit.unit_id, 'concept': 'rating_scale', 'field_name': 'scale bounds',
                        'status': state, 'reason': 'both_explicit_scale_bounds', 'value': scale,
                        'lexical_matches': {}, 'semantic_ranking': [],
                        'locator': {'source_fields': [r['field'].locator for r in bound_records if r['field'] and normalize(r['name']) in ('worst rating', 'minimum rating', 'min rating', 'best rating', 'maximum rating', 'max rating')]}})
        metrics = {'vocabulary_version': vocabulary()['version'],
            'model': MODEL if self.scorer else None, 'mode': 'lexical+e5' if self.scorer else 'lexical',
            'model_revision': REVISION if self.scorer else None,
            'model_available': (not model_error if model_error or getattr(self.scorer, 'last_scored', len(selected)) else None) if self.scorer and selected else None,
            'considered_fields': len(records), 'examined_fields': len(selected),
            'omitted_fields': len(records) - len(selected),
            'truncated_contexts': sum(len(str(r['value'])) > 600 or len(r['unit'].text) > 800 for r in selected),
            'token_truncated_inputs': getattr(self.scorer, 'last_truncated', 0),
            'semantic_omitted_fields': getattr(self.scorer, 'last_omitted', 0),
            'semantic_context_budget': getattr(self.scorer, 'max_new_texts', None),
            'score_semantics': 'cosine similarity, not probability; no automatic acceptance from E5',
            'decisions': len(decisions)}
        return list(units.values()), decisions, metrics


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Provision the pinned local E5 review-recognition model')
    parser.add_argument('--download-model', action='store_true', required=True)
    parser.parse_args()
    from huggingface_hub import snapshot_download
    print(snapshot_download(MODEL, revision=REVISION,
          allow_patterns=['*.json', '*.safetensors', '*.model', 'tokenizer*', '1_Pooling/*']))
