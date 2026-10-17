"""Read-only Timeline state probe through documented SDK getters.
Table locations are specific to the inspected Cinema 4D 2027 build.
"""
import ctypes as C,json,math
from pathlib import Path
import hashlib
if hashlib.sha256(Path('/Applications/Maxon Cinema 4D 2027/corelibs/c4d_manager.xlib').read_bytes()).hexdigest()!='a89f07be5d054a0bf1f2764beb383b70d869089fb8a82bda01f4813a6c26fa3b':
    raise RuntimeError('Timeline native navigation requires the inspected C4D build')
lib=C.CDLL('/usr/lib/libSystem.B.dylib')
lib._dyld_image_count.restype=C.c_uint
lib._dyld_get_image_name.argtypes=[C.c_uint];lib._dyld_get_image_name.restype=C.c_char_p
lib._dyld_get_image_header.argtypes=[C.c_uint];lib._dyld_get_image_header.restype=C.c_void_p
base=next(lib._dyld_get_image_header(i) for i in range(lib._dyld_image_count()) if (lib._dyld_get_image_name(i) or b'').endswith(b'/c4d_manager.xlib'))
lib.mach_vm_read_overwrite.argtypes=[C.c_uint,C.c_uint64,C.c_uint64,C.c_uint64,C.POINTER(C.c_uint64)]
lib.mach_vm_read_overwrite.restype=C.c_int
task=C.c_uint.in_dll(lib,'mach_task_self_').value
def read(address,size=8):
    out=C.create_string_buffer(size);actual=C.c_uint64()
    if lib.mach_vm_read_overwrite(task,address,size,C.addressof(out),C.byref(actual)) or actual.value!=size:raise RuntimeError('Unmapped Timeline state')
    return out.raw
import struct
def ptr(address):return struct.unpack('<Q',read(address))[0]
def member(table,offset,obj,restype=C.c_void_p):
    function,adjust=struct.unpack('<Qq',read(table+offset,16));target=obj+(adjust>>1)
    if adjust&1:function=ptr(ptr(target)+function)
    if not function:raise RuntimeError('Missing SDK getter')
    return C.CFUNCTYPE(restype,C.c_void_p)(function)(target)
