"""Versioned JSON boundaries. No dependency on the scraper, persistence or UI."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

VERSION = '1.0'
ONTOLOGY_VERSION = '0.2'
QUESTIONS = ('price_range', 'visual_presentation', 'keywords', 'category_opinions')
Kind = Literal['Pagina', 'Coleccion', 'Aparicion', 'Producto', 'Categoria',
               'Variante', 'Oferta', 'Imagen', 'UsoDeImagen', 'Texto', 'Resena',
               'ValoracionAgregada', 'Evidencia', 'Afirmacion', 'other']
Method = Literal['observation', 'source_declaration', 'interpretation']
Status = Literal['proposed', 'accepted', 'ambiguous', 'conflict']


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)

    def __getitem__(self, key):
        """Convenient read-only access to typed read projections."""
        return getattr(self, key)


class Datum(Model):
    property: str = Field(min_length=1)
    value: JsonValue
    method: Method = 'source_declaration'
    locator: dict[str, JsonValue] = Field(default_factory=dict)


class Unit(Model):
    unit_id: str = Field(min_length=1)
    modality: Literal['text', 'image', 'structured'] = 'text'
    text: str = ''
    resource_ref: str | None = None
    classification: Kind = 'other'
    classification_method: Method = 'source_declaration'
    fields: list[Datum] = Field(default_factory=list)
    locator: dict[str, JsonValue] = Field(default_factory=dict)
    # Explicit attribution, not guessed from domain or product name.
    voice: Literal['brand', 'seller', 'consumer', 'unknown'] = 'unknown'
    language: str | None = None


class Relation(Model):
    subject_unit: str
    predicate: Literal['contains', 'member', 'represents', 'belongs_to', 'has_variant',
                       'offers', 'presents', 'uses', 'mentions', 'evaluates', 'summarizes']
    object_unit: str
    method: Method = 'source_declaration'


class Sample(Model):
    sample_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    observed_at: str | None = None
    content_units: list[Unit] = Field(min_length=1)
    relations: list[Relation] = Field(default_factory=list)
    context: dict[str, JsonValue] = Field(default_factory=dict)
    coverage: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator('observed_at')
    @classmethod
    def observation_instant(cls, value):
        if value is not None:
            instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if instant.tzinfo is None:
                raise ValueError('observed_at needs an explicit timezone')
        return value

    @model_validator(mode='after')
    def unique_units(self):
        ids = [u.unit_id for u in self.content_units]
        if len(ids) != len(set(ids)):
            raise ValueError('unit_id must be unique within its sample')
        for relation in self.relations:
            if relation.subject_unit not in ids or relation.object_unit not in ids:
                raise ValueError('relation refers to an unknown unit')
        return self


class Input(Model):
    contract_version: Literal['1.0'] = VERSION
    samples: list[Sample] = Field(min_length=1)
    questions: list[Literal['price_range', 'visual_presentation', 'keywords',
                            'category_opinions']] = Field(default_factory=lambda: list(QUESTIONS))
    scope: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator('scope')
    @classmethod
    def supported_scope(cls, value):
        for key, values in value.items():
            if key not in ('source_refs', 'sample_refs'):
                raise ValueError('Unsupported scope filter; filters must never be silently ignored')
            if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                raise ValueError('Scope filters require lists of non-empty references')
        return value

    @model_validator(mode='after')
    def unique_samples(self):
        ids = [s.sample_id for s in self.samples]
        if len(ids) != len(set(ids)):
            raise ValueError('sample_id must be unique in this input')
        if len(self.questions) != len(set(self.questions)):
            raise ValueError('duplicate question')
        return self


class Evidence(Model):
    evidence_id: str
    sample_id: str
    unit_id: str
    source_ref: str
    text: str
    resource_ref: str | None = None
    fields: list[Datum] = Field(default_factory=list)
    locator: dict[str, JsonValue] = Field(default_factory=dict)


class Entity(Model):
    entity_id: str
    kind: Kind
    identity_status: Literal['provisional', 'resolved', 'disputed'] = 'provisional'
    origin_refs: list[str]


class Assertion(Model):
    assertion_id: str
    subject_ref: str
    predicate: str
    value: JsonValue = None
    object_ref: str | None = None
    method: Method
    status: Status = 'accepted'
    evidence_refs: list[str] = Field(min_length=1)
    scope: dict[str, JsonValue] = Field(default_factory=dict)
    justification: str
    decision_history: list[dict[str, JsonValue]] = Field(default_factory=list)


class Issue(Model):
    issue_id: str
    code: str
    message: str
    subject_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class Finding(Model):
    finding_id: str
    subject_ref: str
    reason: str
    extent: Literal['individual', 'pattern', 'discrepancy']
    unique_opinions: int = Field(ge=0)
    assertion_refs: list[str] = Field(min_length=1)
    independence: Literal['known', 'unknown'] = 'unknown'


class OfferView(Model):
    offer_ref: str
    amount: str
    kind: Literal['exact', 'from', 'until', 'previous', 'installment']
    seller: str
    valid_period: JsonValue
    assertion_refs: list[str]


class PriceGroup(Model):
    variant_ref: str
    currency: str
    conditions: JsonValue
    comparison_time: list[str]
    offers: list[OfferView]
    price_observed: str | None
    minimum: str | None
    maximum: str | None
    range_basis: Literal['exact_comparable_offers', 'no_observed_range']


class PriceValues(Model):
    groups: list[PriceGroup]


class ImageUseView(Model):
    usage_ref: str
    image_refs: list[str]
    resources: list[str | None]
    order: int | None
    context: JsonValue
    visibility: Literal['visible', 'hidden', 'unknown'] | None
    functions: list[JsonValue]
    function_status: Literal['declared', 'not_interpreted']


class AppearanceView(Model):
    appearance_ref: str
    subject_refs: list[str]
    image_uses: list[ImageUseView]


class VisualValues(Model):
    appearances: list[AppearanceView]


class KeywordGroup(Model):
    subject_ref: str | None = None
    corpus_id: str | None = None
    kind: Literal['keyword', 'topic']
    label: str
    voice: Literal['brand', 'seller', 'consumer', 'unknown']
    language: str | None
    expressions: list[str]
    assertion_refs: list[str]
    unique_content_units: int = Field(ge=0)
    expression_occurrences: int = Field(ge=0)
    independent_authors: int | None


class KeywordValues(Model):
    groups: list[KeywordGroup]
    definition: Literal['legacy_expressions', 'description_words_v1'] = 'legacy_expressions'


class OpinionGroup(Model):
    category_ref: str
    basis: Literal['explicit_category_opinion', 'product_reviews_in_category']
    aspect: str
    sentiment: Literal['favorable', 'unfavorable', 'mixed', 'neutral', 'indeterminate']
    voice: Literal['brand', 'seller', 'consumer', 'unknown']
    review_refs: list[str]
    assertion_refs: list[str]
    quotes: list[str]
    unique_opinions: int = Field(ge=0)
    independence: Literal['unknown']


class AggregateView(Model):
    aggregate_ref: str
    subject_refs: list[str]
    rating: JsonValue
    scale: JsonValue
    published_count: JsonValue
    count_kind: Literal['ratings', 'reviews', 'unspecified']
    assertion_refs: list[str]


class OpinionValues(Model):
    groups: list[OpinionGroup]
    published_aggregates: list[AggregateView]


class QuestionResult(Model):
    question_id: Literal['price_range', 'visual_presentation', 'keywords', 'category_opinions']
    subject_ref: str | None = None
    status: Literal['answered', 'partial', 'not_answerable']
    values: PriceValues | VisualValues | KeywordValues | OpinionValues
    supporting_assertion_ids: list[str] = Field(default_factory=list)
    exclusions: list[dict[str, JsonValue]] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def typed_result(cls, data):
        if isinstance(data, dict):
            types = {'price_range': PriceValues, 'visual_presentation': VisualValues,
                     'keywords': KeywordValues, 'category_opinions': OpinionValues}
            expected = types.get(data.get('question_id'))
            if expected:
                data = dict(data)
                data['values'] = expected.model_validate(data.get('values'))
        return data


class ProductView(Model):
    entity_id: str
    identity_status: Literal['provisional', 'resolved', 'disputed']
    name: str | None
    brand: str | None
    description: str | None
    url: str | None
    sku: str | None
    gtin: str | None
    field_assertion_refs: dict[str, list[str]]
    category_refs: list[str]
    variant_refs: list[str]
    appearance_refs: list[str]


class CategoryView(Model):
    entity_id: str
    identity_status: Literal['provisional', 'resolved', 'disputed']
    name: str | None
    field_assertion_refs: dict[str, list[str]]


class ReadModel(Model):
    products: list[ProductView] = Field(default_factory=list)
    categories: list[CategoryView] = Field(default_factory=list)
    question_results: list[QuestionResult] = Field(default_factory=list)


class Knowledge(Model):
    entities: list[Entity]
    assertions: list[Assertion]


class Output(Model):
    contract_version: Literal['1.0'] = VERSION
    ontology_version: Literal['0.2'] = ONTOLOGY_VERSION
    processing_id: str
    result_revision: int = Field(default=1, ge=1)
    generated_at: str
    input_refs: list[str]
    scope: dict[str, JsonValue]
    processing_status: Literal['completed', 'completed_with_issues', 'failed']
    data: ReadModel
    knowledge: Knowledge
    evidence: list[Evidence]
    findings: list[Finding]
    issues: list[Issue]
    usage: list[dict[str, JsonValue]] = Field(default_factory=list)

    @classmethod
    def model_json_schema(cls, *args, **kwargs):
        schema = super().model_json_schema(*args, **kwargs)
        # Encode the same question/value pairing checked at runtime for external consumers.
        definition = schema.get('$defs', {}).get('QuestionResult')
        if definition:
            definition['allOf'] = [
                {'if': {'properties': {'question_id': {'const': question}}},
                 'then': {'properties': {'values': {'$ref': '#/$defs/' + value_type}}}}
                for question, value_type in [('price_range', 'PriceValues'), ('visual_presentation', 'VisualValues'),
                                             ('keywords', 'KeywordValues'), ('category_opinions', 'OpinionValues')]]
        return schema

    @model_validator(mode='after')
    def references(self):
        for label, records, key in [('entity', self.knowledge.entities, 'entity_id'),
                                     ('assertion', self.knowledge.assertions, 'assertion_id'),
                                     ('evidence', self.evidence, 'evidence_id')]:
            ids = [getattr(r, key) for r in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f'duplicate {label} identity')
        entities = {e.entity_id for e in self.knowledge.entities}
        evidence = {e.evidence_id for e in self.evidence}
        assertions = {a.assertion_id for a in self.knowledge.assertions}
        for entity in self.knowledge.entities:
            if not set(entity.origin_refs) <= evidence:
                raise ValueError('unresolved entity origin')
        for a in self.knowledge.assertions:
            if a.subject_ref not in entities or (a.object_ref and a.object_ref not in entities):
                raise ValueError('unresolved assertion entity')
            if not set(a.evidence_refs) <= evidence:
                raise ValueError('unresolved assertion evidence')
        for q in self.data.question_results:
            if q.subject_ref and q.subject_ref not in entities:
                raise ValueError('unresolved question subject')
            if not set(q.supporting_assertion_ids) <= assertions:
                raise ValueError('unresolved question assertion')
        def read_refs(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == 'entity_id' or key.endswith('_ref'):
                        if item is not None and item not in entities:
                            raise ValueError('unresolved read-model entity')
                    elif key == 'field_assertion_refs':
                        if any(not set(ids) <= assertions for ids in item.values()):
                            raise ValueError('unresolved field assertion')
                    elif key == 'assertion_refs':
                        if not set(item) <= assertions:
                            raise ValueError('unresolved read-model assertion')
                    elif key.endswith('_refs'):
                        if not set(item) <= entities:
                            raise ValueError('unresolved read-model entity list')
                    else:
                        read_refs(item)
            elif isinstance(value, list):
                for item in value:
                    read_refs(item)
        read_refs([p.model_dump() for p in self.data.products])
        read_refs([c.model_dump() for c in self.data.categories])
        for q in self.data.question_results:
            read_refs(q.values.model_dump())
        for f in self.findings:
            if f.subject_ref not in entities or not set(f.assertion_refs) <= assertions:
                raise ValueError('unresolved finding')
        for issue in self.issues:
            if issue.subject_ref and issue.subject_ref not in entities:
                raise ValueError('unresolved issue subject')
            if not set(issue.evidence_refs) <= evidence:
                raise ValueError('unresolved issue evidence')
        return self
