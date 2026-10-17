"""Build and package a checksummed macOS ARM64 preview without installing it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('version', help='Release tag, e.g. v0.1.0-preview.1')
args = parser.parse_args()
if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', args.version):
    parser.error('Expected a version tag such as v0.1.0-preview.1')
root = Path(__file__).resolve().parents[2]
subprocess.run([sys.executable, str(Path(__file__).with_name('build.py'))], check=True)
package = root / '.build/plugin/SpaceMouseUI'
manifest = json.loads((package / 'SHA256SUMS.json').read_text())
for name, digest in manifest.items():
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise RuntimeError('Unsafe manifest path: ' + name)
    if hashlib.sha256((package / name).read_bytes()).hexdigest() != digest:
        raise RuntimeError('Package checksum mismatch: ' + name)
for library in package.glob('*.dylib'):
    architecture = subprocess.check_output(['lipo', '-archs', str(library)], text=True).strip()
    if architecture != 'arm64':
        raise RuntimeError('Expected ARM64 library: ' + str(library))
    subprocess.run(['codesign', '--verify', '--strict', str(library)], check=True)
output = root / '.build/releases'
output.mkdir(parents=True, exist_ok=True)
archive = output / f'c4d-spacemouse-ui-{args.version}-macos-arm64.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for name in sorted([*manifest, 'SHA256SUMS.json']):
        if '__pycache__' in Path(name).parts or name.endswith('.pyc'):
            continue
        bundle.write(package / name, 'SpaceMouseUI/' + name)
with zipfile.ZipFile(archive) as bundle:
    if bundle.testzip() is not None:
        raise RuntimeError('ZIP integrity check failed')
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(output / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n')
print(archive)
print('SHA256:', digest)
