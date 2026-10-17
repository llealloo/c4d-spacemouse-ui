"""Version-specific Timeline view navigation. Never writes animation data."""
import ctypes as C,json,struct,math,time
from pathlib import Path
ROOT=Path('/Users/leah/Documents/Projects/SpaceMouse')
DIAGNOSTICS=bool(globals().get('SPACEMOUSE_DIAGNOSTICS',False))
last_log=0
pending_redraw={}
scroll_remainders={}
import hashlib
if hashlib.sha256(Path('/Applications/Maxon Cinema 4D 2027/corelibs/c4d_manager.xlib').read_bytes()).hexdigest()!='a89f07be5d054a0bf1f2764beb383b70d869089fb8a82bda01f4813a6c26fa3b':
    raise RuntimeError('Timeline native navigation requires the inspected C4D build')
lib=C.CDLL('/usr/lib/libSystem.B.dylib')
lib._dyld_image_count.restype=C.c_uint
lib._dyld_get_image_name.argtypes=[C.c_uint];lib._dyld_get_image_name.restype=C.c_char_p
lib._dyld_get_image_header.argtypes=[C.c_uint];lib._dyld_get_image_header.restype=C.c_void_p
BASE=next(lib._dyld_get_image_header(i) for i in range(lib._dyld_image_count()) if (lib._dyld_get_image_name(i) or b'').endswith(b'/c4d_manager.xlib'))
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
RANGE=C.CFUNCTYPE(None,C.c_void_p,C.POINTER(TimeValue),C.POINTER(TimeValue),C.c_int)(BASE+0x670b4)
VERTICAL=C.CFUNCTYPE(None,C.c_void_p,C.c_double,C.c_double)(BASE+0x478a4)
REDRAW=C.CFUNCTYPE(None,C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_void_p,C.c_int)(BASE+0x5c900)

# C4D constructs these four TimelineDialog instances at manager+0x3a0e8
# and stores them in its own registry. Resolve relative to this process's image.
# No allocator addresses, document snapshots, or window titles are used.
_registry=[]
_registry_stamp=0
_native_registry=None

def active_document():
    ge=ptr(BASE+0x5b8a80)
    return C.CFUNCTYPE(C.c_void_p)(ptr(ge+0x128))()

def validate_parent(parent):
    area=parent+0x228
    if ptr(parent)!=BASE+0x553290 or ptr(area)!=BASE+0x553058 or ptr(area+0x18)!=parent or ptr(area+0xa88)!=BASE+0x553848:
        raise RuntimeError('Timeline class validation failed')
    return area

