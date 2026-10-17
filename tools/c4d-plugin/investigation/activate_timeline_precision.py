"""Hot-load installed Timeline precision code without input reconnection."""
import builtins,ctypes as C,json,runpy,time
from pathlib import Path
nav=builtins._spacemouse_ui_navigation
nav.end()
if nav.timeline:nav.timeline['flush_redraw']()
module=runpy.run_path(str(nav.package/'plugin_runtime.py'))
api=runpy.run_path(str(nav.package/'runtime/timeline_direct.py'),init_globals={'SPACEMOUSE_STATE':str(nav.state)})
entries=api['refresh_registry'](True);assert entries
nav.target=None;nav.__class__=module['Navigation']
nav.native.SMUIRead.argtypes=[C.POINTER(module['Input'])];nav.native.SMUIContext.argtypes=[C.POINTER(module['Context'])]
nav.timeline=api;nav.last_geometry=0;nav.refresh_geometry()
# Prove fractional packets traverse the installed emitter, without changing views.
realPost=nav.post;sent=[];originalContext=nav.context
try:
 nav.target=('timeline',entries[0]['window'],entries[0]['index'],False,(0,0,100,100))
 nav.post=lambda *args:sent.append(args)
 nav.emit(.05,.05,False);nav.emit(0,.05,True)
 assert sent[1]==(.05,.05,1,False) and sent[3]==(0,.05,1,True)
finally:
 del nav.post;nav.gestures=[False,False];nav.remainders=[0.,0.,0.];nav.target=None;nav.context=originalContext
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-precision-activation.json').write_text(json.dumps({'time':time.time(),'panels':[{k:e[k] for k in ('window','index','mode')} for e in entries],'fractionalEmitter':True,'status':'active; native input connection and sensitivities retained'},indent=2));print('Fractional Timeline navigation active:',len(entries),'panels')
