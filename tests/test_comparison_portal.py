"""Exported comparison UI against an isolated real API, without external calls."""
from pathlib import Path
import json
import re
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from clean_process import process
from clean_process.__main__ import write_json
from clean_process.presentation import present
from src.comparison.api import router
from src.comparison.examples import examples
from src.comparison.service import ComparisonManager
from src.common import semantic_model
from src.server.credentials import router as credentials_router

WEB = Path(__file__).resolve().parents[1] / 'src/web/out'


@pytest.fixture
def comparison_portal(tmp_path, monkeypatch):
    monkeypatch.setattr(semantic_model, 'SAVED_KEY_FILE', tmp_path / 'secrets/jev.json')
    monkeypatch.setattr(semantic_model, 'ENV_FILE', tmp_path / '.env')
    for name in ('TYPESAFE_API_KEY', 'TYPESAFE_TEST_API_KEY', 'TYPESAFE_TEST_MODE'):
        monkeypatch.delenv(name, raising=False)
    if not (WEB / 'compare/index.html').exists():
        pytest.fail('Build the Next portal before running comparison browser tests')
    output = process(examples()[0]).model_dump(mode='json')
    presentation = present(output)
    stages, requests, errors = [], [], []

    def execute(folder, stage, index, spec, cancel, task):
        stages.append((stage, index, spec))
        if stage == 'capture':
            write_json(folder / str(index) / 'capture.json', [])
        else:
            write_json(folder / str(index) / 'output.json', output)
            write_json(folder / str(index) / 'presentation.json', presentation)
        return 'done'

    manager = ComparisonManager(tmp_path / 'jobs', executor=execute)
    app = FastAPI()
    app.include_router(router(manager))
    app.include_router(credentials_router)
    try:
        with TestClient(app) as client, sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))

            def serve(route):
                parsed = urlsplit(route.request.url)
                if parsed.path.startswith('/api/'):
                    requests.append((route.request.method, parsed.path))
                    response = client.request(route.request.method, parsed.path,
                        content=route.request.post_data,
                        headers={key: value for key, value in route.request.headers.items()
                                 if key in ('content-type', 'x-jev-configuration', 'sec-fetch-site')})
                    route.fulfill(status=response.status_code, body=response.content,
                                  content_type='application/json')
                    return
                relative = 'index.html' if parsed.path == '/' else 'compare/index.html' if parsed.path in ('/compare', '/compare/') else parsed.path.lstrip('/')
                file = (WEB / relative).resolve()
                if file.is_relative_to(WEB.resolve()) and file.is_file():
                    route.fulfill(path=str(file))
                else:
                    route.abort()

            page.route('**/*', serve)
            yield page, manager, stages, requests, errors
            browser.close()
    finally:
        manager.close()


@pytest.mark.parametrize('single', [True, False])
def test_comparison_capture_results_evidence_and_reload(comparison_portal, single):
    page, manager, stages, requests, errors = comparison_portal
    page.goto('http://studio.test/compare/' + ('?mode=single' if single else ''))
    page.get_by_role('textbox', name='URL A', exact=True).fill('https://one.example/catalog')
    if not single:
        page.get_by_role('textbox', name='URL B', exact=True).fill('https://two.example/catalog')
    page.get_by_role('button', name=re.compile('^' + ('Extraer y analizar' if single else 'Comparar fuentes'))).click()
    expect(page.get_by_text('Fuentes, diagnósticos y exportaciones', exact=True)).to_be_visible()
    count = 1 if single else 2
    assert [(stage, index) for stage, index, _ in stages] == (
        [('capture', i) for i in range(count)] + [('process', i) for i in range(count)])
    assert len(stages[0][2]['sources']) == count
    assert stages[0][2]['limits']['max_pages'] == (1 if single else 5)
    evidence = page.get_by_role('button', name='Ver evidencia', exact=True).first
    expect(evidence).to_be_visible()
    evidence.click()
    dialog = page.get_by_role('dialog', name='Evidencia de la fuente')
    expect(dialog).to_be_visible()
    expect(dialog.locator('.cp-evidence-claim').first).to_be_visible()
    assert any(method == 'POST' and path.endswith('/evidence') for method, path in requests)
    page.keyboard.press('Escape')
    expect(dialog).to_have_count(0)
    page.reload()
    expect(page.get_by_text('Fuentes, diagnósticos y exportaciones', exact=True)).to_be_visible()
    assert len(manager.list()) == 1
    assert not errors


