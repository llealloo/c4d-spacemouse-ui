"""Runtime-resolved Timeline view navigation. Never writes animation data."""
import ctypes as C,json,struct,math,time
from pathlib import Path
ROOT=Path('/Users/leah/Documents/Projects/SpaceMouse')
DIAGNOSTICS=bool(globals().get('SPACEMOUSE_DIAGNOSTICS',False))
last_log=0
pending_redraw={}
scroll_remainders={}
lib=C.CDLL('/usr/lib/libSystem.B.dylib')
lib.mach_vm_read_overwrite.argtypes=[C.c_uint,C.c_uint64,C.c_uint64,C.c_uint64,C.POINTER(C.c_uint64)]
lib.mach_vm_read_overwrite.restype=C.c_int
TASK=C.c_uint.in_dll(lib,'mach_task_self_').value
def read(address,size=8):
    out=C.create_string_buffer(size);actual=C.c_uint64()
    if lib.mach_vm_read_overwrite(TASK,address,size,C.addressof(out),C.byref(actual)) or actual.value!=size:raise RuntimeError('Timeline target is no longer mapped')
    return out.raw
def ptr(address):return struct.unpack('<Q',read(address))[0]
class TimeValue(C.Structure):
    _fields_=[('numerator',C.c_double),('denominator',C.c_double)]

def sdk_time(seconds):
    # Use BaseTime(numerator, denominator), retaining integral components.
    # Microsecond precision avoids discarding fractional-pixel graph moves.
    # Reduce precision only for extreme ranges to keep the numerator exact.
    seconds=max(-1e15,min(1e15,seconds));denominator=1000000
    while abs(seconds)*denominator>2**50 and denominator>1:denominator//=10
    numerator=math.floor(seconds*denominator+0.5)
    divisor=math.gcd(numerator,denominator)
    return TimeValue(numerator//divisor,denominator//divisor)

bridge_path=globals().get('SPACEMOUSE_BRIDGE')
if not bridge_path:raise RuntimeError('Timeline bridge path was not provided')
bridge=C.CDLL(bridge_path)
bridge.SMTimelineAddress.argtypes=[C.c_int];bridge.SMTimelineAddress.restype=C.c_uint64
bridge.SMTimelineDialogVisible.argtypes=[C.c_uint64];bridge.SMTimelineDialogVisible.restype=C.c_int
bridge.SMTimelineDialogWindow.argtypes=[C.c_uint64];bridge.SMTimelineDialogWindow.restype=C.c_uint64
bridge.SMTimelineDialogRect.argtypes=[C.c_uint64,C.c_int,C.POINTER(C.c_int)];bridge.SMTimelineDialogRect.restype=C.c_int
bridge.SMTimelineDialogSetVisible.argtypes=[C.c_uint64,*([C.c_int]*5)];bridge.SMTimelineDialogSetVisible.restype=C.c_int
bridge.SMTimelineAreaWidth.argtypes=[C.c_uint64];bridge.SMTimelineAreaWidth.restype=C.c_int
bridge.SMTimelineAreaConvert.argtypes=[C.c_uint64,C.POINTER(C.c_double),C.POINTER(C.c_double),C.c_int];bridge.SMTimelineAreaConvert.restype=C.c_int
bridge.SMTimelineAreaRedraw.argtypes=[C.c_uint64];bridge.SMTimelineAreaRedraw.restype=None
CD,CU,LINKS,ATOM,BASELIST=[bridge.SMTimelineAddress(i) for i in range(1,6)]
range_address,vertical_address,redraw_address,REGISTRY=[bridge.SMTimelineAddress(i) for i in range(6,10)]
if not all((CD,CU,LINKS,ATOM,BASELIST,range_address,vertical_address,redraw_address,REGISTRY)):
    raise RuntimeError('Timeline runtime resolver could not identify this C4D implementation')
RANGE=C.CFUNCTYPE(None,C.c_void_p,C.POINTER(TimeValue),C.POINTER(TimeValue),C.c_int)(range_address)
VERTICAL=C.CFUNCTYPE(None,C.c_void_p,C.c_double,C.c_double)(vertical_address)
REDRAW=C.CFUNCTYPE(None,C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_void_p,C.c_int)(redraw_address)

# Resolve C4D's four TimelineDialog instances from the guarded registry found
# by the native bridge. No allocator addresses or window titles are assumed.
_registry=[]
_registry_stamp=0
_native_registry=None
_layout=None

def active_document():
    return bridge.SMTimelineAddress(0)

def timeline_parents():
    return [ptr(REGISTRY+index*8) for index in range(4)]

def resolve_layout():
    global _layout
    if _layout is not None:return _layout
    parents=[parent for parent in timeline_parents() if parent]
    if not parents:raise RuntimeError('Timeline registry is empty')
    parent_vtable=ptr(parents[0])
    if not parent_vtable or any(ptr(parent)!=parent_vtable for parent in parents):
        raise RuntimeError('Timeline registry class validation failed')
    candidates=[]
    for offset in range(0x20,0x800,8):
        try:
            matches=[]
            for parent in parents:
                area=parent+offset;area_vtable=ptr(area)
                if area_vtable and ptr(area+0x18)==parent:matches.append((parent,area_vtable))
            # C4D can retain a registry slot whose dialog is only partly
            # initialized. Require two independent live objects to corroborate
            # one layout, but do not let that incomplete slot veto the others.
            if len(matches)>=2 and all(vtable==matches[0][1] for _,vtable in matches):
                candidates.append((offset,parent_vtable,matches[0][1]))
        except RuntimeError:pass
    if len(candidates)!=1:raise RuntimeError('Timeline user-area layout is ambiguous')
    _layout=candidates[0]
    return _layout

def validate_parent(parent):
    area_offset,parent_vtable,area_vtable=resolve_layout();area=parent+area_offset
    if ptr(parent)!=parent_vtable or ptr(area)!=area_vtable or ptr(area+0x18)!=parent:
        raise RuntimeError('Timeline class validation failed')
    return area

def resolve_definition(parent,doc):
    link=ptr(parent+0x1c0)
    node=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_void_p,C.c_int)(ptr(LINKS+0x10))(link,doc,0) if link and doc else None
    if not node:raise RuntimeError('Timeline has no active document definition')
    function,adjust=struct.unpack('<Qq',read(ATOM+0x20,16));obj=node+(adjust>>1)
    if adjust&1:function=ptr(ptr(obj)+function)
    if C.CFUNCTYPE(C.c_int,C.c_void_p)(function)(obj)!=465001515:
        raise RuntimeError('Unexpected Timeline definition class')
    data=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int)(ptr(BASELIST+0x78))(node,0)
    if not data:raise RuntimeError('Timeline definition is unavailable')
    return node,data

