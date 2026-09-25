from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import re
import subprocess
import tempfile
import time
import wave
from dataclasses import asdict
from pathlib import Path

from .config import atomic_text, source_key
from .media import Cancelled, binary, check_cancel, extract_chunk
from .transcribe import Segment, clean_zh, paragraphs

ENDPOINT = "wss://asr-stream.pixazo.ai/v1/stream?language=zh"
FRAME_SECONDS = .1
FRAME_SAMPLES = 1600
DRAIN_TIMEOUT = 35
QUIET_SECONDS = 2

class PixazoError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable

def api_error(status):
    messages = {
        401: "Pixazo: API key không hợp lệ hoặc đã hết hiệu lực.",
        403: "Pixazo: API key chưa có quyền dùng nhận dạng âm thanh.",
        402: "Pixazo: tài khoản chưa đủ credit để mở phiên. Giảm số luồng hoặc kiểm tra số dư.",
        429: "Pixazo đang giới hạn số kết nối. Hãy giảm số luồng và chạy tiếp.",
    }
    return PixazoError(messages.get(status, "Không kết nối được Pixazo. Kiểm tra mạng và thử chạy tiếp."), status in {429, 500, 502, 503, 504})

def split_ranges(duration, workers, silences=()):
    count = max(math.ceil(duration / 300), min(workers, max(1, math.ceil(duration / 30))))
    target = duration / count
    points = [0.0]
    for i in range(1, count):
        wanted = target * i
        near = [x for x in silences if abs(x-wanted) <= min(8, target*.2) and x > points[-1]+1 and x-points[-1] <= 310]
        points.append(min(near, key=lambda x: abs(x-wanted)) if near else wanted)
    points.append(duration)
    return [(round(a,3),round(b,3)) for a,b in zip(points,points[1:])]

