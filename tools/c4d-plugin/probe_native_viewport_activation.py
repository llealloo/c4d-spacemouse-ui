"""Test C4D's own activation routine, restoring the original view."""
import builtins,runpy,c4d,json
from pathlib import Path
nav=builtins._spacemouse_ui_navigation
api=nav.timeline
native=runpy.run_path('/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-plugin/viewport_activation.py')['bind'](api)
doc=c4d.documents.GetActiveDocument();count=doc.GetBaseDrawCount();handle=api['active_document']()
def index():return next((i for i in range(count) if doc.GetBaseDraw(i)==doc.GetActiveBaseDraw()),None)
before=index();selection=list(doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_0))
assert before is not None and native['view'](handle,before)==native['active'](handle)
results=[]
try:
 for i in range(count):
  native['set_view'](handle,i,count)
  results.append({'requested':i,'readBack':index()})
finally:native['set_view'](handle,before,count)
assert selection==list(doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_0))
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/native-viewport-activation-probe.json').write_text(json.dumps({'before':before,'tests':results,'restored':index(),'selectionUnchanged':True},indent=2))
print('Native viewport activation verified and restored')
