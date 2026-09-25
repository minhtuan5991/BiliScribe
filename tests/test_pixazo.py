import asyncio
import json
import os
import threading
import wave
from dataclasses import asdict
from pathlib import Path

import pytest
from biliscribe.config import Settings
from biliscribe.hardware import Plan
from biliscribe.media import Cancelled
from biliscribe.transcribe import Segment
from biliscribe.pixazo import EventCollector, PixazoError, PixazoTranscriber, api_error, split_ranges

def audio(path, seconds=.3):
    with wave.open(str(path),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(bytes(int(seconds*16000)*2))

def test_ranges_cover_audio_once_and_align_silence():
    ranges=split_ranges(535.68,3,[179.1,355.2])
    assert len(ranges)==3 and ranges[0][1]==179.1
    for duration in (1,31,60,535.68,3600,43200):
        for workers in (1,2,3,4):
            ranges=split_ranges(duration,workers)
            assert ranges[0][0]==0 and ranges[-1][1]==duration
            assert all(0<b-a<=310 for a,b in ranges)
            assert all(a[1]==b[0] for a,b in zip(ranges,ranges[1:]))

def test_protocol_final_replaces_partial_and_duplicate_final_is_ignored():
    c=EventCollector(10)
    c.feed({'type':'input_audio_buffer.speech_started','item_id':'a','audio_start_ms':100},.5)
    c.feed({'type':'conversation.item.input_audio_transcription.text','item_id':'a','text':'wrong'},1)
    c.feed({'type':'input_audio_buffer.speech_stopped','item_id':'a','audio_end_ms':1500},2)
    final={'type':'conversation.item.input_audio_transcription.completed','item_id':'a','transcript':'正确。'}
    c.feed(final,2);c.feed(final,2)
    c.feed({'type':'input_audio_buffer.committed','item_id':'a'},2)
    assert not c.pending and c.finals==1
    assert [(s.start,s.end,s.text) for s in c.segments()]==[(.1,1.5,'正确。')]

def test_fallback_timestamps_use_utterance_boundaries():
    c=EventCollector(10)
    c.feed({'type':'conversation.item.input_audio_transcription.text','item_id':'a','text':'p'},2)
    c.feed({'type':'conversation.item.input_audio_transcription.completed','item_id':'a','transcript':'一。'},3)
    c.feed({'type':'conversation.item.input_audio_transcription.completed','item_id':'b','transcript':'二。'},6)
    assert [(s.start,s.end) for s in c.segments()]==[(0,3),(3,6)]

@pytest.mark.parametrize('status',[401,402,403,429,503])
def test_friendly_errors_without_raw_payload(status):
    exc=api_error(status)
    assert 'Pixazo' in str(exc) and exc.retryable==(status in {429,503})

def test_real_websocket_protocol_and_final_flush(tmp_path,monkeypatch):
    import biliscribe.pixazo as pixazo
    from websockets.asyncio.server import serve
    path=tmp_path/'sample.wav';audio(path)
    monkeypatch.setattr(pixazo,'QUIET_SECONDS',.01)
    messages=[]
    async def handler(ws):
        assert ws.request.headers['Ocp-Apim-Subscription-Key']=='test-secret'
        assert 'test-secret' not in ws.request.path
        msg=json.loads(await ws.recv());messages.append(msg)
        assert msg['session']['input_audio_transcription']['language']=='zh'
        await ws.send(json.dumps({'type':'session.updated'}))
        started=False
        async for raw in ws:
            msg=json.loads(raw);messages.append(msg)
            if msg['type']=='input_audio_buffer.append' and not started:
                started=True
                await ws.send(json.dumps({'type':'input_audio_buffer.speech_started','item_id':'one','audio_start_ms':0}))
                await ws.send(json.dumps({'type':'conversation.item.input_audio_transcription.text','item_id':'one','text':'未定'}))
            if msg['type']=='input_audio_buffer.commit':
                await ws.send(json.dumps({'type':'input_audio_buffer.speech_stopped','item_id':'one','audio_end_ms':300}))
                await ws.send(json.dumps({'type':'input_audio_buffer.committed','item_id':'one'}))
                await asyncio.sleep(.05)
                await ws.send(json.dumps({'type':'conversation.item.input_audio_transcription.completed','item_id':'one','transcript':'你好。'}))
    async def run():
        async with serve(handler,'127.0.0.1',0) as server:
            monkeypatch.setattr(pixazo,'ENDPOINT',f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/stream?language=zh')
            return await pixazo.stream_chunk(path,'test-secret',threading.Event(),lambda n:None)
    result=asyncio.run(run())
    assert ''.join(s.text for s in result)=='你好。'
    assert result[-1].end==.3
    assert messages[-1]['type']=='input_audio_buffer.commit'

@pytest.mark.parametrize('failure',[True,False])
def test_parallel_checkpoint_resume_and_order(tmp_path,monkeypatch,failure):
    import biliscribe.pixazo as pixazo
    monkeypatch.setenv('BILISCRIBE_PIXAZO_KEY','secret-not-in-files')
    cfg=Settings.from_dict({'profile':'pixazo','pixazo_workers':3,'script':'original'})
    plan=Plan('qwen3-asr-flash-realtime','api','pcm',3,3,0)
    source=tmp_path/'input.wav';audio(source)
    folder=tmp_path/'result';folder.mkdir();work=tmp_path/'work';work.mkdir()
    item={'folder':folder,'work':work,'duration':90,'media':source,'source':str(source)}
    monkeypatch.setattr(pixazo,'find_silences',lambda *a:[])
    monkeypatch.setattr(pixazo,'extract_chunk',lambda src,out,*a:audio(out))
    calls=[];active=[0];peak=[0]
    async def stream(path,key,cancel,progress):
        k=int(path.stem.split('-')[1]);calls.append(k);active[0]+=1;peak[0]=max(peak[0],active[0])
        try:
            for _ in range(100):
                if peak[0]>=3:break
                await asyncio.sleep(.005)
            await asyncio.sleep(.06 if k==0 else .01)
            if failure and k==1:raise PixazoError('mid-stream failure')
            return [Segment(0,29,f'段{k}。')]
        finally:active[0]-=1
    monkeypatch.setattr(pixazo,'stream_chunk',stream)
    engine=PixazoTranscriber(cfg,plan,lambda *a,**k:None,threading.Event())
    if failure:
        with pytest.raises(PixazoError):engine.transcribe(item,0)
        cp=json.loads((folder/'checkpoint_pixazo.json').read_text('utf-8'))
        assert set(cp['completed'])=={'0','2'}
        failure=False;calls.clear()
        result,_=engine.transcribe(item,0)
        assert calls==[1]
    else:result,_=engine.transcribe(item,0)
    assert peak[0]==3
    assert [s.text for s in result]==['段0。','段1。','段2。']
    assert [s.start for s in result]==[0,30,60]
    assert 'secret-not-in-files' not in (folder/'checkpoint_pixazo.json').read_text('utf-8')

def test_credentials_encrypted_and_settings_have_no_key(tmp_path,monkeypatch):
    from biliscribe.credentials import load_key,save_key
    monkeypatch.setenv('BILISCRIBE_DATA_DIR',str(tmp_path))
    save_key('unit-secret-should-not-be-plaintext')
    assert load_key()=='unit-secret-should-not-be-plaintext'
    assert b'unit-secret' not in (tmp_path/'pixazo-key.dpapi').read_bytes()
    assert not any('key' in k for k in asdict(Settings()))
    save_key('');assert load_key()==''

def test_api_pipeline_avoids_gpu_detection_and_keeps_three_files(tmp_path,monkeypatch):
    import biliscribe.pipeline as pipeline
    from biliscribe.config import source_key
    monkeypatch.setenv('BILISCRIBE_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('BILISCRIBE_PIXAZO_KEY','test-only')
    def forbidden():raise AssertionError('API must not initialize local GPU')
    monkeypatch.setattr(pipeline,'detect_hardware',forbidden)
    folder=tmp_path/f'test [{source_key("source")[:8]}]';folder.mkdir()
    work=tmp_path/'.biliscribe-cache'/source_key('source');work.mkdir(parents=True)
    item={'source':'source','title':'test','duration':1,'folder':folder,'work':work}
    monkeypatch.setattr(pipeline,'prepare_source',lambda *args:item)
    monkeypatch.setattr(PixazoTranscriber,'transcribe',lambda *a:([Segment(0,1,'你好。')],1))
    cfg=Settings.from_dict({'profile':'pixazo','output_dir':str(tmp_path)})
    assert pipeline.process_batch(['source'],cfg,lambda *a,**k:None,threading.Event())==0
    assert sorted(p.name for p in folder.iterdir())==['doi_chieu_zh.txt','transcript_zh.srt','transcript_zh.txt']
    assert not work.exists()


def test_live_empty_commit_does_not_discard_final_or_pending():
    c=EventCollector(8)
    c.feed({'type':'input_audio_buffer.speech_started','item_id':'x','audio_start_ms':0},.1)
    c.flush_requested=True
    event={'type':'error','error':{'type':'invalid_request_error','message':'Error committing input audio buffer, maybe no invalid audio stream.'}}
    c.feed(event,8)
    assert c.commit_ack and c.pending=={'x'}
    c.feed({'type':'input_audio_buffer.speech_stopped','item_id':'x','audio_end_ms':8000},8)
    c.feed({'type':'conversation.item.input_audio_transcription.completed','item_id':'x','transcript':'你好。'},8)
    assert not c.pending and c.segments()[0].text=='你好。'
    unexpected=EventCollector(8)
    with pytest.raises(PixazoError):unexpected.feed(event,0)


def test_pending_final_timeout_never_returns_partial(tmp_path,monkeypatch):
    import biliscribe.pixazo as pixazo
    from websockets.asyncio.server import serve
    path=tmp_path/'sample.wav';audio(path,.1)
    monkeypatch.setattr(pixazo,'DRAIN_TIMEOUT',.15)
    async def handler(ws):
        await ws.recv();await ws.send(json.dumps({'type':'session.updated'}))
        async for raw in ws:
            msg=json.loads(raw)
            if msg['type']=='input_audio_buffer.commit':
                await ws.send(json.dumps({'type':'input_audio_buffer.committed','item_id':'lost'}))
    async def run():
        async with serve(handler,'127.0.0.1',0) as server:
            monkeypatch.setattr(pixazo,'ENDPOINT',f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}')
            with pytest.raises(PixazoError,match='chưa trả đủ'):
                await pixazo.stream_chunk(path,'test',threading.Event(),lambda _:None)
    asyncio.run(run())


def test_cancel_active_api_stream_promptly(tmp_path,monkeypatch):
    import biliscribe.pixazo as pixazo
    from websockets.asyncio.server import serve
    path=tmp_path/'sample.wav';audio(path,10)
    cancel=threading.Event()
    async def handler(ws):
        await ws.recv();await ws.send(json.dumps({'type':'session.updated'}))
        await ws.recv();cancel.set()
        await ws.wait_closed()
    async def run():
        async with serve(handler,'127.0.0.1',0) as server:
            monkeypatch.setattr(pixazo,'ENDPOINT',f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}')
            with pytest.raises(Cancelled):
                await asyncio.wait_for(pixazo.stream_chunk(path,'test',cancel,lambda _:None),2)
    asyncio.run(run())
