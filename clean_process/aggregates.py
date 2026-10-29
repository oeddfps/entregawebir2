"""Deterministic read projections; no model-generated counts or price ranges."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import json
import re

from .contracts import Finding, QuestionResult
from .ontology import identifier, normalized


def price_results(w):
    groups, excluded = defaultdict(list), []
    for entity in w.entities.values():
        if entity.kind != 'Oferta':
            continue
        eid = entity.entity_id
        variants = w.targets(eid, 'offers')
        amount, currency = w.value(eid, 'amount'), w.value(eid, 'currency')
        kind = w.value(eid, 'price_kind')
        reason = None
        if len(variants) != 1:
            reason = 'variant_unresolved'
        elif not any(w.value(variants[0], p) is not None for p in ('size', 'quantity', 'presentation', 'sku', 'gtin')):
            reason = 'presentation_unresolved'
        elif not isinstance(currency, str) or not re.fullmatch('[A-Z]{3}', currency):
            reason = 'currency_unresolved'
        elif kind not in ('exact', 'from', 'until', 'previous', 'installment'):
            reason = 'price_kind_unresolved'
        elif w.value(eid, 'conditions') is None or not isinstance(w.value(eid, 'seller'), str) or not w.value(eid, 'seller'):
            reason = 'conditions_or_seller_unresolved'
        try:
            if not isinstance(amount, str) or not re.fullmatch(r'\d+(?:\.\d+)?', amount):
                raise InvalidOperation
            value = Decimal(amount)
        except (InvalidOperation, TypeError):
            reason = reason or 'amount_unresolved'
        if reason:
            excluded.append({'offer_ref': eid, 'reason': reason})
            continue
        refs = [a.assertion_id for a in w.assertions if a.subject_ref in (eid, variants[0]) and a.status == 'accepted']
        # Unknown historical validity is not replaced with capture time. Offers
        # can only be compared inside one source sample unless period is explicit.
        period = w.value(eid, 'valid_period')
        sample_id = w.values(eid, 'type')[0].scope['sample_id']
        comparison_time = ('period', json.dumps(period, sort_keys=True)) if period is not None else ('sample', sample_id)
        conditions = w.value(eid, 'conditions')
        key = (variants[0], currency, json.dumps(conditions, sort_keys=True), comparison_time)
        groups[key].append({'offer_ref': eid, 'amount': str(value), 'kind': kind,
                            'seller': w.value(eid, 'seller'), 'valid_period': period,
                            'assertion_refs': refs})
    values, refs = [], []
    for (variant, currency, conditions, time_scope), offers in groups.items():
        exact = [Decimal(o['amount']) for o in offers if o['kind'] == 'exact']
        values.append({'variant_ref': variant, 'currency': currency, 'conditions': json.loads(conditions),
                       'comparison_time': list(time_scope), 'offers': offers,
                       'price_observed': str(exact[0]) if len(exact) == 1 else None,
                       'minimum': str(min(exact)) if len(exact) > 1 else None,
                       'maximum': str(max(exact)) if len(exact) > 1 else None,
                       'range_basis': 'exact_comparable_offers' if len(exact) > 1 else 'no_observed_range'})
        refs.extend(a for o in offers for a in o['assertion_refs'])
    return QuestionResult(question_id='price_range', status=('partial' if excluded else 'answered') if values else 'not_answerable',
                          values={'groups': values}, supporting_assertion_ids=list(dict.fromkeys(refs)), exclusions=excluded)


def visual_results(w):
    appearances, refs = [], []
    for entity in w.entities.values():
        if entity.kind != 'Aparicion':
            continue
        eid = entity.entity_id
        uses = []
        for use in w.targets(eid, 'presents'):
            images = w.targets(use, 'uses')
            uses.append({'usage_ref': use, 'image_refs': images,
                         'resources': [w.value(i, 'url') for i in images],
                         'order': w.value(use, 'order'), 'context': w.value(use, 'context'),
                         'visibility': w.value(use, 'visibility'),
                         'functions': [a.value for a in w.values(use, 'function')],
                         'function_status': 'declared' if w.values(use, 'function') else 'not_interpreted'})
            refs.extend(a.assertion_id for a in w.assertions if a.subject_ref in [eid, use, *images] and a.status == 'accepted')
        if uses:
            appearances.append({'appearance_ref': eid, 'subject_refs': w.targets(eid, 'represents'), 'image_uses': uses})
    incomplete = any(u['order'] is None or u['visibility'] is None or not u['functions']
                     for a in appearances for u in a['image_uses'])
    return QuestionResult(question_id='visual_presentation',
        status=('partial' if incomplete else 'answered') if appearances else 'not_answerable',
        values={'appearances': appearances}, supporting_assertion_ids=list(dict.fromkeys(refs)))


def topic_results(w):
    groups = {}
    for a in w.assertions:
        if a.status != 'accepted' or a.predicate != 'topic' or not isinstance(a.value, dict):
            continue
        quote = a.value.get('quote')
        label = a.value.get('label', quote)
        if not quote or not isinstance(label, str):
            continue
        voice, language = a.scope.get('voice', 'unknown'), a.scope.get('language')
        targets = w.targets(a.subject_ref, 'mentions')
        subject = targets[0] if len(targets) == 1 else a.subject_ref
        key = (subject, a.predicate, normalized(label).casefold(), voice, language)
        group = groups.setdefault(key, {'subject_ref': subject, 'kind': a.predicate, 'label': label,
            'voice': voice, 'language': language, 'expressions': [], 'units': {}, 'assertion_refs': []})
        for ref in a.evidence_refs:
            e = w.evidence[ref]
            # Text reuse in marketing content is different from review identity.
            # Consumer text retains separate source units unless identity is established.
            identity = a.subject_ref if w.entities[a.subject_ref].kind == 'Resena' else (
                ref if voice == 'consumer' else identifier('text', voice, normalized(e.text)))
            intervals = group['units'].setdefault(identity, set())
            text, expression = normalized(e.text), normalized(quote)
            intervals.update((m.start(), m.end()) for m in re.finditer(re.escape(expression), text))
        if quote not in group['expressions']:
            group['expressions'].append(quote)
        group['assertion_refs'].append(a.assertion_id)
    results, refs = [], []
    for group in groups.values():
        units = group.pop('units')
        group['unique_content_units'] = len(units)
        def nonoverlapping(intervals):
            count, previous_end = 0, -1
            for start, end in sorted(intervals):
                if start >= previous_end:
                    count += 1
                previous_end = max(previous_end, end)
            return count
        group['expression_occurrences'] = sum(nonoverlapping(intervals) for intervals in units.values())
        group['independent_authors'] = None
        group['assertion_refs'] = list(dict.fromkeys(group['assertion_refs']))
        refs.extend(group['assertion_refs'])
        results.append(group)
    return QuestionResult(question_id='keywords', status='answered' if results else 'not_answerable',
                          values={'groups': results}, supporting_assertion_ids=list(dict.fromkeys(refs)))


def keyword_results(w):
    from .keywords import description_keywords
    topics = topic_results(w)
    words = description_keywords(w)
    groups = words + [g.model_dump() for g in topics.values.groups]
    refs = list(dict.fromkeys(ref for g in groups for ref in g['assertion_refs']))
    return QuestionResult(question_id='keywords', status='answered' if groups else 'not_answerable',
        values={'groups': groups, 'definition': 'description_words_v1'}, supporting_assertion_ids=refs)


def opinion_results(w):
    groups = {}
    aggregates = []
    exclusions = []
    for entity in w.entities.values():
        eid = entity.entity_id
        if entity.kind == 'ValoracionAgregada':
            aggregates.append({'aggregate_ref': eid, 'subject_refs': w.targets(eid, 'summarizes'),
                'rating': w.value(eid, 'rating'), 'scale': w.value(eid, 'rating_scale'),
                'published_count': w.value(eid, 'rating_count'),
                'count_kind': w.value(eid, 'count_kind', 'unspecified'),
                'assertion_refs': [a.assertion_id for a in w.assertions if a.subject_ref == eid and a.status == 'accepted']})
        if entity.kind != 'Resena':
            continue
        aspects = w.values(eid, 'aspect_opinion')
        targets = w.targets(eid, 'evaluates')
        if not targets:
            exclusions.append({'review_ref': eid, 'reason': 'review_subject_unresolved'})
        if len(targets) > 1:
            exclusions.append({'review_ref': eid, 'reason': 'aspect_subject_ambiguous'})
        if not aspects:
            exclusions.append({'review_ref': eid, 'reason': 'aspects_not_interpreted'})
        destinations = set()
        for target in targets if len(targets) == 1 else []:
            if w.entities[target].kind == 'Categoria':
                destinations.add((target, 'explicit_category_opinion'))
            else:
                for product in w.product_for(target):
                    for category in w.targets(product, 'belongs_to'):
                        destinations.add((category, 'product_reviews_in_category'))
        if targets and not destinations:
            exclusions.append({'review_ref': eid, 'reason': 'category_membership_unresolved'})
        for a in aspects:
            data = a.value
            if not isinstance(data, dict) or data.get('sentiment') not in ('favorable', 'unfavorable', 'mixed', 'neutral', 'indeterminate'):
                continue
            for category, basis in destinations:
                key = (category, basis, data.get('aspect', 'other'), data['sentiment'], a.scope.get('voice', 'unknown'))
                group = groups.setdefault(key, {'category_ref': category, 'basis': basis,
                    'aspect': key[2], 'sentiment': key[3], 'voice': key[4],
                    'review_refs': [], 'assertion_refs': [], 'quotes': []})
                if eid not in group['review_refs']:
                    group['review_refs'].append(eid)
                group['assertion_refs'].append(a.assertion_id)
                group['quotes'].append(data['quote'])
            # Individual adverse reports remain visible even without a resolved category.
            if data.get('material') is True and a.scope.get('voice') not in ('brand', 'seller'):
                fid = identifier('finding', eid, data.get('aspect'), data.get('quote'))
                existing = next((f for f in w.findings if f.finding_id == fid), None)
                if existing:
                    existing.assertion_refs.append(a.assertion_id)
                else:
                    w.findings.append(Finding(finding_id=fid,
                        subject_ref=eid, reason='Individual reported experience material to the question; not a causal conclusion',
                        extent='individual', unique_opinions=1, assertion_refs=[a.assertion_id]))
    rows, refs = [], []
    for group in groups.values():
        group['unique_opinions'] = len(group['review_refs'])
        group['independence'] = 'unknown'
        group['assertion_refs'] = list(dict.fromkeys(group['assertion_refs']))
        refs.extend(group['assertion_refs'])
        rows.append(group)
    refs.extend(a for aggregate in aggregates for a in aggregate['assertion_refs'])
    return QuestionResult(question_id='category_opinions',
        status=('partial' if exclusions or not rows else 'answered') if rows or aggregates else 'not_answerable',
        values={'groups': rows, 'published_aggregates': aggregates},
        supporting_assertion_ids=list(dict.fromkeys(refs)), exclusions=exclusions)


def question_results(work):
    handlers = {'price_range': price_results, 'visual_presentation': visual_results,
                'keywords': keyword_results, 'category_opinions': opinion_results}
    return [handlers[q](work) for q in work.request.questions]
