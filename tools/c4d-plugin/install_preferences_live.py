"""Load installed Preferences/routing code without changing the input bridge."""
import builtins,runpy,json,ctypes as C
nav=builtins._spacemouse_ui_navigation
module=runpy.run_path(str(nav.package/'plugin_runtime.py'),run_name='spacemouse_ui_preferences_runtime')
model=runpy.run_path(str(nav.package/'preferences_model.py'),run_name='spacemouse_ui_preferences_model')
nav.end()
if nav.timeline:nav.timeline['flush_redraw']()
nav.preference_model=model;nav.settings=model['normalise'](nav.settings);nav.save()
nav.target=None;nav.__class__=module['Navigation']
nav.native.SMUIRead.argtypes=[C.POINTER(module['Input'])]
nav.native.SMUIContext.argtypes=[C.POINTER(module['Context'])]
nav.timeline=runpy.run_path(str(nav.package/'runtime/timeline_direct.py'),run_name='spacemouse_ui_preferences_timeline',init_globals={'SPACEMOUSE_STATE':str(nav.state)})
nav.last_geometry=0;nav.refresh_geometry()
owner=runpy.run_path(str(nav.package/'SpaceMouseUI.pyp'),run_name='spacemouse_ui_preferences_owner')
identifier=owner['register_preferences']()
(nav.state/'preferences-update.json').write_text(json.dumps({'id':identifier,'settings':nav.settings,'status':'Preferences registered; original native bridge retained'}))
print('SpaceMouse UI Preferences registered:',identifier)
