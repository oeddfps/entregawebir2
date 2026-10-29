import json
from pathlib import Path
from threading import Event
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from clean_process import Output, process
from clean_process.__main__ import write_json
from clean_process.presentation import present, compare
from src.comparison.api import router
from src.comparison.contracts import ComparisonRequest
from src.comparison.examples import examples
from src.comparison.service import ComparisonManager, TERMINAL


def wait(manager, identity, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = manager.get(identity)
        if data['status'] in TERMINAL:
            return data
        time.sleep(.03)
    pytest.fail('Comparison did not finish')


def request():
    return ComparisonRequest(sources=[{'url': 'https://one.example/catalog', 'label': 'One'},
                                      {'url': 'https://two.example/catalog', 'label': 'Two'}]).model_dump()


def fixture_output():
    return process(examples()[0])


def finish(folder, i):
    output = fixture_output()
    write_json(folder / str(i) / 'output.json', output.model_dump(mode='json'))
    write_json(folder / str(i) / 'presentation.json', present(output))


def test_projection_has_images_ratings_traceability_and_no_assumed_scale():
    output = fixture_output()
    projected = present(output)
    product = projected['products'][0]
    assert product['images'][0]['resources'][0].endswith('demo-0.svg')
    assert product['ratings'][0]['normalized_score'] == pytest.approx(.84)
    assert product['ratings'][0]['scale_group'] == '0.0:5.0'
    assert product['ratings'][0]['count_number'] == 84
    assert product['descriptions'][0]['assertion_refs']
    broken = output.model_dump(mode='json')
    broken['knowledge']['assertions'] = [a for a in broken['knowledge']['assertions'] if a['predicate'] != 'rating_scale']
    # Product projection in this fixture does not reference ratings, so removing
    # the assertion is a valid source without a known rating scale.
    unknown = present(broken)
    assert unknown['products'][0]['ratings'][0]['normalized_score'] is None


def test_comparison_does_not_claim_cross_source_product_equivalence():
    result = compare(process(examples()[0]), process(examples()[1]))
    assert result['product_equivalence'] == 'not_established'
    assert result['question_matrix']['price_range'] == ['answered', 'answered']


def test_two_captures_are_sequential_before_processing(tmp_path):
    calls = []
    def execute(folder, stage, index, spec, cancel, task):
        calls.append((stage, index))
        if stage == 'capture':
            write_json(folder / str(index) / 'capture.json', [{'placeholder': 'captured fixture'}])
        else:
            finish(folder, index)
        return 'done'
    manager = ComparisonManager(tmp_path, executor=execute)
    job = manager.create(request())
    data = wait(manager, job['comparison_id'])
    assert calls == [('capture', 0), ('capture', 1), ('process', 0), ('process', 1)]
    assert data['status'] == 'done'
    assert all(s['result_available'] for s in data['sources'])
    assert manager.result(job['comparison_id'], 0)['products']


@pytest.mark.parametrize('source_count,imported', [(1, False), (2, False), (2, True)])
def test_stage_timer_tracks_real_stage_source_and_confirmed_budget(tmp_path, source_count, imported):
    from datetime import datetime
    from src.comparison.contracts import ComparisonState
    observed = []
    manager = ComparisonManager(tmp_path)
    def execute(folder, stage, index, spec, cancel, task):
        state = manager.get(folder.name)
        timer = state['stage_timer']
        ComparisonState.model_validate(state)
        assert timer['action'] == stage and timer['source_index'] == index
        assert timer['limit_seconds'] == (37 if stage == 'capture' else 19)
        assert datetime.fromisoformat(timer['started_at']) <= datetime.fromisoformat(state['server_time'])
        assert state['phase'] == f'{stage}_{index}'
        assert manager.get(folder.name)['stage_timer'] == timer
        observed.append((stage, index, timer['started_at']))
        if stage == 'capture':
            write_json(folder / str(index) / 'capture.json', [])
        else:
            finish(folder, index)
        return 'done'
    manager.executor = execute
    spec = request()
    spec['sources'] = spec['sources'][:source_count]
    spec['limits'].update(capture_seconds=37, processing_seconds=19)
    identity = manager.create(spec, imported=examples() if imported else None)['comparison_id']
    state = wait(manager, identity)
    expected = ([] if imported else [('capture', i) for i in range(source_count)]) + [('process', i) for i in range(source_count)]
    assert [(stage, i) for stage, i, _ in observed] == expected
    assert len({start for _, _, start in observed}) == len(expected)
    assert state['status'] == 'done' and state['finished_at']
    assert ComparisonManager(tmp_path).get(identity)['stage_timer'] == state['stage_timer']
    manager.close()


@pytest.mark.parametrize('capture_reason,expected', [('done', 'done'), ('timeout', 'partial'), ('error', 'failed')])
def test_single_source_capture_and_real_processing(tmp_path, capture_reason, expected):
    calls = []
    manager = ComparisonManager(tmp_path)
    def execute(folder, stage, index, spec, cancel, task):
        calls.append((stage, index))
        if stage == 'capture':
            if capture_reason != 'error':
                write_json(folder / str(index) / 'capture.json', examples()[0])
            return capture_reason
        return manager._subprocess(folder, stage, index, spec, cancel, task)
    manager.executor = execute
    app = FastAPI()
    app.include_router(router(manager))
    spec = request()
    spec['sources'] = spec['sources'][:1]
    with TestClient(app) as client:
        response = client.post('/api/comparisons', json=spec)
        assert response.status_code == 202
        identity = response.json()['comparison_id']
        data = wait(manager, identity, timeout=30)
        assert data['status'] == expected
        assert len(data['sources']) == 1
        assert not (manager.folder(identity) / '1').exists()
        assert client.get(f'/api/comparisons/{identity}').status_code == 200
        assert client.get(f'/api/comparisons/{identity}/sources/1').status_code == 404
        assert client.post(f'/api/comparisons/{identity}/sources/1/evidence', json={'assertion_ids': []}).status_code == 404
        assert client.get(f'/api/comparisons/{identity}/sources/1/download/output').status_code == 404
        if capture_reason == 'error':
            assert calls == [('capture', 0)]
            assert data['sources'][0]['processing_status'] == 'skipped'
        else:
            assert calls == [('capture', 0), ('process', 0)]
            result = client.get(f'/api/comparisons/{identity}/sources/0').json()
            assert result['products'] and result['charts']
            refs = result['products'][0]['field_assertion_refs']['name']
            assert client.post(f'/api/comparisons/{identity}/sources/0/evidence', json={'assertion_ids': refs}).json()['evidence']
            assert client.get(f'/api/comparisons/{identity}/sources/0/download/output').status_code == 200
        assert len(ComparisonManager(tmp_path).get(identity)['sources']) == 1
    manager.close()


def test_single_source_cancellation_stops_before_processing(tmp_path):
    started = Event()
    calls = []
    def execute(folder, stage, index, spec, cancel, task):
        calls.append((stage, index))
        started.set()
        assert cancel.wait(3)
        return 'cancelled'
    manager = ComparisonManager(tmp_path, executor=execute)
    spec = request()
    spec['sources'] = spec['sources'][:1]
    job = manager.create(spec)
    assert started.wait(2)
    manager.cancel(job['comparison_id'])
    assert wait(manager, job['comparison_id'])['status'] == 'cancelled'
    assert calls == [('capture', 0)]
    manager.close()


def test_partial_source_is_preserved_and_second_source_still_runs(tmp_path):
    calls = []
    def execute(folder, stage, index, spec, cancel, task):
        calls.append((stage, index))
        if stage == 'capture':
            if index == 0:
                return 'error'
            write_json(folder / str(index) / 'capture.json', [])
        else:
            finish(folder, index)
        return 'done'
    manager = ComparisonManager(tmp_path, executor=execute)
    job = manager.create(request())
    data = wait(manager, job['comparison_id'])
    assert data['status'] == 'partial'
    assert data['sources'][1]['result_available']
    assert ('process', 0) not in calls


def test_timeout_processes_saved_capture_and_marks_partial(tmp_path):
    def execute(folder, stage, index, spec, cancel, task):
        if stage == 'capture':
            write_json(folder / str(index) / 'capture.json', [])
            return 'timeout' if index == 0 else 'done'
        finish(folder, index)
        return 'done'
    manager = ComparisonManager(tmp_path, executor=execute)
    data = wait(manager, manager.create(request())['comparison_id'])
    assert data['status'] == 'partial' and data['sources'][0]['stop_reason'] == 'timeout'
    assert all(s['result_available'] for s in data['sources'])


def test_cancellation_prevents_next_capture(tmp_path):
    started = Event()
    calls = []
    def execute(folder, stage, index, spec, cancel, task):
        calls.append((stage, index))
        started.set()
        assert cancel.wait(3)
        return 'cancelled'
    manager = ComparisonManager(tmp_path, executor=execute)
    job = manager.create(request())
    assert started.wait(2)
    manager.cancel(job['comparison_id'])
    data = wait(manager, job['comparison_id'])
    assert data['status'] == 'cancelled'
    assert calls == [('capture', 0)]
    manager.close()


def test_restart_retains_results_and_marks_detached_job_interrupted(tmp_path):
    manager = ComparisonManager(tmp_path, executor=lambda *args: 'error')
    job = manager.create(request())
    wait(manager, job['comparison_id'])
    manager.update(job['comparison_id'], status='running')
    other = ComparisonManager(tmp_path)
    assert other.get(job['comparison_id'])['status'] == 'interrupted'


def test_import_uses_real_isolated_clean_process_workers(tmp_path):
    manager = ComparisonManager(tmp_path)
    job = manager.create(request(), imported=examples())
    try:
        data = wait(manager, job['comparison_id'], timeout=90)
        assert data['status'] == 'done'
        assert all(s['capture_status'] == 'not_required' for s in data['sources'])
        assert manager.result(job['comparison_id'], 1)['charts']['rating_rows']
    finally:
        manager.close()


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'https://user:password@host.test/', 'not a url'])
def test_capture_contract_rejects_invalid_urls(url):
    with pytest.raises(ValueError):
        ComparisonRequest(sources=[{'url': url}, {'url': 'https://valid.test'}])