def find_silences(media, duration, cancel):
    """One fast FFmpeg scan; no ML runtime or decoded whole-file buffer."""
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen([binary("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(media), "-t", str(duration),
                                 "-vn", "-af", "silencedetect=noise=-35dB:d=0.25", "-f", "null", "-"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
                                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        started = time.monotonic()
        try:
            while proc.poll() is None:
                check_cancel(cancel)
                if time.monotonic()-started > 90:
                    return []
                cancel.wait(.1)
            log.seek(0)
            text = log.read().decode("utf-8", "replace")
            return [float(end)-float(length)/2 for end,length in re.findall(r"silence_end: ([0-9.]+) \| silence_duration: ([0-9.]+)",text)]
        finally:
            if proc.poll() is None:
                proc.kill(); proc.wait(timeout=5)

class EventCollector:
    def __init__(self, duration):
        self.duration = duration
        self.items = {}
        self.order = []
        self.pending = set()
        self.commit_ack = False
        self.flush_requested = False
        self.last_event = time.monotonic()
        self.finals = 0

    def feed(self, msg, sent):
        self.last_event = time.monotonic()
        kind = msg.get("type", "")
        ident = str(msg.get("item_id") or "")
        if kind == "error":
            error = msg.get("error", {})
            code = str(error.get("code", "")) if isinstance(error,dict) else ""
            message = str(error.get("message", "")) if isinstance(error,dict) else ""
            empty_vad_commit = self.flush_requested and message == "Error committing input audio buffer, maybe no invalid audio stream."
            if code in {"input_audio_buffer_commit_empty", "input_audio_buffer_too_small"} or empty_vad_commit:
                self.commit_ack = True
                return
            # Never print raw server messages: they can echo credentials/payloads.
            raise PixazoError("Pixazo từ chối đoạn âm thanh. Kiểm tra quyền API, credit và thử chạy tiếp.")
        if kind == "input_audio_buffer.committed":
            self.commit_ack = True
            if ident and ident not in self.items:
                self.pending.add(ident)
        if kind in {"input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped"} or "transcription." in kind:
            if not ident:
                raise PixazoError("Pixazo trả sự kiện thiếu mã đoạn; giữ tiến độ để kiểm tra lại.")
            if ident not in self.items:
                self.items[ident] = {"start": max((x["end"] for x in self.items.values() if x["final"]), default=0), "end": min(self.duration,sent), "text": "", "final": False, "timed_end": False}
                self.order.append(ident)
            item = self.items[ident]
            if item["final"]:
                return
            if kind == "input_audio_buffer.speech_started":
                item["start"] = max(0,min(self.duration,float(msg.get("audio_start_ms",sent*1000))/1000))
            elif kind == "input_audio_buffer.speech_stopped":
                item["end"] = max(item["start"],min(self.duration,float(msg.get("audio_end_ms",sent*1000))/1000))
                item["timed_end"] = True
            elif kind.endswith("transcription.completed"):
                if not isinstance(msg.get("transcript"),str):
                    raise PixazoError("Pixazo trả bản chép lời không hợp lệ.")
                item["text"] = msg["transcript"]
                if not item["final"]: self.finals += 1
                item["final"] = True
                item["end"] = min(self.duration,sent) if not item["timed_end"] else item["end"]
                self.pending.discard(ident)
                return
            self.pending.add(ident)

    def segments(self):
        records=[]
        for ident in self.order:
            row=self.items[ident]
            text=clean_zh(row["text"])
            if not row["final"] or not text: continue
            start=max(records[-1].end if records else 0,row["start"])
            end=min(self.duration,max(start+.001,row["end"]))
            if end <= start:
                raise PixazoError("Pixazo trả mốc thời gian không hợp lệ; chưa đánh dấu hoàn tất.")
            records.append(Segment(round(start,3),round(end,3),text))
        return records

async def stream_chunk(path, key, cancel, progress):
    from websockets.asyncio.client import connect
    from websockets.exceptions import InvalidStatus, ConnectionClosed
    collector=None
    sent_audio=False
    try:
        async with connect(ENDPOINT, additional_headers={"Ocp-Apim-Subscription-Key":key},
                           compression=None, open_timeout=30, close_timeout=2, max_size=2**20,
                           ping_interval=20, ping_timeout=20) as ws:
            with wave.open(str(path),"rb") as audio:
                duration=audio.getnframes()/audio.getframerate()
                if (audio.getframerate(),audio.getnchannels(),audio.getsampwidth()) != (16000,1,2):
                    raise PixazoError("Định dạng âm thanh tạm không hợp lệ.")
                collector=EventCollector(duration)
                await ws.send(json.dumps({"type":"session.update","session":{"modalities":["text"],"input_audio_format":"pcm","sample_rate":16000,
                                          "input_audio_transcription":{"language":"zh"},"turn_detection":{"type":"server_vad"}}}))
                # Wait for applied configuration before sending any billed audio.
                deadline=time.monotonic()+15
                while True:
                    if time.monotonic()>deadline: raise PixazoError("Pixazo chưa xác nhận cấu hình tiếng Trung.",True)
                    check_cancel(cancel)
                    try: msg=json.loads(await asyncio.wait_for(ws.recv(),.25))
                    except asyncio.TimeoutError: continue
                    if msg.get("type")=="session.updated": break
                    collector.feed(msg,0)
                state={"sent":0.,"flushed":None}
                async def send():
                    nonlocal sent_audio
                    clock=time.monotonic()
                    frames=0
                    while True:
                        check_cancel(cancel)
                        raw=audio.readframes(FRAME_SAMPLES)
                        if not raw: break
                        sent_audio=True
                        await ws.send(json.dumps({"type":"input_audio_buffer.append","audio":base64.b64encode(raw).decode("ascii")}))
                        frames+=len(raw)//2;state["sent"]=frames/16000
                        progress(min(duration,state["sent"]))
                        await asyncio.sleep(max(0,clock+frames/16000-time.monotonic()))
                    # A short silent tail lets server VAD finalize a sentence at EOF.
                    for _ in range(8):
                        check_cancel(cancel)
                        await ws.send(json.dumps({"type":"input_audio_buffer.append","audio":base64.b64encode(bytes(3200)).decode("ascii")}))
                        await asyncio.sleep(FRAME_SECONDS)
                    # server_vad may already have committed the silent tail.
                    # Avoid committing an empty buffer after the final event.
                    if collector.pending or not collector.finals:
                        collector.flush_requested = True
                        await ws.send(json.dumps({"type":"input_audio_buffer.commit"}))
                    state["flushed"]=time.monotonic()
                sender=asyncio.create_task(send())
                try:
                    while True:
                        check_cancel(cancel)
                        if sender.done(): sender.result()
                        now=time.monotonic()
                        if state["flushed"] is not None:
                            quiet=now-max(collector.last_event,state["flushed"])
                            if not collector.pending and (collector.commit_ack or collector.finals) and quiet>=QUIET_SECONDS:
                                return collector.segments()
                            if now-state["flushed"]>DRAIN_TIMEOUT:
                                raise PixazoError("Pixazo chưa trả đủ kết quả cuối đoạn. Phần đã hoàn tất được giữ; chạy tiếp để thử lại.")
                        try: raw=await asyncio.wait_for(ws.recv(),.25)
                        except asyncio.TimeoutError: continue
                        collector.feed(json.loads(raw),min(duration,state["sent"]))
                finally:
                    sender.cancel()
                    await asyncio.gather(sender,return_exceptions=True)
    except InvalidStatus as exc:
        raise api_error(exc.response.status_code) from None
    except Cancelled:
        raise
    except PixazoError:
        raise
    except (ConnectionClosed, OSError, asyncio.TimeoutError):
        raise PixazoError("Mất kết nối Pixazo. Các đoạn đã hoàn tất được giữ; chạy tiếp để xử lý phần còn lại.", retryable=not sent_audio) from None
    except (ValueError, TypeError, KeyError):
        raise PixazoError("Pixazo trả dữ liệu không hợp lệ; giữ tiến độ để thử lại.") from None

class PixazoTranscriber:
    def __init__(self,cfg,plan,emit,cancel):
        self.cfg,self.plan,self.emit,self.cancel=cfg,plan,emit,cancel
        self.key=os.environ.get("BILISCRIBE_PIXAZO_KEY", "").strip()
        if not self.key: raise PixazoError("Chưa nhập Pixazo API key.")

    def close(self):
        self.key=""

    def transcribe(self,item,index,task="transcribe"):
        duration=min(item["duration"],self.cfg.preview_seconds) if self.cfg.preview_seconds else item["duration"]
        folder,work=item["folder"],item["work"]
        checkpoint=folder/"checkpoint_pixazo.json"
        key="pixazo-v1:"+source_key(item["source"])+":"+self.cfg.script
        saved={};ranges=None
        if checkpoint.exists() and not self.cfg.force:
            try:
                old=json.loads(checkpoint.read_text("utf-8"))
                candidate=old["ranges"]
                if old["key"]==key and old["duration"]==duration and candidate and candidate[0][0]==0 and candidate[-1][1]==round(duration,3) and all(0<b-a<=310 for a,b in candidate) and all(a[1]==b[0] for a,b in zip(candidate,candidate[1:])):
                    ranges=candidate
                    for part,rows in old["completed"].items():
                        k=int(part);left,right=ranges[k]
                        records=[Segment(**s) for s in rows]
                        if all(left<=s.start<s.end<=right+.001 for s in records):saved[k]=records
            except (OSError,KeyError,ValueError,TypeError,IndexError):
                saved={};ranges=None
        if ranges is None:
            self.emit("item",index=index,active=True,stage="Chia đoạn cho Pixazo",progress=25)
            gaps=find_silences(item["media"],duration,self.cancel)
            ranges=split_ranges(duration,self.cfg.pixazo_workers,gaps)
        if saved:self.emit("log",message=f"Tiếp tục Pixazo: giữ {len(saved)}/{len(ranges)} đoạn đã hoàn tất, không gửi lại các đoạn này.")
        if self.cfg.glossary:self.emit("log",message="Pixazo Realtime không hỗ trợ từ vựng gợi ý; giữ nguyên lời mô hình trả về.")
        converter=None
        if self.cfg.script!="original":
            from opencc import OpenCC
            converter=OpenCC("t2s" if self.cfg.script=="simplified" else "s2t")
        def store():
            atomic_text(checkpoint,json.dumps({"key":key,"duration":duration,"ranges":ranges,"completed":{str(k):[asdict(s) for s in v] for k,v in saved.items()}},ensure_ascii=False))
            records=[s for k in sorted(saved) for s in saved[k]]
            atomic_text(folder/"transcript_zh.partial.txt",paragraphs(records),"utf-8-sig")
            self.emit("preview",index=index,text=paragraphs(records)[-30000:])
        store()
        async def run():
            semaphore=asyncio.Semaphore(self.cfg.pixazo_workers)
            amounts={k:b-a if k in saved else 0 for k,(a,b) in enumerate(ranges)}
            last_emit=[0.]
            stop_new=[False]
            def progress(k,seconds,force=False):
                amounts[k]=max(amounts[k],seconds)
                if force or time.monotonic()-last_emit[0]>=.3:
                    last_emit[0]=time.monotonic()
                    completed=sum(amounts.values())
                    self.emit("item",index=index,active=True,stage="Nhận dạng qua Pixazo",progress=25+69*completed/duration,
                              detail=f"{completed/60:.1f}/{duration/60:.1f} phút · xong {len(saved)}/{len(ranges)} đoạn")
            async def one(k,left,right):
                if k in saved:return
                async with semaphore:
                    if stop_new[0]:
                        raise PixazoError("Các đoạn còn lại đã tạm dừng sau lỗi Pixazo; chạy tiếp để thử lại.")
                    check_cancel(self.cancel)
                    chunk=work/f"pixazo-{k:05}.wav"
                    await asyncio.to_thread(extract_chunk,item["media"],chunk,left,right-left,self.cancel)
                    try:
                        for attempt in range(2):
                            try:
                                records=await stream_chunk(chunk,self.key,self.cancel,lambda seconds:progress(k,seconds))
                                break
                            except PixazoError as exc:
                                if attempt == 0 and exc.retryable:
                                    self.emit("log",message="Pixazo tạm giới hạn kết nối; thử lại một lần trước khi gửi âm thanh.")
                                    await asyncio.sleep(1.5+k*.2)
                                    continue
                                stop_new[0]=True
                                raise
                        for s in records:
                            s.start=round(left+s.start,3);s.end=round(min(right,left+s.end),3)
                            if converter:s.text=converter.convert(s.text)
                        saved[k]=records
                        store()
                        progress(k,right-left,True)
                    finally:
                        chunk.unlink(missing_ok=True)
            tasks=[asyncio.create_task(one(k,a,b)) for k,(a,b) in enumerate(ranges)]
            async def watch_cancel():
                while not self.cancel.is_set():await asyncio.sleep(.1)
                for t in tasks:t.cancel()
            monitor=asyncio.create_task(watch_cancel())
            try:
                outcomes=await asyncio.gather(*tasks,return_exceptions=True)
                check_cancel(self.cancel)
                errors=[x for x in outcomes if isinstance(x,BaseException)]
                if errors: raise errors[0]
            finally:
                monitor.cancel();await asyncio.gather(monitor,return_exceptions=True)
                for t in tasks:t.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
        asyncio.run(run())
        check_cancel(self.cancel)
        return [s for k in sorted(saved) for s in saved[k]],duration
