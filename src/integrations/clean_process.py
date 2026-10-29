"""Translate historical scraper exports to Clean&Process contract 1.0.

This adapter owns legacy role/part knowledge. The clean_process package never
imports it. Original blocks and their JSON pointers are retained as evidence.
"""
from clean_process.contracts import Input, Sample, Unit, Datum, Relation
from clean_process.ontology import identifier


FIELD_MAP = {'product_link': 'url', 'rating_count': 'rating_count', 'review_count': 'rating_count',
             'price': 'amount', 'previous_price': 'amount', 'review_title': 'name'}
KNOWN = {'name', 'description', 'brand', 'sku', 'gtin', 'size', 'quantity', 'rating',
         'review_body', 'author', 'date', 'image', 'url', 'rating_scale', 'rating_count', 'currency'}


def from_scraper(payload, *, export_ref='scraper-export'):
    if isinstance(payload, dict) and 'visits' in payload:
        pages = [{'url': v.get('final_uri') or v.get('requested_uri'), 'result': v.get('result')}
                 for v in payload['visits']]
    elif isinstance(payload, dict) and 'result' in payload:
        pages = [payload]
    elif isinstance(payload, list):
        pages = payload
    else:
        raise ValueError('Expected a scraper page list or an audit export with visits')
    samples = []
    for page_index, page in enumerate(pages):
        if not isinstance(page, dict) or not isinstance(page.get('result'), dict):
            raise ValueError('Scraper page must include its full result; do not silently drop failed pages')
        result = page['result']
        if not isinstance(result.get('entities'), list):
            raise ValueError('Scraper result.entities must be a list')
        url = page.get('url')
        if not isinstance(url, str) or not url:
            raise ValueError('Scraper page requires a URL')
        page_id = 'page'
        units = [Unit(unit_id=page_id, classification='Pagina', fields=[Datum(property='url', value=url)])]
        relations = []
        collection_ids = []
        member_ids = []
        product_records = []
        aggregates = []
        texts = []
        for index, entity in enumerate(result['entities']):
            if not isinstance(entity, dict):
                raise ValueError('Scraper entities must be objects')
            uid = f'block-{index}'
            attrs = entity.get('attributes') or {}
            source = attrs.get('source')
            method = 'source_declaration' if source in ('jsonld', 'head') else 'interpretation'
            fields, name, destination = [], None, None
            raw_fields = {}
            for pi, part in enumerate(entity.get('parts') or []):
                prop = FIELD_MAP.get(part.get('class'), part.get('class'))
                if prop not in KNOWN and prop != 'amount':
                    for vi, raw_value in enumerate(part.get('values') or []):
                        raw = raw_value.get('text', raw_value) if isinstance(raw_value, dict) else raw_value
                        fields.append(Datum(property='raw_field', value={'name': part.get('class') or '',
                            'label': part.get('label') or part.get('name') or (raw_value.get('property') if isinstance(raw_value, dict) else '') or '', 'value': raw},
                            locator={'json_pointer': f'/pages/{page_index}/result/entities/{index}/parts/{pi}/values/{vi}',
                                     'original_value': raw_value}, method=method))
                    continue
                for vi, value in enumerate(part.get('values') or []):
                    raw = value.get('href') if prop == 'url' else value.get('src') if prop == 'image' else value.get('text')
                    if raw is None:
                        raw = value.get('text')
                    if raw is None:
                        continue
                    raw_fields.setdefault(prop, []).append(raw)
                    fields.append(Datum(property=prop, value=raw, method=method,
                        locator={'json_pointer': f'/pages/{page_index}/result/entities/{index}/parts/{pi}/values/{vi}',
                                 'original_value': value}))
                    if part.get('class') in ('review_count', 'rating_count'):
                        fields.append(Datum(property='count_kind', method=method,
                            value='reviews' if part['class'] == 'review_count' else 'ratings',
                            locator={'source_property': part['class']}))
                    if prop == 'name' and name is None:
                        name = str(raw)
                    if prop == 'url' and destination is None:
                        destination = str(raw)
            # Preserve explicit scale bounds from standardized nested declarations.
            declared = attrs.get('declared')
            if isinstance(declared, dict):
                for obj in [declared, declared.get('aggregateRating'), declared.get('reviewRating')]:
                    if not isinstance(obj, dict):
                        continue
                    for bound in ('bestRating', 'worstRating'):
                        if bound in obj:
                            fields.append(Datum(property='raw_field', value={'name': bound, 'value': obj[bound]},
                                method='source_declaration', locator={'declared_property': bound,
                                    'original_value': obj[bound]}))
            role = entity.get('role')
            kind = {'semantic_collection': 'Coleccion', 'product': 'Producto'}.get(role, 'Texto')
            if role == 'semantic_item' and name and destination:
                # Reuse explicit producer field meaning; do not infer products from CSS or brand text.
                kind = 'Producto'
            if role == 'reviews':
                kind = 'Resena' if raw_fields.get('review_body') else 'ValoracionAgregada'
            unit = Unit(unit_id=uid, text=entity.get('text') or '', classification=kind,
                classification_method=method, fields=fields,
                locator={'export_ref': export_ref, 'page_index': page_index, 'block_index': index,
                         'selector': entity.get('selector'), 'original_block': entity})
            units.append(unit)
            relations.append(Relation(subject_unit=page_id, predicate='contains', object_unit=uid, method='observation'))
            if kind == 'Coleccion':
                collection_ids.append(uid)
            if kind == 'Producto':
                appearance = uid + '-appearance'
                units.append(Unit(unit_id=appearance, classification='Aparicion', classification_method='observation',
                                  locator={'export_ref': export_ref, 'block_index': index}))
                relations.append(Relation(subject_unit=appearance, predicate='represents', object_unit=uid, method=method))
                product_records.append((uid, raw_fields))
                if role == 'semantic_item':
                    member_ids.append(appearance)
            if kind == 'ValoracionAgregada':
                aggregates.append((uid, raw_fields))
            if kind == 'Texto':
                texts.append((uid, entity))
        # Membership is asserted only with one collection, not for every nearby list.
        if len(collection_ids) == 1:
            for member in member_ids:
                relations.append(Relation(subject_unit=collection_ids[0], predicate='member', object_unit=member, method='interpretation'))
        for uid, aggregate in aggregates:
            matches = [pid for pid, f in product_records if aggregate.get('rating') and
                       aggregate.get('rating_count') and aggregate.get('rating') == f.get('rating') and
                       aggregate.get('rating_count') == f.get('rating_count')]
            if len(matches) == 1:
                relations.append(Relation(subject_unit=uid, predicate='summarizes', object_unit=matches[0], method='interpretation'))
        # Relate duplicate article/card descriptions by exact shared field evidence,
        # never by fuzzy product names alone.
        by_name_selector = {}
        for index, entity in enumerate(result['entities']):
            if any(pid == f'block-{index}' for pid, _ in product_records):
                for part in entity.get('parts') or []:
                    if part.get('class') == 'name':
                        for value in part.get('values') or []:
                            if value.get('selector'):
                                by_name_selector.setdefault(value['selector'], set()).add(f'block-{index}')
        for uid, entity in texts:
            matches = set()
            for part in entity.get('parts') or []:
                if part.get('class') == 'name':
                    for value in part.get('values') or []:
                        matches.update(by_name_selector.get(value.get('selector'), set()))
            if len(matches) == 1:
                relations.append(Relation(subject_unit=uid, predicate='mentions', object_unit=next(iter(matches)), method='interpretation'))
        samples.append(Sample(sample_id=identifier('sample', export_ref, page_index, url), source_ref=url,
            content_units=units, relations=relations, context={'export_ref': export_ref, 'page_index': page_index, 'keyword_corpus_ref': export_ref},
            coverage={'producer': 'historical_scraper', 'field_interpretation':
                      (result.get('classification') or {}).get('coverage', {}).get('field_interpretation', {})}))
    return Input(samples=samples)


def main():
    import argparse
    import json
    from pathlib import Path
    from clean_process.__main__ import write_json
    parser = argparse.ArgumentParser(description='Adapt a historical scraper export to Clean&Process input')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('output must not overwrite source evidence')
    payload = json.loads(args.input.read_text(encoding='utf-8-sig'))
    request = from_scraper(payload, export_ref=args.input.name)
    write_json(args.output, request.model_dump(mode='json'))


if __name__ == '__main__':
    main()
