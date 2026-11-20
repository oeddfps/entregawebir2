"""Safe, source-independent failure messages for capture and processing stages."""
import json
import re
import sqlite3
from contextlib import closing


MESSAGES = {
    'network_access_denied': 'El proceso de captura no tiene permiso para acceder a Internet. Inicia el servicio con acceso de red.',
    'certificate_error': 'No se pudo validar el certificado HTTPS. Revisa los certificados de confianza del entorno.',
    'dns_error': 'No se pudo resolver el dominio de la fuente. Revisa la URL y la conexión.',
    'connection_error': 'No se pudo establecer la conexión con la fuente.',
    'navigation_timeout': 'La página no terminó de cargar dentro del tiempo de navegación disponible.',
    'browser_unavailable': 'El navegador de captura no está instalado o no pudo iniciarse. Revisa la instalación de Playwright.',
    'stage_timeout': 'La etapa alcanzó su límite de tiempo. Se conserva la evidencia disponible.',
    'missing_credential': 'Falta la clave API de Jev. Configúrala desde Configuración avanzada.',
    'provider_error': 'Jev no pudo completar la interpretación. Revisa la credencial y la disponibilidad del proveedor.',
    'capture_failed': 'La captura no produjo contenido procesable. Revisa la disponibilidad de la fuente y el historial de captura.',
    'processing_failed': 'No se pudo procesar el contenido de esta fuente. Se conservan los archivos disponibles.',
}


def _capture_error(folder):
    path = folder / 'audit' / 'audit.sqlite3'
    if not path.is_file():
        return ''
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            row = db.execute('SELECT error FROM visits WHERE error IS NOT NULL ORDER BY started_at DESC LIMIT 1').fetchone()
            return row[0] if row else ''
    except sqlite3.Error:
        return ''


def stage_diagnostic(folder, stage, reason, error=None):
    if reason in ('done', 'cancelled', None):
        return None
    try:
        saved = json.loads((folder / 'stage-error.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        saved = {}
    if not isinstance(saved, dict) or saved.get('stage') != stage:
        saved = {}
    detail = str(error or '')
    if stage == 'capture':
        detail = _capture_error(folder) or detail
    detail = detail or str(saved.get('message', ''))
    code = 'capture_failed' if stage == 'capture' else 'processing_failed'
    if reason == 'timeout':
        code = 'stage_timeout'
    elif any(value in detail for value in ('ERR_NETWORK_ACCESS_DENIED', 'WinError 10013')):
        code = 'network_access_denied'
    elif any(value in detail for value in ('ERR_CERT_', 'CERTIFICATE_VERIFY_FAILED')):
        code = 'certificate_error'
    elif 'ERR_NAME_NOT_RESOLVED' in detail:
        code = 'dns_error'
    elif any(value in detail for value in ('ERR_CONNECTION_', 'ERR_INTERNET_DISCONNECTED')):
        code = 'connection_error'
    elif 'Timeout' in detail or 'timeout' in detail:
        code = 'navigation_timeout'
    elif "Executable doesn't exist" in detail or 'BrowserType.launch' in detail:
        code = 'browser_unavailable'
    elif 'A Jev API key must be supplied' in detail:
        code = 'missing_credential'
    elif 'Jev request failed' in detail or 'Invalid Jev response' in detail:
        code = 'provider_error'
    elif match := re.search(r'HTTP ([45]\d\d)\b', detail):
        status = int(match[1])
        return {'stage': stage, 'code': 'http_error', 'http_status': status,
                'message': f'La fuente respondió HTTP {status}. Comprueba que sea pública y esté disponible.'}
    elif saved.get('code') in MESSAGES:
        code = saved['code']
    elif saved.get('code') == 'http_error' and type(saved.get('http_status')) is int:
        status = saved['http_status']
        if 400 <= status <= 599:
            return {'stage': stage, 'code': 'http_error', 'http_status': status,
                    'message': f'La fuente respondió HTTP {status}. Comprueba que sea pública y esté disponible.'}
    return {'stage': stage, 'code': code, 'message': MESSAGES[code]}
