import builtins,c4d,ctypes as C,json,time
from pathlib import Path
nav=builtins._spacemouse_ui_navigation
doc=c4d.documents.GetActiveDocument();Input=nav.__class__.__init__.__globals__['Input'];input=Input();nav.native.SMUIRead(C.byref(input))
keys=['BASEDRAW_DISPLAYFILTER_HIGHLIGHTING','BASEDRAW_DISPLAYFILTER_HIGHLIGHTING_HANDLES','BASEDRAW_DISPLAYFILTER_OBJECTHIGHLIGHTING']
result={'axes':list(input.axes),'inputAge':time.monotonic()-input.lastInput,'reports':input.reports,'views':[]}
for i in range(doc.GetBaseDrawCount()):
 v=doc.GetBaseDraw(i)
 result['views'].append({'index':i,'active':v==doc.GetActiveBaseDraw(),'projection':v[c4d.BASEDRAW_DATA_PROJECTION],'filters':{k:v[getattr(c4d,k)] for k in keys},'frame':v.GetFrameScreen()})
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/hover-recovery-inspection.json').write_text(json.dumps(result,indent=2))
print('Hover recovery inspection saved')
