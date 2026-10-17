"""Load the installed Python-only routing update without replacing the client."""
import builtins,runpy,json
navigation=builtins._spacemouse_ui_navigation
module=runpy.run_path(str(navigation.package/'plugin_runtime.py'),run_name='spacemouse_ui_updated_runtime')
navigation.end()
navigation.native.SMUIClaim(0)
navigation.target=None
navigation.__class__=module['Navigation']
# Rebind snapshot pointer types to the reloaded module's ctypes classes.
navigation.native.SMUIRead.argtypes=[module['C'].POINTER(module['Input'])]
navigation.native.SMUIContext.argtypes=[module['C'].POINTER(module['Context'])]
if hasattr(navigation,'_node_geometry'):del navigation._node_geometry
navigation.last_geometry=0
navigation.refresh_geometry()
(navigation.state/'docked-node-update.json').write_text(json.dumps({'nodeGraphs':navigation.graphs,'status':'Python-only update loaded; existing SDK client retained'}))
print('SpaceMouse UI docked Node update loaded:',navigation.graphs)
