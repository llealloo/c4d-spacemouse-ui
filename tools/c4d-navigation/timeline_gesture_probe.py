"""Isolated, view-only Timeline touch-pan experiment. No global input posting.
Run from C4D's Python console. Owns only synthetic NSEvent instances.
"""
import ctypes as C
import runpy
import builtins
n = runpy.run_path('/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-navigation/inspect_native_views.py',run_name='gesture_geometry')
o, call, Point, Rect = n['objc'], n['call'], n['Point'], n['Rect']
cg = C.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
cf = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
cg.CGEventCreateScrollWheelEvent.argtypes=[C.c_void_p,C.c_uint,C.c_uint];cg.CGEventCreateScrollWheelEvent.restype=C.c_void_p
cg.CGEventCreateMouseEvent.argtypes=[C.c_void_p,C.c_uint,Point,C.c_uint];cg.CGEventCreateMouseEvent.restype=C.c_void_p
cg.CGEventSetIntegerValueField.argtypes=[C.c_void_p,C.c_uint,C.c_longlong]
cg.CGEventSetLocation.argtypes=[C.c_void_p,Point]
cg.CGEventSetWindowLocation.argtypes=[C.c_void_p,Point]
cf.CFRelease.argtypes=[C.c_void_p]
o.object_getClass.argtypes=[C.c_void_p];o.object_getClass.restype=C.c_void_p
o.objc_allocateClassPair.argtypes=[C.c_void_p,C.c_char_p,C.c_ulong];o.objc_allocateClassPair.restype=C.c_void_p
o.class_addMethod.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p,C.c_char_p];o.class_addMethod.restype=C.c_bool
o.objc_registerClassPair.argtypes=[C.c_void_p]
o.object_setClass.argtypes=[C.c_void_p,C.c_void_p];o.object_setClass.restype=C.c_void_p


def main():
    app=call(o.objc_getClass(b'NSApplication'),'sharedApplication')
    windows=call(app,'orderedWindows')
    window=None
    for i in range(call(windows,'count',C.c_ulong)):
        w=call(windows,'objectAtIndex:',args=(i,),types=(C.c_ulong,))
        if n['text'](call(w,'title')).startswith('Timeline'):
            window=w;break
    if not window: raise RuntimeError('Open a floating Timeline first')
    view=call(window,'contentView');bounds=call(view,'bounds',Rect)
    point=Point(bounds.origin.x+bounds.size.width*.65,bounds.origin.y+bounds.size.height*.5)
    local=call(view,'convertPoint:toView:',Point,(point,None),(Point,C.c_void_p))
    native=call(window,'convertPointToScreen:',Point,(local,),(Point,))
    screens=call(o.objc_getClass(b'NSScreen'),'screens')
    screen=call(screens,'objectAtIndex:',args=(0,),types=(C.c_ulong,))
    primary_height=call(screen,'frame',Rect).size.height
    quartz=Point(native.x,primary_height-native.y)
    wid=call(window,'windowNumber',C.c_long)
    print('Target Timeline window:',wid)
    event_class=o.objc_getClass(b'NSEvent')
    def event(dx,dy,phase):
        raw=cg.CGEventCreateScrollWheelEvent(None,0,2,C.c_int(dy),C.c_int(dx))
        cg.CGEventSetIntegerValueField(raw,88,1)
        cg.CGEventSetIntegerValueField(raw,99,phase)
        cg.CGEventSetIntegerValueField(raw,51,wid)
        cg.CGEventSetLocation(raw,quartz);cg.CGEventSetWindowLocation(raw,local)
        obj=call(event_class,'eventWithCGEvent:',args=(raw,),types=(C.c_void_p,))
        cf.CFRelease(raw)
        subclass=getattr(builtins,'_spacemouse_touch_event_class',None)
        if not subclass:
            callback=C.CFUNCTYPE(C.c_long,C.c_void_p,C.c_void_p)(lambda obj,sel:0x53504d)
            subclass=o.objc_allocateClassPair(o.object_getClass(obj),b'SpaceMouseTrialTouchScrollEvent',0)
            if not subclass: raise RuntimeError('Synthetic event class already exists without retained callback')
            if not o.class_addMethod(subclass,o.sel_registerName(b'deviceID'),C.cast(callback,C.c_void_p),b'q@:'):
                raise RuntimeError('Cannot install synthetic device identity')
            o.objc_registerClassPair(subclass)
            builtins._spacemouse_touch_event_callback=callback
            builtins._spacemouse_touch_event_class=subclass
        o.object_setClass(obj,subclass)
        return obj
    initial=event(0,0,1)
    # Prime this manager's hover state, without relocating the system pointer.
    moved=cg.CGEventCreateMouseEvent(None,5,quartz,0)
    cg.CGEventSetIntegerValueField(moved,51,wid);cg.CGEventSetWindowLocation(moved,local)
    hover=call(event_class,'eventWithCGEvent:',args=(moved,),types=(C.c_void_p,));cf.CFRelease(moved)
    call(view,'mouseMoved:',None,(hover,),(C.c_void_p,))
    call(view,'touchesBeganWithEvent:',None,(initial,),(C.c_void_p,))
    print('Synthetic touch identity:',call(initial,'deviceID',C.c_long), 'window:',call(initial,'windowNumber',C.c_long), 'expected:',wid, 'local:',call(initial,'locationInWindow',Point).x,call(initial,'locationInWindow',Point).y)
    for dx,dy,phase in [(0,0,1),(-120,0,2),(0,0,4)]:
        scroll=event(dx,dy,phase)
        call(view,'scrollWheel:',None,(scroll,),(C.c_void_p,))
    print('Timeline touch-pan test sent directly; physical pointer unchanged.')

if __name__=='__main__': main()
