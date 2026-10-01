import json
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from biliscribe.config import Settings, atomic_text, data_dir, source_key
from biliscribe.hardware import Hardware, Plan, choose_plan
from biliscribe.history import load_history, record_history
from biliscribe.media import Cancelled
from biliscribe.transcribe import Segment, Transcriber
from biliscribe.sensevoice import result_segments
from biliscribe.comparison import compare_transcripts


@pytest.fixture(autouse=True)
def private_data(tmp_path, monkeypatch):
    monkeypatch.setenv('BILISCRIBE_DATA_DIR', str(tmp_path / 'data'))


def test_atomic_write_preserves_old_file_when_replace_fails(tmp_path, monkeypatch):
    path = tmp_path / 'record.json'
    path.write_text('old', 'utf-8')
    def fail(*args):
        raise OSError('disk failure')
    monkeypatch.setattr('biliscribe.config.os.replace', fail)
    with pytest.raises(OSError):
        atomic_text(path, 'new')
    assert path.read_text() == 'old'
    assert list(tmp_path.glob('*.tmp')) == []


def test_history_survives_concurrent_writers_and_deduplicates(tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: record_history({'folder': str(tmp_path / str(i)), 'title': str(i)}), range(12)))
    assert len(load_history()) == 12
    record_history({'folder': str(tmp_path / '2'), 'title': 'updated'})
    assert len(load_history()) == 12 and load_history()[0]['title'] == 'updated'


@pytest.mark.parametrize('content', ['invalid', '{}', '[null, 4, {}, {"folder":42}]'])
def test_corrupt_history_is_ignored(content):
    (data_dir() / 'history.json').write_text(content, 'utf-8')
    assert load_history() == []


def test_completed_video_is_recorded_before_batch_cancellation(tmp_path, monkeypatch):
    import biliscribe.pipeline as pipeline
    cancel = threading.Event()
    monkeypatch.setattr(pipeline, 'detect_hardware', lambda: Hardware(8, 4, 4))
    monkeypatch.setattr(pipeline, 'prepare_source', lambda source, *args: {'source': source, 'title': source, 'folder': tmp_path / f'{source} [{source_key(source)[:8]}]', 'work': tmp_path / '.biliscribe-cache' / source_key(source), 'duration': 1})
    monkeypatch.setattr(pipeline.SenseVoiceTranscriber, 'transcribe', lambda *args: ([Segment(0, 1, '你好。')], 1))
    def emit(kind, **data):
        if kind == 'result':
            cancel.set()
    with pytest.raises(Cancelled):
        pipeline.process_batch(['first', 'second'], Settings.from_dict({'profile': 'fast', 'output_dir': str(tmp_path)}), emit, cancel)
    assert len(load_history()) == 1
    assert load_history()[0]['title'] == 'first'
    assert (Path(load_history()[0]['folder']) / 'transcript_zh.txt').is_file()


def test_cpu_auto_uses_bundled_model_and_translation_uses_whisper():
    cpu = Hardware(4, 1.1, 2)
    plan = choose_plan(Settings.from_dict({}), cpu)
    assert (plan.model, plan.device, plan.threads) == ('sensevoice-small', 'cpu', 1)
    translated = choose_plan(Settings.from_dict({'profile': 'fast', 'english': True}), cpu)
    assert translated.model == 'large-v3'
    gpu = Hardware(16, 8, 8, 'NVIDIA', 12, True)
    assert choose_plan(Settings.from_dict({'vad': False}), gpu).batch_size == 1


def test_ctc_timestamps_preserve_punctuation_and_no_fake_confidence():
    result = SimpleNamespace(text='你好，世界。', tokens=list('你好，世界。'), timestamps=[0.1, 0.3, 0.6, 0.7, 1.0, 1.2])
    segments = list(result_segments(result, 1.5))
    assert ''.join(s.text for s in segments) == result.text
    assert len(segments) == 2
    assert all(0 <= w.start < w.end <= 1.5 for s in segments for w in s.words)
    assert all(not hasattr(s, 'avg_logprob') for s in segments)
    # A backend without matching tokenization must retain its complete text.
    result.tokens = ['different']
    fallback = list(result_segments(result, 1.5))
    assert fallback[0].text == result.text and fallback[0].words is None


def test_comparison_flags_difference_without_rewriting(tmp_path):
    primary = [Segment(0, 1, '电子粒显示日期。'), Segment(2, 3, '今天下雨。')]
    secondary = [Segment(0, 1, '电子日历显示日期。'), Segment(2, 3, '今天下雨。')]
    before = [s.text for s in primary]
    assert compare_transcripts(primary, secondary, tmp_path) > 0
    assert [s.text for s in primary] == before
    assert primary[0].review and not primary[1].review
    report = json.loads((tmp_path / 'doi_chieu_zh.json').read_text('utf-8'))
    assert report['differences'][0]['start'] == 0


def test_streamed_progress_is_monotonic_across_chinese_and_english(tmp_path, monkeypatch):
    cfg = Settings.from_dict({'english': True, 'script': 'original'})
    events = []
    r = Transcriber(cfg, Plan('small', 'cpu', 'int8', 1, 1, 5), lambda kind, **data: events.append((kind, data)), threading.Event())
    monkeypatch.setattr('biliscribe.transcribe.extract_chunk', lambda *args: None)
    def decode(*args):
        r.progress_callback(4)
        r.progress_callback(8)
        return [SimpleNamespace(start=0, end=10, text='测试', words=None, avg_logprob=-.1, no_speech_prob=.1, compression_ratio=1)]
    r._one_chunk = decode
    item = {'folder': tmp_path, 'work': tmp_path, 'duration': 10, 'media': tmp_path / 'audio'}
    r.transcribe(item, 0)
    r.transcribe(item, 0, 'translate')
    values = [data['progress'] for kind, data in events if kind == 'item']
    assert values == sorted(values)
    assert values[0] == 25 and values[-1] == 95 and len(set(values)) > 4
