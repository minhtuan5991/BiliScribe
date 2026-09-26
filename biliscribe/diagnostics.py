import json
import os
import threading
import wave
from pathlib import Path


def self_test(destination):
    output = Path(destination)
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["BILISCRIBE_DATA_DIR"] = str(output / "appdata")
    checks = {}
    try:
        import yt_dlp
        import av
        import ctranslate2
        import onnxruntime
        from faster_whisper import WhisperModel
        from faster_whisper.vad import get_speech_timestamps, VadOptions
        from opencc import OpenCC
        import numpy as np
        import sherpa_onnx
        from .config import Settings
        from .hardware import Hardware, choose_plan
        from .sensevoice import SenseVoiceTranscriber, valid_model
        from .config import resource_path
        checks["imports"] = True
        checks["bundled_model_hash"] = valid_model(resource_path("vendor/models/sensevoice-small"))
        if not checks["bundled_model_hash"]:
            raise RuntimeError("Thiếu / sai checksum mô hình CPU đi kèm bộ cài.")
        cfg = Settings.from_dict({"profile": "fast"})
        engine = SenseVoiceTranscriber(cfg, choose_plan(cfg, Hardware(4, 2, 2)), lambda *a, **k: None, threading.Event())
        engine.load()
        sample = engine.model.create_stream()
        sample.accept_waveform(16000, np.zeros(16000, dtype=np.float32))
        engine.model.decode_stream(sample)
        checks["sensevoice_inference"] = isinstance(sample.result.text, str)
        engine.close()
        checks["opencc"] = OpenCC("t2s").convert("中文繁體轉換") == "中文繁体转换"
        checks["vad_silence"] = get_speech_timestamps(np.zeros(16000, dtype=np.float32), VadOptions()) == []
        from .media import make_mp3, duration_seconds
        wav = output / "silence.wav"
        with wave.open(str(wav), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 16000)
        make_mp3(wav, output / "silence.mp3", threading.Event())
        checks["ffmpeg_mp3"] = 0.9 <= duration_seconds(output / "silence.mp3") <= 1.3
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFontDatabase
        from .ui import MainWindow, STYLE, app_icon
        app = QApplication.instance() or QApplication([])
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "msyh.ttc"):
            QFontDatabase.addApplicationFont(str(fonts / name))
        app.setStyle("Fusion")
        app.setStyleSheet(STYLE)
        win = MainWindow()
        win.show()
        app.processEvents()
        checks["ui_render"] = win.grab().save(str(output / "app-main.png"))
        win.resize(960, 690)
        app.processEvents()
        checks["ui_small"] = win.grab().save(str(output / "app-small.png"))
        win._toggle_advanced()
        app.processEvents()
        checks["ui_advanced"] = win.grab().save(str(output / "app-advanced.png"))
        win._start()
        checks["empty_input_validation"] = win.input_error.isVisible() and win.proc is None
        win.urls.setPlainText("https://bilibili.com.evil.example/video/BV1sDLG6DED3")
        win._start()
        checks["host_validation"] = win.input_error.isVisible() and win.proc is None
        win.urls.setPlainText("https://www.bilibili.com/video/BV1sDLG6DED3/")
        win.profile.setCurrentIndex(win.profile.findData("pixazo"))
        win.api_key.clear()
        win._start()
        checks["pixazo_missing_key_validation"] = win.input_error.isVisible() and win.proc is None
        checks["pixazo_options_visible"] = win.api_options.isVisible() and not win.model.isEnabled()
        checks["pixazo_ui"] = win.grab().save(str(output / "app-pixazo.png"))
        import websockets
        checks["websockets_import"] = bool(websockets.__version__)
        from .updates import StartupCheck, Update, REPOSITORY
        win.update_check = StartupCheck(lambda: Update("1.3.0", REPOSITORY + "/releases/tag/v1.3.0"))
        win.update_check.start()
        import time
        for _ in range(20):
            app.processEvents()
            time.sleep(.02)
            win._poll_update()
            if win.update_url:
                break
        checks["update_notice"] = win.update_btn.isVisible() and bool(win.update_url)
        checks["update_ui"] = win.grab().save(str(output / "app-update.png"))
        win._navigate(2)
        app.processEvents()
        checks["help_render"] = win.grab().save(str(output / "app-help.png"))
        app_icon().pixmap(256, 256).save(str(output / "app-icon.png"))
        win.close()
        checks["versions"] = {"yt_dlp": yt_dlp.version.__version__, "ctranslate2": ctranslate2.__version__, "onnxruntime": onnxruntime.__version__, "av": av.__version__, "sherpa_onnx": sherpa_onnx.__version__}
    except Exception as exc:
        import traceback
        checks["error"] = str(exc)
        checks["traceback"] = traceback.format_exc()
    output.joinpath("self-test.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), "utf-8")
    return 0 if "error" not in checks and all(value is not False for value in checks.values()) else 1
