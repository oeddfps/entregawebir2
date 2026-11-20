"""Process ownership and control on Windows, retaining POSIX process groups."""
import os
import signal
from pathlib import Path

if os.name == 'nt':
    import psutil


def process_handle(pid):
    """Keep PID and creation time together when supervising a Windows process."""
    if os.name != 'nt':
        return pid
    try:
        return psutil.Process(pid)
    except psutil.NoSuchProcess:
        return None


def terminate_tree(process):
    if process is None:
        return
    if os.name != 'nt':
        try:
            os.killpg(process if isinstance(process, int) else process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return
    try:
        parent = psutil.Process(process) if isinstance(process, int) else process
        children = parent.children(recursive=True)
        # Stop the parent first so it cannot launch more children during cleanup.
        try:
            parent.kill()
        except psutil.NoSuchProcess:
            pass
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs([parent, *children], timeout=5)
        if alive:
            raise TimeoutError('No se pudieron detener todos los procesos de la actividad.')
    except psutil.NoSuchProcess:
        pass


def pause_tree(pid, paused):
    if os.name != 'nt':
        os.killpg(pid, signal.SIGSTOP if paused else signal.SIGCONT)
        return
    try:
        parent = psutil.Process(pid)
        members = [parent, *parent.children(recursive=True)]
        for process in members:
            try:
                process.suspend() if paused else process.resume()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess as exc:
        raise ProcessLookupError(pid) from exc


def snapshot():
    if os.name == 'nt':
        return {p.pid: (p.info['ppid'], 0)
                for p in psutil.process_iter(['ppid']) if p.info['ppid'] is not None}
    result = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            result[int(path.parent.name)] = (int(fields[1]), int(fields[2]))
        except (OSError, ValueError, IndexError):
            continue
    return result


def memory_mb(pids):
    total = 0
    for pid in pids:
        if os.name == 'nt':
            try:
                total += psutil.Process(pid).memory_full_info().uss / 1024**2
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        else:
            try:
                text = (Path('/proc') / str(pid) / 'smaps_rollup').read_text()
                total += next(int(line.split()[1]) for line in text.splitlines()
                              if line.startswith('Pss:')) / 1024
            except (OSError, ValueError, StopIteration):
                pass
    return total


def windows_workers(activity_ids, root):
    """Read arguments only for Python candidates and match activity AND store."""
    for process in psutil.process_iter(['name']):
        if not (process.info['name'] or '').lower().startswith('python'):
            continue
        try:
            args = process.cmdline()
            if 'src.persistent.worker' not in args or '--activity' not in args or '--root' not in args:
                continue
            if args[args.index('--activity') + 1] in activity_ids and Path(
                    args[args.index('--root') + 1]).resolve() == Path(root).resolve():
                yield process
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, IndexError):
            continue
