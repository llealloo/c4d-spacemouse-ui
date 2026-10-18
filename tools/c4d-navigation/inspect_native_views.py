"""Read native view geometry inside C4D; no mutation or event delivery."""
import ctypes as C
import json
from pathlib import Path

class Point(C.Structure):
    _fields_ = [('x', C.c_double), ('y', C.c_double)]
class Size(C.Structure):
    _fields_ = [('width', C.c_double), ('height', C.c_double)]
class Rect(C.Structure):
    _fields_ = [('origin', Point), ('size', Size)]

objc = C.CDLL('/usr/lib/libobjc.A.dylib')
objc.objc_getClass.argtypes = [C.c_char_p]
objc.objc_getClass.restype = C.c_void_p
objc.sel_registerName.argtypes = [C.c_char_p]
objc.sel_registerName.restype = C.c_void_p
objc.object_getClassName.argtypes = [C.c_void_p]
objc.object_getClassName.restype = C.c_char_p

FLOATING_GRAPH_TITLES = ('Node Editor', 'Node Editor *', 'XPresso Editor')

def call(obj, selector, restype=C.c_void_p, args=(), types=()):
    fn = C.CFUNCTYPE(restype, C.c_void_p, C.c_void_p, *types)(('objc_msgSend', objc))
    return fn(obj, objc.sel_registerName(selector.encode()), *args)

def text(obj):
    return call(obj, 'UTF8String', C.c_char_p).decode() if obj else ''

def inventory():
    app = call(objc.objc_getClass(b'NSApplication'), 'sharedApplication')
    windows = call(app, 'windows')
    output = []
    for i in range(call(windows, 'count', C.c_ulong)):
        window = call(windows, 'objectAtIndex:', args=(i,), types=(C.c_ulong,))
        title = text(call(window, 'title'))
        if title not in FLOATING_GRAPH_TITLES: continue
        result = {'title': title, 'window': call(window, 'windowNumber', C.c_long), 'views': []}
        def walk(view, depth=0):
            if not view or depth>30: return
            bounds = call(view, 'bounds', Rect)
            local = call(view, 'convertRect:toView:', Rect, (bounds, None), (Rect,C.c_void_p))
            screen = call(window, 'convertRectToScreen:', Rect, (local,), (Rect,))
            result['views'].append({'class': objc.object_getClassName(view).decode(), 'depth': depth,
                'hidden': bool(call(view, 'isHidden', C.c_bool)),
                'screen': [screen.origin.x, screen.origin.y, screen.size.width, screen.size.height]})
            children = call(view,'subviews')
            for j in range(call(children,'count',C.c_ulong)):
                walk(call(children,'objectAtIndex:',args=(j,),types=(C.c_ulong,)),depth+1)
        walk(call(window,'contentView'))
        output.append(result)
    return output

def read_node_graphs():
    screens = call(objc.objc_getClass(b'NSScreen'), 'screens')
    primary = call(screens, 'objectAtIndex:', args=(0,), types=(C.c_ulong,))
    primary_height = call(primary, 'frame', Rect).size.height
    result = []
    for window in inventory():
        if window['title'] not in FLOATING_GRAPH_TITLES: continue
        views = window['views']
        if not views: continue
        content = views[0]['screen']
        candidates = [v for v in views if v['depth'] > 0 and not v['hidden']
                      and v['class'] == 'MaxonView' and v['screen'][2] > 200
                      and v['screen'][3] > content[3] * 0.5]
        if not candidates: continue
        graph = max(candidates, key=lambda v: v['screen'][2] * v['screen'][3])['screen']
        x, y, width, height = graph
        result.append({'window': window['window'], 'x': x,
                       'y': primary_height-y-height, 'width': width, 'height': height})
    return result

def main():
    output = inventory()
    Path('/Users/leah/Documents/Projects/SpaceMouse/.build/native-views.json').write_text(json.dumps(output,indent=2))
    print('Native Node Editor view inventory saved.')

if __name__ == '__main__': main()
