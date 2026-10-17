"""Explicit live lifecycle verification and activation of the installed update."""
import builtins,c4d,json,runpy,time
from pathlib import Path
nav=builtins._spacemouse_ui_navigation
project=Path('/Users/leah/Documents/Projects/SpaceMouse')
trial=getattr(builtins,'_spacemouse_ortho_draw_trial',None)
if trial:
    runpy.run_path(str(project/'tools/c4d-plugin/investigation/restore_ortho_draw_trial.py'))
    del builtins._spacemouse_ortho_draw_trial
controller=runpy.run_path(str(nav.package/'ortho_hover.py'))['Correction'](nav.timeline,nav.package)
original=c4d.documents.GetActiveDocument()
def python_count():
    count=0;doc=c4d.documents.GetFirstDocument()
    while doc:count+=1;doc=doc.GetNext()
    return count
assert len(list(controller.documents()))==python_count()
initial=len(list(controller.instances()))
controller.update(True)
assert all(v==controller.helper.SMOrthoVTable() for p,v in controller.instances())
probe=c4d.documents.BaseDocument();probe.SetDocumentName('SpaceMouse temporary lifecycle check')
try:
    c4d.documents.InsertBaseDocument(probe)
    assert len(list(controller.documents()))==python_count()
    controller.update(True)
    assert len(list(controller.instances()))==initial+1
    assert all(v==controller.helper.SMOrthoVTable() for p,v in controller.instances())
    controller.update(False)
    assert all(v==controller.base+0x50530 for p,v in controller.instances())
    controller.update(True)
    assert all(v==controller.helper.SMOrthoVTable() for p,v in controller.instances())
finally:
    c4d.documents.SetActiveDocument(original)
    c4d.documents.KillDocument(probe)
controller.update(True)
assert len(list(controller.instances()))==initial
controller.close()
assert all(v==controller.base+0x50530 for p,v in controller.instances())
controller.update(True)
# Adopt the new runtime without replacing the accepted native input connection.
module=runpy.run_path(str(nav.package/'plugin_runtime.py'))
nav.__class__=module['Navigation']
nav.native.SMUIRead.argtypes=[module['C'].POINTER(module['Input'])]
nav.native.SMUIContext.argtypes=[module['C'].POINTER(module['Context'])]
nav.preference_model=runpy.run_path(str(nav.package/'preferences_model.py'))
nav.settings=nav.preference_model['normalise'](nav.settings);nav.save()
nav.ortho_hover=controller;nav._ortho_failed=False;nav._ortho_next=0
controller.update(nav.settings['fixOrthographicHover'])
c4d.DrawViews(c4d.DRAWFLAGS_NO_THREAD|c4d.DRAWFLAGS_NO_ANIMATION|c4d.DRAWFLAGS_FORCEFULLREDRAW)
(project/'.build/packaged-ortho-hover-check.json').write_text(json.dumps({'liveDocuments':initial,'newDocument':True,'documentClose':True,'disableRestore':True,'reenable':True,'runtimeCloseRestore':True,'active':nav.settings['fixOrthographicHover'],'timestamp':time.time()},indent=2))
print('Installed orthographic hover correction active; document lifecycle and restore checks passed')