def refresh_registry(force=False):
    global _registry,_registry_stamp,_native_registry
    if not force and time.monotonic()-_registry_stamp<.075:return _registry
    import runpy
    if _native_registry is None:
        _native_registry=runpy.run_path(str(ROOT/'tools/c4d-navigation/inspect_native_views.py'),run_name='timeline_registry_native')
    native=_native_registry
    o,call=native['objc'],native['call']
    app=call(o.objc_getClass(b'NSApplication'),'sharedApplication')
    windows=call(app,'windows');handles={}
    for i in range(call(windows,'count',C.c_ulong)):
        window=call(windows,'objectAtIndex:',args=(i,),types=(C.c_ulong,))
        if not call(window,'isVisible',C.c_bool) or call(window,'isMiniaturized',C.c_bool):continue
        number=call(window,'windowNumber',C.c_long)
        handles[window]=(number,window)
        handles[call(window,'contentView')]=(number,window)
    doc=active_document();entries=[];diagnostics=[]
    for index in range(4):
        parent=ptr(REGISTRY+index*8)
        detail={'index':index,'parent':hex(parent or 0)}
        try:
            if not parent:continue
            area=validate_parent(parent)
            # Match GeDialog.IsVisible(): hidden dock tabs can retain their old
            # geometry, so host-window visibility alone is insufficient.
            if not bridge.SMTimelineDialogVisible(parent):
                detail['reason']='Timeline manager is hidden';continue
            handle=bridge.SMTimelineDialogWindow(parent)
            detail['nativeHandle']=hex(handle or 0)
            if handle not in handles:
                detail['reason']='no visible host window';continue
            window,_=handles[handle]
            node,data=resolve_definition(parent,doc)
            width,plot_width,rect=geometry(parent,area)
            x=C.c_double(rect[0]);y=C.c_double(rect[1])
            ok=bridge.SMTimelineAreaConvert(area,C.byref(x),C.byref(y),1)
            if not ok or rect[2]-rect[0]<50 or rect[3]-rect[1]<40:continue
            mode=struct.unpack('<i',read(data+0x124,4))[0]
            if mode not in (0,1):continue
            entry={'index':index,'parent':parent,'area':area,'window':window,'handle':handle,'doc':doc,'definition':node,
                   'x':x.value,'y':y.value,'width':rect[2]-rect[0],'height':rect[3]-rect[1], 'mode':mode,'state':data}
            entry['plotX']=x.value+width-plot_width-rect[0]
            entries.append(entry);detail.update(entry)
        except RuntimeError as error:detail['reason']=str(error)
        finally:diagnostics.append(detail)
    _registry=entries;_registry_stamp=time.monotonic()
    live={(e['window'],e['area'],e['state']) for e in entries}
    for key in list(scroll_remainders):
        if key[:3] not in live:del scroll_remainders[key]
    if DIAGNOSTICS:(ROOT/'.build/timeline-registry.json').write_text(json.dumps({'pid':__import__('os').getpid(),'timestamp':time.time(),'entries':diagnostics}))
    return entries

