"""Check corrected scale ratios, fractional delivery and pointer preservation."""
import builtins,ctypes as C,json,runpy,time,hashlib
from pathlib import Path
root=Path('/Users/leah/Documents/Projects/SpaceMouse');nav=builtins._spacemouse_ui_navigation;package=root/'.build/plugin-node-precision/SpaceMouseUI'
# Reuse the already tested native image; do not load duplicate ObjC classes.
helper=builtins._spacemouse_precise_scroll_trial
builtins._spacemouse_ui_scroll_library={'digest':hashlib.sha256((package/'libSpaceMouseUIScroll.dylib').read_bytes()).hexdigest(),'helper':helper}
module=runpy.run_path(str(package/'node_event_transport.py'));transport=module['Transport'](package,nav.timeline)
reader=runpy.run_path(str(package/'node_pan_scale.py'))['ScaleReader'](nav.timeline)
nav.refresh_geometry();graph=next(g for g in nav.graphs if reader.scale(g.get('message',0)) is not None);message=graph['message']
x=graph['x']+graph['width']/2;y=graph['y']+graph['height']/2
Context=nav.tick.__globals__['Context']
beforePointer=Context();nav.native.SMUIContext(C.byref(beforePointer));rows=[]
def move(dx,dy,zoom):
 for a,b,phase in [(0,0,128),(dx,dy,1),(0,0,4)]:assert transport.post(graph['window'],x,y,a,b,phase,zoom)
initialScale=reader.scale(message)
for delta in (.05,.25,1,10,-10,-1,-.25,-.05):
 before=reader.scale(message);move(0,delta,True);after=reader.scale(message)
 amount=abs(delta)*.002;expected=1/(1-amount) if delta>0 else 1-amount
 ratio=after/before;assert abs(ratio-expected)<3e-7,(delta,ratio,expected)
 rows.append({'delta':delta,'ratio':ratio,'expected':expected})
assert abs(reader.scale(message)/initialScale-1)<2e-6
for _ in range(20):move(.05,0,False)
for _ in range(20):move(-.05,0,False)
afterPointer=Context();nav.native.SMUIContext(C.byref(afterPointer))
assert (beforePointer.x,beforePointer.y)==(afterPointer.x,afterPointer.y)
(root/'.build/node-precise-transport-check.json').write_text(json.dumps({'time':time.time(),'graph':graph,'zoomRatios':rows,'fractionalPan':True,'pointerUnchanged':True},indent=2));print('Precise Node transport and reciprocal zoom checks passed')
