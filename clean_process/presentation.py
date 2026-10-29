"""Consumer projections computed by Clean&Process, independent of any UI framework."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import math
from typing import Literal

from pydantic import Field

from .contracts import Output, Model, ProductView, ImageUseView, QuestionResult, Finding, Issue, CategoryView
from pydantic import JsonValue


class PublishedRating(Model):
    score: JsonValue
    score_number: float | None
    scale: JsonValue
    count: JsonValue
    count_number: float | None
    count_kind: str
    normalized_score: float | None = Field(ge=0, le=1)
    scale_group: str | None = None
    assertion_refs: list[str]


class Description(Model):
    text: JsonValue
    voice: str
    assertion_refs: list[str]


class ReviewExcerpt(Model):
    review_ref: str
    text: JsonValue
    author: JsonValue
    aspects: list[dict[str, JsonValue]]


class PresentedProduct(ProductView):
    images: list[ImageUseView]
    descriptions: list[Description]
    ratings: list[PublishedRating]
    reviews: list[ReviewExcerpt]


class Summary(Model):
    products: int = Field(ge=0)
    textual_reviews: int = Field(ge=0)
    offers: int = Field(ge=0)
    image_uses: int = Field(ge=0)
    published_rating_records: int = Field(ge=0)
    findings: int = Field(ge=0)
    issues: int = Field(ge=0)


class PresentedFinding(Finding):
    quotes: list[str] = Field(default_factory=list)
    aspects: list[str] = Field(default_factory=list)
    evaluated_subject_refs: list[str] = Field(default_factory=list)


class ChartRows(Model):
    rating_rows: list[dict[str, JsonValue]]
    published_count_rows: list[dict[str, JsonValue]]
    keyword_rows: list[dict[str, JsonValue]]
    opinion_rows: list[dict[str, JsonValue]]


class Presentation(Model):
    contract_version: Literal['1.0']
    processing_id: str
    result_revision: int
    generated_at: str
    products: list[PresentedProduct]
    categories: list[CategoryView]
    labels: dict[str, str]
    questions: dict[str, QuestionResult]
    charts: ChartRows
    summary: Summary
    findings: list[PresentedFinding]
    issues: list[Issue]


def numeric(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        number = Decimal(str(value))
        result = float(number) if number.is_finite() else None
        return result if result is not None and math.isfinite(result) else None
    except InvalidOperation:
        return None


def present(payload: Output | dict):
    output = Output.model_validate(payload)
    accepted = [a for a in output.knowledge.assertions if a.status == 'accepted']
    by_subject = defaultdict(list)
    for a in accepted:
        by_subject[a.subject_ref].append(a)
    def values(subject, predicate):
        return [a for a in by_subject[subject] if a.predicate == predicate]
    def targets(subject, predicate):
        return list(dict.fromkeys(a.object_ref for a in values(subject, predicate) if a.object_ref))
    def literal(subject, predicate):
        return next((a.value for a in values(subject, predicate)), None)
    labels = {e.entity_id: literal(e.entity_id, 'name') or
              (f'{e.kind} · {literal(e.entity_id, "size")}' if literal(e.entity_id, 'size') else e.kind)
              for e in output.knowledge.entities}
    questions = {q.question_id: q.model_dump(mode='json') for q in output.data.question_results}
    visual = questions.get('visual_presentation', {}).get('values', {}).get('appearances', [])
    products = []
    for p in output.data.products:
        row = p.model_dump(mode='json')
        row['images'] = [use for appearance in visual if p.entity_id in appearance['subject_refs']
                         for use in appearance['image_uses']]
        descriptions = values(p.entity_id, 'description')
        row['descriptions'] = [{'text': a.value, 'voice': a.scope.get('voice', 'unknown'),
                                'assertion_refs': [a.assertion_id]} for a in descriptions]
        rating_subjects = [p.entity_id] + [a.subject_ref for a in accepted if
            a.predicate == 'summarizes' and a.object_ref == p.entity_id]
        ratings, seen = [], set()
        for subject in rating_subjects:
            score, scale, count = literal(subject, 'rating'), literal(subject, 'rating_scale'), literal(subject, 'rating_count')
            if score is None and count is None:
                continue
            key = (str(score), str(scale), str(count), str(literal(subject, 'count_kind')))
            if key in seen:
                continue
            seen.add(key)
            bounds = scale if isinstance(scale, dict) else {}
            lower, upper = numeric(bounds.get('min')), numeric(bounds.get('max'))
            score_number = numeric(score)
            comparable = lower is not None and upper is not None and upper > lower and score_number is not None and lower <= score_number <= upper
            refs = [a.assertion_id for a in by_subject[subject] if a.predicate in
                    ('rating', 'rating_scale', 'rating_count', 'count_kind')]
            ratings.append({'score': score, 'score_number': score_number, 'scale': scale,
                            'count': count, 'count_number': numeric(count),
                            'count_kind': literal(subject, 'count_kind') or 'unspecified',
                            'normalized_score': (score_number-lower)/(upper-lower) if comparable else None,
                            'scale_group': f'{lower}:{upper}' if comparable else None,
                            'assertion_refs': refs})
        row['ratings'] = ratings
        reviews = []
        for entity in output.knowledge.entities:
            if entity.kind != 'Resena':
                continue
            evaluated = targets(entity.entity_id, 'evaluates')
            if p.entity_id not in evaluated and not set(p.variant_refs).intersection(evaluated):
                continue
            reviews.append({'review_ref': entity.entity_id, 'text': literal(entity.entity_id, 'review_body'),
                            'author': literal(entity.entity_id, 'author'),
                            'aspects': [{'value': a.value, 'assertion_refs': [a.assertion_id]}
                                        for a in values(entity.entity_id, 'aspect_opinion')]})
        row['reviews'] = reviews
        products.append(row)
    entities = {e.entity_id: e.kind for e in output.knowledge.entities}
    charts = {'rating_rows': [], 'published_count_rows': [], 'keyword_rows': [], 'opinion_rows': []}
    for p in products:
        for rating in p['ratings']:
            row = {'product_ref': p['entity_id'], 'label': p['name'] or 'Producto sin nombre', **rating}
            charts['rating_rows'].append(row)
            if rating['count_number'] is not None and rating['count_number'] >= 0:
                charts['published_count_rows'].append(row)
    for group in questions.get('keywords', {}).get('values', {}).get('groups', []):
        charts['keyword_rows'].append({**group, 'subject_label': labels.get(group['subject_ref'], 'Contenido')})
    for group in questions.get('category_opinions', {}).get('values', {}).get('groups', []):
        charts['opinion_rows'].append({**group, 'category_label': labels.get(group['category_ref'], 'Categoría')})
    findings = []
    for finding in output.findings:
        statements = [a for a in accepted if a.assertion_id in finding.assertion_refs and isinstance(a.value, dict)]
        findings.append({**finding.model_dump(),
            'quotes': list(dict.fromkeys(a.value['quote'] for a in statements if isinstance(a.value.get('quote'), str))),
            'aspects': list(dict.fromkeys(a.value['aspect'] for a in statements if isinstance(a.value.get('aspect'), str))),
            'evaluated_subject_refs': targets(finding.subject_ref, 'evaluates')})
    result = {'contract_version': '1.0', 'processing_id': output.processing_id,
            'result_revision': output.result_revision, 'generated_at': output.generated_at,
            'products': products, 'categories': [c.model_dump() for c in output.data.categories],
            'labels': labels, 'questions': questions, 'charts': charts,
            'summary': {'products': len(products), 'textual_reviews': sum(k == 'Resena' for k in entities.values()),
                        'offers': sum(k == 'Oferta' for k in entities.values()),
                        'image_uses': sum(k == 'UsoDeImagen' for k in entities.values()),
                        'published_rating_records': sum(len(p['ratings']) for p in products),
                        'findings': len(output.findings), 'issues': len(output.issues)},
            'findings': findings,
            'issues': [i.model_dump() for i in output.issues]}
    return Presentation.model_validate(result).model_dump(mode='json')


def compare(left, right):
    """No cross-source equivalence or currency/scale conversion is assumed."""
    views = [present(left), present(right)]
    return {'contract_version': '1.0', 'sources': views,
            'question_matrix': {key: [v['questions'].get(key, {}).get('status', 'not_answerable') for v in views]
                                for key in ('price_range', 'visual_presentation', 'keywords', 'category_opinions')},
            'product_equivalence': 'not_established',
            'note': 'Source-level comparison; product identity across sources has not been established.'}
