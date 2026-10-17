"""Offline checks of the actual pure Timeline conversion/accumulation code."""
import ast
import ctypes as C
import math
from pathlib import Path
import unittest

source=Path(__file__).resolve().parents[1]/'c4d-navigation/timeline_direct.py'
tree=ast.parse(source.read_text())
definitions=ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))
    and n.name in ('TimeValue','sdk_time','scroll_pixels','navigate')],type_ignores=[])

class TimelinePrecision(unittest.TestCase):
    def setUp(self):
        self.api={'C':C,'math':math,'scroll_remainders':{}}
        exec(compile(definitions,str(source),'exec'),self.api)
    def test_submillisecond_ranges_keep_integral_fraction_components(self):
        for seconds in (-12.345678,-.00001,.00001,4.58301,3600.123456):
            value=self.api['sdk_time'](seconds)
            self.assertEqual(value.numerator,math.trunc(value.numerator))
            self.assertEqual(value.denominator,math.trunc(value.denominator))
            self.assertAlmostEqual(value.numerator/value.denominator,seconds,places=6)
    def test_extreme_range_numerator_stays_exact(self):
        for seconds in (1e9,1e12,1e15):
            value=self.api['sdk_time'](seconds)
            self.assertLessEqual(abs(value.numerator),2**50)
            self.assertEqual(value.numerator/value.denominator,seconds)
    def test_small_list_moves_accumulate_without_rounding_bias(self):
        step=self.api['scroll_pixels'];key=(1,2,3,0,False)
        self.assertEqual(sum(step(key,.1) for _ in range(100)),10)
        self.assertEqual(sum(step(key,-.1) for _ in range(100)),-10)
        self.assertEqual(self.api['scroll_remainders'][key],0)
    def test_list_remainders_are_separate_and_direction_reverses(self):
        step=self.api['scroll_pixels'];a=(1,2,3,0,False);b=(1,2,3,0,True)
        self.assertEqual(step(a,.75),0);self.assertEqual(step(b,.75),0)
        self.assertEqual(step(a,-.75),0);self.assertEqual(step(b,.25),1)
    def test_pan_boundary_clears_only_its_area_and_zoom_keeps_pan_remainder(self):
        self.api['target']=lambda window,screen:(10,20,30)
        owner=(1,20,30,0,False);other=(2,20,30,0,False)
        remainders=self.api['scroll_remainders'];remainders.update({owner:.75,other:.25})
        packet={'window':1,'screen':[0,0],'phase':4,'zoom':True}
        self.assertTrue(self.api['navigate'](packet));self.assertEqual(remainders[owner],.75)
        packet['zoom']=False
        self.assertTrue(self.api['navigate'](packet));self.assertNotIn(owner,remainders)
        self.assertEqual(remainders[other],.25)

if __name__=='__main__':unittest.main()
