"""Replace only the session guard with local smooth file-panel scrolling."""
import builtins, ctypes as C, json
from pathlib import Path
root=Path('/Users/leah/Documents/Projects/SpaceMouse')
nav=builtins._spacemouse_ui_navigation
Input=nav.tick.__globals__['Input'];state=Input();nav.native.SMUIRead(C.byref(state))
assert state.ready and state.client,'Vendor input bridge not ready'
old=getattr(builtins,'_spacemouse_file_dialog_trial',None)
old_close=nav.close
helper=C.CDLL(str(root/'.build/libSpaceMouseFileDialogScrollV10.dylib'))
helper.SMFileDialogStart.argtypes=[C.c_uint16];helper.SMFileDialogStart.restype=C.c_int
helper.SMFileDialogStop.argtypes=[];helper.SMFileDialogStop.restype=None
helper.SMFileDialogReport.argtypes=[C.c_char_p];helper.SMFileDialogReport.restype=None
helper.SMFileDialogRead.argtypes=[C.POINTER(C.c_uint64)];helper.SMFileDialogRead.restype=None
if old:
    old['helper'].SMFileDialogStop()
    original_close=old['close']
else: original_close=nav.close
result=helper.SMFileDialogStart(state.client)
if result:
    if old: old['helper'].SMFileDialogStart(state.client)
    raise RuntimeError('Scroll trial refused installation: %s'%result)
def close():
    helper.SMFileDialogStop()
    original_close()
nav.close=close
if old:
    retained=getattr(builtins,'_spacemouse_retired_dialog_trials',[])
    retained.append(old);builtins._spacemouse_retired_dialog_trials=retained
builtins._spacemouse_file_dialog_trial=dict(helper=helper,nav=nav,close=original_close)
helper.SMFileDialogReport(str(root/'.build/file-dialog-scroll-state.json').encode())
(root/'.build/file-dialog-scroll-activation.json').write_text(json.dumps(dict(result=result,client=state.client)))
print('File-dialog trial active. macOS input-posting permission:',bool(helper.SMDialogPostAccess()))
