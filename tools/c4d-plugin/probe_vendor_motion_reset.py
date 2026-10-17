import builtins,runpy,json
from pathlib import Path
nav=builtins._spacemouse_ui_navigation
binding=runpy.run_path('/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-plugin/vendor_motion_reset.py')['bind'](nav.timeline)
result={'chain':binding['chain']}
for name in (b'view.affine',b'view.perspective',b'view.rotatable'):
 status,value=binding['read'](name)
 result[name.decode()]={'status':status,'type':value.type,'data':bytes(value.data).hex()}
nav._vendor_motion_reset=binding
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/vendor-navlib-probe.json').write_text(json.dumps(result,indent=2))
print('Vendor Navlib read-only probe saved')
