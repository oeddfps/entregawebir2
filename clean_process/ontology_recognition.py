"""Recognize producer class/field names without changing or importing a scraper."""
from functools import lru_cache
from decimal import Decimal
from importlib.resources import files
import json
import re

from .commerce import enrich_commerce, money, percentage
from .contracts import Datum, Relation
from .ontology import RELATIONS, canonical_url
from .review_recognition import normalize, numeric, matches as review_matches


@lru_cache(maxsize=1)
def vocabulary():
    return json.loads(files('clean_process').joinpath('vocabularies/ontology.v1.json').read_text(encoding='utf-8'))


def concepts(names, prefix, *, exact=True):
    names = [normalize(n) for n in names if isinstance(n, str) and n.strip()]
    return [key[len(prefix):] for key, item in vocabulary()['concepts'].items()
            if key.startswith(prefix) and any(
                name == normalize(term) if exact else ' '+normalize(term)+' ' in ' '+name+' '
                for name in names for term in item['terms'])]


def field_records(unit):
    for field in unit.fields:
        if field.property == 'raw_field' and isinstance(field.value, dict):
            yield field.value.get('name', ''), field.value.get('label', ''), field.value.get('value'), field.locator


def literals(unit, prop):
    return [f.value for f in unit.fields if f.property == prop]


def resolve(value, units):
    if isinstance(value, dict):
        value = value.get('unit_id', value.get('target_unit', value.get('@id')))
    if not isinstance(value, str):
        return None
    if value in units:
        return value
    url = canonical_url(value)
    if url:
        matches = [uid for uid, u in units.items()
                   if url in [canonical_url(v) for v in literals(u, 'url') if isinstance(v, str)]]
        if len(matches) == 1:
            return matches[0]
    return None


def compatible_class(kind, unit, sample, units):
    has = lambda prop: any(v is not None and v != '' for v in literals(unit, prop))
    referenced = {r.predicate for r in sample.relations if r.subject_unit == unit.unit_id}
    for name, label, value, _ in field_records(unit):
        for predicate in concepts([name, label], 'relation.'):
            if resolve(value, units):
                referenced.add(predicate)
    if kind == 'Pagina':
        return any(canonical_url(v) for v in literals(unit, 'url') if isinstance(v, str))
    if kind == 'Coleccion':
        return bool(referenced & {'contains', 'member'}) or any(isinstance(v, list) for _, _, v, _ in field_records(unit))
    if kind == 'Producto':
        return any(isinstance(v, str) and v.strip() for v in literals(unit, 'name')) and (
            any(canonical_url(v) for v in literals(unit, 'url') if isinstance(v, str)) or
            any(isinstance(v, str) and v.strip() for prop in ('sku', 'gtin') for v in literals(unit, prop)))
    if kind == 'Categoria':
        return has('name') or has('category_name')
    if kind == 'Variante':
        return any(has(prop) for prop in ('size', 'quantity', 'presentation', 'sku', 'gtin'))
    if kind == 'Oferta':
        return any(isinstance(v, str) and re.fullmatch(r'\d+(?:\.\d+)?', v) and
                   Decimal(v).is_finite() and (prop != 'discount_percent' or Decimal(v) <= 100)
                   for prop in ('amount', 'discount_percent', 'discount_amount') for v in literals(unit, prop))
    if kind == 'Imagen':
        return bool(canonical_url(unit.resource_ref) if unit.resource_ref else False) or any(
            canonical_url(v) for prop in ('url', 'image') for v in literals(unit, prop) if isinstance(v, str))
    if kind == 'Aparicion':
        return 'represents' in referenced
    if kind == 'UsoDeImagen':
        return 'uses' in referenced
    if kind == 'Resena':
        return any(isinstance(v, str) and len(v.split()) >= 3 and 'review_control' not in review_matches(v)
                   for v in literals(unit, 'review_body'))
    if kind == 'ValoracionAgregada':
        return any(numeric(v, count=True) is not None for v in literals(unit, 'rating_count')) or any(
            numeric(v) is not None for v in literals(unit, 'rating'))
    if kind == 'Texto':
        return bool(unit.text.strip()) or has('description')
    return False


