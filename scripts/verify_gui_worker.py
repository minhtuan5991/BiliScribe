"""Exercise QProcess launch, JSON event delivery and cancellation against the frozen worker."""
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['BILISCRIBE_DATA_DIR'] = str(root / 'verification/bridge-data')
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from biliscribe import ui

app = QApplication([])
for name in ('segoeui.ttf', 'segoeuib.ttf', 'msyh.ttc'):
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name))
app.setStyle('Fusion')
app.setStyleSheet(ui.STYLE)
ui.sys = SimpleNamespace(frozen=True, executable=str(root / 'dist/BiliScribe-1.1.1/BiliScribe.exe'))
win = ui.MainWindow()
win.show()
request = json.loads((root / 'verification/full-request.json').read_text('utf-8-sig'))
request['settings']['output_dir'] = str(root / 'verification/bridge-output')
request['settings']['force'] = True
started = time.monotonic()
result = {}
win._launch(request, 'transcribe')

def cancel():
    result['job_object_assigned'] = bool(win.job and win.job.handle)
    result['worker_started'] = win.proc is not None
    win._cancel()

def poll():
    if win.proc is None:
        result['cancel_completed'] = True
        result['status'] = win.status.text()
        result['events_received'] = bool(win.log.toPlainText().find('RAM') >= 0)
        result['elapsed'] = round(time.monotonic() - started, 2)
        win.grab().save(str(root / 'verification/gui-worker-cancel.png'))
        (root / 'verification/gui-worker-test.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
        win.close()
        app.quit()
    elif time.monotonic() - started > 25:
        result['timeout'] = True
        win._force_stop(win.proc)

QTimer.singleShot(1800, cancel)
timer = QTimer()
timer.timeout.connect(poll)
timer.start(100)
QTimer.singleShot(30000, app.quit)
app.exec()
assert result.get('worker_started') and result.get('cancel_completed') and not result.get('timeout'), result
print(json.dumps(result, ensure_ascii=False))
