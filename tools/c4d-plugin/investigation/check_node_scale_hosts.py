"""Read-only comparison of current docked/floating graph routing and scale."""
import builtins,json,time
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;nav.refresh_geometry()
rows=[]
for graph in nav.graphs:
 row=dict(graph);row['scale']=nav._node_scale.scale(graph.get('message',0))
 rows.append(row)
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/node-scale-hosts.json').write_text(json.dumps({'time':time.time(),'graphs':rows,'viewports':nav.viewports},indent=2));print('Node host scale diagnostics saved')
