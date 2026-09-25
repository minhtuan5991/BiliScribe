from pathlib import Path
import json, os, sys, threading, time
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
from biliscribe.config import Settings
from biliscribe.pipeline import process_batch
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--seconds',type=int,default=8)
parser.add_argument('--workers',type=int,default=1)
parser.add_argument('--label',default='short')
parser.add_argument('--frozen',action='store_true')
args=parser.parse_args()
work=root/('verification/v1.2.0/pixazo-live-'+args.label)
work.mkdir(parents=True,exist_ok=True)
os.environ['BILISCRIBE_DATA_DIR']=str(work/'data')
cfg=Settings.from_dict({'profile':'pixazo','pixazo_workers':args.workers,'preview_seconds':args.seconds,'output_dir':str(work/'result'),'force':True})
events=[]
def emit(kind,**data):
    events.append({'event':kind,**data})
    if kind in {'result','done','fatal','log'}:print(json.dumps({'event':kind,**data},ensure_ascii=False),flush=True)
start=time.monotonic()
sources=[str(root/'release/Mau-kiem-thu/audio.mp3')]
if args.frozen:
    import subprocess
    from dataclasses import asdict
    from biliscribe.windows import ProcessJob
    request=work/'request.json'
    request.write_text(json.dumps({'sources':sources,'settings':asdict(cfg)},ensure_ascii=False),'utf-8')
    secret=os.environ.get('BILISCRIBE_PIXAZO_KEY','')
    assert secret and secret not in request.read_text('utf-8')
    with (work/'stderr.log').open('w',encoding='utf-8') as err:
        proc=subprocess.Popen([str(root/'dist/BiliScribe-1.2.0/BiliScribeWorker.exe'),'--worker',str(request)],
            cwd=work,env=os.environ.copy(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        job=ProcessJob(proc.pid)
        def read():
            for line in proc.stdout:
                data=json.loads(line)
                emit(data.pop('event'),**data)
        reader=threading.Thread(target=read,daemon=True);reader.start()
        try:
            code=proc.wait(timeout=240)
            reader.join(3)
        finally:
            job.close()
            if proc.poll() is None:proc.kill();proc.wait(timeout=5)
        assert secret not in json.dumps(events,ensure_ascii=False)
        assert secret not in (work/'stderr.log').read_text('utf-8')
else:
    code=process_batch(sources,cfg,emit,threading.Event())
(work/'events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),'utf-8')
summary={'exit_code':code,'elapsed':round(time.monotonic()-start,2),'real_api':True,'audio_seconds':args.seconds,'workers':args.workers,'frozen':args.frozen}
results=[e for e in events if e['event']=='result']
if results:
    folder=Path(results[0]['folder']);summary.update(folder=str(folder),files=sorted(p.name for p in folder.iterdir()),text=(folder/'transcript_zh.txt').read_text('utf-8-sig'))
if code==0:
    assert results and summary['files']==['doi_chieu_zh.txt','transcript_zh.srt','transcript_zh.txt']
    assert not (work/'result/.biliscribe-cache').exists()
    import re
    pairs=re.findall(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})',(folder/'transcript_zh.srt').read_text('utf-8-sig'))
    def seconds(t):
        h,m,s=t.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(s)
    times=[(seconds(a),seconds(b)) for a,b in pairs]
    assert times and all(0<=a<b<=args.seconds+.001 for a,b in times)
    assert all(a[1]<=b[0] for a,b in zip(times,times[1:]))
    summary.update(cues=len(times),last_end=times[-1][1],cache_removed=True,times_monotonic=True)
(work/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(summary,ensure_ascii=False))
sys.exit(code)
