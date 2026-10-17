"""Experimental local Timeline gesture delivery, executed on C4D's main thread."""
import ctypes as C
import builtins
import json
import os
from pathlib import Path
import runpy
import socket
import stat
import time

ROOT=Path('/Users/leah/Documents/Projects/SpaceMouse')
n=runpy.run_path(str(ROOT/'tools/c4d-navigation/inspect_native_views.py'),run_name='timeline_native')
o,call,Point=n['objc'],n['call'],n['Point']
cg=C.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
cf=C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
cg.CGEventCreateScrollWheelEvent.argtypes=[C.c_void_p,C.c_uint,C.c_uint];cg.CGEventCreateScrollWheelEvent.restype=C.c_void_p
cg.CGEventCreateMouseEvent.argtypes=[C.c_void_p,C.c_uint,Point,C.c_uint];cg.CGEventCreateMouseEvent.restype=C.c_void_p
cg.CGEventSetIntegerValueField.argtypes=[C.c_void_p,C.c_uint,C.c_longlong]
cg.CGEventSetDoubleValueField.argtypes=[C.c_void_p,C.c_uint,C.c_double]
cg.CGEventSetFlags.argtypes=[C.c_void_p,C.c_ulonglong]
cg.CGEventSetLocation.argtypes=[C.c_void_p,Point]
cg.CGEventSetTimestamp.argtypes=[C.c_void_p,C.c_ulonglong]
cg.CGEventSetWindowLocation.argtypes=[C.c_void_p,Point]
cf.CFRelease.argtypes=[C.c_void_p]
o.object_getClass.argtypes=[C.c_void_p];o.object_getClass.restype=C.c_void_p
o.objc_allocateClassPair.argtypes=[C.c_void_p,C.c_char_p,C.c_ulong];o.objc_allocateClassPair.restype=C.c_void_p
o.class_addMethod.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p,C.c_char_p];o.class_addMethod.restype=C.c_bool
o.objc_registerClassPair.argtypes=[C.c_void_p]
o.object_setClass.argtypes=[C.c_void_p,C.c_void_p];o.object_setClass.restype=C.c_void_p
o.objc_retain.argtypes=[C.c_void_p];o.objc_retain.restype=C.c_void_p
o.objc_release.argtypes=[C.c_void_p]

def defer_gesture(view,event,zoom):
    state=getattr(builtins,'_spacemouse_deferred_gestures',None)
    if state is None:
        dispatch=C.CDLL('/usr/lib/system/libdispatch.dylib')
        dispatch.dispatch_async_f.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p]
        state={'pending':{},'next':0,'dispatch':dispatch,
               'queue':C.addressof(C.c_char.in_dll(dispatch,'_dispatch_main_q'))}
        def execute(token):
            target,item,is_zoom=state['pending'].pop(token)
            try:
                call(target,'magnifyWithEvent:' if is_zoom else 'scrollWheel:',None,(item,),(C.c_void_p,))
                (ROOT/'.build/timeline-deferred.json').write_text(json.dumps({'time':time.time(),'zoom':is_zoom}))
            except Exception as error:
                print('Deferred Timeline gesture:',error)
            finally:
                o.objc_release(item);o.objc_release(target)
        state['callback']=C.CFUNCTYPE(None,C.c_void_p)(execute)
        builtins._spacemouse_deferred_gestures=state
    state['next']+=1;token=state['next']
    state['pending'][token]=(o.objc_retain(view),o.objc_retain(event),zoom)
    state['dispatch'].dispatch_async_f(state['queue'],token,C.cast(state['callback'],C.c_void_p))