def test_comparison_popstate_clears_previous_result_and_restores_mode(comparison_portal):
    page, manager, stages, requests, errors = comparison_portal
    page.goto('http://studio.test/compare/')
    page.get_by_role('textbox', name='URL A', exact=True).fill('https://one.example/catalog')
    page.get_by_role('textbox', name='URL B', exact=True).fill('https://two.example/catalog')
    page.get_by_role('button', name=re.compile('^Comparar fuentes')).click()
    expect(page.get_by_text('Fuentes, diagnósticos y exportaciones', exact=True)).to_be_visible()
    page.evaluate("history.pushState(null,'','/compare/?mode=single'); dispatchEvent(new PopStateEvent('popstate'))")
    expect(page.get_by_role('heading', name='Análisis de una fuente', exact=True)).to_be_visible()
    expect(page.get_by_text('Fuentes, diagnósticos y exportaciones', exact=True)).to_have_count(0)
    expect(page.get_by_role('textbox', name='URL B', exact=True)).to_have_count(0)
    assert not errors


@pytest.mark.parametrize('valid', [True, False])
def test_comparison_import_validates_json_contract_in_the_api(comparison_portal, valid):
    page, manager, stages, requests, errors = comparison_portal
    page.goto('http://studio.test/compare/')
    page.get_by_role('button', name='Importar JSON', exact=True).click()
    for index, letter in enumerate('AB'):
        payload = examples()[index] if valid else {}
        page.get_by_label('JSON ' + letter, exact=True).set_input_files({
            'name': letter + '.json', 'mimeType': 'application/json',
            'buffer': json.dumps(payload).encode('utf-8')})
    page.get_by_role('button', name=re.compile('^Comparar fuentes')).click()
    if valid:
        expect(page.get_by_text('Fuentes, diagnósticos y exportaciones', exact=True)).to_be_visible()
        assert [(stage, index) for stage, index, _ in stages] == [('process', 0), ('process', 1)]
        assert manager.list()[0]['imported'] is True
    else:
        expect(page.locator('.cp-error[role="alert"]')).to_contain_text('El JSON de la fuente A no cumple un contrato compatible.')
        assert not stages and not manager.list()
    assert ('POST', '/api/comparisons/import') in requests
    assert not errors


@pytest.mark.parametrize('save_method', ['click', 'enter'])
def test_paste_jev_key_then_run_with_jev_and_reload(comparison_portal, save_method):
    page, manager, stages, requests, errors = comparison_portal
    page.goto('http://studio.test/compare/')
    page.get_by_role('button', name='Configuración avanzada', exact=True).click()
    settings = page.get_by_role('dialog', name='Límites y procesamiento')
    settings.locator('select').nth(1).select_option('jev')
    capture_seconds = settings.get_by_label(re.compile('^Tiempo máximo de captura'))
    capture_seconds.fill('37')
    settings.get_by_label(re.compile('^Enlaces que se pueden seguir')).select_option('all')
    panel = page.get_by_role('region', name='Configuración de Jev')
    field = panel.get_by_label('Clave API de Jev', exact=True)
    expect(field).to_be_visible()
    field.fill('browser-fixture-key')
    if save_method == 'enter':
        field.press('Enter')
    else:
        panel.get_by_role('button', name='Guardar clave Jev', exact=True).click()
    expect(panel.get_by_role('status')).to_contain_text('Clave guardada.')
    expect(settings).to_be_visible()
    expect(capture_seconds).to_have_value('37')
    expect(settings.get_by_label(re.compile('^Enlaces que se pueden seguir'))).to_have_value('all')
    expect(settings.locator('select').nth(1)).to_have_value('jev')
    expect(field).to_have_value('')
    assert requests.count(('PUT', '/api/service/credentials/jev')) == 1
    assert not any(method == 'POST' for method, _ in requests)
    settings.get_by_role('button', name='Confirmar parámetros', exact=True).click()
    expect(settings).to_have_count(0)
    page.get_by_role('button', name='Configuración avanzada', exact=True).click()
    expect(capture_seconds).to_have_value('37')
    expect(settings.get_by_label(re.compile('^Enlaces que se pueden seguir'))).to_have_value('all')
    settings.get_by_role('button', name='Confirmar parámetros', exact=True).click()
    assert 'browser-fixture-key' not in page.content()
    assert not page.evaluate("[localStorage,sessionStorage].some(storage=>Object.values(storage).some(value=>value.includes('browser-fixture-key')))")
    assert semantic_model.api_key() == 'browser-fixture-key'
    page.goto('http://studio.test/compare/?mode=single')
    page.get_by_role('button', name='Configuración avanzada', exact=True).click()
    settings = page.get_by_role('dialog', name='Límites y procesamiento')
    settings.locator('select').nth(1).select_option('jev')
    panel = page.get_by_role('region', name='Configuración de Jev')
    expect(panel.locator('summary')).to_contain_text('Clave configurada')
    settings.get_by_role('button', name='Confirmar parámetros', exact=True).click()
    page.get_by_role('textbox', name='URL A', exact=True).fill('https://one.example/catalog')
    page.get_by_role('button', name=re.compile('^Extraer y analizar')).click()
    expect(page.get_by_text('Fuentes, diagnósticos y exportaciones', exact=True)).to_be_visible()
    assert stages[0][2]['interpreter'] == 'jev'
    assert not errors


