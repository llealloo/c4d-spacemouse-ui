"""Build a self-contained local C4D plugin. Does not install or alter baselines."""
from pathlib import Path
import shutil
import subprocess
import hashlib
import json
root=Path(__file__).resolve().parents[2]
dest=root/'.build/plugin/SpaceMouseUI'
dest.mkdir(parents=True,exist_ok=True)
shutil.copy2(root/'tools/c4d-plugin/plugin_ids.py',dest/'plugin_ids.py')
for name in ('SpaceMouseUI.pyp','file_dialog_scroll.py','plugin_runtime.py','node_pan_scale.py','node_event_transport.py','preferences_model.py','preferences_ui.py','settings_dialog.py','viewport_activation.py','vendor_motion_reset.py','ortho_hover.py','README.txt'):
 shutil.copy2(root/'tools/c4d-plugin'/name,dest/name)
shutil.copy2(root/'LICENSE',dest/'LICENSE')
shutil.copy2(root/'docs/INSTALLATION.md',dest/'INSTALLATION.md')
subprocess.run(['clang','-fobjc-arc','-O2','-Wall','-Wextra','-Wno-unused-parameter','-dynamiclib',
 '-I/Library/Frameworks/3DconnexionClient.framework/Headers','-F/Library/Frameworks','-framework','3DconnexionClient',
 '-framework','AppKit','-framework','ApplicationServices',str(root/'tools/c4d-plugin/input_bridge.m'),'-o',str(dest/'libSpaceMouseUIInput.dylib')],check=True)
subprocess.run(['codesign','--force','--sign','-','--identifier','local.spacemouse.c4d.ui.input',str(dest/'libSpaceMouseUIInput.dylib')],check=True)
subprocess.run(['clang','-fobjc-arc','-O2','-Wall','-dynamiclib','-framework','AppKit',
 str(root/'tools/c4d-plugin/hover_gate.m'),'-o',str(dest/'libSpaceMouseUIHover.dylib')],check=True)
subprocess.run(['codesign','--force','--sign','-','--identifier','local.spacemouse.c4d.ui.hover',str(dest/'libSpaceMouseUIHover.dylib')],check=True)
subprocess.run(['clang','-O2','-Wall','-Wextra','-Werror','-std=c11','-dynamiclib',
 str(root/'tools/c4d-plugin/ortho_draw.c'),'-o',str(dest/'libSpaceMouseUIOrtho.dylib')],check=True)
subprocess.run(['codesign','--force','--sign','-','--identifier','local.spacemouse.c4d.ui.ortho',str(dest/'libSpaceMouseUIOrtho.dylib')],check=True)
subprocess.run(['clang','-fobjc-arc','-O2','-Wall','-Wextra','-Wno-unused-parameter','-dynamiclib',
 '-framework','AppKit','-framework','ApplicationServices',str(root/'tools/c4d-plugin/scroll_transport.m'),'-o',str(dest/'libSpaceMouseUIScroll.dylib')],check=True)
subprocess.run(['codesign','--force','--sign','-','--identifier','local.spacemouse.c4d.ui.scroll',str(dest/'libSpaceMouseUIScroll.dylib')],check=True)
subprocess.run(['clang','-fobjc-arc','-O2','-Wall','-Wextra','-Wno-unused-parameter','-dynamiclib',
 '-I/Library/Frameworks/3DconnexionClient.framework/Headers','-F/Library/Frameworks','-framework','3DconnexionClient',
 '-framework','AppKit','-framework','ApplicationServices',str(root/'tools/c4d-plugin/file_dialog_scroll.m'),'-o',str(dest/'libSpaceMouseUIDialog.dylib')],check=True)
subprocess.run(['codesign','--force','--sign','-','--identifier','local.spacemouse.c4d.ui.dialog',str(dest/'libSpaceMouseUIDialog.dylib')],check=True)
source=root/'tools/c4d-navigation'
(dest/'runtime').mkdir(exist_ok=True)
shutil.copy2(root/'tools/c4d-plugin/docked_node_geometry.py',dest/'runtime/docked_node_geometry.py')
geometry=(source/'inspect_native_views.py').read_text().split('\ndef main():',1)[0]
(dest/'runtime/inspect_native_views.py').write_text(geometry+'\n')
# Parameterize diagnostics/runtime storage, retaining the accepted navigation
# implementation verbatim otherwise. No project-root dependency is packaged.
text=(source/'timeline_direct.py').read_text()
text=text.replace("ROOT=Path('/Users/leah/Documents/Projects/SpaceMouse')", "SOURCE=Path(__file__).resolve().parent\nSTATE=Path(SPACEMOUSE_STATE)\nSTATE.mkdir(parents=True,exist_ok=True)")
text=text.replace("ROOT/'tools/c4d-navigation/inspect_native_views.py'","SOURCE/'inspect_native_views.py'")
text=text.replace("ROOT/'.build/","STATE/'")
if 'ROOT' in text or '/Users/leah/' in text:raise RuntimeError('Unexpected project dependency in Timeline module')
(dest/'runtime/timeline_direct.py').write_text(text)
import runpy
runpy.run_path(str(root/'tools/c4d-plugin/build_preferences_resources.py'))['generate'](dest/'res')
manifest={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json'}
(dest/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(dest)
