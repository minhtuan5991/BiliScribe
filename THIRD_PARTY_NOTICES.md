# Third-party notices

BiliScribe's original implementation is supplied in source form. It was developed after inspecting the user-provided BiliDownloader v1.6 and TranscriptTool Python312 v3 archives. Original reference files are retained under reference/ for local comparison; they are not executed or bundled in the installer.

## Runtime components

- Python 3.12: Python Software Foundation license. https://www.python.org/psf/license/
- PySide6 / Qt 6.9.3 / Shiboken: LGPL v3 / GPL v3 or commercial terms, with component-specific notices. Used as dynamically linked libraries; binaries may be replaced with compatible builds. https://doc.qt.io/qtforpython-6/licenses.html
- faster-whisper 1.2.1: MIT. https://github.com/SYSTRAN/faster-whisper
- CTranslate2 4.8.2: MIT. https://github.com/OpenNMT/CTranslate2
- yt-dlp 2026.08.19: Unlicense, with dependencies under their own licenses. https://github.com/yt-dlp/yt-dlp
- ONNX Runtime: MIT. https://github.com/microsoft/onnxruntime
- OpenCC Python reimplementation: Apache 2.0. https://github.com/yichen0831/opencc-python
- PyAV: BSD; its bundled multimedia libraries have separate licenses. https://github.com/PyAV-Org/PyAV
- Hugging Face Hub, tokenizers, NumPy, psutil and dependencies: see the installed license files under _internal/licenses.
- PyInstaller bootloader: GPL with exception permitting distribution of packaged programs. https://pyinstaller.org/en/stable/license.html

## FFmpeg

ffmpeg.exe and ffprobe.exe are unchanged binaries from the user-provided BiliDownloader archive. Their reported version is 9.0.1-essentials_build-www.gyan.dev, built with GPLv3 components. They run as separate executables.

Project and source: https://ffmpeg.org/ and https://github.com/FFmpeg/FFmpeg/tree/n9.0.1
Build provider and source/build information: https://www.gyan.dev/ffmpeg/builds/
GPLv3 license: https://www.gnu.org/licenses/gpl-3.0.html
Build configuration and binary checksums: vendor/PROVENANCE.txt.

No claim is made to the authorship of these components. When redistributing the application, retain these notices and comply with each component's source-availability terms.

## Optional downloads

Whisper model weights are fetched from the model publishers on Hugging Face and retain their respective model licenses. The installer does not include them. https://huggingface.co/Systran/faster-whisper-large-v3 and https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo

NVIDIA CUDA runtime 12.4.127, cuBLAS 12.4.5.8 and cuDNN 9.1.0.70 are downloaded only when the user requests GPU preparation. Downloads use NVIDIA's PyPI wheel distributions and verify published SHA-256 checksums before extraction. Their license texts are extracted beside the DLLs. NVIDIA driver software is not installed or modified.

## SenseVoice CPU engine (bundled in 1.1.0)

sherpa-onnx 1.13.8 and sherpa-onnx-core: Apache 2.0. https://github.com/k2-fsa/sherpa-onnx
SenseVoiceSmall: https://github.com/QwenAudio/SenseVoice and https://huggingface.co/FunAudioLLM/SenseVoiceSmall (MIT model card). Upstream license text is included in licenses/SenseVoice/LICENSE.
ONNX INT8 conversion by the sherpa-onnx project: https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17
Pinned revision: 2365baeacb507f821a0c8120fcee3d484dba7a07. Model SHA-256: c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51. The converter's original notice, model, tokens and provenance are retained in vendor/models/sensevoice-small. No Python code from model repositories is executed.

Vietnamese installer translation: https://github.com/jrsoftware/issrc/blob/main/Files/Languages/Unofficial/Vietnamese.isl (translator attribution retained in installer/Vietnamese.isl).


## Pixazo integration (1.2.0)

WebSocket transport uses websockets 17.1 (BSD-3-Clause), license in licenses/websockets. API service: Pixazo Qwen ASR Realtime, documentation https://www.pixazo.ai/models/qwen-audio. Requires the user's own API key and account credit. No credentials are distributed. The supplied ChineseTranscript 1.2.0 executable and README were inspected as a functional reference; its executable is not bundled.
