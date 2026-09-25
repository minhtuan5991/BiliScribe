from importlib.metadata import distributions
from pathlib import Path
import shutil
root = Path(__file__).resolve().parent.parent
out = root / 'licenses'
for dist in distributions():
    name = dist.metadata.get('Name', 'unknown')
    for entry in dist.files or []:
        lower = str(entry).lower()
        if any(token in lower for token in ('license', 'copying', 'notice')) and '.py' not in lower:
            src = Path(dist.locate_file(entry))
            if src.is_file():
                dest = out / name / Path(entry).name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
print('Collected dependency licenses.')