def event_state(obj):
    state=getattr(builtins,'_spacemouse_gesture_event_state_v4',None)
    if state: return state
    values={}
    queries={"device":0,"magnification":0,"type":0}
    def query(name,value):
        queries[name]+=1
        return value
    identity=C.CFUNCTYPE(C.c_long,C.c_void_p,C.c_void_p)(lambda obj,sel:query("device",0x53504d))
    magnify=C.CFUNCTYPE(C.c_double,C.c_void_p,C.c_void_p)(lambda obj,sel:query("magnification",values.get(obj,0.0)))
    kinds={}
    kind=C.CFUNCTYPE(C.c_ulong,C.c_void_p,C.c_void_p)(lambda obj,sel:query("type",kinds.get(obj,22)))
    cls=o.objc_allocateClassPair(o.object_getClass(obj),b'SpaceMouseTrialGestureEventV4',0)
    if not cls: raise RuntimeError('Synthetic event class lacks retained callbacks')
    for name,callback,signature in [(b'deviceID',identity,b'q@:'),(b'magnification',magnify,b'd@:'),(b'type',kind,b'Q@:')]:
        if not o.class_addMethod(cls,o.sel_registerName(name),C.cast(callback,C.c_void_p),signature):
            raise RuntimeError('Cannot add synthetic gesture property')
    o.objc_registerClassPair(cls)
    state={'queries':queries,'class':cls,'values':values,'kinds':kinds,'times':{},'callbacks':(identity,magnify,kind)}
    builtins._spacemouse_gesture_event_state_v4=state
    return state


