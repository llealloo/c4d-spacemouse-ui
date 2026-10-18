"""Settings migration and independent sensitivity regression checks."""
import importlib.util
from pathlib import Path
import unittest,json
spec=importlib.util.spec_from_file_location('preferences_model',Path(__file__).with_name('preferences_model.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Preferences(unittest.TestCase):
 def test_existing_feel_and_directions_are_preserved(self):
  settings=m.normalise({'zoomGain':6.,'invertHorizontal':True,'invertVertical':True})
  self.assertEqual(settings['zoomGain'],6.)
  self.assertEqual(m.get(settings,1011),1.)
  self.assertTrue(settings['invertHorizontal'])
  self.assertEqual(settings['panels']['node'],{'panX':1.85,'panY':1.85,'zoom':.8})
  self.assertEqual(settings['panels']['xpresso'],{'panX':2.405,'panY':2.405,'zoom':.64})
 def test_per_type_and_axis_independence(self):
  settings=m.normalise({'zoomGain':6})
  m.set_value(settings,1100,2.)
  m.set_value(settings,1201,1.5)
  m.set_value(settings,1142,.5)
  self.assertEqual(settings['panels']['node']['panX'],3.7)
  self.assertEqual(settings['panels']['node']['panY'],1.85)
  self.assertEqual(settings['panels']['xpresso']['panX'],2.405)
  self.assertAlmostEqual(settings['panels']['xpresso']['panY'],3.6075)
  self.assertEqual(settings['panels']['fcurve']['zoom'],.5)
  self.assertEqual(settings['panels']['dope']['zoom'],1.)
 def test_master_zoom_round_trip_after_restart(self):
  settings=m.normalise({'zoomGain':6})
  m.set_value(settings,1011,3.)
  restored=m.normalise(json.loads(json.dumps(settings)))
  self.assertEqual(restored['zoomGain'],18.)
  self.assertEqual(m.get(restored,1011),3.)
 def test_invalid_gains_and_separate_instances(self):
  a=m.normalise({'panGain':float('nan'),'panels':{'node':{'panY':float('inf')}}})
  b=m.normalise({});m.set_value(a,1100,2.)
  self.assertEqual(a['panGain'],1.)
  self.assertEqual(a['panels']['node']['panY'],1.85)
  self.assertEqual(b['panels']['node']['panX'],1.85)
 def test_current_tuning_is_unchanged_and_displays_all_100_percent(self):
  current={'zoomGain':6.,'zoomReference':6.,'panGain':1.,'panels':{
   'node':{'panX':1.85,'panY':1.85,'zoom':.8},
   'xpresso':{'panX':2.405,'panY':2.405,'zoom':.64},
   'dope':{'panX':3.,'panY':3.,'zoom':1.},
   'fcurve':{'panX':3.,'panY':3.,'zoom':1.},
   'tracks':{'panX':0.,'panY':3.,'zoom':0.},
   'lists':{'panX':6.,'panY':6.,'zoom':0.}}}
  settings=m.normalise(current)
  for key,value in current.items():self.assertEqual(settings[key],value)
  for identifier,group,path,label,default in m.FIELDS:
   if not isinstance(default,bool):self.assertEqual(m.get(settings,identifier),1.)
  self.assertEqual(m.normalise(settings),settings)
 def test_accepted_xpresso_adjustments_migrate_to_100_percent(self):
  settings=m.normalise({'panels':{'xpresso':{
   'panX':2.4050000000000002,'panY':2.4050000000000002,'zoom':.6400000000000001}}})
  for identifier in (1200,1201,1202):self.assertAlmostEqual(m.get(settings,identifier),1.)
 def test_relative_range_survives_restart_and_reset(self):
  settings=m.normalise({})
  m.set_value(settings,1181,10.)
  self.assertEqual(settings['panels']['lists']['panY'],60.)
  restored=m.normalise(json.loads(json.dumps(settings)))
  self.assertEqual(m.get(restored,1181),10.)
  m.set_value(restored,1181,1.)
  self.assertEqual(restored['panels']['lists']['panY'],6.)
  for identifier,group,path,label,default in m.FIELDS:
   if not isinstance(default,bool):self.assertEqual(m.get(m.normalise({}),identifier),1.)
if __name__=='__main__':unittest.main()
