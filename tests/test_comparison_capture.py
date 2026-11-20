"""Capture through the real worker and browser, using source-neutral local pages."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

import pytest

from src.comparison.contracts import ComparisonRequest, ComparisonState
from src.comparison.diagnostics import stage_diagnostic
from src.comparison.service import ComparisonManager
from tests.test_comparison import wait


@pytest.fixture
def pages():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/missing'):
                self.send_error(404)
                return
            name = 'Sample One' if self.path.startswith('/one') else 'Sample Two'
            product = {'@context': 'https://schema.org', '@type': 'Product', 'name': name,
                       'description': 'A neutral fixture product.', 'offers': {
                           '@type': 'Offer', 'price': '17.00', 'priceCurrency': 'EUR'}}
            body = ('<html><head><title>' + name + '</title><script type="application/ld+json">'
                    + json.dumps(product) + '</script></head><body><main><h1>' + name
                    + '</h1><p>A neutral fixture product.</p></main></body></html>').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize('first_path,expected', [('/one?variant=1', 'done'), ('/missing', 'partial')])
def test_two_urls_real_capture_processing_and_source_failure(pages, tmp_path, first_path, expected):
    manager = ComparisonManager(tmp_path / 'comparisons')
    spec = ComparisonRequest(sources=[{'url': pages + first_path}, {'url': pages + '/two'}],
        interpreter='declared', review_recognition='off', limits={
            'max_pages': 1, 'max_hops': 0, 'capture_seconds': 45, 'processing_seconds': 30}).model_dump()
    try:
        state = wait(manager, manager.create(spec)['comparison_id'], timeout=170)
        ComparisonState.model_validate(state)
        assert state['status'] == expected
        assert manager.result(state['comparison_id'], 1)['products'][0]['name'] == 'Sample Two'
        if expected == 'done':
            assert manager.result(state['comparison_id'], 0)['products'][0]['name'] == 'Sample One'
            assert all(source['result_available'] and not source['diagnostics'] for source in state['sources'])
        else:
            assert state['sources'][0]['processing_status'] == 'skipped'
            diagnostic = state['sources'][0]['diagnostics'][0]
            assert diagnostic['code'] == 'http_error' and diagnostic['http_status'] == 404
            assert 'HTTP 404' in diagnostic['message']
            assert not state['sources'][1]['diagnostics']
    finally:
        manager.close()


@pytest.mark.parametrize('detail,code', [
    ('Page.goto: net::ERR_NETWORK_ACCESS_DENIED at https://example.org?token=private-value', 'network_access_denied'),
    ('Page.goto: net::ERR_NAME_NOT_RESOLVED', 'dns_error'),
    ('Page.goto: net::ERR_CERT_AUTHORITY_INVALID', 'certificate_error'),
    ('Page.goto: net::ERR_CONNECTION_REFUSED', 'connection_error'),
    ('Page.goto: Timeout 30000ms exceeded', 'navigation_timeout'),
    ("BrowserType.launch: Executable doesn't exist at private-path", 'browser_unavailable'),
])
def test_diagnostics_preserve_cause_without_exposing_raw_details(tmp_path, detail, code):
    diagnostic = stage_diagnostic(tmp_path, 'capture', 'error', RuntimeError(detail))
    assert diagnostic['code'] == code
    assert 'private-value' not in diagnostic['message'] and 'private-path' not in diagnostic['message']


def test_legacy_capture_failure_gets_diagnostics_from_saved_audit(tmp_path):
    from src.common.scrapper import AuditStore
    audit = AuditStore(tmp_path / 'audit')
    run = audit.start_run({})
    visit = audit.start_visit(run, 'https://example.org', 'https://example.org', 0, None, None, '')
    audit.fail_visit(visit, 'Error: Page.goto: net::ERR_NETWORK_ACCESS_DENIED')
    diagnostic = stage_diagnostic(tmp_path, 'capture', 'error')
    assert diagnostic['code'] == 'network_access_denied'