def resolve_definition(parent,doc):
    links=ptr(BASE+0x5b8b70);link=ptr(parent+0x1c0)
    node=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_void_p,C.c_int)(ptr(links+0x10))(link,doc,0) if link and doc else None
    if not node:raise RuntimeError('Timeline has no active document definition')
    atom=ptr(BASE+0x5b8b88)
    function,adjust=struct.unpack('<Qq',read(atom+0x20,16));obj=node+(adjust>>1)
    if adjust&1:function=ptr(ptr(obj)+function)
    if C.CFUNCTYPE(C.c_int,C.c_void_p)(function)(obj)!=465001515:
        raise RuntimeError('Unexpected Timeline definition class')
    bl=ptr(BASE+0x5b8af8)
    data=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int)(ptr(bl+0x78))(node,0)
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
    cd_table=ptr(BASE+0x5b8ad8)
    for index in range(4):
        parent=ptr(BASE+0x5774f0+index*8)
        detail={'index':index,'parent':hex(parent or 0)}
        try:
            if not parent:continue
            area=validate_parent(parent);cd=ptr(parent+8)
            if not cd:continue
            # Match GeDialog.IsVisible(): hidden dock tabs can retain their old
            # geometry, so host-window visibility alone is insufficient.
            visible=C.CFUNCTYPE(C.c_bool,C.c_void_p,C.c_int,C.c_int,C.c_void_p,
                C.c_int,C.c_int,C.c_int,C.c_int,C.c_void_p,C.c_void_p)(ptr(cd_table+0x110))
            if not visible(cd,59,0,None,0,0,0,0,None,None):
                detail['reason']='Timeline manager is hidden';continue
            handle=C.CFUNCTYPE(C.c_void_p,C.c_void_p)(ptr(cd_table+0x188))(cd)
            detail['nativeHandle']=hex(handle or 0)
            if handle not in handles:
                detail['reason']='no visible host window';continue
            window,_=handles[handle]
            node,data=resolve_definition(parent,doc)
            cu_table,cu,width,plot_width,rect=geometry(parent,area)
            x=C.c_double(rect[0]);y=C.c_double(rect[1])
            ok=C.CFUNCTYPE(C.c_bool,C.c_void_p,C.POINTER(C.c_double),C.POINTER(C.c_double))(ptr(cu_table+0x2a0))(cu,C.byref(x),C.byref(y))
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
    cd_table=ptr(BASE+0x5b8ad8)
    handle=C.CFUNCTYPE(C.c_void_p,C.c_void_p)(ptr(cd_table+0x188))(ptr(parent+8))
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
    cu_table=ptr(BASE+0x5b8ae0);cd_table=ptr(BASE+0x5b8ad8)
    cu=ptr(area+0x10);cd=ptr(parent+8)
    width=C.CFUNCTYPE(C.c_int,C.c_void_p)(ptr(cu_table+0x10))(cu)
    coords=[C.c_int() for _ in range(4)]
    ok=C.CFUNCTYPE(C.c_bool,C.c_void_p,C.c_int,*([C.POINTER(C.c_int)]*4))(ptr(cd_table+0xd8))(cd,0x232d,*[C.byref(c) for c in coords])
    if not ok:raise RuntimeError('Timeline viewport is unavailable')
    rect=[c.value for c in coords]
    plot_width=struct.unpack('<i',read(area+0x80+0x604,4))[0]
    if not 50<plot_width<=width:raise RuntimeError('Invalid Timeline plot width')
    return cu_table,cu,width,plot_width,rect

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
    cu_table,cu,width,plot_width,rect=geometry(parent,area)
    x,y=[C.c_double(v) for v in data['screen']]
    C.CFUNCTYPE(C.c_bool,C.c_void_p,C.POINTER(C.c_double),C.POINTER(C.c_double))(ptr(cu_table+0x298))(cu,C.byref(x),C.byref(y))
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
        cd=ptr(parent+8);cd_table=ptr(BASE+0x5b8ad8)
        shift=scroll_pixels((*owner,mode,in_plot),-dy)
        if shift:
            C.CFUNCTYPE(C.c_bool,C.c_void_p,*([C.c_int]*5))(ptr(cd_table+0xc0))(cd,0x232d,rect[0],rect[1]+shift,rect[2],rect[3]+shift)
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
        cu=ptr(area+0x10)
        cu_table=ptr(BASE+0x5b8ae0);cd_table=ptr(BASE+0x5b8ad8)
        gadget=C.CFUNCTYPE(C.c_int,C.c_void_p)(ptr(cu_table+0x20))(cu)
        # Same documented SDK call as GeUserArea.Redraw(threaded=True).
        # Queue a complete BFM_DRAW rather than relying on scroll-blit damage.
        C.CFUNCTYPE(C.c_bool,C.c_void_p,C.c_int)(ptr(cd_table+0xd0))(ptr(parent+8),gadget)

def set_range(parent,left,right):
    if not (math.isfinite(left) and math.isfinite(right) and right>left):raise RuntimeError('Invalid requested view range')
    RANGE(parent,C.byref(sdk_time(left)),C.byref(sdk_time(right)),1)

def probe():
    request=ROOT/'.build/timeline-transform-probe.json'
    if not request.exists():return
    command=json.loads(request.read_text());request.unlink()
    parent,area,data=target(command['window']);before=values(data)
    cu_table,cu,width,plot_width,original_rect=geometry(parent,area)
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
            C.CFUNCTYPE(C.c_bool,C.c_void_p,C.POINTER(C.c_double),C.POINTER(C.c_double))(ptr(cu_table+0x2a0))(cu,C.byref(x),C.byref(y))
            packet={'window':command['window'],'screen':[x.value,y.value],'dx':8,'dy':-8,'zoom':False}
            report['panAccepted']=navigate(packet);report['panResult']=values(data);report['panRect']=geometry(parent,area)[4]
            packet.update(dx=0,dy=5,zoom=True)
            report['zoomAccepted']=navigate(packet);report['zoomResult']=values(data)
            flush_redraw()
    finally:
        set_range(parent,before[0],before[1])
        VERTICAL(parent,before[2],before[3])
        cd=ptr(parent+8);cd_table=ptr(BASE+0x5b8ad8)
        C.CFUNCTYPE(C.c_bool,C.c_void_p,*([C.c_int]*5))(ptr(cd_table+0xc0))(cd,0x232d,*original_rect)
        REDRAW(parent,0,2,0,1,1,None,0)
        report['restored']=values(data)
        report['graphHeader']=list(struct.unpack('<8q',read(area+0xa88+8,64)))
        (ROOT/'.build/timeline-transform-result.json').write_text(json.dumps(report,indent=2))
