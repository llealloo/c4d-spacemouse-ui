"""Reversible viewport highlighting A/B probe, run explicitly from C4D Console."""
import builtins,c4d,json
from pathlib import Path

def snapshot():
 doc=c4d.documents.GetActiveDocument();view=doc.GetActiveBaseDraw()
 return {'mode':doc.GetMode(),'tool':doc.GetAction(),
         'filters':{name:view[getattr(c4d,name)] for name in ('BASEDRAW_DISPLAYFILTER_HIGHLIGHTING','BASEDRAW_DISPLAYFILTER_HIGHLIGHTING_HANDLES','BASEDRAW_DISPLAYFILTER_OBJECTHIGHLIGHTING') if hasattr(c4d,name)}}

def disable():
 if getattr(builtins,'_spacemouse_highlight_probe',None):raise RuntimeError('Restore the previous probe first')
 doc=c4d.documents.GetActiveDocument();view=doc.GetActiveBaseDraw()
 key=c4d.BASEDRAW_DISPLAYFILTER_HIGHLIGHTING
 original=view[key]
 builtins._spacemouse_highlight_probe=(view,key,original)
 view[key]=False
 c4d.EventAdd()
 print('Temporary highlighting filter disabled; editing mode and selection unchanged')

def restore():
 saved=getattr(builtins,'_spacemouse_highlight_probe',None)
 if saved:
  view,key,value=saved;view[key]=value
  builtins._spacemouse_highlight_probe=None;c4d.EventAdd()
  print('Original highlighting filter restored')

if __name__=='__main__':
 print(snapshot())