def public_regions():
    return [{key:entry[key] for key in ('index','window','x','y','width','height','mode','plotX')} for entry in refresh_registry()]

def target(window,screen=None,area_id=None):
    entries=refresh_registry()
    candidates=[e for e in entries if e['window']==window and (area_id is None or e['area']==area_id)]
    if screen is not None:
        x,y=screen
        candidates=[e for e in candidates if e['x']<=x<e['x']+e['width'] and e['y']<=y<e['y']+e['height']]
    if len(candidates)!=1:raise RuntimeError('No unique visible Timeline panel at pointer')
    entry=candidates[0];parent=entry['parent'];area=validate_parent(parent)
    doc=active_document()
    if doc!=entry['doc']:raise RuntimeError('Timeline document is changing')
    handle=bridge.SMTimelineDialogWindow(parent)
    if handle!=entry['handle']:raise RuntimeError('Timeline host window changed')
    node,data=resolve_definition(parent,doc)
    if node!=entry['definition']:raise RuntimeError('Timeline definition changed')
    return parent,area,data

def values(data):
    a,b,c,d=struct.unpack('<4d',read(data+0x90,32))
    scale,offset=struct.unpack('<2d',read(data+0xe0,16))
    if not b or not d or not all(math.isfinite(v) for v in [a,b,c,d,scale,offset]) or scale<=0:raise RuntimeError('Invalid Timeline view state')
    return a/b,c/d,scale,offset

def geometry(parent,area):
    width=bridge.SMTimelineAreaWidth(area)
    coordinates=(C.c_int*4)();ok=bridge.SMTimelineDialogRect(parent,0x232d,coordinates)
    if not ok:raise RuntimeError('Timeline viewport is unavailable')
    rect=list(coordinates)
    plot_width=struct.unpack('<i',read(area+0x80+0x604,4))[0]
    if not 50<plot_width<=width:raise RuntimeError('Invalid Timeline plot width')
    return width,plot_width,rect

def scroll_pixels(key,delta):
    total=scroll_remainders.get(key,0.0)+delta
    shift=math.trunc(total+math.copysign(1e-9,total))
    rest=total-shift
    scroll_remainders[key]=0.0 if abs(rest)<1e-9 else rest
    return shift

