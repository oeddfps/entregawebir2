"""Explicit synthetic demonstration, never a source-specific extraction rule."""
from copy import deepcopy
import json
from pathlib import Path


def examples():
    template = json.loads((Path(__file__).resolve().parents[2] / 'clean_process/examples/input.json').read_text(encoding='utf-8'))
    results = []
    for index in range(2):
        payload = deepcopy(template)
        sample = payload['samples'][0]
        sample['sample_id'] = f'demonstration-{index}'
        sample['source_ref'] = f'document:demonstration-{index}'
        sample['context'] = {'synthetic': True}
        for unit in sample['content_units']:
            for datum in unit.get('fields', []):
                if unit['unit_id'] == 'product':
                    if datum['property'] == 'name':
                        datum['value'] = ['Hidratante diario · 50 ml', 'Gel hidratante · 50 ml'][index]
                    if datum['property'] == 'image':
                        datum['value']['url'] = f'/compare-assets/demo-{index}.svg'
                if datum['property'] == 'amount':
                    datum['value'] = str(float(datum['value']) + index * 3)
            if unit['unit_id'] == 'product':
                unit['fields'].extend([{'property': 'description', 'value': ['Hidratación diaria con una textura cremosa.', 'Una fórmula ligera para una rutina sencilla.'][index]},
                    {'property': 'rating', 'value': ['4.2', '4.6'][index]},
                    {'property': 'rating_scale', 'value': {'min': 0, 'max': 5}},
                    {'property': 'rating_count', 'value': ['84', '126'][index]},
                    {'property': 'count_kind', 'value': 'ratings'}])
        if index:
            review = next(u for u in sample['content_units'] if u['unit_id'] == 'review')
            review['text'] = 'It absorbs quickly.'
            review['fields'][0]['value'] = {'quote': review['text'], 'aspect': 'absorption', 'sentiment': 'favorable', 'material': False}
        results.append(payload)
    return results