def test_empty_jev_enter_does_not_submit_modal_or_bypass_limit_validation(comparison_portal):
    page, manager, stages, requests, errors = comparison_portal
    page.goto('http://studio.test/compare/')
    page.get_by_role('button', name='Configuración avanzada', exact=True).click()
    settings = page.get_by_role('dialog', name='Límites y procesamiento')
    settings.locator('select').nth(1).select_option('jev')
    field = settings.get_by_label('Clave API de Jev', exact=True)
    field.fill('   ')
    field.press('Enter')
    expect(settings).to_be_visible()
    expect(settings.get_by_role('button', name='Guardar clave Jev', exact=True)).to_be_disabled()
    assert ('PUT', '/api/service/credentials/jev') not in requests
    capture_seconds = settings.get_by_label(re.compile('^Tiempo máximo de captura'))
    capture_seconds.fill('1')
    settings.get_by_role('button', name='Confirmar parámetros', exact=True).click()
    expect(settings).to_be_visible()
    assert not capture_seconds.evaluate('(element)=>element.validity.valid')
    field.fill('')
    capture_seconds.fill('37')
    settings.get_by_role('button', name='Confirmar parámetros', exact=True).click()
    expect(settings).to_have_count(0)
    assert not stages and not manager.list()
    assert not errors


@pytest.mark.parametrize('failed_sources', [1, 2])
def test_capture_failures_show_source_diagnostics_instead_of_empty_results(comparison_portal, failed_sources):
    page, manager, stages, requests, errors = comparison_portal
    execute = manager.executor
    def fail_capture(folder, stage, index, spec, cancel, task):
        if stage == 'capture' and index < failed_sources:
            write_json(folder / str(index) / 'stage-error.json', {
                'stage': 'capture', 'code': 'network_access_denied',
                'message': 'El proceso de captura no tiene permiso para acceder a Internet.'})
            return 'error'
        return execute(folder, stage, index, spec, cancel, task)
    manager.executor = fail_capture
    page.goto('http://studio.test/compare/')
    page.get_by_role('textbox', name='URL A', exact=True).fill('https://one.example/catalog')
    page.get_by_role('textbox', name='URL B', exact=True).fill('https://two.example/catalog')
    page.get_by_role('button', name=re.compile('^Comparar fuentes')).click()
    alerts = page.locator('.cp-error[role="alert"]').filter(has_text='no tiene permiso para acceder a Internet')
    expect(alerts).to_have_count(failed_sources)
    expect(alerts.first).to_contain_text('Fuente A')
    support = page.locator('.cp-support')
    support.locator('summary').first.click()
    expect(support.get_by_text('1 diagnósticos', exact=True)).to_have_count(failed_sources)
    assert not errors
