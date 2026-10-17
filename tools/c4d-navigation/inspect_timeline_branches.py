"""Read only: find the document's Timeline definition branches."""
import c4d,json
from pathlib import Path
result=[]
doc=c4d.documents.GetActiveDocument()
def walk(owner,depth=0):
    if depth>2:return
    for branch in owner.GetBranchInfo(64) or []:
        head=branch.get('head')
        item=head.GetDown() if head else None
        items=[];count=0
        while item and count<100:
            entry={'type':item.GetType(),'pythonClass':type(item).__name__}
            items.append(entry)
            if item.GetType()==465001515:
                data=item.GetData()
                entry['data']=[{'id':key,'type':data.GetType(key),'value':repr(value)[:160]} for key,value in data]
            if depth<2 and item.GetType() not in (5140,5612):walk(item,depth+1)
            item=item.GetNext();count+=1
        result.append({'depth':depth,'branch':str(branch.get('name')),'items':items})
if doc:walk(doc)
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-branches.json').write_text(json.dumps(result,indent=2))
