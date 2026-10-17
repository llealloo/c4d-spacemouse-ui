"""Controlled, reversible graph navigation only; never changes nodes."""
import builtins,json,time
from pathlib import Path
nav=builtins._spacemouse_ui_navigation
nav.refresh_geometry()
assert nav.graphs, 'Open a Node Editor graph first'
graph=max(nav.graphs,key=lambda g:g['width']*g['height'])
# Existing native bridge expects Quartz screen points, matching discovered bounds.
x=graph['x']+graph['width']*.5;y=graph['y']+graph['height']*.5
history=[]
def move(dx=0,dy=0,zoom=False):
    events=[]
    for a,b,phase in [(0,0,128),(dx,dy,1),(0,0,4)]:
        events.append(nav.native.SMUIScroll(graph['window'],x,y,a,b,phase,int(zoom)))
    history.append({'dx':dx,'dy':dy,'zoom':zoom,'events':events,'time':time.time()})
    Path('/Users/leah/Documents/Projects/SpaceMouse/.build/node-pan-probe.json').write_text(json.dumps({'graph':graph,'history':history},indent=2))
    print('Graph navigation probe:',dx,dy,'zoom' if zoom else 'pan',events)
builtins._spacemouse_node_pan_probe={'move':move,'graph':graph,'history':history}
print('Graph navigation probe ready')
