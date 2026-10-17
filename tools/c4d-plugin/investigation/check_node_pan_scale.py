"""Verify the new read-only scale resolver against actual C4D zoom events."""
import builtins,runpy,json,math,time
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;root=Path('/Users/leah/Documents/Projects/SpaceMouse');module=runpy.run_path(str(root/'tools/c4d-plugin/node_pan_scale.py'))
reader=module['ScaleReader'](nav.timeline)
geometry=runpy.run_path(str(root/'tools/c4d-plugin/docked_node_geometry.py'))
graphs=geometry['read_node_graphs'](nav.geometry,nav.timeline,nav.viewports)
graph=next(g for g in graphs if g.get('message'));message=graph['message']
a=reader.scale(message);assert a is not None
builtins._spacemouse_node_pan_probe['move'](0,-40,True)
b=reader.scale(message);assert b is not None and b<a
builtins._spacemouse_node_pan_probe['move'](0,40,True)
c=reader.scale(message);assert c is not None and c>b
result={'time':time.time(),'graph':graph,'before':a,'zoomOut':b,'zoomIn':c,'panFactors':[1/a,1/b,1/c]}
(root/'.build/node-scale-live-check.json').write_text(json.dumps(result,indent=2));builtins._spacemouse_node_scale_reader=reader
print('Node scale read verified',a,b,c)