class TimelineTransport:
    def __init__(self):
        self.direct=runpy.run_path(str(ROOT/'tools/c4d-navigation/timeline_direct.py'),run_name='spacemouse_direct_navigation')
        self.native=C.CDLL(str(ROOT/'.build/libSpaceMouseTimelineV1.dylib'))
        self.native.SMTimelineDispatch.argtypes=[C.c_long,C.c_double,C.c_double,C.c_double,C.c_double,C.c_long,C.c_int]
        self.native.SMTimelineDispatch.restype=None
        self.observer=C.CDLL(str(ROOT/'.build/libSpaceMouseTimelineObserver.dylib'))
        self.observer.SMStartTimelineObserver.argtypes=[]
        self.observer.SMStartTimelineObserver.restype=None
        self.observer.SMStartTimelineObserver()
        self.path=ROOT/'.build/timeline-input.sock'
        if self.path.exists():
            if not stat.S_ISSOCK(self.path.stat().st_mode): raise RuntimeError('Input path is not a socket')
            self.path.unlink()
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
        self.socket.bind(str(self.path));os.chmod(self.path,0o600);self.socket.setblocking(False)
        self.registered=set();self.count=0;self.last_log=0

    def close(self):
        self.socket.close()
        if self.path.exists() and stat.S_ISSOCK(self.path.stat().st_mode): self.path.unlink()

    def pump(self):
        for _ in range(256):
            try: raw=self.socket.recv(4096)
            except BlockingIOError: break
            try:
                data=json.loads(raw)
                if data.get('pid')!=os.getpid() or abs(time.time()-data.get('time',0))>.2: continue
                self.deliver(data)
            except Exception as error:
                if str(error)!=getattr(self,'last_error',None):
                    print('SpaceMouse Timeline input:',error);self.last_error=str(error)
        try:
            self.direct['flush_redraw']()
        except RuntimeError as error:
            if str(error)!=getattr(self,'last_redraw_error',None):
                print('SpaceMouse Timeline redraw:',error);self.last_redraw_error=str(error)

    def deliver(self,data):
        app=call(o.objc_getClass(b'NSApplication'),'sharedApplication')
        workspace=call(o.objc_getClass(b'NSWorkspace'),'sharedWorkspace')
        front=call(workspace,'frontmostApplication')
        if call(front,'processIdentifier',C.c_int)!=os.getpid() and not data.get('diagnostic',False): return
        windows=call(app,'windows');window=None
        for i in range(call(windows,'count',C.c_ulong)):
            w=call(windows,'objectAtIndex:',args=(i,),types=(C.c_ulong,))
            if call(w,'windowNumber',C.c_long)==data['window']:
                window=w;break
        if not window:return
        if data.get('route') not in ('view','deferred','python','native'):
            try:
                if self.direct['navigate'](data):return
                if data['zoom']:return
            except RuntimeError as error:
                if str(error)!=getattr(self,'direct_error',None):
                    print('Timeline direct navigation:',error);self.direct_error=str(error)
                if data['zoom']:return
        if data.get('route') not in ('view','deferred','python'):
            self.native.SMTimelineDispatch(data['window'],*data['screen'],data['dx'],data['dy'],data['phase'],int(data['zoom']))
            return
        view=call(window,'contentView')
        quartz=Point(*data['screen']);local=Point(*data['local'])
        zoom=data['zoom'];amount=max(-.2,min(.2,data['dy']*.002)) if zoom else 0
        raw=cg.CGEventCreateScrollWheelEvent(None,0,2,C.c_int(0 if zoom else round(data['dy'])),C.c_int(0 if zoom else round(data['dx'])))
        # C4D's embedded ctypes runtime loses the variadic wheel arguments on
        # Apple Silicon. Populate the documented fields through fixed signatures.
        for delta,point_field,fixed_field in [(0 if zoom else data['dy'],96,93),(0 if zoom else data['dx'],97,94)]:
            cg.CGEventSetIntegerValueField(raw,point_field,round(delta))
            cg.CGEventSetDoubleValueField(raw,fixed_field,delta/10.0)
        cg.CGEventSetIntegerValueField(raw,88,1);cg.CGEventSetIntegerValueField(raw,99,data['phase'])
        cg.CGEventSetIntegerValueField(raw,51,data['window']);cg.CGEventSetFlags(raw,0)
        cg.CGEventSetLocation(raw,quartz);cg.CGEventSetWindowLocation(raw,local)
        # Direct view delivery bypasses Quartz's usual timestamp assignment.
        # C4D treats timestamp-zero events as stale and reuses cached coordinates.
        cg.CGEventSetTimestamp(raw,time.monotonic_ns())
        event=call(o.objc_getClass(b'NSEvent'),'eventWithCGEvent:',args=(raw,),types=(C.c_void_p,));cf.CFRelease(raw)
        state=event_state(event);o.object_setClass(event,state['class']);state['values'][event]=amount
        state['kinds'][event]=30 if zoom else 22
        try:
            moved=cg.CGEventCreateMouseEvent(None,5,quartz,0)
            cg.CGEventSetTimestamp(moved,time.monotonic_ns())
            cg.CGEventSetIntegerValueField(moved,51,data['window']);cg.CGEventSetFlags(moved,0);cg.CGEventSetWindowLocation(moved,local)
            hover=call(o.objc_getClass(b'NSEvent'),'eventWithCGEvent:',args=(moved,),types=(C.c_void_p,));cf.CFRelease(moved)
            call(view,'mouseMoved:',None,(hover,),(C.c_void_p,))
            if data['window'] not in self.registered:
                call(view,'touchesBeganWithEvent:',None,(event,),(C.c_void_p,));self.registered.add(data['window'])
            if data.get('diagnostic',False) and data.get('route')=='view':
                call(view,'magnifyWithEvent:' if zoom else 'scrollWheel:',None,(event,),(C.c_void_p,))
            elif data.get('diagnostic',False) and data.get('route')=='deferred':
                defer_gesture(view,event,zoom)
            else:
                call(app,'postEvent:atStart:',None,(event,False),(C.c_void_p,C.c_bool))
            self.count+=1
            if time.monotonic()-self.last_log>1:
                self.last_log=time.monotonic()
                location=call(event,'locationInWindow',Point)
                event_window=call(event,'window')
                (ROOT/'.build/timeline-delivery.json').write_text(json.dumps({
                    'time':time.time(),'window':data['window'],'count':self.count,'zoom':zoom,'queries':dict(state['queries']),
                    'packet':data,'viewClass':o.object_getClassName(view).decode(),
                    'eventWindow':call(event_window,'windowNumber',C.c_long) if event_window else None,
                    'location':[location.x,location.y],
                    'timestamp':call(event,'timestamp',C.c_double),
                    'delta':[call(event,'scrollingDeltaX',C.c_double),call(event,'scrollingDeltaY',C.c_double)],
                    'phase':call(event,'phase',C.c_ulong),
                    'device':call(event,'deviceID',C.c_long),
                    'magnification':call(event,'magnification',C.c_double)}))
        finally:
            state['times'][event]=time.monotonic()
            if len(state['times'])>1024:
                for old,stamp in list(state['times'].items()):
                    if time.monotonic()-stamp>3:
                        state['times'].pop(old,None);state['values'].pop(old,None);state['kinds'].pop(old,None)
