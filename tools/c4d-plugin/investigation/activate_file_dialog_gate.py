"""Session-only file dialog guard; no driver profile changes."""
import builtins, ctypes as C, json
from pathlib import Path
import c4d
root=Path('/Users/leah/Documents/Projects/SpaceMouse')
nav=builtins._spacemouse_ui_navigation
assert not getattr(builtins,'_spacemouse_file_dialog_trial',None), 'Trial already loaded'
Input=nav.tick.__globals__['Input']; state=Input(); nav.native.SMUIRead(C.byref(state))
assert state.ready and state.client, 'Existing input bridge is not ready'
helper=C.CDLL(str(root/'.build/libSpaceMouseFileDialogTrial.dylib'))
helper.SMFileDialogStart.argtypes=[C.c_uint16]; helper.SMFileDialogStart.restype=C.c_int
helper.SMFileDialogStop.argtypes=[]; helper.SMFileDialogStop.restype=None
helper.SMFileDialogReport.argtypes=[C.c_char_p]; helper.SMFileDialogReport.restype=None
helper.SMFileDialogRead.argtypes=[C.POINTER(C.c_uint64)]; helper.SMFileDialogRead.restype=None
result=helper.SMFileDialogStart(state.client)
assert result==0, 'Dialog guard refused installation: %s'%result
original_close=nav.close
def close():
    helper.SMFileDialogStop()
    original_close()
nav.close=close
doc=c4d.documents.GetActiveDocument()
snapshots=[]
for i in range(doc.GetBaseDrawCount()):
    view=doc.GetBaseDraw(i)
    camera=view.GetSceneCamera(doc) or view.GetEditorCamera()
    snapshots.append((view,camera,c4d.Matrix(camera.GetMg())))
builtins._spacemouse_file_dialog_trial=dict(helper=helper,nav=nav,close=original_close,doc=doc,snapshots=snapshots)
helper.SMFileDialogReport(str(root/'.build/file-dialog-gate-state.json').encode())
(root/'.build/file-dialog-gate-activation.json').write_text(json.dumps(dict(result=result,client=state.client,views=len(snapshots))))
print('File dialog guard active for this session. Driver profile unchanged.')