ge=ptr(base+0x5b8a80);doc_table=ptr(base+0x5b8b10);bl=ptr(base+0x5b8af8);atom=ptr(base+0x5b8b88)
doc=C.CFUNCTYPE(C.c_void_p)(ptr(ge+0x128))()
hook=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int)(ptr(doc_table+0x108))(doc,100004808) if doc else None
node_data=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int)(ptr(bl+0x78))(hook,0) if hook else None
result={'doc':hex(doc or 0),'hook':hex(hook or 0),'hookData':hex(node_data or 0),'definitions':[]}
if node_data:
    for head_offset in [0x70,0x78]:
        head=ptr(node_data+head_offset)
        item=member(atom,0x170,head) if head else None
        count=0
        while item and count<8:
            typ=member(atom,0x20,item,C.c_int)
            entry={'headOffset':hex(head_offset),'node':hex(item),'type':typ}
            if typ==465001515:
                nd=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int)(ptr(bl+0x78))(item,0)
                entry['data']=hex(nd or 0)
                if nd:
                    entry['viewValues']=list(struct.unpack('<16d',read(nd+0x90,128)))
                    entry['mode']=struct.unpack('<i',read(nd+0x124,4))[0]
            result['definitions'].append(entry)
            item=member(atom,0xb0,item);count+=1
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-state.json').write_text(json.dumps(result,indent=2))
# Bounded, guarded pointer traversal from each native Timeline view. No writes.
import runpy,collections
n=runpy.run_path('/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-navigation/inspect_native_views.py',run_name='timeline_readonly_native')
o=n['objc'];call=n['call']
o.class_getInstanceVariable.argtypes=[C.c_void_p,C.c_char_p];o.class_getInstanceVariable.restype=C.c_void_p
o.ivar_getOffset.argtypes=[C.c_void_p];o.ivar_getOffset.restype=C.c_long
ivar=o.class_getInstanceVariable(o.objc_getClass(b'MaxonView'),b'_messageView');view_offset=o.ivar_getOffset(ivar)
app=call(o.objc_getClass(b'NSApplication'),'sharedApplication');windows=call(app,'windows');result['windows']=[]
for i in range(call(windows,'count',C.c_ulong)):
    window=call(windows,'objectAtIndex:',args=(i,),types=(C.c_ulong,))
    if not n['text'](call(window,'title')).startswith('Timeline'):continue
    view=call(window,'contentView');root=ptr(view+view_offset)
    queue=collections.deque([(root,[])])
    visited=set();matches=[]
    while queue and len(visited)<12000:
        address,path=queue.popleft()
        if address in visited:continue
        visited.add(address)
        try:blob=read(address,0x1000)
        except RuntimeError:continue
        table=struct.unpack_from('<Q',blob)[0]
        if table in (base+0x553058,base+0x553848):
            match={'address':hex(address),'vtable':hex(table-base),'path':[hex(k) for k in path]}
            if table==base+0x553058:match['configuration']=list(struct.unpack('<ii',read(address+0x2908,8)));match['cachedPan']=list(struct.unpack('<2d',read(address+0x1898,16)));match['graphTable']=hex(ptr(address+0xa88)-base);match['stateLink']=hex(ptr(address+0x1c0));match['embeddedLink']=hex(ptr(address+0x20))
            matches.append(match)
        if len(path)>=5:continue
        for off in range(0x8,len(blob),8):
            target=struct.unpack_from('<Q',blob,off)[0]
            if 0x1000000000<target<0x8000000000 and not target%8 and target not in visited:queue.append((target,path+[off]))
    result['windows'].append({'window':call(window,'windowNumber',C.c_long),'root':hex(root),'searched':len(visited),'matches':matches})
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-state.json').write_text(json.dumps(result,indent=2))
# Locate sibling Timeline user areas in the same allocator neighborhood only.
# Never publish unrelated memory; keep only exact class + embedded graph matches.
result['nearbyAreas']=[]
seeds=[int(m['address'],16) for w in result['windows'] for m in w['matches'] if m['vtable']=='0x553058']
# Previously observed candidate neighborhood in this exact process only.
import os
if os.getpid()==49782:seeds.append(0x75ff228128)
for origin in set(seed & ~0xffffff for seed in seeds):
    needle=struct.pack('<Q',base+0x553058)
    for page in range(origin,origin+0x1000000,0x100000):
        try:block=read(page,0x100000)
        except RuntimeError:continue
        start=0
        while True:
            at=block.find(needle,start)
            if at<0:break
            address=page+at;start=at+8
            if address%8:continue
            try:
                if ptr(address+0xa88)!=base+0x553848:continue
                result['nearbyAreas'].append({'address':hex(address),'cu':hex(ptr(address+0x10)),
                    'configuration':list(struct.unpack('<ii',read(address+0x2908,8))),
                    'stateLink':hex(ptr(address+0x1c0)),'cachedPan':list(struct.unpack('<2d',read(address+0x1898,16)))})
            except RuntimeError:continue
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-state.json').write_text(json.dumps(result,indent=2))
cd_table=ptr(base+0x5b8ad8);link_table=ptr(base+0x5b8b70)
for area in result['nearbyAreas']:
    address=int(area['address'],16)
    parent=ptr(address+0x18)
    area['parent']=hex(parent)
    if not parent or ptr(parent)!=base+0x553290:continue
    area['parentClass']='TimelineDialog'
    area['configuration']=list(struct.unpack('<ii',read(parent+0x2908,8)))
    area['cachedPan']=list(struct.unpack('<2d',read(parent+0x1898,16)))
    cd=ptr(parent+8)
    handle=C.CFUNCTYPE(C.c_void_p,C.c_void_p)(ptr(cd_table+0x188))(cd) if cd else None
    area['nativeHandle']=hex(handle or 0)
    for i in range(call(windows,'count',C.c_ulong)):
        w=call(windows,'objectAtIndex:',args=(i,),types=(C.c_ulong,))
        if handle in (w,call(w,'contentView')):area['window']=call(w,'windowNumber',C.c_long)
    link=ptr(parent+0x1c0)
    target=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_void_p,C.c_int)(ptr(link_table+0x10))(link,doc,0) if link else None
    area['definition']=hex(target or 0)
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-state.json').write_text(json.dumps(result,indent=2))
cu_table=ptr(base+0x5b8ae0)
for area in result['nearbyAreas']:
    if area.get('parentClass')!='TimelineDialog':continue
    root=int(area['address'],16)
    graph=root+0xa88
    graph_cu=ptr(graph+0x10)
    area['graphCu']=hex(graph_cu)
    if graph_cu:
        area['graphSize']=[C.CFUNCTYPE(C.c_int,C.c_void_p)(ptr(cu_table+off))(graph_cu) for off in (0x10,0x18)]
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-state.json').write_text(json.dumps(result,indent=2))
for area in result['nearbyAreas']:
    if area.get('parentClass')!='TimelineDialog':continue
    root=int(area['address'],16)
    area['regions']={}
    for offset in [0x80,0x9e0,0xa88,0x16b0]:
        area['regions'][hex(offset)]={'class':hex(ptr(root+offset)-base),
            'rects':list(struct.unpack('<8i',read(root+offset+0x28,32))), 'layout':list(struct.unpack('<24i',read(root+offset+0x5d0,96)))}
    cu=ptr(root+0x10)
    area['rootSize']=[C.CFUNCTYPE(C.c_int,C.c_void_p)(ptr(cu_table+off))(cu) for off in (0x10,0x18)]
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-state.json').write_text(json.dumps(result,indent=2))
for area in result['nearbyAreas']:
    if not area.get('window'):continue
    root=int(area['address'],16);cu=ptr(root+0x10)
    x=C.c_double();y=C.c_double()
    C.CFUNCTYPE(C.c_bool,C.c_void_p,C.POINTER(C.c_double),C.POINTER(C.c_double))(ptr(cu_table+0x2a0))(cu,C.byref(x),C.byref(y))
    area['globalOrigin']=[x.value,y.value]
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-state.json').write_text(json.dumps(result,indent=2))
for area in result['nearbyAreas']:
    if not area.get('window'):continue
    parent=int(area['parent'],16);cd=ptr(parent+8);area['scrollGroups']={}
    for group in [0x232c,0x232d,0x232e,0x232f]:
        coords=[C.c_int() for _ in range(4)]
        ok=C.CFUNCTYPE(C.c_bool,C.c_void_p,C.c_int,*([C.POINTER(C.c_int)]*4))(ptr(cd_table+0xd8))(cd,group,*[C.byref(c) for c in coords])
        if ok:area['scrollGroups'][hex(group)]=[c.value for c in coords]
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-state.json').write_text(json.dumps(result,indent=2))
