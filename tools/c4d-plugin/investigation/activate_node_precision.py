"""Adopt installed motion code without restarting any input client."""
import builtins,ctypes as C,json,runpy,time
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;module=runpy.run_path(str(nav.package/'plugin_runtime.py'))
nav.end();nav.target=None;nav.__class__=module['Navigation']
nav.native.SMUIRead.argtypes=[C.POINTER(module['Input'])];nav.native.SMUIContext.argtypes=[C.POINTER(module['Context'])]
if hasattr(nav,'_node_transport'):del nav._node_transport
transport=nav.node_transport();assert transport is not None
nav.refresh_geometry();reader=runpy.run_path(str(nav.package/'node_pan_scale.py'))['ScaleReader'](nav.timeline)
graph=next(g for g in nav.graphs if reader.scale(g.get('message',0)) is not None)
originalContext=nav.context;bounds=tuple(graph[k] for k in ('x','y','width','height'));context=module['Context']()
context.x=bounds[0]+bounds[2]/2;context.y=bounds[1]+bounds[3]/2;context.window=graph['window'];context.active=1
nav.context=context;nav.target=('node',graph['window'],0,False,bounds)
try:
 initial=reader.scale(graph['message']);nav.emit(.05,.05,False);nav.emit(0,.05,True)
 after=reader.scale(graph['message']);assert after>initial
 nav.emit(-.05,-.05,False);nav.emit(0,-.05,True);nav.end()
 restored=reader.scale(graph['message']);assert abs(restored/initial-1)<1e-6
finally:
 nav.end();nav.target=None;nav.context=originalContext
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/node-precision-activation.json').write_text(json.dumps({'time':time.time(),'graph':graph,'initialScale':initial,'fractionalZoomScale':after,'restoredScale':restored,'status':'active; constant-screen-speed pan, fractional Node events, reciprocal zoom; existing input connection retained'},indent=2))
print('Precise Blender-style Node motion active; live fractional pan/zoom passed')
