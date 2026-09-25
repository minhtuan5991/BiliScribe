import json, os, sys, time
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['BILISCRIBE_DATA_DIR']=str(root/'verification/appdata')
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from biliscribe import ui
app=QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf','msyh.ttc'):
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
app.setStyle('Fusion'); app.setStyleSheet(ui.STYLE)
ui.sys=SimpleNamespace(frozen=True,executable=str(root/'dist/BiliScribe-1.1.1/BiliScribe.exe'))
win=ui.MainWindow(); win.show()
win.urls.setPlainText('https://www.bilibili.com/video/BV1sDLG6DED3/?p=1')
win.output.setText(str(root/'verification/v1.1.1/quality-result'))
win.cache_path.setText(str(root/'model-cache'))
win.profile.setCurrentIndex(win.profile.findData('quality'))
win.model.setCurrentIndex(win.model.findData('large-v3'))
win.device.setCurrentIndex(win.device.findData('auto'))
win.force.setChecked(False)
start=time.monotonic()
win.start_btn.click()
result={}
def poll():
    if win.proc is None:
        result.update(status=win.status.text(), elapsed=round(time.monotonic()-start,2), preview_chars=len(win.preview.toPlainText()), reused_checkpoint=('Tiếp tục từ đoạn' in win.log.toPlainText()), input_locked_after_finish=not win.urls.isEnabled(), compare_enabled=win.compare_btn.isEnabled(), audio_enabled=win.audio_btn.isEnabled())
        win.grab().save(str(root/'release/Giao-dien-1.1.1.png'))
        (root/'verification/v1.1.1/cached-gui-test.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
        win.close(); app.quit()
    elif time.monotonic()-start>45:
        result['timeout']=True; win._force_stop(win.proc)
timer=QTimer();timer.timeout.connect(poll);timer.start(100)
app.exec()
assert result.get('compare_enabled') and result.get('audio_enabled') and result.get('reused_checkpoint') and result.get('preview_chars',0)>100 and not result.get('input_locked_after_finish') and not result.get('timeout'),result
print(json.dumps(result,ensure_ascii=False))
