import importlib.util
import math
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('node_event_transport',Path(__file__).with_name('node_event_transport.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ZoomResponse(unittest.TestCase):
    def test_matches_view2d_span_change_and_reverses(self):
        for delta in (.001,.05,.5,1,10,100):
            positive=(1+m.zoom_event_delta(delta)/1000)**2
            negative=(1+m.zoom_event_delta(-delta)/1000)**2
            self.assertAlmostEqual(positive,1/(1-.002*delta),places=12)
            self.assertAlmostEqual(negative,1-.002*delta,places=12)
            self.assertAlmostEqual(positive*negative,1,places=12)
    def test_small_motion_gain_and_invalid_input(self):
        self.assertAlmostEqual(m.zoom_event_delta(.00001)/.00001,1,places=6)
        for value in (0,float('nan'),float('inf')):self.assertEqual(m.zoom_event_delta(value),0)
        self.assertTrue(math.isfinite(m.zoom_event_delta(100000)))

class FractionalEmission(unittest.TestCase):
    def test_timeline_emits_fractions_without_loading_node_transport(self):
        import runpy,sys,types
        sys.modules.setdefault('c4d',types.ModuleType('c4d'))
        runtime=runpy.run_path(str(Path(__file__).with_name('plugin_runtime.py')))
        n=runtime['Navigation'].__new__(runtime['Navigation'])
        n.target=('timeline',1,0,False,(0,0,100,100))
        n.gestures=[False,False];n.remainders=[0.,0.,0.];events=[]
        n.post=lambda *args:events.append(args)
        n.emit(.05,.1,False);n.emit(0,.025,True)
        self.assertEqual(events,[(0,0,128,False),(.05,.1,1,False),
            (0,0,128,True),(0,.025,1,True)])
    def test_node_emits_each_fraction_without_waiting_for_a_tick(self):
        import runpy,sys,types
        sys.modules.setdefault('c4d',types.ModuleType('c4d'))
        runtime=runpy.run_path(str(Path(__file__).with_name('plugin_runtime.py')))
        n=runtime['Navigation'].__new__(runtime['Navigation'])
        n.target=('node',1,0,False,(0,0,100,100));n._node_transport=object()
        n.gestures=[False,False];n.remainders=[0.,0.,0.];events=[]
        n.post=lambda *args:events.append(args)
        n.emit(.05,.1,False);n.emit(0,.025,True);n.emit(.05,.1,False)
        self.assertEqual(events,[(0,0,128,False),(.05,.1,1,False),
            (0,0,128,True),(0,.025,1,True),(.05,.1,2,False)])
        n.end();self.assertEqual(n.gestures,[False,False])

if __name__=='__main__':unittest.main()
