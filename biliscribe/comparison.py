from __future__ import annotations

import json
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path

from .config import atomic_text
from .transcribe import paragraphs, timestamp


def compare_transcripts(primary, secondary, folder: Path):
    """Flag differences for listening; preserve the primary transcript verbatim."""
    from opencc import OpenCC
    convert = OpenCC('t2s').convert
    def flatten(segments):
        chars, owners = [], []
        for index, segment in enumerate(segments):
            text = convert(segment.text).lower()
            for char in text:
                if char.isalnum():
                    chars.append(char); owners.append(index)
        return ''.join(chars), owners
    a, owners = flatten(primary)
    b, _ = flatten(secondary)
    changes = []
    for kind, i, j, k, l in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if kind == 'equal':
            continue
        ids = sorted(set(owners[i:j] or owners[max(0, i-1):i+1]))
        for index in ids:
            primary[index].review = True
        begin = primary[ids[0]].start if ids else 0
        end = primary[ids[-1]].end if ids else begin
        changes.append({'start': begin, 'end': end, 'primary': a[i:j], 'sensevoice': b[k:l],
                        'primary_context': a[max(0,i-10):j+10], 'sensevoice_context': b[max(0,k-10):l+10]})
    note = 'Đây là sai khác giữa hai mô hình, không phải danh sách lỗi đã xác nhận. Số viết bằng chữ / chữ số cũng có thể bị đánh dấu. Nghe lại video / file nguồn theo mốc thời gian để quyết định; app giữ nguyên bản Large v3.\n\n'
    lines = [note]
    for item in changes:
        lines += [f"{timestamp(item['start'])} — {timestamp(item['end'])}",
                  'Large v3: ' + item['primary_context'], 'SenseVoice: ' + item['sensevoice_context'], '']
    if not changes:
        lines.append('Hai bản không có sai khác sau khi bỏ dấu câu; vẫn cần kiểm tra tên riêng.\n')
    atomic_text(folder / 'doi_chieu_zh.txt', '\n'.join(lines), 'utf-8-sig')
    atomic_text(folder / 'doi_chieu_zh.json', json.dumps({'note': note, 'differences': changes}, ensure_ascii=False, indent=2))
    return len(changes)