def property_value(prop, value, label, unit):
    if prop in ('amount', 'previous_amount', 'discount_amount'):
        parsed = money(value)
        return (parsed['amount'] if parsed else None), 'monetary_label_and_value'
    if prop == 'discount_percent':
        names = normalize(label)
        explicit = any(word in names.split() for word in ('percent', 'percentage', 'porcentaje', 'percentual'))
        return percentage(value, explicit_numeric=explicit), 'discount_label_and_percentage'
    if prop == 'discount_status':
        if isinstance(value, bool):
            if any(term in normalize(label) for term in ('sin descuento', 'no discount', 'non discounted')):
                value = not value
            return ('discount' if value else 'no_discount'), 'explicit_discount_boolean'
        token = normalize(value)
        if token in ('sin descuento', 'no discount', 'non discounted', 'no discounted', 'false', 'no', 'no discount offer', 'no discount status', 'no discount applied', 'no discount available', 'no_discount'):
            return 'no_discount', 'explicit_no_discount_declaration'
        if token in ('con descuento', 'discount', 'discounted', 'true', 'yes', 'si'):
            return 'discount', 'explicit_discount_declaration'
        return None, 'unknown_discount_declaration'
    if prop in ('url', 'image'):
        return (canonical_url(value) if isinstance(value, str) else None), 'explicit_resource_reference'
    if prop == 'order':
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value, 'explicit_nonnegative_position'
        if isinstance(value, str) and value.isdigit():
            return int(value), 'explicit_nonnegative_position'
        return None, 'invalid_position'
    if prop == 'visibility':
        token = normalize(value)
        return {'visible': 'visible', 'true': 'visible', 'hidden': 'hidden', 'oculta': 'hidden', 'false': 'hidden', 'unknown': 'unknown'}.get(token), 'explicit_visibility_declaration'
    if prop == 'function':
        return None, 'visual_function_requires_visual_evidence'
    if prop in ('rating', 'rating_count', 'rating_scale', 'author', 'date', 'review_body'):
        # These meanings are handled by the dedicated review stage.
        return None, 'delegated_to_review_recognition'
    if prop in ('conditions', 'valid_period'):
        return (value if isinstance(value, (str, dict, list)) else None), 'explicit_conditions_or_period'
    if prop == 'currency':
        return (value if isinstance(value, str) and re.fullmatch('[A-Z]{3}', value) else None), 'explicit_currency_code'
    if isinstance(value, str) and value.strip():
        return value, 'explicit_field_label'
    if prop == 'quantity' and isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value, 'explicit_quantity'
    return None, 'incompatible_value'


