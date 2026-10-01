import os
from pathlib import Path

import pytest

from biliscribe.output_files import ascii_title, rename_transcripts, transcript_file


def test_vietnamese_filename_and_content(tmp_path):
    assert ascii_title("Đường đến những câu chuyện kỳ lạ") == "Duong den nhung cau chuyen ky la"
    assert ascii_title("Tiếng Việt: / ?") == "Tieng Viet"
    assert ascii_title("规则怪谈") == "Video"
    for ext in (".txt", ".srt"):
        (tmp_path / ("transcript_zh" + ext)).write_bytes(b"\xef\xbb\xbfunchanged\r\n")
    (tmp_path / "doi_chieu_zh.txt").write_text("review")
    result = rename_transcripts(tmp_path, "Những câu chuyện kỳ lạ về luật lệ")
    assert result == {"txt_file": "Nhung cau chuyen ky la ve luat le_zh.txt", "srt_file": "Nhung cau chuyen ky la ve luat le_zh.srt"}
    assert len(list(tmp_path.iterdir())) == 3
    for name in result.values(): assert (tmp_path / name).read_bytes() == b"\xef\xbb\xbfunchanged\r\n"
    assert transcript_file(tmp_path, ".txt").name == result["txt_file"]


def test_collision_and_rollback(tmp_path, monkeypatch):
    for ext in (".txt", ".srt"): (tmp_path / ("transcript_zh" + ext)).write_text(ext)
    target = tmp_path / "Ten_zh.srt"
    target.write_text("existing")
    with pytest.raises(OSError): rename_transcripts(tmp_path, "Tên")
    assert target.read_text() == "existing" and (tmp_path / "transcript_zh.txt").exists()
    target.unlink()
    rename = Path.rename
    def fail_second(self, destination):
        if self.name == "transcript_zh.srt": raise PermissionError("file locked")
        return rename(self, destination)
    monkeypatch.setattr(Path, "rename", fail_second)
    with pytest.raises(OSError): rename_transcripts(tmp_path, "Tên")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["transcript_zh.srt", "transcript_zh.txt"]


def test_path_budget_and_legacy_lookup(tmp_path):
    folder = tmp_path / ("long" * 12)
    folder.mkdir()
    for ext in (".txt", ".srt"): (folder / ("transcript_zh" + ext)).write_text("kept")
    assert transcript_file(folder, ".txt").name == "transcript_zh.txt"
    files = rename_transcripts(folder, "Tên rất dài " * 60)
    assert all(len(str(folder / name)) <= 248 for name in files.values())
    (tmp_path / "doi_chieu_zh.txt").write_text("review only")
    assert transcript_file(tmp_path, ".txt") is None


@pytest.mark.parametrize("legacy", [False, True])
def test_gui_opens_and_previews_new_and_old_results(tmp_path, monkeypatch, legacy):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("BILISCRIBE_DATA_DIR", str(tmp_path / "data"))
    from PySide6.QtWidgets import QApplication
    from biliscribe import ui
    app = QApplication.instance() or QApplication([])
    stem = "transcript_zh" if legacy else "Nhung cau chuyen ky la ve luat le_zh"
    for ext in (".txt", ".srt"): (tmp_path / (stem + ext)).write_text("中文内容", "utf-8-sig")
    opened = []
    monkeypatch.setattr(ui.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    win = ui.MainWindow()
    win.last_folder = tmp_path
    win._load_preview(tmp_path)
    assert win.preview.toPlainText() == "中文内容" and win.srt_btn.isEnabled()
    win._open_txt(); win.srt_btn.click()
    assert [Path(p).name for p in opened] == [stem + ".txt", stem + ".srt"]
    win.close()
