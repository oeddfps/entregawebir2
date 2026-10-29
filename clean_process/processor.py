"""Evidence-backed processing. All I/O and model access are injected or in the CLI."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from uuid import uuid4

from .contracts import (Input, Output, Entity, Evidence, Assertion, Issue, Finding,
                        Knowledge, ReadModel, Unit)
from .ontology import PROPERTIES, RELATIONS, canonical_url, identifier, normalized


class Workspace:
    def __init__(self, request):
        self.request = request
        self.entities = {}
        self.assertions = []
        self.evidence = {}
        self.issues = []
        self.findings = []
        self.units = {}
        self.subjects = {}
        self.identities = {}
        self.names = defaultdict(set)

    def issue(self, code, message, subject=None, refs=(), **details):
        self.issues.append(Issue(issue_id=identifier('issue', code, subject, list(refs), details),
                                 code=code, message=message, subject_ref=subject,
                                 evidence_refs=list(refs), details=details))

    def entity(self, kind, key, evidence_ref):
        eid = identifier('entity', kind, key)
        if eid not in self.entities:
            self.entities[eid] = Entity(entity_id=eid, kind=kind, origin_refs=[evidence_ref])
        elif evidence_ref not in self.entities[eid].origin_refs:
            self.entities[eid].origin_refs.append(evidence_ref)
        return eid

    def assert_(self, subject, predicate, *, value=None, target=None, method='observation',
                refs, scope=None, justification='Explicitly supported by the supplied source'):
        aid = identifier('assertion', subject, predicate, value, target, method, refs, scope)
        previous = next((a for a in self.assertions if a.assertion_id == aid), None)
        if previous:
            return previous
        a = Assertion(assertion_id=aid, subject_ref=subject, predicate=predicate,
                      value=value, object_ref=target, method=method, evidence_refs=list(refs),
                      scope=scope or {}, justification=justification)
        self.assertions.append(a)
        return a

    def values(self, subject, predicate):
        return [a for a in self.assertions if a.subject_ref == subject and
                a.predicate == predicate and a.status == 'accepted']

    def targets(self, subject, predicate):
        return list(dict.fromkeys(a.object_ref for a in self.values(subject, predicate) if a.object_ref))

    def value(self, subject, predicate, default=None):
        values = self.values(subject, predicate)
        return values[0].value if values else default

    def product_for(self, subject):
        if self.entities[subject].kind == 'Producto':
            return [subject]
        if self.entities[subject].kind == 'Variante':
            return list(dict.fromkeys(a.subject_ref for a in self.assertions if
                        a.predicate == 'has_variant' and a.object_ref == subject and a.status == 'accepted'))
        return []

    def ingest(self, sample, unit, original=None):
        ref = identifier('evidence', sample.sample_id, unit.unit_id)
        original = original or unit
        self.evidence[ref] = Evidence(evidence_id=ref, sample_id=sample.sample_id,
            unit_id=unit.unit_id, source_ref=sample.source_ref, text=original.text,
            resource_ref=original.resource_ref, fields=original.fields, locator=original.locator)
        self.units[ref] = unit
        kind = unit.classification
        fields = defaultdict(list)
        for field in unit.fields:
            fields[field.property].append(field.value)
        # Only compatible, explicitly attributed identities may be associated.
        # A name, SKU or URL alone never establishes product identity.
        key = (sample.sample_id, unit.unit_id)
        name = next((v for v in fields['name'] if isinstance(v, str) and v.strip()), '')
        url = next((canonical_url(v) for v in fields['url'] if isinstance(v, str) and canonical_url(v)), None)
        if kind == 'Producto' and name and url:
            identity = (url, normalized(name).casefold())
            candidates = self.identities.get(identity, [])
            incoming = {prop: set(map(str, fields[prop])) for prop in ('sku', 'gtin')}
            compatible_candidates = [candidate for candidate in candidates if all(
                not incoming[prop] or not self.values(candidate, prop) or
                incoming[prop] == {str(a.value) for a in self.values(candidate, prop)} for prop in incoming)]
            existing = compatible_candidates[0] if len(compatible_candidates) == 1 else None
            compatible = existing is not None
            if compatible:
                key = self.entities[existing].entity_id
            elif candidates:
                self.issue('identity_conflict', 'Same destination and name have incompatible identifiers',
                           candidates[0], [ref])
            else:
                key = identity
            if compatible:
                subject = existing
                self.entities[subject].origin_refs.append(ref)
            else:
                subject = self.entity(kind, key, ref)
                self.identities.setdefault(identity, []).append(subject)
            self.names[normalized(name).casefold()].add(subject)
        elif kind == 'Resena' and fields['review_identity']:
            identity = fields['review_identity'][0]
            # Explicit namespace/id plus identical body: text alone never deduplicates reviews.
            body = unit.text or next((v for v in fields['review_body'] if isinstance(v, str)), '')
            if isinstance(identity, dict) and identity.get('namespace') and identity.get('id') and body:
                key = (identity['namespace'], identity['id'], normalized(body))
            subject = self.entity(kind, key, ref)
        else:
            subject = self.entity(kind, key, ref)
        self.subjects[(sample.sample_id, unit.unit_id)] = subject
        scope = {'sample_id': sample.sample_id, 'source_ref': sample.source_ref,
                 'voice': unit.voice, 'language': unit.language, 'observed_at': sample.observed_at}
        self.assert_(subject, 'type', value=kind, method=unit.classification_method,
                     refs=[ref], scope=scope, justification='Classification supplied or interpreted; evidence is retained')
        for field in unit.fields:
            if field.property == 'raw_field':
                continue  # Retained in evidence; recognition is a separate, explicit stage.
            if field.property not in PROPERTIES or field.property == 'other':
                self.issue('unsupported_property', 'Unmapped property retained in evidence', subject,
                           [ref], property=field.property)
                continue
            invalid = False
            if field.property in ('name', 'description', 'brand', 'sku', 'gtin', 'currency', 'seller', 'review_body', 'author'):
                invalid = not isinstance(field.value, str) or not field.value.strip()
            elif field.property == 'url':
                invalid = not isinstance(field.value, str) or not canonical_url(field.value)
            elif field.property in ('keyword', 'topic', 'aspect_opinion'):
                invalid = not isinstance(field.value, dict)
                if field.property == 'aspect_opinion' and isinstance(field.value, dict):
                    invalid = (field.value.get('sentiment') not in ('favorable', 'unfavorable', 'mixed', 'neutral', 'indeterminate') or
                        not isinstance(field.value.get('aspect'), str) or not field.value['aspect'].strip() or
                        ('material' in field.value and type(field.value['material']) is not bool))
            elif field.property == 'visibility':
                invalid = field.value not in ('visible', 'hidden', 'unknown')
            elif field.property == 'order':
                invalid = type(field.value) is not int or field.value < 0
            elif field.property == 'count_kind':
                invalid = field.value not in ('ratings', 'reviews', 'unspecified')
            if invalid:
                self.issue('invalid_property_value', 'Value retained as evidence, not accepted as a typed assertion',
                           subject, [ref], property=field.property)
                continue
            if field.property in ('keyword', 'topic', 'aspect_opinion') and isinstance(field.value, dict):
                quote = field.value.get('quote')
                if not isinstance(quote, str) or not quote or quote not in unit.text:
                    self.issue('unsupported_quote', 'Semantic interpretation requires an exact source quote', subject, [ref])
                    continue
            self.assert_(subject, field.property, value=field.value, method=field.method,
                         refs=[ref], scope={**scope, 'value_locator': field.locator})
        if kind == 'other' and unit.text:
            self.issue('uninterpreted_content', 'Content retained without a supported classification', subject, [ref])
        if unit.modality == 'image' and kind == 'other':
            self.issue('visual_interpretation_unavailable', 'Image resource retained; no visual meaning inferred', subject, [ref])
        if kind == 'Producto':
            explicit = [r.subject_unit for r in sample.relations if r.predicate == 'represents' and r.object_unit == unit.unit_id]
            if len(explicit) == 1:
                appearance_ref = identifier('evidence', sample.sample_id, explicit[0])
                appearance = self.entity('Aparicion', (sample.sample_id, explicit[0]), appearance_ref)
            else:
                appearance = self.entity('Aparicion', (sample.sample_id, unit.unit_id, 'appearance'), ref)
            self.assert_(appearance, 'represents', target=subject, refs=[ref], scope=scope)
            for position, image in enumerate(fields['image']):
                image_ref = image.get('url') if isinstance(image, dict) else image
                if not isinstance(image_ref, str) or not image_ref:
                    continue
                image_id = self.entity('Imagen', image_ref, ref)
                self.assert_(image_id, 'url', value=image_ref, refs=[ref], scope=scope)
                usage = self.entity('UsoDeImagen', (sample.sample_id, unit.unit_id, position), ref)
                self.assert_(appearance, 'presents', target=usage, refs=[ref], scope=scope)
                self.assert_(usage, 'uses', target=image_id, refs=[ref], scope=scope)
                # List order, visibility and image function are NOT guessed from field order or alt.
                if isinstance(image, dict):
                    for prop in ('order', 'context', 'visibility', 'function'):
                        if prop in image:
                            if prop == 'function':
                                self.issue('visual_function_unverified', 'Supplied image function needs visual evidence', usage, [ref])
                                continue
                            if (prop == 'order' and (type(image[prop]) is not int or image[prop] < 0)) or (
                                    prop == 'visibility' and image[prop] not in ('visible', 'hidden', 'unknown')):
                                self.issue('invalid_image_metadata', 'Image metadata retained but not projected', usage, [ref], property=prop)
                                continue
                            self.assert_(usage, prop, value=image[prop], refs=[ref], scope=scope)
        return subject

    def relations(self, sample):
        for relation in sample.relations:
            subject = self.subjects[(sample.sample_id, relation.subject_unit)]
            target = self.subjects[(sample.sample_id, relation.object_unit)]
            sk, tk = self.entities[subject].kind, self.entities[target].kind
            allowed_subjects, allowed_objects = RELATIONS[relation.predicate]
            refs = [identifier('evidence', sample.sample_id, relation.subject_unit),
                    identifier('evidence', sample.sample_id, relation.object_unit)]
            if sk not in allowed_subjects or (allowed_objects and tk not in allowed_objects):
                self.issue('incompatible_relation', 'Relation contradicts ontology classes', subject,
                           refs, predicate=relation.predicate, object_ref=target)
                continue
            self.assert_(subject, relation.predicate, target=target, method=relation.method,
                         refs=refs, scope={'sample_id': sample.sample_id, 'source_ref': sample.source_ref})

    def conflicts(self):
        scalar = {'amount', 'currency', 'price_kind', 'seller', 'conditions', 'valid_period',
                  'sku', 'gtin', 'rating', 'rating_scale', 'rating_count', 'count_kind', 'size', 'quantity'}
        groups = defaultdict(list)
        for a in self.assertions:
            if a.predicate in scalar:
                groups[(a.subject_ref, a.predicate, a.scope.get('sample_id'))].append(a)
        for (subject, predicate, _), assertions in groups.items():
            if len({json.dumps(a.value, sort_keys=True, ensure_ascii=False) for a in assertions}) > 1:
                for a in assertions:
                    a.status = 'conflict'
                    a.decision_history.append({'from': 'accepted', 'to': 'conflict', 'reason': 'incompatible_scalar_values'})
                self.issue('conflicting_values', 'Incompatible values within the same source sample', subject,
                           list(dict.fromkeys(e for a in assertions for e in a.evidence_refs)), property=predicate,
                           assertion_refs=[a.assertion_id for a in assertions])

    def read_model(self):
        products, categories = [], []
        for entity in self.entities.values():
            eid = entity.entity_id
            if entity.kind not in ('Producto', 'Categoria'):
                continue
            fields = ('name', 'brand', 'description', 'url', 'sku', 'gtin')
            row = {'entity_id': eid, 'identity_status': entity.identity_status,
                   **{p: self.value(eid, p) for p in fields},
                   'field_assertion_refs': {p: [a.assertion_id for a in self.values(eid, p)] for p in fields}}
            if entity.kind == 'Producto':
                row.update(category_refs=self.targets(eid, 'belongs_to'), variant_refs=self.targets(eid, 'has_variant'),
                           appearance_refs=list(dict.fromkeys(a.subject_ref for a in self.assertions if
                               a.predicate == 'represents' and a.object_ref == eid and a.status == 'accepted')))
                products.append(row)
            else:
                categories.append({'entity_id': eid, 'identity_status': entity.identity_status,
                    'name': self.value(eid, 'name'),
                    'field_assertion_refs': {'name': [a.assertion_id for a in self.values(eid, 'name')]}})
        return ReadModel(products=products, categories=categories)


def process(payload: Input | dict, *, interpreter=None, review_recognizer=None) -> Output:
    """Run synchronously without fetching sources or starting the scraper.

    No interpreter means declared/previously interpreted data only. Unknown text
    remains unresolved instead of being classified through site-specific heuristics.
    """
    request = Input.model_validate(payload)
    work = Workspace(request)
    usage = []
    active_samples = [s for s in request.samples if
        ('source_refs' not in request.scope or s.source_ref in request.scope['source_refs']) and
        ('sample_refs' not in request.scope or s.sample_id in request.scope['sample_refs'])]
    if not active_samples:
        work.issue('empty_scope', 'No supplied samples match the requested scope')
    for sample in active_samples:
        units = {u.unit_id: u for u in sample.content_units}
        if interpreter is not None:
            try:
                interpretation = interpreter.interpret(sample.model_copy(deep=True), list(request.questions))
                for unit in interpretation.units:
                    original = units.get(unit.unit_id)
                    if original is None:
                        raise ValueError('Interpreter returned an unknown unit')
                    # A provider cannot rewrite original text, resources or source fields.
                    if unit.text != original.text or unit.resource_ref != original.resource_ref:
                        raise ValueError('Interpreter attempted to alter source evidence')
                    if (unit.voice != original.voice or unit.modality != original.modality or
                            unit.locator != original.locator or unit.fields[:len(original.fields)] != original.fields or
                            len(unit.fields) < len(original.fields)):
                        raise ValueError('Interpreter attempted to rewrite source metadata')
                    if original.classification != 'other' and unit.classification != original.classification:
                        raise ValueError('Interpreter attempted to replace an explicit classification')
                    for added in unit.fields[len(original.fields):]:
                        start, end = added.locator.get('start'), added.locator.get('end')
                        if added.method != 'interpretation' or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(original.text):
                            raise ValueError('Interpretation must point to an exact source span')
                        quote = added.value.get('quote') if isinstance(added.value, dict) else added.value
                        if quote != original.text[start:end]:
                            raise ValueError('Interpretation invented or changed a quote')
                units.update({u.unit_id: u for u in interpretation.units})
                for code, message, details in interpretation.issues:
                    work.issue(code, message, **details)
            except Exception:
                # Never include credentials or raw provider exceptions in the output.
                work.issue('interpreter_failure', 'Interpretation failed; source data retained', sample_id=sample.sample_id)
            usage = list(interpreter.usage)
        decisions, metrics = [], None
        if review_recognizer is not None:
            try:
                recognized, decisions, metrics = review_recognizer.recognize(
                    sample.model_copy(update={'content_units': list(units.values())}))
                units = {u.unit_id: u for u in recognized}
            except Exception:
                work.issue('review_recognition_failure', 'Review recognition failed; original source data retained',
                           sample_id=sample.sample_id)
        originals = {u.unit_id: u for u in sample.content_units}
        for unit in units.values():
            work.ingest(sample, unit, originals[unit.unit_id])
        for decision in decisions:
            uid = decision['unit_id']
            subject = work.subjects[(sample.sample_id, uid)]
            ref = identifier('evidence', sample.sample_id, uid)
            work.issue('review_recognition_decision', 'Review candidate evaluated with vocabulary and context',
                       subject, [ref], source_url=sample.source_ref, **decision)
        if metrics is not None:
            work.issue('review_recognition_summary', 'Review recognition coverage and model information',
                       sample_id=sample.sample_id, **metrics)
        work.relations(sample)
        if sample.coverage:
            work.issue('source_coverage', 'Source supplied coverage information', sample_id=sample.sample_id,
                       coverage=sample.coverage)
    work.conflicts()
    from .aggregates import question_results
    read_model = work.read_model()
    read_model.question_results = question_results(work)
    for question in read_model.question_results:
        if question.status == 'not_answerable':
            work.issue('not_found_in_scope', 'No eligible evidence for this question in the supplied scope',
                       question.subject_ref, question_id=question.question_id)
    return Output(processing_id=str(uuid4()), generated_at=datetime.now(timezone.utc).isoformat(),
                  input_refs=[s.sample_id for s in active_samples], scope=request.scope,
                  processing_status='completed_with_issues' if work.issues else 'completed',
                  data=read_model, knowledge=Knowledge(entities=list(work.entities.values()), assertions=work.assertions),
                  evidence=list(work.evidence.values()), findings=work.findings, issues=work.issues, usage=usage)
