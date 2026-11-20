"""Private installation credential configuration; responses never contain keys."""
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..common import semantic_model

router = APIRouter(prefix='/api/service/credentials/jev', tags=['Configuración Jev'])


class CredentialStatus(BaseModel):
    configured: bool
    source: Literal['environment', 'interface', 'file', 'test'] | None
    editable: bool


@router.get('', response_model=CredentialStatus)
def status():
    return semantic_model.credential_status()


@router.put('', response_model=CredentialStatus, openapi_extra={
    'requestBody': {'required': True, 'content': {'application/json': {'schema': {
        'type': 'object', 'required': ['api_key'], 'additionalProperties': False,
        'properties': {'api_key': {'type': 'string', 'minLength': 1,
                                   'maxLength': 4096, 'writeOnly': True}}}}}},
    'parameters': [{'in': 'header', 'name': 'X-Jev-Configuration', 'required': True,
                    'schema': {'type': 'string', 'enum': ['1']}}],
})
async def configure(request: Request):
    # JSON plus a custom header requires a CORS preflight from another origin.
    # The private application does not enable cross-origin credential writes.
    if request.headers.get('x-jev-configuration') != '1' or request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Configura Jev desde la interfaz de esta aplicación.')
    if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
        raise HTTPException(415, 'Se requiere JSON.')
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 8192:
            raise HTTPException(413, 'La configuración supera el tamaño permitido.')
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, 'No se pudo leer la configuración.') from None
    # Do not use default validation errors: they can echo submitted secrets.
    if not isinstance(payload, dict) or set(payload) != {'api_key'}:
        raise HTTPException(422, 'Indica únicamente la clave API de Jev.')
    if not semantic_model.credential_status()['editable']:
        raise HTTPException(409, 'La credencial está administrada por el entorno del servidor.')
    try:
        return semantic_model.save_api_key(payload['api_key'])
    except ValueError:
        raise HTTPException(422, 'Pega una clave API válida, sin espacios ni saltos de línea.') from None
    except OSError:
        raise HTTPException(503, 'No se pudo guardar la clave en el servidor. Revisa los permisos de almacenamiento.') from None
