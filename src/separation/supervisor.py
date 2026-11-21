"""Supervisor Linux de uma operação. Recolhe inclusive netos de workers interrompidos."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time

import psutil

from .process_shield import apply_process_shield


def _terminate_descendants(group: int) -> None:
    try:
        os.killpg(group, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process = psutil.Process()
    while True:
        for child in reversed(process.children(recursive=True)):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if not pid:
            time.sleep(.01)


def main() -> int:
    cancelled = False

    def cancel(sig, frame):
        nonlocal cancelled
        cancelled = True

    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    parent = int(os.environ["ATMOSSPLIT_PARENT_PID"])
    prctl = ctypes.CDLL(None, use_errno=True).prctl
    for option, value in ((36, 1), (1, signal.SIGTERM)):  # CHILD_SUBREAPER, PDEATHSIG
        if prctl(option, value, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "Falha ao isolar a árvore do worker")
    if os.getppid() != parent or cancelled:
        return 130
    apply_process_shield()
    worker = subprocess.Popen([sys.executable, *sys.argv[1:]], start_new_session=True)
    try:
        while not cancelled:
            status = worker.poll()
            if status is not None:
                return status
            time.sleep(.025)
        return 130
    finally:
        _terminate_descendants(worker.pid)
        worker.wait()


if __name__ == "__main__":
    sys.exit(main())
