"""Credential-free update discovery. No installer download or execution."""
from __future__ import annotations
import json
import queue
import re
import threading
import time
from dataclasses import dataclass
from urllib.request import Request, urlopen
from . import __version__

REPOSITORY = "https://github.com/minhtuan5991/BiliScribe"
FEED_URL = "https://api.github.com/repos/minhtuan5991/BiliScribe/releases/latest"
MAX_BYTES = 262144

@dataclass(frozen=True)
class Update:
    version: str
    url: str

def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})", value):
        raise ValueError("Expected stable major.minor.patch")
    return tuple(map(int, value.removeprefix("v").split(".")))

def parse_update(payload, current=__version__):
    if not isinstance(payload, dict):
        raise ValueError("Invalid metadata")
    if payload.get("draft", False) is not False or payload.get("prerelease", False) is not False:
        return None
    version = payload.get("tag_name")
    latest = version_tuple(version)
    expected = REPOSITORY + "/releases/tag/v" + version.removeprefix("v")
    if payload.get("html_url") != expected:
        raise ValueError("Unexpected release URL")
    return Update(version.removeprefix("v"), expected) if latest > version_tuple(current) else None

def fetch_update(current=__version__):
    request = Request(FEED_URL, headers={"User-Agent": "BiliScribe/" + current,
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    with urlopen(request, timeout=8) as response:
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("Metadata too large")
    return parse_update(json.loads(payload), current)

class StartupCheck:
    """Network thread only writes a queue, never Qt objects or user settings."""
    def __init__(self, fetch=None, deadline=12.0):
        self._fetch = fetch or fetch_update
        self._deadline = deadline
        self._results = queue.Queue(maxsize=1)
        self._started = False
        self._finished = False
        self._until = 0.0

    def start(self):
        if self._started or self._finished:
            return
        self._started = True
        self._until = time.monotonic() + self._deadline
        fetch, results = self._fetch, self._results
        def work():
            try:
                results.put(("ok", fetch()))
            except Exception:
                results.put(("unavailable", None))
        threading.Thread(target=work, name="BiliScribe-update", daemon=True).start()

    def poll(self):
        if self._finished or not self._started:
            return None
        try:
            result = self._results.get_nowait()
        except queue.Empty:
            if time.monotonic() < self._until:
                return None
            result = ("unavailable", None)
        self._finished = True
        return result

    def close(self):
        self._finished = True