def navigate(data):
    global last_log
    parent,area,state=target(data['window'],data['screen'])
    owner=(data['window'],area,state)
    if data.get('phase',2) in (128,4):
        if not data['zoom']:
            for key in list(scroll_remainders):
                if key[:3]==owner:del scroll_remainders[key]
        return True
    width,plot_width,rect=geometry(parent,area)
    x,y=[C.c_double(v) for v in data['screen']]
    bridge.SMTimelineAreaConvert(area,C.byref(x),C.byref(y),0)
    if not (rect[0]<=x.value<=rect[2] and rect[1]+35<=y.value<=rect[3]):return False
    in_plot=x.value>=width-plot_width
    if not in_plot and data['zoom']:return True
    left,right,scale,offset=values(state)
    mode=struct.unpack('<i',read(state+0x124,4))[0]
    dx,dy=float(data['dx']),float(data['dy'])
    factor=math.exp(max(-.2,min(.2,dy*.002))) if data['zoom'] else 1.0
    span=(right-left)/factor
    center=(left+right)*.5
    if not data['zoom']:center-=dx*(right-left)/plot_width
    if in_plot and (dx or data['zoom']):set_range(parent,center-span*.5,center+span*.5)
    if mode==1 and in_plot:
        # C4D's graph map uses normalized vertical zoom: pixels/unit is
        # scale * (plot height / 300); offset is negative center value.
        if not data['zoom']:offset-=dy/(scale*max(1,rect[3]-rect[1]-35)/300.0)
        VERTICAL(parent,max(1e-7,min(1e7,scale*factor)),offset)
    elif dy and not data['zoom']:
        shift=scroll_pixels((*owner,mode,in_plot),-dy)
        if shift:
            bridge.SMTimelineDialogSetVisible(parent,0x232d,rect[0],rect[1]+shift,rect[2],rect[3]+shift)
        elif not dx:return True
    # Pan and zoom arrive as separate packets. Finish both state updates before
    # repainting, then explicitly invalidate the complete SDK user area.
    pending_redraw[(data['window'],area)]=(parent,area)
    if DIAGNOSTICS and time.monotonic()-last_log>1:
        last_log=time.monotonic()
        (ROOT/'.build/timeline-direct-result.json').write_text(json.dumps({'time':time.time(),'window':data['window'],
            'mode':mode,'pointer':[x.value,y.value],'rect':rect,'plotWidth':plot_width,
            'before':[left,right,scale], 'after':values(state),'zoom':data['zoom']}))
    return True

def flush_redraw():
    targets=list(pending_redraw.items())
    pending_redraw.clear()
    for (window,area_id),(parent,area) in targets:
        if target(window,area_id=area_id)[:2]!=(parent,area):continue
        # Mode 1 takes the unconditional cache-rebuild branch in 0x93bc0
        # (0x94314 -> 0x943ac). Mode 4 permits incremental drawing, whose
        # drag-session cache assumptions do not hold for this direct route.
        REDRAW(parent,0,1,0,1,1,None,0)
        # Queue a complete BFM_DRAW through the documented SDK wrapper rather
        # than relying on scroll-blit damage or a table-slot offset.
        bridge.SMTimelineAreaRedraw(area)

def set_range(parent,left,right):
    if not (math.isfinite(left) and math.isfinite(right) and right>left):raise RuntimeError('Invalid requested view range')
    RANGE(parent,C.byref(sdk_time(left)),C.byref(sdk_time(right)),1)

def probe():
    request=ROOT/'.build/timeline-transform-probe.json'
    if not request.exists():return
    command=json.loads(request.read_text());request.unlink()
    parent,area,data=target(command['window']);before=values(data)
    width,plot_width,original_rect=geometry(parent,area)
    report={'time':time.time(),'before':before}
    try:
        shift=max(-.1,min(.1,float(command.get('shift',.05))))
        set_range(parent,before[0]+shift,before[1]+shift)
        report['after']=values(data)
        VERTICAL(parent,before[2]*1.01,before[3]+.001)
        report['verticalAfter']=values(data)
        if command.get('testNavigation'):
            set_range(parent,before[0],before[1]);VERTICAL(parent,before[2],before[3])
            x=C.c_double(width-plot_width*.5);y=C.c_double((original_rect[1]+35+original_rect[3])*.5)
            bridge.SMTimelineAreaConvert(area,C.byref(x),C.byref(y),1)
            packet={'window':command['window'],'screen':[x.value,y.value],'dx':8,'dy':-8,'zoom':False}
            report['panAccepted']=navigate(packet);report['panResult']=values(data);report['panRect']=geometry(parent,area)[2]
            packet.update(dx=0,dy=5,zoom=True)
            report['zoomAccepted']=navigate(packet);report['zoomResult']=values(data)
            flush_redraw()
    finally:
        set_range(parent,before[0],before[1])
        VERTICAL(parent,before[2],before[3])
        bridge.SMTimelineDialogSetVisible(parent,0x232d,*original_rect)
        REDRAW(parent,0,2,0,1,1,None,0)
        report['restored']=values(data)
        report['graphHeader']=list(struct.unpack('<8q',read(area+0xa88+8,64)))
        (ROOT/'.build/timeline-transform-result.json').write_text(json.dumps(report,indent=2))
