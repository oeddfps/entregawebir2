"""Installation credential setup, with fixture keys and no provider traffic."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.common import semantic_model
from src.server.credentials import router

HEADERS = {'X-Jev-Configuration': '1'}
URL = '/api/service/credentials/jev'


@pytest.fixture
def credentials(tmp_path, monkeypatch):
    monkeypatch.delenv('TYPESAFE_TEST_MODE', raising=False)
    monkeypatch.delenv('TYPESAFE_TEST_API_KEY', raising=False)
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.setattr(semantic_model, 'ENV_FILE', tmp_path / '.env')
    monkeypatch.setattr(semantic_model, 'SAVED_KEY_FILE', tmp_path / 'secrets/jev.json')
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        yield client


def test_save_replace_and_read_without_exposing_the_key(credentials):
    client = credentials
    assert client.get(URL).json() == {'configured': False, 'source': None, 'editable': True}
    for key in ['fixture-first-key', 'fixture-replacement-key']:
        response = client.put(URL, json={'api_key': key}, headers=HEADERS)
        assert response.status_code == 200
        assert response.json() == {'configured': True, 'source': 'interface', 'editable': True}
        assert key not in response.text and key not in client.get(URL).text
        assert semantic_model.api_key() == key
    if os.name != 'nt':
        assert semantic_model.SAVED_KEY_FILE.stat().st_mode & 0o777 == 0o600
    assert not list(semantic_model.SAVED_KEY_FILE.parent.glob('.jev-*'))
    # Fresh workers read the saved key without a restart of the API or environment mutation.
    code = "from pathlib import Path; import sys; from src.common import semantic_model as m; m.SAVED_KEY_FILE=Path(sys.argv[1]); m.ENV_FILE=Path(sys.argv[2]); assert m.api_key()=='fixture-replacement-key'"
    subprocess.run([sys.executable, '-c', code, str(semantic_model.SAVED_KEY_FILE),
                    str(semantic_model.ENV_FILE)], check=True, timeout=15)


@pytest.mark.parametrize('payload', [{'api_key': ''}, {'api_key': 'secret\nvalue'},
    {'api_key': None}, {'api_key': {'secret': 'fixture-value'}},
    {'api_key': 'fixture-value', 'extra': 'private-fixture'}, ['fixture-value']])
def test_invalid_input_never_echoes_submitted_secrets(credentials, payload):
    response = credentials.put(URL, json=payload, headers=HEADERS)
    assert response.status_code == 422
    assert 'fixture-value' not in response.text and 'private-fixture' not in response.text
    assert not semantic_model.SAVED_KEY_FILE.exists()


def test_cross_origin_and_oversized_requests_are_rejected(credentials):
    assert credentials.put(URL, json={'api_key': 'fixture'}).status_code == 403
    assert credentials.put(URL, json={'api_key': 'fixture'},
        headers={**HEADERS, 'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert credentials.put(URL, content='x' * 8193,
        headers={**HEADERS, 'Content-Type': 'application/json'}).status_code == 413
    assert not semantic_model.SAVED_KEY_FILE.exists()


def test_environment_precedence_and_test_isolation(credentials, monkeypatch):
    semantic_model.save_api_key('saved-fixture')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'environment-fixture')
    assert credentials.get(URL).json()['editable'] is False
    response = credentials.put(URL, json={'api_key': 'replacement-fixture'}, headers=HEADERS)
    assert response.status_code == 409
    assert semantic_model.api_key() == 'environment-fixture'
    monkeypatch.setenv('TYPESAFE_TEST_MODE', '1')
    assert semantic_model.api_key() == ''
    monkeypatch.setenv('TYPESAFE_TEST_API_KEY', 'test-fixture')
    assert semantic_model.api_key() == 'test-fixture'


def test_saved_key_is_used_by_extractor_and_comparison_worker(credentials, tmp_path, monkeypatch):
    from clean_process import process
    from clean_process.__main__ import write_json
    from src.comparison import worker
    from src.comparison.examples import examples
    semantic_model.save_api_key('shared-fixture')
    headers = []
    def provider(request, **kwargs):
        headers.append(request.get_header('Authorization'))
        return io.StringIO(json.dumps({'answers': {}}))
    semantic_model.predict({}, {}, opener=provider)
    assert headers == ['Bearer shared-fixture']
    output = process(examples()[0])
    def processor(data, *, interpreter, review_recognizer):
        assert interpreter.predictor.api_key == 'shared-fixture'
        return output
    monkeypatch.setattr(worker, 'process', processor)
    folder = tmp_path / 'worker'
    write_json(folder / 'import.json', examples()[0])
    worker.processing(folder, 'jev', 'off')
    assert (folder / 'presentation.json').is_file()
