from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from clean_process import Input, Output
from clean_process.presentation import Presentation
from ..integrations.clean_process import from_scraper
from ..common.semantic_model import api_key
from .contracts import ComparisonRequest, ImportRequest, ComparisonState
from .service import ComparisonManager


def router(manager: ComparisonManager):
    api = APIRouter(prefix='/api/comparisons', tags=['Comparaciones'])

    def configured(mode):
        if mode == 'jev' and not api_key():
            raise HTTPException(422, 'Configura tu clave API en el panel Jev antes de iniciar el análisis.')

    @api.get('')
    def history():
        return {'items': manager.list()}

    @api.get('/contract')
    def contract():
        from clean_process.presentation import Presentation
        return {'contract_version': '1.0', 'request': ComparisonRequest.model_json_schema(),
                'import': ImportRequest.model_json_schema(), 'state': ComparisonState.model_json_schema(),
                'presentation': Presentation.model_json_schema()}

    @api.post('', status_code=202, response_model=ComparisonState)
    def start(request: ComparisonRequest):
        configured(request.interpreter)
        try:
            return manager.create(request.model_dump())
        except RuntimeError as error:
            raise HTTPException(409, str(error))

    @api.post('/import', status_code=202, response_model=ComparisonState)
    def import_sources(request: ImportRequest):
        configured(request.interpreter)
        imported, sources = [], []
        for i, source in enumerate(request.sources):
            value = source.payload
            try:
                if isinstance(value, dict) and 'knowledge' in value:
                    output = Output.model_validate(value)
                    origin = next((e.source_ref for e in output.evidence), '')
                elif isinstance(value, dict) and 'samples' in value:
                    data = Input.model_validate(value)
                    origin = data.samples[0].source_ref
                else:
                    data = from_scraper(value)
                    origin = data.samples[0].source_ref
            except (ValueError, TypeError, KeyError):
                raise HTTPException(422, f'El JSON de la fuente {"AB"[i]} no cumple un contrato compatible.') from None
            imported.append(value)
            sources.append({'url': origin, 'label': source.label or f'Fuente {"AB"[i]}'})
        payload = {'contract_version': '1.0', 'sources': sources, 'limits': request.limits.model_dump(), 'interpreter': request.interpreter, 'review_recognition': request.review_recognition}
        try:
            return manager.create(payload, imported=imported)
        except RuntimeError as error:
            raise HTTPException(409, str(error))

    @api.post('/example', status_code=202, response_model=ComparisonState)
    def example():
        from .examples import examples
        request = {'contract_version': '1.0', 'sources': [
            {'url': 'document:demonstration-0', 'label': 'Ejemplo A'},
            {'url': 'document:demonstration-1', 'label': 'Ejemplo B'}],
            'limits': {'max_pages': 1, 'max_hops': 0, 'capture_seconds': 30, 'processing_seconds': 30},
            'interpreter': 'declared'}
        try:
            job = manager.create(request, imported=examples())
            manager.update(job['comparison_id'], synthetic=True)
            return manager.get(job['comparison_id'])
        except RuntimeError as error:
            raise HTTPException(409, str(error))

    def get(identity):
        try:
            return manager.get(identity)
        except KeyError:
            raise HTTPException(404, 'Comparación no encontrada.') from None

    @api.get('/{identity}', response_model=ComparisonState)
    def state(identity: str):
        return get(identity)

    @api.post('/{identity}/cancel', response_model=ComparisonState)
    def cancel(identity: str):
        get(identity)
        return manager.cancel(identity)

    @api.get('/{identity}/sources/{index}', response_model=Presentation)
    def result(identity: str, index: int):
        get(identity)
        try:
            return manager.result(identity, index)
        except KeyError:
            raise HTTPException(404, 'Resultado todavía no disponible.') from None

    class EvidenceRequest(BaseModel):
        assertion_ids: list[str] = Field(max_length=100)

    @api.post('/{identity}/sources/{index}/evidence')
    def evidence(identity: str, index: int, request: EvidenceRequest):
        get(identity)
        try:
            return manager.evidence(identity, index, request.assertion_ids)
        except KeyError:
            raise HTTPException(404, 'Evidencia no disponible.') from None

    @api.get('/{identity}/sources/{index}/download/{kind}')
    def download(identity: str, index: int, kind: str):
        job = get(identity)
        if not 0 <= index < len(job['sources']) or kind not in ('capture', 'import', 'input', 'output', 'presentation', 'usage'):
            raise HTTPException(404, 'Archivo no disponible.')
        path = manager.folder(identity) / str(index) / f'{kind}.json'
        if not path.exists():
            raise HTTPException(404, 'Archivo todavía no disponible.')
        return FileResponse(path, media_type='application/json', filename=f'{identity}-{"AB"[index]}-{kind}.json')

    return api
