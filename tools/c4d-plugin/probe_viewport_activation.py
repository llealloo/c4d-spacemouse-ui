"""Isolated active-flag probe; restores every viewport flag before returning."""
import c4d,json
from pathlib import Path
doc=c4d.documents.GetActiveDocument()
views=[doc.GetBaseDraw(i) for i in range(doc.GetBaseDrawCount())]
original=[bool(v.GetBit(c4d.BIT_ACTIVE)) for v in views]
def index():
 active=doc.GetActiveBaseDraw()
 return next((i for i,v in enumerate(views) if v==active),None)
result={'before':index(),'views':[{'index':i,'active':original[i],'frame':v.GetFrameScreen()} for i,v in enumerate(views)],'tests':[]}
try:
 for i,view in enumerate(views):
  for candidate in views:candidate.DelBit(c4d.BIT_ACTIVE)
  view.SetBit(c4d.BIT_ACTIVE)
  result['tests'].append({'requested':i,'readBack':index()})
finally:
 for view,active in zip(views,original):
  if active:view.SetBit(c4d.BIT_ACTIVE)
  else:view.DelBit(c4d.BIT_ACTIVE)
result['restored']=index()
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/viewport-activation-probe.json').write_text(json.dumps(result,indent=2))
print('Viewport flag probe saved; original flags restored')
