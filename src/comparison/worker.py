"""Single isolated capture or processing stage. Never starts a persistent crawler."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
from urllib.parse import urlsplit

from clean_process import Input, Output, process
from clean_process.__main__ import write_json
from clean_process.presentation import present
from .diagnostics import stage_diagnostic


def kill_tree(pid):
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def snapshot_capture(folder):
    from ..common.scrapper import AuditStore
    if not (folder / 'audit' / 'audit.sqlite3').exists():
        return []
    audit = AuditStore(folder / 'audit')
    pages = []
    for run in audit.list_runs():
        for item in audit.list_visits(run['id']):
            v = audit.get_visit(item['id'])
            if v and v.get('result'):
                pages.append({'url': v.get('final_uri') or v['requested_uri'], 'result': v['result'],
                              'capture_status': v['status']})
    if pages:
        write_json(folder / 'capture.json', pages)
    return pages


def capture(folder, spec, limits):
    from ..common.scrapper import AuditStore, Scrapper, ScrapperConfig, SemanticMetadataStrategy
    audit = AuditStore(folder / 'audit')
    def progress(data):
        write_json(folder / 'progress.json', data)
        snapshot_capture(folder)
    config = ScrapperConfig(max_threads=1, max_sites=limits['max_pages'], max_hops=limits['max_hops'],
        max_retries=0, same_host_only=limits.get('same_host_only', True),
        allowed_domains=(urlsplit(spec['url']).hostname,) if limits.get('same_host_only', True) else (),
        strategy=SemanticMetadataStrategy(follow_navigation=limits['max_hops'] is None or limits['max_hops'] > 0, interpret_fields=False),
        audit_dir=folder / 'audit')
    summary = Scrapper(config, audit=audit).run([spec['url']], on_progress=progress)
    pages = snapshot_capture(folder)
    if not pages:
        raise RuntimeError('La captura no produjo contenido procesable.')
    write_json(folder / 'capture-summary.json', vars(summary))


def processing(folder, interpreter, review_recognition='e5'):
    path = folder / 'import.json'
    payload = json.loads((path if path.exists() else folder / 'capture.json').read_text(encoding='utf-8'))
    if isinstance(payload, dict) and 'knowledge' in payload and 'processing_id' in payload:
        output = Output.model_validate(payload)
    else:
        if isinstance(payload, dict) and 'samples' in payload:
            request = Input.model_validate(payload)
        else:
            from ..integrations.clean_process import from_scraper
            request = from_scraper(payload, export_ref='comparison-capture')
        write_json(folder / 'input.json', request.model_dump(mode='json'))
        backend = None
        if interpreter == 'jev':
            from clean_process.interpreters import JevClient, JevInterpreter
            class RecordedClient(JevClient):
                def __call__(self, state, questions):
                    write_json(folder / 'usage.json', {'calls': self.usage, 'inflight': True, 'complete': False})
                    try:
                        return super().__call__(state, questions)
                    finally:
                        write_json(folder / 'usage.json', {'calls': self.usage, 'inflight': False,
                                   'complete': all(c['usage_complete'] for c in self.usage)})
            from ..common.semantic_model import api_key
            backend = JevInterpreter(RecordedClient(api_key()))
        from clean_process.review_recognition import E5Scorer, ReviewRecognizer
        recognizer = ReviewRecognizer(E5Scorer() if review_recognition == 'e5' else None) if review_recognition != 'off' else None
        output = process(request, interpreter=backend, review_recognizer=recognizer)
    write_json(folder / 'output.json', output.model_dump(mode='json'))
    write_json(folder / 'presentation.json', present(output))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['capture', 'process'])
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    request = json.loads((args.folder.parent / 'request.json').read_text(encoding='utf-8'))
    index = int(args.folder.name)
    limit = request['limits']['capture_seconds' if args.stage == 'capture' else 'processing_seconds']
    # A hard API crash must not leave an unbounded capture process.
    timer = threading.Timer(limit + 2, lambda: kill_tree(os.getpid()))
    timer.daemon = True
    timer.start()
    try:
        if args.stage == 'capture':
            capture(args.folder, request['sources'][index], request['limits'])
        else:
            processing(args.folder, request['interpreter'], request.get('review_recognition', 'e5'))
    except Exception as error:
        diagnostic = stage_diagnostic(args.folder, args.stage, 'error', error)
        write_json(args.folder / 'stage-error.json', diagnostic)
        print(diagnostic['message'], flush=True)
        raise SystemExit(1)
    finally:
        timer.cancel()


if __name__ == '__main__':
    main()
