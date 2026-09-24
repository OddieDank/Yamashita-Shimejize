#!/usr/bin/env python3
"""Build a reproducible, directly installable shaderpack ZIP."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
output = root / 'dist' / 'Yamashita-Shimejize-mc26.2-DH-alpha.4.zip'
output.parent.mkdir(exist_ok=True)
files = sorted(p for p in (root / 'shaders').rglob('*') if p.is_file())
files.append(root / 'README.md')
names = [p.relative_to(root).as_posix().lower() for p in files]
assert len(names) == len(set(names)), 'Case-insensitive file name collision in shaderpack'
with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
    for file in files:
        entry = ZipInfo(file.relative_to(root).as_posix(), (2026, 9, 24, 0, 0, 0))
        entry.compress_type = ZIP_DEFLATED
        entry.external_attr = 0o644 << 16
        archive.writestr(entry, file.read_bytes())
with ZipFile(output) as archive:
    assert archive.testzip() is None
    for folder in ['', 'world0/', 'world-1/', 'world1/']:
        for program in ['dh_terrain', 'dh_water', 'dh_shadow']:
            for stage in ['vsh', 'fsh']:
                assert f'shaders/{folder}{program}.{stage}' in archive.namelist()
digest = sha256(output.read_bytes()).hexdigest()
output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n')
print(f'{output}\nSHA256 {digest}\n{len(files)} files; ZIP integrity and DH entry points verified.')
