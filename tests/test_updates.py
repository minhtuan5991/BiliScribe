import json
import os
import threading
import time
import pytest
from biliscribe import updates


def metadata(version="1.3.0"):
    return {"tag_name": "v" + version, "html_url": updates.REPOSITORY + "/releases/tag/v" + version,
            "draft": False, "prerelease": False}


@pytest.mark.parametrize("version,available", [("1.3.0",True),("1.2.10",True),("2.0.0",True),("1.2.1",False),("1.2.0",False)])
def test_version_comparison(version, available):
    assert bool(updates.parse_update(metadata(version), "1.2.1")) == available


@pytest.mark.parametrize("version", [None, 12, "1.2", "1.2.3-beta", "01.2.3", "1.2.3/evil"])
def test_reject_invalid_versions(version):
    with pytest.raises(ValueError): updates.version_tuple(version)


def test_untrusted_metadata():
    for field in ("draft", "prerelease"):
        data=metadata(); data[field]=True
        assert updates.parse_update(data) is None
    for url in ("https://evil.example", updates.REPOSITORY + "/releases/tag/v1.3.0?x=1", "file:///C:/evil.exe"):
        data=metadata(); data["html_url"]=url
        with pytest.raises(ValueError): updates.parse_update(data)


def test_fetch_bounded_no_credentials(monkeypatch):
    from io import BytesIO
    seen=[]
    def open_mock(request, timeout):
        seen.append((request,timeout))
        return BytesIO(json.dumps(metadata()).encode())
    monkeypatch.setattr(updates,"urlopen",open_mock)
    assert updates.fetch_update("1.2.1").version == "1.3.0"
    request,timeout=seen[0]
    assert request.full_url == updates.FEED_URL and timeout == 8
    assert not request.has_header("Authorization")
    monkeypatch.setattr(updates,"urlopen",lambda *a,**k: BytesIO(b" "*(updates.MAX_BYTES+1)))
    with pytest.raises(ValueError): updates.fetch_update()


def wait_result(check):
    until=time.monotonic()+2
    while time.monotonic()<until:
        result=check.poll()
        if result is not None: return result
        time.sleep(.005)
    raise AssertionError("No result")


def test_single_check_and_offline():
    calls=[]
    def fail():
        calls.append(1)
        raise OSError("private proxy details")
    check=updates.StartupCheck(fail)
    check.start(); check.start()
    assert wait_result(check) == ("unavailable",None)
    check.start()
    assert calls == [1] and check.poll() is None


def test_slow_check_deadline_and_close():
    gate=threading.Event()
    def slow(): gate.wait(2)
    check=updates.StartupCheck(slow,deadline=.01)
    start=time.monotonic(); check.start()
    assert time.monotonic()-start < .2
    assert wait_result(check) == ("unavailable",None)
    check.close();gate.set()
    assert check.poll() is None


def test_gui_update_settings_and_close(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from biliscribe.config import Settings, save_settings
    from biliscribe.ui import MainWindow
    monkeypatch.setenv("BILISCRIBE_DATA_DIR",str(tmp_path))
    save_settings(Settings(profile="pixazo",pixazo_workers=2))
    before=(tmp_path/"settings.json").read_bytes()
    calls=[]
    def fetch():
        calls.append(1)
        return updates.parse_update(metadata(),"1.2.1")
    monkeypatch.setattr(updates,"fetch_update",fetch)
    app=QApplication.instance() or QApplication([])
    win=MainWindow();win.show()
    win.start_update_check();win.start_update_check()
    until=time.monotonic()+2
    while win.update_btn.isHidden() and time.monotonic()<until: QTest.qWait(25)
    assert win.update_btn.isVisible() and "1.3.0" in win.update_btn.text()
    assert calls==[1] and not win.update_timer.isActive()
    import biliscribe.ui as ui
    opened=[]
    monkeypatch.setattr(ui.QDesktopServices,"openUrl",lambda url: opened.append(url.toString()) or True)
    win.update_btn.click()
    assert opened == [updates.REPOSITORY + "/releases/tag/v1.3.0"]
    assert win.profile.currentData()=="pixazo" and win.pixazo_workers.currentData()==2
    assert (tmp_path/"settings.json").read_bytes()==before
    win.close()
    gate=threading.Event()
    monkeypatch.setattr(updates,"fetch_update",lambda: gate.wait(2))
    win=MainWindow();win.start_update_check()
    start=time.monotonic();win.close()
    assert time.monotonic()-start<.2 and not win.update_timer.isActive()
    gate.set()
