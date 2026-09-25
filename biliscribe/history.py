from __future__ import annotations

import json
from pathlib import Path

from filelock import FileLock
from .config import atomic_text, data_dir


def load_history() -> list[dict]:
    try:
        records = json.loads((data_dir() / 'history.json').read_text('utf-8'))
    except (OSError, ValueError):
        return []
    if not isinstance(records, list):
        return []
    return [row for row in records if isinstance(row, dict) and isinstance(row.get('folder'), str)]


def record_history(summary: dict) -> None:
    """Persist each completed video before starting the next, with cross-process locking."""
    path = data_dir() / 'history.json'
    with FileLock(str(path) + '.lock', timeout=5):
        rows = load_history()
        identity = str(Path(summary['folder']).resolve()).casefold()
        rows = [row for row in rows if str(Path(row['folder']).resolve()).casefold() != identity]
        atomic_text(path, json.dumps([summary, *rows][:200], ensure_ascii=False, indent=2))
