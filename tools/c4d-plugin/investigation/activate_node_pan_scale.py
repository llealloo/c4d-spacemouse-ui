"""Hot-load the installed Python refinement, retaining all native connections."""
import builtins,runpy,ctypes as C,json,time
from pathlib import Path
nav=builtins._spacemouse_ui_navigation
module=runpy.run_path(str(nav.package/'plugin_runtime.py'))
nav.end();nav.target=None;nav.__class__=module['Navigation']
nav.native.SMUIRead.argtypes=[C.POINTER(module['Input'])]
nav.native.SMUIContext.argtypes=[C.POINTER(module['Context'])]
nav._node_geometry=runpy.run_path(str(nav.package/'runtime/docked_node_geometry.py'))
if hasattr(nav,'_node_scale'):del nav._node_scale
nav.refresh_geometry();checks=[]
for g in nav.graphs:
 bounds=tuple(g[k] for k in ('x','y','width','height'))
 target=('node',g['window'],0,False,bounds)
 factor=nav.node_pan_factor(target)
 scale=nav._node_scale.scale(g.get('message',0)) if nav._node_scale else None
 if scale is not None:
  assert abs(factor-2/(1+scale))<1e-6
  started=time.perf_counter()
  for _ in range(100):assert nav.node_pan_factor(target)==factor
  elapsed=(time.perf_counter()-started)/100
  checks.append({'window':g['window'],'bounds':bounds,'scale':scale,'panFactor':factor,'readSeconds':elapsed})
assert checks,'No live Node Editor graph scale resolved'
assert nav.node_pan_factor(('scroll',0,0,False,()))==1
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/node-pan-scale-activation.json').write_text(json.dumps({'time':time.time(),'graphs':checks,'status':'active; native connections retained'},indent=2))
print('Zoom-relative Node pan active:',checks)
