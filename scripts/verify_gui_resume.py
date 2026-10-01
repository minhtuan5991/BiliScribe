"""Exercise cancel, checkpoint resume and preview using the real frozen worker."""
import json, os, sys, time, threading
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
work=root/'verification/v1.2.2/gui-resume';work.mkdir(parents=True,exist_ok=True)
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['BILISCRIBE_DATA_DIR']=str(work/'appdata')
from biliscribe.media import extract_chunk
clip=work/'【完结短剧】规则怪谈 [a052c382].wav'
extract_chunk(root/'release/Mau-kiem-thu/audio.mp3',clip,0,60,threading.Event())
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from biliscribe import ui
app=QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf','msyh.ttc'):
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
app.setStyle('Fusion');app.setStyleSheet(ui.STYLE)
ui.sys=SimpleNamespace(frozen=True,executable=str(root/'dist/BiliScribe-1.2.2/BiliScribe.exe'))
win=ui.MainWindow();win.show()
win.local_files=[str(clip)];win.output.setText(str(work/'result'))
win.profile.setCurrentIndex(win.profile.findData('fast'))
win.model.setCurrentIndex(win.model.findData('auto'))
win.device.setCurrentIndex(win.device.findData('cpu'))
win.force.setChecked(True)
start=time.monotonic();result={};state={'phase':'first','cancelled':False}
win.start_btn.click()
def poll():
    elapsed=time.monotonic()-start
    if elapsed>120:
        result['timeout']=True
        if win.proc:win._force_stop(win.proc)
        else:win.close();app.quit()
        return
    if state['phase']=='first' and not state['cancelled'] and win.row_progress.get(0,0)>26:
        result['job_assigned']=bool(win.job and win.job.handle)
        state['cancelled']=True;state['cancel_time']=elapsed;win.stop_btn.click()
    if win.proc is not None:return
    if state['phase']=='first':
        result['cancel_status']=win.status.text()
        result['cancel_latency']=round(elapsed-state.get('cancel_time',elapsed),2)
        checkpoints=list((work/'result').glob('*/checkpoint_zh.json'))
        result['saved_chunks']=json.loads(checkpoints[0].read_text('utf-8'))['finished'] if checkpoints else 0
        state['phase']='resume';win.force.setChecked(False);win.start_btn.click()
    elif state['phase']=='resume':
        result.update(resume_status=win.status.text(),reused_checkpoint='Tiếp tục từ đoạn' in win.log.toPlainText(),
                      preview_chars=len(win.preview.toPlainText()),buttons_enabled=win.srt_btn.isEnabled() and win.open_txt_btn.isEnabled(),
                      input_unlocked=win.urls.isEnabled(),elapsed=round(elapsed,2))
        result['folder_name']=win.last_folder.name
        assert win.last_folder.name=='Những câu chuyện kỳ lạ về luật lệ - 规则怪谈'
        result['final_files']=sorted(p.name for p in win.last_folder.iterdir())
        assert result['final_files']==['doi_chieu_zh.txt','transcript_zh.srt','transcript_zh.txt']
        assert clip.is_file() and not (work/'result/.biliscribe-cache').exists()
        win.grab().save(str(work/'gui-resume.png'))
        (work/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
        win.close();app.quit()
timer=QTimer();timer.timeout.connect(poll);timer.start(100)
app.exec()
assert result.get('job_assigned') and result.get('saved_chunks',0)>0 and result.get('reused_checkpoint'), result
assert result.get('buttons_enabled') and result.get('input_unlocked') and result.get('preview_chars',0)>100 and not result.get('timeout'),result
assert 'Đã dừng' in result['cancel_status'] and '1 thành công' in result['resume_status'],result
print(json.dumps(result,ensure_ascii=False))
