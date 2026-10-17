"""Isolated view-range precision test; restore exact original fractions."""
import builtins,ctypes as C,json,math,struct,time
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;api=nav.timeline;rows=[]
def value(seconds):
 numerator=math.floor(seconds*1000000+.5);denominator=1000000;gcd=math.gcd(numerator,denominator)
 return api['TimeValue'](numerator//gcd,denominator//gcd)
for entry in api['refresh_registry'](True):
 parent=entry['parent'];_,state=api['resolve_definition'](parent,entry['doc']);raw=struct.unpack('<4d',api['read'](state+0x90,32));before=api['values'](state)
 row={'index':entry['index'],'mode':entry['mode'],'window':entry['window'],'before':before,'checks':[]}
 try:
  for shift in (.00001,.0001):
   left,right=before[0]+shift,before[1]+shift
   api['RANGE'](parent,C.byref(value(left)),C.byref(value(right)),1)
   after=api['values'](state);row['checks'].append({'shift':shift,'after':after,'actualShift':after[0]-before[0]})
 finally:
  api['RANGE'](parent,C.byref(api['TimeValue'](*raw[:2])),C.byref(api['TimeValue'](*raw[2:])),1)
  api['REDRAW'](parent,0,1,0,1,1,None,0)
 row['restored']=api['values'](state);assert row['restored']==before
 rows.append(row)
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-time-precision-probe.json').write_text(json.dumps({'time':time.time(),'entries':rows},indent=2));print('Timeline time precision probe completed:',len(rows))
