"""Guarded recognition of C4D 2027 Node Editor drawing surfaces in any host."""
import ctypes as C

def is_node_surface(message,api,floating=False):
    """Inspect only the view's own class/owner records, never scan memory."""
    ptr,read=api['ptr'],api['read']
    def identity(obj):
        return read(ptr(ptr(obj)+16),96).split(b'\0',1)[0]
    try:
        if identity(message)!=b'net.maxon.ui.oswindowclass.widgetuserdraw':return False
        # The renderer backlink is transient in XPresso: it can disappear or
        # become unreadable while the dock remains visible. The concrete
        # widgetuserdraw identity is stable; geometry and viewport exclusion
        # below provide the host-level guard. Requiring the renderer here made
        # a valid XPresso canvas vanish from routing altogether.
        return True
    except RuntimeError:return False

def read_node_graphs(native,api,viewports=()):
    result=native['read_node_graphs']()
    if not api:return result  # Version guard unavailable: retain floating path.
    o,call,Rect=native['objc'],native['call'],native['Rect']
    o.class_getInstanceVariable.argtypes=[C.c_void_p,C.c_char_p];o.class_getInstanceVariable.restype=C.c_void_p
    o.ivar_getOffset.argtypes=[C.c_void_p];o.ivar_getOffset.restype=C.c_long
    ivar=o.class_getInstanceVariable(o.objc_getClass(b'MaxonView'),b'_messageView')
    if not ivar:return result
    offset=o.ivar_getOffset(ivar)
    screens=call(o.objc_getClass(b'NSScreen'),'screens')
    primary=call(screens,'objectAtIndex:',args=(0,),types=(C.c_ulong,))
    primary_height=call(primary,'frame',Rect).size.height
    app=call(o.objc_getClass(b'NSApplication'),'sharedApplication');windows=call(app,'windows')
    for index in range(call(windows,'count',C.c_ulong)):
        window=call(windows,'objectAtIndex:',args=(index,),types=(C.c_ulong,))
        if not call(window,'isVisible',C.c_bool) or call(window,'isMiniaturized',C.c_bool):continue
        title=native['text'](call(window,'title'))
        floating=title in ('Node Editor','Node Editor *','XPresso Editor')
        if not floating and not title.endswith(' - Main'):continue
        number=call(window,'windowNumber',C.c_long)
        def walk(view,depth=0):
            if not view or depth>24 or call(view,'isHiddenOrHasHiddenAncestor',C.c_bool):return
            if depth>0 and o.object_getClassName(view)==b'MaxonView':
                bounds=call(view,'bounds',Rect)
                if bounds.size.width>200 and bounds.size.height>100:
                    try:message=api['ptr'](view+offset)
                    except RuntimeError:message=0
                    recognized=bool(message and is_node_surface(message,api,floating=floating))
                    # XPresso can temporarily clear its private _messageView
                    # backlink while its Cocoa drawing view remains alive.
                    # In a named floating editor, or in a main window after
                    # native viewport exclusion, the large visible MaxonView
                    # itself is the stable routing boundary.
                    fallback=not recognized and (floating or title.endswith(' - Main'))
                    if recognized or fallback:
                        local=call(view,'convertRect:toView:',Rect,(bounds,None),(Rect,C.c_void_p))
                        screen=call(window,'convertRectToScreen:',Rect,(local,),(Rect,))
                        region={'window':number,'x':screen.origin.x,'y':primary_height-screen.origin.y-screen.size.height,
                                'width':screen.size.width,'height':screen.size.height}
                        if title=='XPresso Editor' or fallback:region['kind']='xpresso'
                        # The native 3D viewport keeps driver ownership even if
                        # a future layout hosts it in a child drawing surface.
                        def overlaps(frame):
                            x,y,w,h=frame
                            return (region['x']<x+w and x<region['x']+region['width']
                                and region['y']<y+h and y<region['y']+region['height'])
                        if floating or not any(overlaps(frame) for frame in viewports):
                            geometry_keys=('window','x','y','width','height')
                            existing=next((r for r in result if all(r[k]==region[k] for k in geometry_keys)),None)
                            if existing is None:
                                existing=region;result.append(existing)
                            existing['message']=message
                            if title=='XPresso Editor':existing['kind']='xpresso'
            children=call(view,'subviews')
            for child in range(call(children,'count',C.c_ulong)):
                walk(call(children,'objectAtIndex:',args=(child,),types=(C.c_ulong,)),depth+1)
        walk(call(window,'contentView'))
    return result
