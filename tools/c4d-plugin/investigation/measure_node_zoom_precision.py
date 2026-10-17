"""Measure existing local scroll transport at fractional input deltas."""
import builtins,runpy,time,json
from pathlib import Path
root=Path('/Users/leah/Documents/Projects/SpaceMouse');nav=builtins._spacemouse_ui_navigation
module=runpy.run_path(str(root/'tools/c4d-plugin/node_pan_scale.py'));reader=module['ScaleReader'](nav.timeline)
nav.refresh_geometry();graph=next(g for g in nav.graphs if reader.scale(g.get('message',0)) is not None)
message=graph['message'];x=graph['x']+graph['width']/2;y=graph['y']+graph['height']/2
initial=reader.scale(message);rows=[]
scroll=nav.native.SMUIScroll
if globals().get('PRECISE',False):
 import ctypes as C
 helper=C.CDLL(str(root/'.build/libSpaceMouseUIScroll.dylib'))
 helper.SMPreciseScroll.argtypes=[C.c_int64,*([C.c_double]*4),C.c_int,C.c_int];helper.SMPreciseScroll.restype=C.c_int
 builtins._spacemouse_precise_scroll_trial=helper
 scroll=helper.SMPreciseScroll
def event(dx,dy,zoom):
 for a,b,phase in [(0,0,128),(dx,dy,1),(0,0,4)]:
  assert scroll(graph['window'],x,y,a,b,phase,int(zoom))
def state():
 # Resolve using the verified callback ownership chain, like ScaleReader.
 ptr,read=nav.timeline['ptr'],nav.timeline['read'];obs=ptr(message+0x110);entries=ptr(obs+0x28)
 callback=ptr(entries+8);window=ptr(ptr(callback+0x18));import struct
 return list(struct.unpack('<3f',read(window+0x638+0x1a40,12)))
for delta in (.05,.1,.25,.5,1.,2.,4.,-4.,-2.,-1.,-.5,-.25,-.1,-.05):
 before=state();event(0,delta,True);after=state()
 rows.append({'kind':'zoom','delta':delta,'before':before,'after':after,'ratio':after[2]/before[2]})
for delta in (.05,.1,.25,.5,1.,-.05,-.1,-.25,-.5,-1.):
 before=state();event(delta,0,False);after=state()
 rows.append({'kind':'pan','delta':delta,'before':before,'after':after,'screenDelta':(after[0]-before[0])})
(root/('.build/node-zoom-precision'+('-fractional' if globals().get('PRECISE',False) else '')+'.json')).write_text(json.dumps({'time':time.time(),'graph':graph,'initialScale':initial,'finalScale':reader.scale(message),'rows':rows},indent=2));print('Node zoom and fractional input measurements saved')
