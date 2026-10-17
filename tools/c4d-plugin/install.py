"""Install the built local preview and reversibly disable the old layout bridge."""
from pathlib import Path
import hashlib,json,shutil,sys,time
root=Path(__file__).resolve().parents[2]
source=root/'.build/plugin/SpaceMouseUI'
plugins=Path(sys.argv[1]).expanduser().resolve()
manifest=json.loads((source/'SHA256SUMS.json').read_text())
for name,digest in manifest.items():
 if hashlib.sha256((source/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Package checksum mismatch: '+name)
backup=root/'.build/plugin-install-backup'/time.strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True)
plugins.mkdir(parents=True,exist_ok=True)
destination=plugins/'SpaceMouseUI'
if destination.exists():shutil.copytree(destination,backup/'SpaceMouseUI')
staging=plugins/'SpaceMouseUI.installing'
if staging.exists():raise RuntimeError('Unfinished installation staging directory exists')
shutil.copytree(source,staging)
old=plugins/'SpaceMouseLayoutTrial/SpaceMouseLayoutTrial.pyp'
if old.exists():
 shutil.copy2(old,backup/old.name)
 disabled=old.with_suffix('.pyp.disabled')
 if disabled.exists():raise RuntimeError('Both active and disabled layout bridge exist; inspect before proceeding')
 old.rename(disabled)
if destination.exists():shutil.rmtree(destination)
staging.rename(destination)
for name,digest in manifest.items():
 if hashlib.sha256((destination/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Installed checksum mismatch: '+name)
print('Installed and verified:',destination)
print('Recovery backup:',backup)
