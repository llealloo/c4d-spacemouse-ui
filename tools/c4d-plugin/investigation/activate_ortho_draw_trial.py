"""Apply a reversible, single-document Draw return correction for this session."""
import builtins, c4d, ctypes as C, hashlib, json, runpy
from pathlib import Path
root=Path('/Users/leah/Documents/Projects/SpaceMouse')
x=runpy.run_path(str(root/'tools/c4d-plugin/investigation/inspect_ortho_draw.py'))
api=x['api'];read=x['read'];ptr=x['ptr'];base=x['base'];instance=x['instance']
core=Path('/Applications/Maxon Cinema 4D 2027/corelibs/c4d_base.xlib')
assert hashlib.sha256(core.read_bytes()).hexdigest()=='1c0e204bc48bee5c7898b4e72e353a0f15304ea9b1036412434675f7ec848b62'
corebase=x['images'][str(core)]
expected={'scene_camera':0x76be50,'editor_camera':0x76be58,'camera_projection':0x1e2964}
for name,offset in expected.items():
 assert x['functions'][name]==corebase+offset, ('Unexpected SDK entry',name)
# Confirm SDK camera projection values for each live viewport before wrapping.
scene=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_void_p)(x['functions']['scene_camera'])
editor=C.CFUNCTYPE(C.c_void_p,C.c_void_p)(x['functions']['editor_camera'])
projection=C.CFUNCTYPE(C.c_int,C.c_void_p)(x['functions']['camera_projection'])
get_view=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int)(ptr(x['doc_table']+25*8))
document=c4d.documents.GetActiveDocument();projections=[]
for index in range(document.GetBaseDrawCount()):
 view=get_view(x['doc'],index);camera=scene(view,x['doc']) or editor(view)
 projections.append(projection(camera))
assert projections and projections[0]==0 and all(p>1 for p in projections[1:]),projections
helper=C.CDLL(str(root/'.build/libSpaceMouseOrthoDrawTrial.dylib'))
helper.SMOrthoInstall.argtypes=[C.c_void_p,C.c_uint64,C.c_uint64,C.c_void_p,C.c_void_p,C.c_void_p];helper.SMOrthoInstall.restype=C.c_int
helper.SMOrthoRestore.argtypes=[C.c_void_p];helper.SMOrthoRestore.restype=C.c_int
helper.SMOrthoEnable.argtypes=[C.c_bool]
helper.SMOrthoCalls.restype=C.c_ulong;helper.SMOrthoCorrected.restype=C.c_ulong
c4d.StopAllThreads()
assert ptr(instance)==base+0x50530
status=helper.SMOrthoInstall(instance,base+0x50530,base+0x5c98,*[x['functions'][n] for n in ('scene_camera','editor_camera','camera_projection')])
assert status==0,status
assert ptr(ptr(instance)+27*8)!=base+0x5c98
builtins._spacemouse_ortho_draw_trial={'helper':helper,'instance':instance,'original_vtable':base+0x50530,'doc':x['doc'],'projections':projections}
c4d.DrawViews(c4d.DRAWFLAGS_NO_THREAD|c4d.DRAWFLAGS_NO_ANIMATION|c4d.DRAWFLAGS_FORCEFULLREDRAW)
Path(root/'.build/ortho-draw-trial-state.json').write_text(json.dumps({'status':status,'projections':projections,'calls':helper.SMOrthoCalls(),'corrected':helper.SMOrthoCorrected()},indent=2))
print('Session-only orthographic Draw correction active; navigation callbacks unchanged')
