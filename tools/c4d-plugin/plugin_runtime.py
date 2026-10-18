"""SpaceMouse UI: C4D-owned input, live panel routing, and local navigation."""
import ctypes as C
import json
import math
import os
import runpy
import time
from pathlib import Path
import c4d

class Input(C.Structure):
    _fields_=[('ready',C.c_int),('error',C.c_int),('client',C.c_int),('claimed',C.c_int),('reports',C.c_uint64),('axes',C.c_double*6),('lastInput',C.c_double)]
class Context(C.Structure):
    _fields_=[('window',C.c_int64),('active',C.c_int),('buttons',C.c_int),('x',C.c_double),('y',C.c_double),('wx',C.c_double),('wy',C.c_double),('width',C.c_double),('height',C.c_double),('title',C.c_char*512)]

def contains(rect,x,y):
    return rect[0]<=x<rect[0]+rect[2] and rect[1]<=y<rect[1]+rect[3]

def response(value):
    magnitude=min(abs(value)/350.0,1.0)
    # Small noise guard, followed by a linear ramp for responsive starts.
    return 0.0 if magnitude<=.01 else math.copysign((magnitude-.01)/.99,value)

class Navigation:
    def __init__(self,package):
        self.package=Path(package)
        self.state=Path(c4d.storage.GeGetC4DPath(c4d.C4D_PATH_PREFS))/'SpaceMouseUI'
        self.state.mkdir(parents=True,exist_ok=True)
        self.settings_path=self.state/'settings.json'
        self.settings={'enabled':True,'invertHorizontal':False,'invertVertical':True,'zoomEnabled':True,'zoomGain':6.0}
        self.native=C.CDLL(str(self.package/'libSpaceMouseUIInput.dylib'))
        self.native.SMUISizes.argtypes=[];self.native.SMUISizes.restype=C.c_uint64
        if self.native.SMUISizes()!=((C.sizeof(Input)<<32)|C.sizeof(Context)):
            raise RuntimeError('SpaceMouse native/Python input ABI mismatch')
        self.native.SMUIImportSettings.argtypes=[C.c_void_p,C.c_int];self.native.SMUIImportSettings.restype=C.c_int
        if not self.settings_path.exists():
            legacy=C.create_string_buffer(4096)
            if self.native.SMUIImportSettings(legacy,len(legacy)):
                self.settings.update(json.loads(legacy.value))
        try:self.settings.update(json.loads(self.settings_path.read_text()))
        except (OSError,ValueError):pass
        self.preference_model=runpy.run_path(str(self.package/'preferences_model.py'),run_name='spacemouse_ui_preference_model')
        self.settings=self.preference_model['normalise'](self.settings)
        self.save()
        for name,args,result in [('SMUIStart',[],None),('SMUIStop',[],None),('SMUIRead',[C.POINTER(Input)],None),('SMUIClaim',[C.c_int],None),('SMUIContext',[C.POINTER(Context)],None),('SMUICompanionRunning',[],C.c_int),('SMUIScroll',[C.c_int64,*([C.c_double]*4),C.c_int,C.c_int],C.c_int)]:
            function=getattr(self.native,name);function.argtypes=args;function.restype=result
        source=self.package/'runtime'
        self.geometry=runpy.run_path(str(source/'inspect_native_views.py'),run_name='spacemouse_ui_geometry')
        self.timeline=None
        try:
            self.timeline=runpy.run_path(str(source/'timeline_direct.py'),run_name='spacemouse_ui_timeline',init_globals={'SPACEMOUSE_STATE':str(self.state)})
        except Exception as error:print('SpaceMouse UI Timeline unavailable:',error)
        self.last_tick=time.monotonic();self.last_geometry=0;self.last_status=0
        self.viewports=[];self.graphs=[];self.timelines=[];self.target=None
        self.remainders=[0.0,0.0,0.0];self.gestures=[False,False]
        self.status='Starting driver client';self.closed=False
        self.diagnostics=False
        self.native.SMUIStart()
        self.init_hover_gate()
        self.dialog_scroll=runpy.run_path(str(self.package/"file_dialog_scroll.py"))["DialogScroll"](self.package)
        self.ortho_hover=None;self._ortho_failed=False;self._ortho_next=0

    def init_hover_gate(self):
        self.hover_gate=None
        try:
            helper=C.CDLL(str(self.package/'libSpaceMouseUIHover.dylib'))
            helper.SMHoverGateSet.argtypes=[C.c_int,C.c_longlong,*([C.c_double]*4)]
            helper.SMHoverGateSet.restype=None
            for name in ('SMHoverGateStart','SMHoverGateStop'):
                getattr(helper,name).argtypes=[];getattr(helper,name).restype=None
            helper.SMHoverGateStart();self.hover_gate=helper
        except Exception as error:print('SpaceMouse UI: component hover suppression unavailable:',error)

    def update_ortho_hover(self,now):
        if getattr(self,'_ortho_failed',False) or now<getattr(self,'_ortho_next',0):return
        self._ortho_next=now+.1
        try:
            if not getattr(self,'ortho_hover',None):
                if not self.timeline:return
                module=runpy.run_path(str(self.package/'ortho_hover.py'))
                self.ortho_hover=module['Correction'](self.timeline,self.package)
            self.ortho_hover.update(self.settings.get('fixOrthographicHover',True))
        except Exception as error:
            if getattr(self,'ortho_hover',None):self.ortho_hover.helper.SMOrthoEnable(False)
            self._ortho_failed=True
            print('SpaceMouse UI: orthographic hover correction unavailable:',error)

    def update_hover_gate(self,context,input,now):
        helper=getattr(self,'hover_gate',None)
        if helper is None:return
        active=False;window=0;frame=(0.,0.,0.,0.)
        if (self.settings.get('suppressComponentHover',True) and self.settings['enabled']
            and input.ready and context.active and not context.buttons
            and context.title.decode(errors='replace').endswith(' - Main')
            and now-input.lastInput<.1 and max(abs(v) for v in input.axes)>3.5):
            doc=c4d.documents.GetActiveDocument()
            if doc and doc.GetMode() in (c4d.Mpoints,c4d.Medges,c4d.Mpolygons):
                for index in range(doc.GetBaseDrawCount()):
                    f=doc.GetBaseDraw(index).GetFrameScreen()
                    if f and f['cl']<=context.x<f['cr'] and f['ct']<=context.y<f['cb']:
                        active=True;window=context.window
                        frame=(f['cl'],f['ct'],f['cr']-f['cl'],f['cb']-f['ct']);break
        helper.SMHoverGateSet(active,window,*frame)

    def save(self):
        temporary=self.settings_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.settings,indent=2));os.replace(temporary,self.settings_path)

    def refresh_geometry(self):
        frames=[];doc=c4d.documents.GetActiveDocument()
        if doc:
            for index in range(doc.GetBaseDrawCount()):
                f=doc.GetBaseDraw(index).GetFrameScreen()
                if f and f['cr']-f['cl']>10 and f['cb']-f['ct']>10:
                    frames.append((f['cl']-8,f['ct']-30,f['cr']-f['cl']+17,f['cb']-f['ct']+39))
        if not hasattr(self,'_node_geometry'):
            self._node_geometry=runpy.run_path(str(self.package/'runtime/docked_node_geometry.py'),run_name='spacemouse_ui_node_geometry')
        graphs=self._node_geometry['read_node_graphs'](self.geometry,self.timeline,frames)
        timelines=self.timeline['public_regions']() if self.timeline else []
        self.viewports,self.graphs,self.timelines=frames,graphs,timelines
        self.last_geometry=time.monotonic()

    def node_transport(self):
        if not hasattr(self,'_node_transport'):
            try:
                if not self.timeline:raise RuntimeError('C4D build guard unavailable')
                module=runpy.run_path(str(self.package/'node_event_transport.py'))
                self._node_transport=module['Transport'](self.package,self.timeline)
            except Exception as error:
                self._node_transport=None
                print('SpaceMouse UI: precise Node events unavailable:',error)
        return self._node_transport

    def route(self,context):
        x,y=context.x,context.y;window=context.window
        if not context.active or context.buttons or not window:return None
        # Timeline hit regions include both the graph and its nested track list.
        for panel in self.timelines:
            bounds=tuple(panel[k] for k in ('x','y','width','height'))
            if panel['window']==window and contains(bounds,x,y):
                return ('timeline',window,panel['index'],False,bounds)
        title=context.title.decode(errors='replace')
        for graph in self.graphs:
            bounds=tuple(graph[k] for k in ('x','y','width','height'))
            if graph['window']==window and contains(bounds,x,y):
                return ('node',window,0,False,bounds)
        if title in ('Node Editor','Node Editor *'):
            graph=next((p for p in self.graphs if p['window']==window),None)
            if not graph:return None
            bounds=tuple(graph[k] for k in ('x','y','width','height'))
            if contains(bounds,x,y):return ('node',window,0,False,bounds)
            inspector=(context.wx+2,bounds[1],context.width-4,bounds[3])
            if contains(inspector,x,y):return ('scroll',window,0,False,inspector)
            return None
        main=title.endswith(' - Main')
        objects=title=='Objects' or title.startswith('Objects (')
        attributes=title=='Attributes' or title.startswith('Attributes (')
        if main:
            if any(contains(f,x,y) for f in self.viewports):return None
            # Preserve the accepted main-window scrolling envelope.
            bounds=(context.wx+8,context.wy+90,context.width-16,context.height-125)
        elif objects or attributes:
            top=106 if attributes else 55
            bounds=(context.wx+8,context.wy+top,context.width-16,context.height-top-8)
        else:return None
        return ('scroll',window,0,attributes,bounds) if contains(bounds,x,y) else None

    def activate_hovered_viewport(self,context,input,now):
        """Return True while a vendor stop/activation handoff owns input."""
        if (not self.settings['enabled'] or not input.ready or not context.active
            or context.buttons or not context.title.decode(errors='replace').endswith(' - Main')):
            self._viewport_handoff=None;return False
        doc=c4d.documents.GetActiveDocument()
        if not doc:self._viewport_handoff=None;return False
        count=doc.GetBaseDrawCount();hovered=None
        for index in range(count):
            draw=doc.GetBaseDraw(index);frame=draw.GetFrameScreen()
            if frame and frame['cl']<=context.x<frame['cr'] and frame['ct']<=context.y<frame['cb']:
                hovered=index;break
        if hovered is None:self._viewport_handoff=None;return False
        key=(doc,context.window,hovered)
        pending=getattr(self,'_viewport_handoff',None)
        if pending and pending['key']!=key:pending=None;self._viewport_handoff=None
        if pending and 'resume' in pending:
            if now<pending['resume']:return True
            self._viewport_handoff=None;return False
        if doc.GetBaseDraw(hovered)==doc.GetActiveBaseDraw():
            self._viewport_handoff=None;return False
        if not hasattr(self,'_viewport_activation'):
            self._viewport_activation=None
            try:self._viewport_activation=runpy.run_path(str(self.package/'viewport_activation.py'))['bind'](self.timeline)
            except Exception as error:print('SpaceMouse UI hover activation unavailable:',error)
        if not self._viewport_activation:return False
        if not hasattr(self,'_vendor_motion_reset'):
            self._vendor_motion_reset=None
            try:self._vendor_motion_reset=runpy.run_path(str(self.package/'vendor_motion_reset.py'))['bind'](self.timeline)
            except Exception as error:print('SpaceMouse UI: seamless reset unavailable; using neutral guard:',error)
        if pending is None:
            self._viewport_handoff={'key':key,'reports':input.reports,
                'waitNeutral':not self._vendor_motion_reset and now-input.lastInput<=.1 and max(abs(v) for v in input.axes)>3.5}
            return True
        # Wait for a report captured while claimed: the native forwarder sends
        # the vendor a zero-axis report before suppressing further movement.
        moving=now-input.lastInput<=.1 and max(abs(v) for v in input.axes)>3.5
        if not input.claimed or input.reports<=pending['reports']:return True
        if pending.get('waitNeutral'):
            # An existing physical gesture must end before the vendor can
            # establish a new camera frame. Never transfer a held gesture.
            if max(abs(v) for v in input.axes)>3.5:return True
            pending['waitNeutral']=False
            pending['neutralSeen']=True
        if not moving and not pending.get('neutralSeen'):return True
        # The captured stop report and synchronous SDK reset provide the
        # boundary; do not add timer-based settling waits.
        if self._vendor_motion_reset:
            try:self._vendor_motion_reset['reset']()
            except Exception as error:
                print('SpaceMouse UI: reset failed; waiting for neutral:',error)
                self._vendor_motion_reset=None;pending['waitNeutral']=True
                pending.pop('stopped',None);return True
        handle=self.timeline['active_document']()
        self._viewport_activation['set_view'](handle,hovered,count)
        pending['resume']=now
        if getattr(self,'diagnostics',False):(self.state/'viewport-activation.json').write_text(json.dumps({'index':hovered,'time':time.time(),'pointer':[context.x,context.y],'handoff':'navlib-reset-no-wait' if self._vendor_motion_reset else 'neutral-boundary'}))
        return False

    def post(self,dx,dy,phase,zoom):
        if not self.target:return
        kind,window,index,vertical,bounds=self.target
        context=self.context
        if kind=='timeline':
            self.timeline['navigate']({'window':window,'screen':[context.x,context.y],'dx':dx,'dy':dy,'phase':phase,'zoom':zoom})
        else:
            x,y=context.x,context.y
            if kind=='node' and zoom:x,y=bounds[0]+bounds[2]*.5,bounds[1]+bounds[3]*.5
            transport=self.node_transport() if kind=='node' else None
            if transport:transport.post(window,x,y,dx,dy,phase,zoom)
            else:self.native.SMUIScroll(window,x,y,dx,dy,phase,int(zoom))

    def sensitivity_profile(self,context,target):
        if target[0]=='node':return 'node'
        if target[0]!='timeline':return 'lists'
        panel=next((p for p in self.timelines if p['window']==target[1] and p['index']==target[2]),{})
        if context.x<panel.get('plotX',float('-inf')):return 'tracks'
        return 'fcurve' if panel.get('mode')==1 else 'dope'

    def end(self):
        for index,running in enumerate(self.gestures):
            if running:self.post(0,0,4,bool(index))
        self.gestures=[False,False];self.remainders=[0.0,0.0,0.0]

    def emit(self,dx,dy,zoom):
        index=int(zoom);running=self.gestures[index]
        if abs(dx)+abs(dy)<.00001:
            if running:self.post(0,0,4,zoom)
            self.gestures[index]=False
            if zoom:self.remainders[2]=0
            else:self.remainders[:2]=[0.0,0.0]
            return
        kind=self.target[0] if getattr(self,'target',None) else None
        if kind=='timeline' or (kind=='node' and self.node_transport()):
            if not running:self.post(0,0,128,zoom)
            self.post(dx,dy,2 if running else 1,zoom);self.gestures[index]=True
            return
        if zoom:
            self.remainders[2]+=dy;px=0;py=math.trunc(self.remainders[2]);self.remainders[2]-=py
        else:
            self.remainders[0]+=dx;self.remainders[1]+=dy
            px,py=map(math.trunc,self.remainders[:2]);self.remainders[0]-=px;self.remainders[1]-=py
        if px==0 and py==0:return
        if not running:self.post(0,0,128,zoom)
        self.post(px,py,2 if running else 1,zoom);self.gestures[index]=True

    def tick(self):
        if self.closed:return
        now=time.monotonic();dt=min(max(now-self.last_tick,0),.025);self.last_tick=now
        try:
            self.update_ortho_hover(now)
            input=Input();self.native.SMUIRead(C.byref(input))
            context=Context();self.native.SMUIContext(C.byref(context))
            if now-self.last_geometry>=.08:self.refresh_geometry()
            companion=self.native.SMUICompanionRunning()
            self.dialog_scroll.update(input.client,input.ready,self.settings["enabled"] and not companion,now)
            target=self.route(context) if self.settings['enabled'] and input.ready and not companion else None
            if target!=self.target:
                self.end();self.target=target
            self.context=context
            eligible=target is not None
            viewport_gate=False
            if not eligible and not companion:viewport_gate=self.activate_hovered_viewport(context,input,now)
            else:self._viewport_handoff=None
            self.native.SMUIClaim(int(eligible or viewport_gate))
            if companion:self.status='Waiting: quit the separate SpaceMouse C4D Trial app'
            elif not input.ready:self.status='Driver starting' if not input.error else 'Driver error %s'%input.error
            elif not self.settings['enabled']:self.status='Paused — native 3D navigation'
            elif not eligible:self.status='Native 3D navigation / outside supported panel'
            elif not input.claimed:self.status='Activating panel navigation'
            elif now-input.lastInput>.25:self.end();self.status='Ready over %s (%s reports)'%(target[0],input.reports)
            else:
                vertical=target[3];kind=target[0]
                dx=(0 if vertical else response(input.axes[0]))*1000*dt*(-1 if self.settings['invertHorizontal'] else 1)
                dy=-response(input.axes[2])*1000*dt*(-1 if self.settings['invertVertical'] else 1)
                zoom=response(input.axes[1])*350*self.settings['zoomGain']*dt if self.settings['zoomEnabled'] and kind in ('timeline','node') else 0
                profile=self.settings['panels'][self.sensitivity_profile(context,target)]
                dx*=self.settings['panGain']*profile['panX']
                dy*=self.settings['panGain']*profile['panY']
                zoom*=profile['zoom']
                self.emit(dx,dy,False);self.emit(0,zoom,True)
                self.status='Navigating %s (%s reports)'%(kind,input.reports)
            self.update_hover_gate(context,input,now)
            if self.timeline:self.timeline['flush_redraw']()
            if getattr(self,'diagnostics',False) and now-self.last_status>=1:
                self.last_status=now
                (self.state/'status.json').write_text(json.dumps({'pid':os.getpid(),'timestamp':time.time(),'status':self.status,'inputReady':bool(input.ready),'client':input.client,'reports':input.reports,'claimed':bool(input.claimed),'timelineCount':len(self.timelines),'nodeCount':len(self.graphs),'target':self.target}))
        except Exception as error:
            if getattr(self,'hover_gate',None):self.hover_gate.SMHoverGateSet(0,0,0,0,0,0)
            self.native.SMUIClaim(0)
            self.gestures=[False,False];self.target=None
            self.status='Navigation retry: %s'%error
            if str(error)!=getattr(self,'last_error',None):print('SpaceMouse UI:',error);self.last_error=str(error)

    def close(self):
        if self.closed:return
        if getattr(self,"dialog_scroll",None):self.dialog_scroll.close()
        if getattr(self,'hover_gate',None):self.hover_gate.SMHoverGateStop()
        if getattr(self,'ortho_hover',None):
            try:self.ortho_hover.close()
            except Exception as error:
                self.ortho_hover.helper.SMOrthoEnable(False)
                print('SpaceMouse UI: orthographic hover cleanup:',error)
        try:self.end()
        finally:self.native.SMUIClaim(0);self.native.SMUIStop();self.closed=True
