"""Exercise fractional direct navigation and restore exact view fractions."""
import builtins,ctypes as C,json,runpy,struct,time,math
from pathlib import Path
root=Path('/Users/leah/Documents/Projects/SpaceMouse');nav=builtins._spacemouse_ui_navigation
api=runpy.run_path(str(root/'tools/c4d-navigation/timeline_direct.py'));rows=[]
for entry in api['refresh_registry'](True):
 parent,area=entry['parent'],entry['area'];_,state=api['resolve_definition'](parent,entry['doc'])
 raw=struct.unpack('<4d',api['read'](state+0x90,32));before=api['values'](state)
 cu_table,cu,width,plot_width,rect=api['geometry'](parent,area)
 x=C.c_double(width-plot_width*.5);y=C.c_double((rect[1]+35+rect[3])*.5)
 convert=C.CFUNCTYPE(C.c_bool,C.c_void_p,C.POINTER(C.c_double),C.POINTER(C.c_double))(api['ptr'](cu_table+0x2a0))
 assert convert(cu,C.byref(x),C.byref(y))
 packet={'window':entry['window'],'screen':[x.value,y.value],'dx':0,'dy':0,'zoom':False,'phase':128}
 row={'index':entry['index'],'mode':entry['mode'],'window':entry['window'],'before':before}
 try:
  assert api['navigate'](packet)
  packet.update(dx=.05,dy=.05,phase=1);assert api['navigate'](packet)
  after=api['values'](state);row['fractionalPan']=after
  expectedCenter=(before[0]+before[1])*.5-.05*(before[1]-before[0])/plot_width
  assert abs((after[0]+after[1])*.5-expectedCenter)<1.1e-6
  assert after[:2]!=before[:2]
  if entry['mode']==1:assert after[3]!=before[3]
  packet.update(dx=0,dy=.05,zoom=True);assert api['navigate'](packet)
  zoomed=api['values'](state);row['fractionalZoom']=zoomed
  assert zoomed[1]-zoomed[0]<after[1]-after[0]
  if entry['mode']==1:assert abs(zoomed[2]/after[2]-math.exp(.0001))<1e-10
  api['flush_redraw']()
 finally:
  api['RANGE'](parent,C.byref(api['TimeValue'](*raw[:2])),C.byref(api['TimeValue'](*raw[2:])),1)
  api['VERTICAL'](parent,before[2],before[3])
  cd=api['ptr'](parent+8);cd_table=api['ptr'](api['BASE']+0x5b8ad8)
  C.CFUNCTYPE(C.c_bool,C.c_void_p,*([C.c_int]*5))(api['ptr'](cd_table+0xc0))(cd,0x232d,*rect)
  api['REDRAW'](parent,0,1,0,1,1,None,0)
 row['restored']=api['values'](state);assert row['restored']==before
 rows.append(row)
assert rows,'No Timeline is visible'
(root/'.build/timeline-fractional-check.json').write_text(json.dumps({'time':time.time(),'entries':rows},indent=2));print('Fractional Timeline checks and exact view restore passed:',len(rows))
