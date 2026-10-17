"""Fractional Node Editor events and Blender-style reciprocal zoom steps."""
import builtins
import ctypes as C
import hashlib
import math
import runpy

def zoom_event_delta(delta):
    """Invert C4D's measured (1+d/1000)^2 response for a View2D zoom step.

    Blender shrinks visible span by (1-a), or expands it by its reciprocal.
    Preserve the existing infinitesimal gain, a=abs(input)*.002. Bound only
    oversized steps which would otherwise cross a zero-sized visible span.
    """
    if not math.isfinite(delta) or delta==0:return 0.0
    amount=min(abs(delta)*.002,.95)
    exponent=(-.5 if delta>0 else .5)*math.log1p(-amount)
    return 1000.0*math.expm1(exponent)

class Transport:
    def __init__(self,package,api):
        # The response inversion is specific to the inspected C4D modules.
        runpy.run_path(str(package/'node_pan_scale.py'))['ScaleReader'](api)
        path=package/'libSpaceMouseUIScroll.dylib'
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        cache=getattr(builtins,'_spacemouse_ui_scroll_library',None)
        if cache and cache['digest']==digest:self.helper=cache['helper']
        else:
            self.helper=C.CDLL(str(path))
            # ObjC event subclasses retain IMPs into this library. Keep it
            # alive through runtime reloads for the entire process lifetime.
            builtins._spacemouse_ui_scroll_library={'digest':digest,'helper':self.helper}
        self.helper.SMPreciseScroll.argtypes=[C.c_int64,*([C.c_double]*4),C.c_int,C.c_int]
        self.helper.SMPreciseScroll.restype=C.c_int

    def post(self,window,x,y,dx,dy,phase,zoom):
        if zoom:dy=zoom_event_delta(dy)
        return self.helper.SMPreciseScroll(window,x,y,dx,dy,phase,int(zoom))