def test_api_validation_evidence_and_download_boundaries(tmp_path, monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.delenv('TYPESAFE_TEST_API_KEY', raising=False)
    def execute(folder, stage, index, spec, cancel, task):
        finish(folder, index)
        return 'done'
    manager = ComparisonManager(tmp_path, executor=execute)
    app = FastAPI()
    app.include_router(router(manager))
    with TestClient(app) as client:
        assert client.post('/api/comparisons', json={'sources': []}).status_code == 422
        invalid = request()
        invalid['interpreter'] = 'jev'
        assert client.post('/api/comparisons', json=invalid).status_code == 422
        assert client.post('/api/comparisons/import', json={'sources': [{'payload': {}}, {'payload': {}}]}).status_code == 422
        response = client.post('/api/comparisons/import', json={'sources': [
            {'payload': examples()[0], 'label': 'A'}, {'payload': fixture_output().model_dump(mode='json'), 'label': 'B'}]})
        assert response.status_code == 202
        identity = response.json()['comparison_id']
        wait(manager, identity)
        result = client.get(f'/api/comparisons/{identity}/sources/0').json()
        refs = result['products'][0]['field_assertion_refs']['name']
        evidence = client.post(f'/api/comparisons/{identity}/sources/0/evidence', json={'assertion_ids': refs})
        assert evidence.status_code == 200 and evidence.json()['evidence']
        assert client.get(f'/api/comparisons/{identity}/sources/0/download/output').status_code == 200
        assert client.get(f'/api/comparisons/{identity}/sources/3').status_code == 404
        assert client.get(f'/api/comparisons/{identity}/sources/0/download/request').status_code == 404
        assert client.get('/api/comparisons/not-an-id').status_code == 404
        assert client.get('/api/comparisons').json()['items']
    manager.close()


def test_capture_can_delegate_interpretation_without_calling_a_model(monkeypatch):
    from src.common.scrapper import PageCapture, SemanticMetadataStrategy
    from src.common.scrapper.strategies import semantic, semantic_fields
    capture = PageCapture('https://neutral.example/', 'https://neutral.example/', 'Sample', '<main><h1>Sample</h1><p>Content.</p></main>')
    monkeypatch.setattr(semantic, 'observe_navigation', lambda *a, **k: ([capture], [], {}))
    def forbidden(*a, **k):
        pytest.fail('Capture must delegate interpretation to Clean&Process')
    monkeypatch.setattr(semantic_fields, 'enrich_fields', forbidden)
    class API:
        def __init__(self):
            self.capture = capture
            self.events = []
        def report_expense(self, value):
            pass
        def emit_content(self, value):
            self.events.append(value)
    api = API()
    SemanticMetadataStrategy(follow_navigation=False, interpret_fields=False).process(None, api)
    analysis = api.events[0]
    assert analysis.result.classification['coverage']['field_interpretation']['enabled'] is False


def test_scraper_published_review_counts_survive_adapter_and_projection():
    from src.integrations.clean_process import from_scraper
    parts = [{'class': key, 'values': [{'text': value}]} for key, value in [
        ('name', 'Neutral product'), ('rating', '4.7'), ('review_count', '285')]]
    output = process(from_scraper([{'url': 'https://neutral.example/', 'result': {'entities': [
        {'role': 'product', 'attributes': {'source': 'jsonld'}, 'parts': parts}]}}]))
    view = present(output)
    row = view['charts']['published_count_rows'][0]
    assert row['count_number'] == 285 and row['count_kind'] == 'reviews'
    assert row['normalized_score'] is None  # No fabricated five-point scale.


def test_time_only_contract_and_unbounded_traversal(tmp_path):
    from contextlib import contextmanager
    from src.common.scrapper import PageCapture, Scrapper, ScrapperConfig, SemanticMetadataStrategy
    parsed = ComparisonRequest(sources=[{'url': 'https://one.example/'}, {'url': 'https://two.example/'}],
        limits={'max_pages': None, 'max_hops': None, 'capture_seconds': 300, 'same_host_only': False})
    assert parsed.limits.max_pages is None and parsed.limits.max_hops is None
    visited = []
    @contextmanager
    def loader(url):
        visited.append(url)
        index = int(url.rsplit('/', 1)[-1])
        link = f'<a href="https://other.example/{index+1}">Next</a>' if index < 3 else ''
        yield PageCapture(url, url, 'Page', f'<main><h1>Page {index}</h1>{link}</main>')
    scraper = Scrapper(ScrapperConfig(max_sites=None, max_hops=None, max_threads=1,
        page_loader=loader, strategy=SemanticMetadataStrategy(interpret_fields=False), audit_dir=tmp_path))
    summary = scraper.run(['https://first.example/0'])
    assert summary.succeeded == 4 and len(visited) == 4
