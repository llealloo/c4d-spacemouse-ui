"""Offline routing and gesture regressions; does not register with the driver."""
import ctypes as C
import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest
sys.modules['c4d']=types.ModuleType('c4d')
spec=importlib.util.spec_from_file_location('plugin_runtime',Path(__file__).with_name('plugin_runtime.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Routing(unittest.TestCase):
    def setUp(self):
        self.nav=m.Navigation.__new__(m.Navigation)
        self.nav.viewports=[(10,100,800,500)]
        self.nav.graphs=[dict(window=2,x=20,y=110,width=700,height=400)]
        self.nav.timelines=[dict(window=1,index=1,x=10,y=650,width=800,height=300),dict(window=1,index=2,x=850,y=650,width=400,height=300)]
    def context(self,x,y,window=1,title=b'Test - Main'):
        c=m.Context();c.active=1;c.window=window;c.x=x;c.y=y;c.title=title;c.width=1300;c.height=1000
        return c
    def test_viewport_handoff(self):
        self.assertIsNone(self.nav.route(self.context(400,300)))
    def test_same_host_multiple_timelines(self):
        self.assertEqual(self.nav.route(self.context(400,700))[:3],('timeline',1,1))
        self.assertEqual(self.nav.route(self.context(900,700))[:3],('timeline',1,2))
    def test_graph_and_track_sensitivity_types(self):
        self.nav.timelines[0].update(mode=1,plotX=200)
        self.nav.timelines[1].update(mode=0,plotX=900)
        self.assertEqual(self.nav.sensitivity_profile(self.context(50,700),('timeline',1,1,False,())), 'tracks')
        self.assertEqual(self.nav.sensitivity_profile(self.context(400,700),('timeline',1,1,False,())), 'fcurve')
        self.assertEqual(self.nav.sensitivity_profile(self.context(1000,700),('timeline',1,2,False,())), 'dope')
    def test_full_node_graph_and_inspector(self):
        self.assertEqual(self.nav.route(self.context(690,300,2,b'Node Editor'))[0],'node')
        self.assertEqual(self.nav.route(self.context(1000,300,2,b'Node Editor'))[0],'scroll')
    def test_docked_node_graph_uses_its_own_bounds(self):
        self.nav.graphs=[dict(window=1,x=20,y=110,width=700,height=400)]
        target=self.nav.route(self.context(690,300))
        self.assertEqual(target[0],'node')
        self.assertEqual(target[4],(20,110,700,400))
    def test_foreground_and_button_guards(self):
        c=self.context(400,700);c.active=0;self.assertIsNone(self.nav.route(c))
        c.active=1;c.buttons=1;self.assertIsNone(self.nav.route(c))
    def test_wrong_host_and_unknown_window(self):
        self.assertIsNone(self.nav.route(self.context(400,700,99,b'Unrelated')))

class Gestures(unittest.TestCase):
    def test_centered_zoom_keeps_physical_context(self):
        n=m.Navigation.__new__(m.Navigation)
        n.target=('node',1,0,False,(20,100,700,400));n._node_transport=None
        n.context=types.SimpleNamespace(x=50,y=150)
        events=[]
        n.native=types.SimpleNamespace(SMUIScroll=lambda *args:events.append(args))
        n.post(0,3,2,True)
        self.assertEqual(events[0][:3],(1,370,300))
        self.assertEqual((n.context.x,n.context.y),(50,150))
    def test_independent_pan_zoom_and_fractional_accumulation(self):
        n=m.Navigation.__new__(m.Navigation);n.gestures=[False,False];n.remainders=[0.,0.,0.]
        events=[];n.post=lambda *args:events.append(args)
        for _ in range(4):n.emit(.25,0,False)
        self.assertEqual(events,[(0,0,128,False),(1,0,1,False)])
        n.emit(0,3,True);n.emit(1,0,False);n.emit(0,0,True)
        self.assertEqual(n.gestures,[True,False]);self.assertEqual(events[-1],(0,0,4,True))
        n.end();self.assertEqual(n.gestures,[False,False]);self.assertEqual(events[-1],(0,0,4,False))
    def test_response_matches_baseline(self):
        self.assertEqual(m.response(3.5),0)
        self.assertGreater(m.response(10),0)
        self.assertAlmostEqual(m.response(175),(.5-.01)/.99)
        self.assertEqual(m.response(350),1)
        self.assertAlmostEqual(m.response(175),-m.response(-175))

if __name__=='__main__':unittest.main()

class NodeIdentity(unittest.TestCase):
    def test_renderer_name_is_not_required(self):
        import runpy
        identify=runpy.run_path(str(Path(__file__).with_name('docked_node_geometry.py')))['is_node_surface']
        memory={1000:3000,3016:5000,2000:4000,4016:6000,1000+0x78:2000}
        names={5000:b'net.maxon.ui.oswindowclass.widgetuserdraw\0',6000:b'net.maxon.drawport.oswindowclass.metal\0'}
        api={'ptr':lambda address:memory[address],'read':lambda address,size:names[address]}
        self.assertTrue(identify(1000,api))
        names[5000]=b'net.maxon.ui.oswindowclass.window\0'
        self.assertFalse(identify(1000,api))

class HoverActivation(unittest.TestCase):
    def test_motion_activates_hovered_view_without_claiming_input(self):
        import tempfile
        n=m.Navigation.__new__(m.Navigation);n.settings={'enabled':True}
        draws=[types.SimpleNamespace(GetFrameScreen=lambda:dict(cl=0,ct=0,cr=100,cb=100)),
               types.SimpleNamespace(GetFrameScreen=lambda:dict(cl=100,ct=0,cr=200,cb=100))]
        doc=types.SimpleNamespace(GetBaseDrawCount=lambda:2,GetBaseDraw=lambda i:draws[i],GetActiveBaseDraw=lambda:draws[0])
        m.c4d.documents=types.SimpleNamespace(GetActiveDocument=lambda:doc)
        calls=[]
        n._viewport_activation={'set_view':lambda *args:calls.append(args) or True}
        n.timeline={'active_document':lambda:123};n._vendor_motion_reset=None
        context=m.Context();context.active=1;context.title=b'Test - Main';context.x=150;context.y=50
        input=m.Input();input.ready=1;input.lastInput=10
        with tempfile.TemporaryDirectory() as directory:
            n.state=Path(directory)
            n.activate_hovered_viewport(context,input,10)
            self.assertEqual(calls,[])
            input.axes[4]=10
            input.claimed=1;input.reports=1
            self.assertFalse(n.activate_hovered_viewport(context,input,10))
            self.assertEqual(calls,[(123,1,2)])
            self.assertFalse(n.activate_hovered_viewport(context,input,10.04))
            calls.clear();context.buttons=1
            n.activate_hovered_viewport(context,input,10);self.assertEqual(calls,[])
            context.buttons=0;context.active=0
            n.activate_hovered_viewport(context,input,10);self.assertEqual(calls,[])
            context.active=1
            self.assertTrue(n.activate_hovered_viewport(context,input,11));self.assertEqual(calls,[])

    def test_held_gesture_waits_for_physical_neutral(self):
        import tempfile
        n=m.Navigation.__new__(m.Navigation);n.settings={'enabled':True}
        first=object();second=types.SimpleNamespace(GetFrameScreen=lambda:dict(cl=100,ct=0,cr=200,cb=100))
        doc=types.SimpleNamespace(GetBaseDrawCount=lambda:1,GetBaseDraw=lambda i:second,GetActiveBaseDraw=lambda:first)
        m.c4d.documents=types.SimpleNamespace(GetActiveDocument=lambda:doc)
        calls=[];n._viewport_activation={'set_view':lambda *args:calls.append(args) or True}
        n.timeline={'active_document':lambda:123};n._vendor_motion_reset=None
        context=m.Context();context.active=1;context.title=b'Test - Main';context.x=150;context.y=50
        input=m.Input();input.ready=1;input.lastInput=10;input.axes[0]=100
        with tempfile.TemporaryDirectory() as directory:
            n.state=Path(directory)
            self.assertTrue(n.activate_hovered_viewport(context,input,10))
            input.claimed=1;input.reports=1
            self.assertTrue(n.activate_hovered_viewport(context,input,10.01))
            self.assertTrue(n.activate_hovered_viewport(context,input,10.08))
            self.assertEqual(calls,[])
            input.axes[0]=0;input.reports=2
            self.assertFalse(n.activate_hovered_viewport(context,input,10.09))
            self.assertEqual(calls,[(123,0,1)])

    def test_continuous_motion_uses_sdk_reset_before_activation(self):
        import tempfile
        n=m.Navigation.__new__(m.Navigation);n.settings={'enabled':True}
        old=object();draw=types.SimpleNamespace(GetFrameScreen=lambda:dict(cl=0,ct=0,cr=100,cb=100))
        doc=types.SimpleNamespace(GetBaseDrawCount=lambda:1,GetBaseDraw=lambda i:draw,GetActiveBaseDraw=lambda:old)
        m.c4d.documents=types.SimpleNamespace(GetActiveDocument=lambda:doc)
        calls=[];n._vendor_motion_reset={'reset':lambda:calls.append('reset')}
        n._viewport_activation={'set_view':lambda *args:calls.append('activate') or True}
        n.timeline={'active_document':lambda:123}
        context=m.Context();context.active=1;context.title=b'Test - Main';context.x=50;context.y=50
        input=m.Input();input.ready=1;input.lastInput=10;input.axes[0]=100
        with tempfile.TemporaryDirectory() as directory:
            n.state=Path(directory)
            self.assertTrue(n.activate_hovered_viewport(context,input,10))
            input.claimed=1;input.reports=1
            self.assertFalse(n.activate_hovered_viewport(context,input,10.01))
            self.assertEqual(calls,['reset','activate'])
            self.assertFalse(n.activate_hovered_viewport(context,input,10.09))

class ComponentHover(unittest.TestCase):
    def test_only_component_navigation_inside_view_is_gated(self):
        n=m.Navigation.__new__(m.Navigation)
        n.settings={'enabled':True,'suppressComponentHover':True}
        events=[];n.hover_gate=types.SimpleNamespace(SMHoverGateSet=lambda *args:events.append(args))
        m.c4d.Mpoints=3;m.c4d.Medges=4;m.c4d.Mpolygons=5
        mode=[3]
        view=types.SimpleNamespace(GetFrameScreen=lambda:dict(cl=10,ct=20,cr=110,cb=120))
        doc=types.SimpleNamespace(GetMode=lambda:mode[0],GetBaseDrawCount=lambda:1,GetBaseDraw=lambda i:view)
        m.c4d.documents=types.SimpleNamespace(GetActiveDocument=lambda:doc)
        context=m.Context();context.active=1;context.window=2;context.title=b'Test - Main';context.x=50;context.y=50
        input=m.Input();input.ready=1;input.lastInput=10;input.axes[0]=100
        n.update_hover_gate(context,input,10)
        self.assertEqual(events[-1],(True,2,10,20,100,100))
        for component_mode in (3,4,5):
            mode[0]=component_mode;n.update_hover_gate(context,input,10);self.assertTrue(events[-1][0])
        mode[0]=1;n.update_hover_gate(context,input,10);self.assertFalse(events[-1][0])
        mode[0]=3;context.buttons=1;n.update_hover_gate(context,input,10);self.assertFalse(events[-1][0])
        context.buttons=0;context.x=150;n.update_hover_gate(context,input,10);self.assertFalse(events[-1][0])
        context.x=50;input.axes[0]=0;n.update_hover_gate(context,input,10);self.assertFalse(events[-1][0])
        input.axes[0]=100;n.update_hover_gate(context,input,11);self.assertFalse(events[-1][0])
        n.settings['suppressComponentHover']=False;n.update_hover_gate(context,input,10);self.assertFalse(events[-1][0])
