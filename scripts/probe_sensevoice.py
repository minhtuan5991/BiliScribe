import json, os, sys, time, threading, wave
from pathlib import Path
root=Path.cwd(); sys.path.insert(0,str(root))
from biliscribe.media import extract_chunk
import numpy as np, sherpa_onnx, psutil
folder=root/'model-cache/sensevoice-small'
t0=time.monotonic()
r=sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(folder/'model.int8.onnx'), tokens=str(folder/'tokens.txt'),num_threads=4,language='zh',use_itn=True)
print('Loaded',round(time.monotonic()-t0,2),flush=True)
audio=root/'release/Mau-kiem-thu/audio.mp3'
work=root/'verification/v1.0.1'; rows=[]
for start in range(0,90,28):
    wav=work/'sense-test.wav'
    left=max(0,start-1); end=min(90,start+29)
    extract_chunk(audio,wav,left,end-left,threading.Event())
    with wave.open(str(wav),'rb') as f: samples=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
    stream=r.create_stream(); stream.accept_waveform(16000,samples)
    t=time.monotonic(); r.decode_stream(stream)
    result=stream.result
    row={'left':left,'owner_start':start,'owner_end':min(90,start+28),'seconds':round(time.monotonic()-t,3),'text':result.text,'tokens':result.tokens,'timestamps':result.timestamps,'result':str(result),'rss_mb':psutil.Process().memory_info().rss/2**20}
    rows.append(row); print(row['seconds'],row['rss_mb'],result.text,flush=True)
(work/'sensevoice-probe.json').write_text(json.dumps({'elapsed':time.monotonic()-t0,'chunks':rows},ensure_ascii=False,indent=2),encoding='utf-8')
wav.unlink(missing_ok=True)
