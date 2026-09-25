import os
import queue
import subprocess
import sys
import threading

import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows pipe / CRT regression')
def test_numpy_import_and_cancellation_with_open_stdin_pipe():
    # Keep stdin open like QProcess does. communicate() would close it and hide the bug.
    code = '''
import threading, time
from biliscribe.worker_control import listen_cancel
stop = threading.Event()
threading.Thread(target=listen_cancel, args=(stop,), daemon=True).start()
time.sleep(0.2)
import numpy
import onnxruntime
print('runtime-ready', flush=True)
assert stop.wait(10), 'Cancel command was not received'
print('cancelled', flush=True)
'''
    p = subprocess.Popen([sys.executable, '-X', 'utf8', '-c', code], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    lines = queue.Queue()
    def read():
        for line in p.stdout:
            lines.put(line.strip())
    threading.Thread(target=read, daemon=True).start()
    try:
        assert lines.get(timeout=20) == 'runtime-ready'
        # Partial writes must not block native initialization or lose a command.
        p.stdin.write('can'); p.stdin.flush()
        p.stdin.write('cel\n'); p.stdin.flush()
        assert lines.get(timeout=3) == 'cancelled'
        assert p.wait(timeout=5) == 0
    finally:
        if p.poll() is None:
            p.kill(); p.wait()
        p.stdin.close(); p.stdout.close(); p.stderr.close()
