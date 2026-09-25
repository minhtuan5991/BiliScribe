# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata
from pathlib import Path
root = Path(SPECPATH)
datas = [(str(root / 'vendor'), 'vendor'), (str(root / 'licenses'), 'licenses'), (str(root / 'docs'), 'docs')]
for package in ('faster_whisper', 'opencc', 'certifi'):
    datas += collect_data_files(package)
for package in ('faster-whisper', 'ctranslate2', 'yt-dlp', 'huggingface-hub', 'tokenizers', 'onnxruntime', 'sherpa-onnx', 'sherpa-onnx-core', 'filelock', 'websockets'):
    datas += copy_metadata(package)
binaries = collect_dynamic_libs('ctranslate2') + collect_dynamic_libs('onnxruntime') + collect_dynamic_libs('sherpa_onnx')
a = Analysis(['main.py'], pathex=[str(root)], binaries=binaries, datas=datas,
             hiddenimports=['PySide6.QtSvg', 'onnxruntime.capi.onnxruntime_pybind11_state', 'numpy', 'sherpa_onnx', 'websockets.asyncio.client'],
             excludes=['PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtNetwork', 'torch', 'tensorflow', 'matplotlib', 'scipy', 'pandas', 'pytest', 'tkinter'], noarchive=False)
pyz = PYZ(a.pure)
common = dict(exclude_binaries=True, debug=False, strip=False, upx=False, icon=str(root / 'assets/app.ico'), version=str(root / 'installer/version.txt'))
ui = EXE(pyz, a.scripts, [], name='BiliScribe', console=False, **common)
worker = EXE(pyz, a.scripts, [], name='BiliScribeWorker', console=True, **common)
coll = COLLECT(ui, worker, a.binaries, a.datas, strip=False, upx=False, name='BiliScribe-1.2.0')
