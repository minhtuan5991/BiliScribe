import hashlib
import json
import shutil
import zipfile
from pathlib import Path
root = Path(__file__).resolve().parent.parent
release = root / 'release'
release.mkdir(exist_ok=True)
source_paths = ['biliscribe', 'main.py', 'tests', 'scripts', 'installer', 'assets', 'docs', 'licenses', 'BiliScribe.spec', 'BUILD_WINDOWS.ps1', 'README_VI.md', 'README.md', 'THIRD_PARTY_NOTICES.md', 'requirements.txt', 'requirements-lock.txt', 'vendor', 'pytest.ini']
with zipfile.ZipFile(release / 'BiliScribe-Source-1.2.2.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for value in source_paths:
        item = root / value
        for path in item.rglob('*') if item.is_dir() else [item]:
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                archive.write(path, path.relative_to(root))
shutil.copyfile(root / 'README_VI.md', release / 'HUONG_DAN.md')
sums = []
for path in sorted(release.glob('*')):
    if path.suffix in ('.exe', '.zip'):
        h = hashlib.sha256()
        with path.open('rb') as file:
            while chunk := file.read(2**20):
                h.update(chunk)
        sums.append(f'{h.hexdigest()}  {path.name}')
(release / 'SHA256SUMS.txt').write_text('\n'.join(sums) + '\n', 'utf-8')
print('\n'.join(sums))
