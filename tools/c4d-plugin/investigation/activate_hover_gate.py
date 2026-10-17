"""Session-only A/B hover-event test. No installed plugin changes."""
import builtins,ctypes as C,c4d,time
nav=builtins._spacemouse_ui_navigation
previous=getattr(builtins,'_spacemouse_hover_gate',None)
if previous:previous.SMHoverGateStop()
helper=C.CDLL('/Users/leah/Documents/Projects/SpaceMouse/.build/libSpaceMouseHoverGateTrial2.dylib')
helper.SMHoverGateSet.argtypes=[C.c_int,C.c_longlong,*([C.c_double]*4)]
helper.SMHoverGateStart.argtypes=[];helper.SMHoverGateStop.argtypes=[]
helper.SMHoverGateCount.restype=C.c_uint64
helper.SMHoverGateResumeCount.restype=C.c_uint64
helper.SMHoverGateEnabled.restype=C.c_int
helper.SMHoverGateStart()
cls=nav.__class__
original=getattr(builtins,'_spacemouse_hover_original_tick',cls.tick)
builtins._spacemouse_hover_original_tick=original
builtins._spacemouse_hover_gate=helper

def tick(self):
    original(self)
    active=False;window=0;frame=(0.,0.,0.,0.)
    try:
        doc=c4d.documents.GetActiveDocument()
        if doc and doc.GetMode() in (c4d.Mpoints,c4d.Medges,c4d.Mpolygons) and self.settings['enabled']:
            Input=self.__class__.__init__.__globals__['Input'];Context=self.__class__.__init__.__globals__['Context']
            input=Input();context=Context()
            self.native.SMUIRead(C.byref(input));self.native.SMUIContext(C.byref(context))
            if (input.ready and context.active and not context.buttons and context.title.decode(errors='replace').endswith(' - Main')
                and time.monotonic()-input.lastInput<.1 and max(abs(v) for v in input.axes)>3.5):
                for i in range(doc.GetBaseDrawCount()):
                    f=doc.GetBaseDraw(i).GetFrameScreen()
                    if f and f['cl']<=context.x<f['cr'] and f['ct']<=context.y<f['cb']:
                        active=True;window=context.window
                        frame=(f['cl'],f['ct'],f['cr']-f['cl'],f['cb']-f['ct']);break
    finally:
        state=(active,window,frame)
        previous=getattr(self,'_hover_gate_debug',None)
        if previous is None or previous['state']!=state:
            history=getattr(self,'_hover_gate_history',[])
            history.append({'state':state,'time':time.monotonic(),'axes':list(input.axes) if 'input' in locals() else None})
            self._hover_gate_history=history[-24:]
        self._hover_gate_debug={'state':state,'time':time.monotonic(),'axes':list(input.axes) if 'input' in locals() else None}
        helper.SMHoverGateSet(active,window,*frame)
cls.tick=tick
print('Session-only component hover gate running; clicks/drags pass through')
