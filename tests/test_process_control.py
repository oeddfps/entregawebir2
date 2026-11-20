"""Real process cleanup preserves unrelated activities and store ownership."""
import os
import subprocess
import sys

import psutil

from src.persistent.cancellation import cancel_workers
from src.persistent.processes import terminate_tree


def launch(code, *args):
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    return subprocess.Popen([sys.executable, '-u', '-c', code, *map(str, args)],
                            stdout=subprocess.PIPE, text=True, **flags)


def cleanup(process):
    if process.poll() is None:
        terminate_tree(process.pid)
    process.wait(timeout=5)
    process.stdout.close()


def test_terminate_tree_stops_descendants_and_preserves_other_process():
    parent = launch("import subprocess,sys,time; child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(child.pid,flush=True); time.sleep(60)")
    other = launch("import time; print('ready',flush=True); time.sleep(60)")
    try:
        child = psutil.Process(int(parent.stdout.readline()))
        assert other.stdout.readline().strip() == 'ready'
        terminate_tree(parent.pid)
        assert parent.wait(timeout=5) != 0
        assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
        assert other.poll() is None
    finally:
        cleanup(parent)
        cleanup(other)


def test_cancel_workers_requires_both_activity_and_store(tmp_path):
    root = tmp_path / 'service'
    other_root = tmp_path / 'other-service'
    code = "import time; print('ready',flush=True); time.sleep(60)"
    processes = [launch(code, 'src.persistent.worker', '--root', folder, '--activity', activity)
                 for folder, activity in [(root, 'one'), (other_root, 'one'), (root, 'two')]]
    try:
        for process in processes:
            assert process.stdout.readline().strip() == 'ready'
        cancel_workers({'one'}, root)
        assert processes[0].wait(timeout=3) != 0
        assert all(process.poll() is None for process in processes[1:])
    finally:
        for process in processes:
            cleanup(process)
