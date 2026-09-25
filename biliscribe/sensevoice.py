from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path
from types import SimpleNamespace

from .config import MODELS, atomic_text, resource_path
from .media import check_cancel
from .transcribe import Transcriber

REVISION = '2365baeacb507f821a0c8120fcee3d484dba7a07'
FILES = {
    'model.int8.onnx': 'c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51',
    'tokens.txt': 'f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc',
}


def valid_model(folder: Path) -> bool:
    for name, expected in FILES.items():
        path = folder / name
        if not path.is_file():
            return False
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(2**20), b''):
                digest.update(block)
        if digest.hexdigest() != expected:
            return False
    return True


def result_segments(result, duration):
    """Use native CTC token timestamps; never invent a confidence score."""
    tokens, times = list(result.tokens), list(result.timestamps)
    compact = lambda value: ''.join(value.split())
    if not tokens or len(tokens) != len(times) or compact(''.join(tokens)) != compact(result.text):
        if result.text.strip():
            yield SimpleNamespace(start=0.0, end=duration, text=result.text, words=None)
        return
    words = []
    for i, (token, stamp) in enumerate(zip(tokens, times)):
        start = min(duration, max(0.0, float(stamp)))
        following = float(times[i + 1]) if i + 1 < len(times) else duration
        end = min(duration, max(start + 0.01, min(start + 0.35, following)))
        words.append(SimpleNamespace(start=start, end=end, word=token))
        text = ''.join(w.word for w in words)
        if token.rstrip().endswith(('。', '！', '？', '；', '，', '!', '?', ';', ',')) or len(text) >= 32 or i == len(tokens) - 1:
            yield SimpleNamespace(start=words[0].start, end=words[-1].end, text=text, words=words)
            words = []


class SenseVoiceTranscriber(Transcriber):
    # 28 seconds owned by this chunk, with one second of acoustic context at each side.
    chunk_seconds = 28.0
    overlap = 1.0

    def _download_model(self):
        bundled = resource_path('vendor/models/sensevoice-small')
        if valid_model(bundled):
            self.emit('log', message='Dùng SenseVoice có sẵn trong ứng dụng; không cần tải mô hình.')
            return bundled
        folder = Path(self.cfg.cache_dir) / 'sensevoice-small'
        if valid_model(folder):
            return folder
        from huggingface_hub import hf_hub_download
        self.emit('model', message='Khôi phục mô hình SenseVoice (~239 MB).', progress=-1)
        for name, expected in FILES.items():
            check_cancel(self.cancel)
            path = Path(hf_hub_download(MODELS['sensevoice-small'][0], name, revision=REVISION,
                                      token=False, local_dir=str(folder)))
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                path.unlink(missing_ok=True)
                raise RuntimeError('Mô hình SenseVoice bị lỗi. Hãy chạy lại để tải lại.')
        atomic_text(folder / 'biliscribe-ready.json', json.dumps({'revision': REVISION}))
        return folder

    def load(self):
        if self.model is not None:
            return
        # Initialize NumPy/OpenBLAS and the newer ORT DLL before sherpa creates threads.
        # Keep the same numerical DLL initialization order in both recognition engines.
        import numpy
        import onnxruntime
        import sherpa_onnx
        if self.model_path is None:
            self.model_path = self._download_model()
        check_cancel(self.cancel)
        self.emit('model', message='Nạp SenseVoice · CPU INT8 · tiếng Trung', progress=-1)
        self.model = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(self.model_path / 'model.int8.onnx'), tokens=str(self.model_path / 'tokens.txt'),
            num_threads=self.plan.threads, provider='cpu', language='zh', use_itn=True)
        if self.cfg.glossary:
            self.emit('log', message='SenseVoice chưa hỗ trợ gợi ý tên riêng. Chọn chế độ Ưu tiên độ sát để dùng từ vựng gợi ý với Large v3.')

    def _one_chunk(self, chunk, task):
        if task != 'transcribe':
            raise ValueError('SenseVoice chỉ chép lời; bản dịch tiếng Anh cần Whisper Large v3.')
        self.load()
        import numpy as np
        with wave.open(str(chunk), 'rb') as stream:
            samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        check_cancel(self.cancel)
        duration = len(samples) / 16000
        if self.cfg.vad:
            from faster_whisper.vad import get_speech_timestamps, VadOptions
            speech = get_speech_timestamps(samples, VadOptions(threshold=0.35, min_speech_duration_ms=60,
                                                              min_silence_duration_ms=700, speech_pad_ms=400))
            if not speech:
                if self.progress_callback:
                    self.progress_callback(duration)
                return []
        stream = self.model.create_stream()
        stream.accept_waveform(16000, samples)
        self.model.decode_stream(stream)
        check_cancel(self.cancel)
        if self.progress_callback:
            self.progress_callback(duration)
        return list(result_segments(stream.result, duration))
