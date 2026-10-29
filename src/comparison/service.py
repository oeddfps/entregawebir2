"""Persisted comparison jobs. A/B capture is sequential and cancellation is scoped."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Event, RLock, Thread
import time
from uuid import uuid4

from clean_process.__main__ import write_json
from .worker import kill_tree, snapshot_capture

TERMINAL = {'done', 'partial', 'failed', 'cancelled', 'interrupted'}
PROJECT = Path(__file__).resolve().parents[2]


def now():
    return datetime.now(timezone.utc).isoformat()


class ComparisonManager:
    def __init__(self, root=None, *, executor=None):
        self.root = Path(root or PROJECT / 'data' / 'comparisons')
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.running = {}
        self.executor = executor or self._subprocess

    def folder(self, identity):
        if not re.fullmatch('[a-f0-9]{32}', identity):
            raise KeyError(identity)
        folder = self.root / identity
        if not (folder / 'manifest.json').is_file():
            raise KeyError(identity)
        return folder

    def get(self, identity):
        with self.lock:
            folder = self.folder(identity)
            data = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
            # A detached run is not reported as actively supervised after a restart.
            if data['status'] not in TERMINAL and identity not in self.running:
                data.update(status='interrupted', phase='interrupted', finished_at=now())
                data['events'].append({'at': now(), 'message': 'El servicio se reinició; se conservaron los resultados disponibles.'})
                write_json(folder / 'manifest.json', data)
            for i, source in enumerate(data['sources']):
                progress = folder / str(i) / 'progress.json'
                if progress.is_file():
                    source['progress'] = json.loads(progress.read_text(encoding='utf-8'))
                source['result_available'] = (folder / str(i) / 'presentation.json').is_file()
                source['artifacts'] = [kind for kind in ('capture', 'import', 'input', 'output', 'presentation', 'usage')
                                       if (folder / str(i) / f'{kind}.json').is_file()]
            return data

    def list(self):
        items = []
        for path in self.root.glob('*/manifest.json'):
            try:
                items.append(self.get(path.parent.name))
            except (KeyError, ValueError, OSError):
                continue
        return sorted(items, key=lambda item: item['created_at'], reverse=True)[:50]

    def update(self, identity, *, source=None, event=None, **changes):
        with self.lock:
            folder = self.folder(identity)
            data = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
            if source is None:
                data.update(changes)
            else:
                data['sources'][source].update(changes)
            if event:
                data['events'].append({'at': now(), 'message': event})
            write_json(folder / 'manifest.json', data)

    def create(self, request, *, imported=None):
        with self.lock:
            if sum(not task['cancel'].is_set() for task in self.running.values()) >= 2:
                raise RuntimeError('Ya hay dos comparaciones activas.')
            identity = uuid4().hex
            folder = self.root / identity
            folder.mkdir()
            sources = deepcopy(request['sources'])
            manifest = {'contract_version': '1.0', 'comparison_id': identity, 'status': 'queued',
                'phase': 'queued', 'created_at': now(), 'finished_at': None, 'imported': imported is not None,
                'sources': [{**s, 'status': 'queued', 'capture_status': 'not_required' if imported else 'queued',
                             'processing_status': 'queued', 'stop_reason': None} for s in sources],
                'events': [{'at': now(), 'message': 'Comparación creada.'}]}
            for i in range(2):
                (folder / str(i)).mkdir()
                if imported:
                    write_json(folder / str(i) / 'import.json', imported[i])
            write_json(folder / 'request.json', request)
            write_json(folder / 'manifest.json', manifest)
            task = {'cancel': Event(), 'process': None}
            self.running[identity] = task
            thread = Thread(target=self._run, args=(identity, request, imported is not None, task), daemon=True)
            task['thread'] = thread
            thread.start()
            return self.get(identity)

    def _subprocess(self, folder, stage, index, request, cancel, task):
        flags = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        with (folder / str(index) / f'{stage}.log').open('wb') as log:
            child = subprocess.Popen([sys.executable, '-m', 'src.comparison.worker', stage, str(folder / str(index))],
                cwd=PROJECT, stdout=log, stderr=log, **flags)
            task['process'] = child
            started = time.monotonic()
            budget = request['limits']['capture_seconds' if stage == 'capture' else 'processing_seconds']
            reason = 'done'
            try:
                while child.poll() is None:
                    if cancel.wait(.15):
                        reason = 'cancelled'
                        break
                    if time.monotonic() - started >= budget:
                        reason = 'timeout'
                        break
                if child.poll() is None:
                    kill_tree(child.pid)
                child.wait(timeout=10)
                if reason == 'done' and child.returncode:
                    reason = 'error'
                return reason
            finally:
                if child.poll() is None:
                    kill_tree(child.pid)
                    child.wait(timeout=10)
                task['process'] = None

    def _run(self, identity, request, imported, task):
        folder = self.root / identity
        cancelled = task['cancel']
        try:
            self.update(identity, status='running')
            if not imported:
                for i in range(2):
                    if cancelled.is_set():
                        break
                    self.update(identity, phase=f'capture_{i}', event=f'Capturando fuente {"AB"[i]}.')
                    self.update(identity, source=i, status='capturing', capture_status='running', started_at=now())
                    reason = self.executor(folder, 'capture', i, request, cancelled, task)
                    if reason != 'done':
                        snapshot_capture(folder / str(i))
                    captured = (folder / str(i) / 'capture.json').is_file()
                    self.update(identity, source=i, capture_status='done' if reason == 'done' else 'partial' if captured else 'failed',
                                status='captured' if captured else 'failed', stop_reason=reason, capture_finished_at=now())
            for i in range(2):
                if cancelled.is_set():
                    break
                if not imported and not (folder / str(i) / 'capture.json').exists():
                    self.update(identity, source=i, processing_status='skipped')
                    continue
                self.update(identity, phase=f'process_{i}', event=f'Procesando fuente {"AB"[i]} con Clean&Process.')
                self.update(identity, source=i, status='processing', processing_status='running')
                reason = self.executor(folder, 'process', i, request, cancelled, task)
                available = (folder / str(i) / 'presentation.json').is_file()
                self.update(identity, source=i, processing_status='done' if available else 'failed',
                            status='done' if available else 'failed', processing_stop_reason=reason, finished_at=now())
            data = self.get(identity)
            ready = sum(s['result_available'] for s in data['sources'])
            partial = any(s['capture_status'] == 'partial' or s.get('stop_reason') in ('error', 'timeout') for s in data['sources'])
            status = 'cancelled' if cancelled.is_set() else 'done' if ready == 2 and not partial else 'partial' if ready else 'failed'
            self.update(identity, status=status, phase=status, finished_at=now(), event='Comparación finalizada.' if status == 'done' else 'Se conservaron los resultados disponibles.')
        except Exception:
            self.update(identity, status='cancelled' if cancelled.is_set() else 'failed', phase='failed', finished_at=now(),
                        event='La comparación se detuvo. Los archivos guardados se conservaron.')
        finally:
            with self.lock:
                self.running.pop(identity, None)

    def cancel(self, identity):
        with self.lock:
            task = self.running.get(identity)
            if task:
                task['cancel'].set()
                self.update(identity, phase='cancelling', event='Cancelación solicitada.')
            return self.get(identity)

    def close(self):
        with self.lock:
            tasks = list(self.running.values())
        for task in tasks:
            task['cancel'].set()
        for task in tasks:
            task['thread'].join(timeout=12)

    def result(self, identity, index):
        folder = self.folder(identity)
        if index not in (0, 1):
            raise KeyError(index)
        path = folder / str(index) / 'presentation.json'
        if not path.exists():
            raise KeyError(index)
        return json.loads(path.read_text(encoding='utf-8'))

    def evidence(self, identity, index, assertion_ids):
        folder = self.folder(identity)
        if index not in (0, 1):
            raise KeyError(index)
        path = folder / str(index) / 'output.json'
        if not path.exists():
            raise KeyError(index)
        output = json.loads(path.read_text(encoding='utf-8'))
        selected = [a for a in output['knowledge']['assertions'] if a['assertion_id'] in assertion_ids]
        refs = {r for a in selected for r in a['evidence_refs']}
        return {'assertions': selected, 'evidence': [e for e in output['evidence'] if e['evidence_id'] in refs]}