class OntologyRecognizer:
    def __init__(self, scorer=None, *, max_records=96):
        self.scorer = scorer
        self.max_records = max_records

    def recognize(self, sample):
        units = {u.unit_id: u.model_copy(deep=True) for u in sample.content_units}
        records = []
        for unit in units.values():
            labels = unit.locator.get('source_type_names', [])
            if labels:
                records.append({'unit': unit, 'type': 'entity.', 'names': labels,
                                'value': unit.text, 'locator': unit.locator})
            records.extend({'unit': unit, 'type': 'property.', 'names': [name, label], 'value': value, 'locator': locator}
                           for name, label, value, locator in field_records(unit))
            # Standalone producer price/discount blocks may have their value as text.
            if unit.text and concepts(labels, 'entity.') == ['Oferta']:
                records.append({'unit': unit, 'type': 'property.', 'names': labels,
                                'value': unit.text, 'locator': unit.locator})
        records.sort(key=lambda r: not bool(concepts(r['names'], r['type']) or concepts(r['names'], 'relation.')))
        selected = records[:self.max_records]
        diagnostics = []
        relation_records = []
        class_records = []
        failed = False
        semantic_omitted, token_truncated = 0, 0
        for prefix in ('property.', 'entity.'):
            rows = [r for r in selected if r['type'] == prefix]
            rankings = [[] for _ in rows]
            if self.scorer and rows:
                texts = [f'Clase o campo: {" / ".join(r["names"])[:200]}. Valor: {str(r["value"])[:600]}. Contexto: {r["unit"].text[:600]}' for r in rows]
                try:
                    rankings = self.scorer.rank_for(texts, prefix) if hasattr(self.scorer, 'rank_for') else self.scorer.rank(texts)
                    if len(rankings) != len(rows):
                        raise ValueError('Missing rankings')
                    semantic_omitted += getattr(self.scorer, 'last_omitted', 0)
                    token_truncated += getattr(self.scorer, 'last_truncated', 0)
                except Exception:
                    failed, rankings = True, [[] for _ in rows]
            for record, ranking in zip(rows, rankings):
                unit, value = record['unit'], record['value']
                hits = concepts(record['names'], prefix)
                decision = {'unit_id': unit.unit_id, 'field_name': ' / '.join(record['names']),
                    'value': value, 'concepts': hits, 'status': 'ambiguous',
                    'semantic_ranking': [{'concept': k, 'cosine_similarity': round(float(v), 6)} for k, v in ranking],
                    'locator': {k: v for k, v in record['locator'].items() if k != 'original_block'},
                    'reason': 'semantic_candidate_requires_explicit_support'}
                if prefix == 'entity.':
                    class_records.append((record, decision))
                    continue
                relations = concepts(record['names'], 'relation.')
                if relations:
                    relation_records.append((record, relations))
                prop = hits[0] if len(hits) == 1 else None
                commercial_class = 'Oferta' in concepts(unit.locator.get('source_type_names', []), 'entity.')
                if prop is None and commercial_class and money(value):
                    prop = 'amount'
                if prop is None and commercial_class and 'Oferta' in concepts(record['names'], 'entity.') and percentage(value) is not None:
                    prop = 'discount_percent'
                if prop == 'discount_percent' and money(value) and money(value)['symbol']:
                    prop = 'discount_amount'
                # $ and % are candidate signals even with unknown field names.
                if prop is None and isinstance(value, str) and value.lstrip().startswith(('$', '%')):
                    decision['reason'] = 'currency_or_percentage_symbol_without_field_meaning'
                if prop:
                    mapped, reason = property_value(prop, value, ' '.join(record['names']), unit)
                    decision.update(reason=reason, property=prop)
                    if mapped is not None:
                        existing = literals(unit, prop)
                        if existing and any(v != mapped for v in existing):
                            decision.update(status='conflict', reason='existing_property_disagrees')
                        else:
                            if not existing:
                                unit.fields.append(Datum(property=prop, value=mapped, method='interpretation',
                                    locator={**decision['locator'], 'recognition_rule': reason, 'original_literal': value}))
                            parsed = money(value) if prop in ('amount', 'previous_amount', 'discount_amount') else None
                            if parsed:
                                for p, v in [('currency_symbol', parsed['symbol']), ('currency', parsed['currency'])]:
                                    if v is not None and v not in literals(unit, p):
                                        unit.fields.append(Datum(property=p, value=v, method='interpretation', locator=decision['locator']))
                            decision['status'] = 'accepted'
                if hits or ranking or relations or decision['reason'].startswith('currency_or'):
                    diagnostics.append(decision)
        for unit in units.values():
            for detail in enrich_commerce(unit):
                diagnostics.append({'unit_id': unit.unit_id, 'status': 'ambiguous', **detail})
        for record, decision in class_records:
            unit = record['unit']
            viable = [kind for kind in decision['concepts'] if compatible_class(kind, unit, sample, units)]
            if len(viable) == 1:
                kind = viable[0]
                if unit.classification in ('other', 'Texto', kind):
                    if unit.classification != kind:
                        unit.classification, unit.classification_method = kind, 'interpretation'
                    decision.update(status='accepted', reason='producer_class_and_compatible_structure', classification=kind)
                    if kind == 'Imagen' and not literals(unit, 'url'):
                        resource = unit.resource_ref or next((v for v in literals(unit, 'image') if isinstance(v, str)), None)
                        if resource:
                            unit.fields.append(Datum(property='url', value=resource, method='interpretation', locator=decision['locator']))
                else:
                    decision.update(status='conflict', reason='existing_classification_disagrees')
            else:
                decision['reason'] = 'missing_structure_or_multiple_class_candidates'
            if decision['concepts'] or decision['semantic_ranking']:
                diagnostics.append(decision)
        relations = list(sample.relations)
        for record, predicates in relation_records:
            value = record['value']
            targets = value if isinstance(value, list) else [value]
            for target_value in targets:
                target = resolve(target_value, units)
                for predicate in predicates:
                    unit = record['unit']
                    allowed_from, allowed_to = RELATIONS[predicate]
                    accepted = target is not None and unit.classification in allowed_from and (
                        not allowed_to or units[target].classification in allowed_to)
                    diagnostics.append({'unit_id': unit.unit_id, 'predicate': predicate,
                        'target_unit': target, 'value': target_value, 'status': 'accepted' if accepted else 'ambiguous',
                        'reason': 'explicit_endpoint_and_compatible_types' if accepted else 'unresolved_or_incompatible_endpoint'})
                    if accepted and not any(r.subject_unit == unit.unit_id and r.object_unit == target and r.predicate == predicate for r in relations):
                        relations.append(Relation(subject_unit=unit.unit_id, predicate=predicate, object_unit=target, method='interpretation'))
        # Newly recognized offers get their explicit/unknown discount status too.
        for unit in units.values():
            if unit.classification == 'Oferta' and not literals(unit, 'discount_status'):
                unit.fields.append(Datum(property='discount_status', value='unknown', method='interpretation',
                    locator={'recognition_rule': 'no_evidence_of_discount_status'}))
        metrics = {'vocabulary_version': vocabulary()['version'], 'ontology_version': '0.3',
            'considered_records': len(records), 'examined_records': len(selected),
            'omitted_records': len(records)-len(selected), 'semantic_omitted_records': semantic_omitted,
            'token_truncated_inputs': token_truncated, 'model_failed': failed,
            'text_truncated_records': sum(len(str(r['value'])) > 600 or len(r['unit'].text) > 600 for r in selected),
            'mode': 'lexical+e5' if self.scorer else 'lexical'}
        return list(units.values()), relations, diagnostics, metrics
