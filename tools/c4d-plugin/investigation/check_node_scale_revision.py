"""Read-only live check of floating graph metadata and bounded pan curve."""
import builtins,runpy,json,time
from pathlib import Path
root=Path('/Users/leah/Documents/Projects/SpaceMouse');nav=builtins._spacemouse_ui_navigation
geometry=runpy.run_path(str(root/'tools/c4d-plugin/docked_node_geometry.py'))
module=runpy.run_path(str(root/'tools/c4d-plugin/node_pan_scale.py'));reader=module['ScaleReader'](nav.timeline)
graphs=geometry['read_node_graphs'](nav.geometry,nav.timeline,nav.viewports);checks=[]
for graph in graphs:
 scale=reader.scale(graph.get('message',0))
 checks.append(dict(graph,scale=scale,factor=reader.factor(graph.get('message',0))))
assert checks and all(g['scale'] is not None for g in checks)
assert all(0<g['factor']<2 for g in checks)
(root/'.build/node-scale-revision-check.json').write_text(json.dumps({'time':time.time(),'graphs':checks},indent=2));print('All current graph scales verified:',checks)
