"""Load the installed component-hover helper without replacing input bridge."""
import builtins,runpy
nav=builtins._spacemouse_ui_navigation
trial=getattr(builtins,'_spacemouse_hover_gate',None)
if trial:trial.SMHoverGateStop()
if getattr(nav,'hover_gate',None):nav.hover_gate.SMHoverGateStop()
module=runpy.run_path(str(nav.package/'plugin_runtime.py'))
nav.end();nav.native.SMUIClaim(0);nav.target=None
nav.__class__=module['Navigation']
nav.native.SMUIRead.argtypes=[module['C'].POINTER(module['Input'])]
nav.native.SMUIContext.argtypes=[module['C'].POINTER(module['Context'])]
nav.preference_model=runpy.run_path(str(nav.package/'preferences_model.py'))
nav.settings=nav.preference_model['normalise'](nav.settings);nav.save()
nav.init_hover_gate()
assert nav.hover_gate is not None
print('Packaged component-mode hover suppression active; input bridge unchanged')
