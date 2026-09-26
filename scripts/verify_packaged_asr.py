"""Run the frozen CPU engine with an empty app-data directory and offline HF settings."""
import json
import sys
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
import psutil

root = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
work = root / 'verification/v1.2.1/packaged-cpu'
work.mkdir(parents=True, exist_ok=True)
request = {
    'sources': [str(root / 'release/Mau-kiem-thu/audio.mp3')],
    'settings': {'profile': 'fast', 'device': 'cpu', 'model': 'auto', 'force': True,
                 'output_dir': str(work / 'result'), 'cache_dir': str(work / 'empty-model-cache')},
}
(work / 'request.json').write_text(json.dumps(request, ensure_ascii=False), 'utf-8')
env = os.environ.copy()
env.update(BILISCRIBE_DATA_DIR=str(work/'appdata'), HF_HUB_OFFLINE='1',
           HTTP_PROXY='http://127.0.0.1:9', HTTPS_PROXY='http://127.0.0.1:9',
           ALL_PROXY='http://127.0.0.1:9', NO_PROXY='',
           PATH=str(Path(os.environ['WINDIR'])/'System32'))
for key in ('VIRTUAL_ENV', 'PYTHONHOME', 'PYTHONPATH'):
    env.pop(key, None)
t0 = time.monotonic()
events = queue.Queue()
with (work/'stderr.log').open('w', encoding='utf-8') as err:
    proc = subprocess.Popen([str(root/'dist/BiliScribe-1.2.1/BiliScribeWorker.exe'), '--worker', str(work/'request.json')],
        cwd=work, env=env, stdout=subprocess.PIPE, stderr=err, stdin=subprocess.PIPE,
        text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
    def read():
        for line in proc.stdout:
            try:
                row=json.loads(line)
                event={'elapsed': round(time.monotonic()-t0,3), **row}
                events.put(event)
                with (work/'live.jsonl').open('a',encoding='utf-8') as live:
                    live.write(json.dumps(event,ensure_ascii=False)+'\n')
            except ValueError:
                pass
    reader=threading.Thread(target=read,daemon=True); reader.start()
    peak=0
    while proc.poll() is None:
        try:
            parent=psutil.Process(proc.pid)
            total=parent.memory_info().rss + sum(c.memory_info().rss for c in parent.children(recursive=True) if c.is_running())
            peak=max(peak,total)
        except psutil.Error:
            pass
        if time.monotonic()-t0>600:
            for child in psutil.Process(proc.pid).children(recursive=True): child.kill()
            proc.kill(); raise RuntimeError('Frozen CPU test exceeded 10 minutes')
        time.sleep(.1)
    reader.join(3)
rows=[]
while not events.empty(): rows.append(events.get())
(work/'events.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf-8')
completed=[x for x in rows if x['event']=='result']
assert proc.returncode==0 and completed, rows[-3:]
folder=Path(completed[0]['folder'])
from biliscribe.output_cleanup import FINAL_FILES
import re
assert {p.name for p in folder.iterdir()} == FINAL_FILES
assert not (folder.parent/'.biliscribe-cache').exists()
text=(folder/'transcript_zh.txt').read_text('utf-8-sig')
duration=completed[0]['duration']
def seconds(value):
    h,m,s=value.replace(',', '.').split(':')
    return int(h)*3600+int(m)*60+float(s)
pairs=re.findall(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', (folder/'transcript_zh.srt').read_text('utf-8-sig'))
segments=[{'start':seconds(a),'end':seconds(b)} for a,b in pairs]
assert len(text)>3000 and segments[-1]['end']>duration-4
assert all(0<=s['start']<s['end']<=duration+0.001 for s in segments)
assert all(a['end']<=b['start'] for a,b in zip(segments,segments[1:]))
assert completed[0]['model']=='sensevoice-small'
assert any('có sẵn' in x.get('message','') for x in rows)
progress=[x['progress'] for x in rows if x['event']=='item' and x.get('active')]
assert progress==sorted(progress)
summary={'exit_code':proc.returncode, 'elapsed_seconds':round(time.monotonic()-t0,2),
         'peak_worker_and_children_rss_mb':round(peak/2**20,1), 'audio_seconds':duration,
         'segments':len(segments), 'characters':len(text), 'last_end':segments[-1]['end'],
         'offline_hf':True,'external_proxy_unreachable':True,'empty_model_cache':not (work/'empty-model-cache').exists(),
         'system_only_path':True,'timing_monotonic':True,'progress_monotonic':True,'output':str(folder), 'final_files':sorted(FINAL_FILES), 'cache_removed':True}
(work/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(summary,ensure_ascii=False))
