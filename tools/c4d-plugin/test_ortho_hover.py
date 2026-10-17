"""Drawing-return semantics and document-lifecycle regression checks."""
import ctypes as C
import runpy
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
sys.modules.setdefault('c4d',types.ModuleType('c4d'))
m=runpy.run_path(str(Path(__file__).with_name('ortho_hover.py')))

class Lifecycle(unittest.TestCase):
 def test_new_closed_documents_disable_and_reenable(self):
  n=m['Correction'].__new__(m['Correction']);n.base=1000;n.functions=[1,2,3]
  original=n.base+0x50530;clone=9000;live={1:original,2:original};events=[]
  class Helper:
   wrapped=0
   def SMOrthoVTable(self):return self.wrapped
   def SMOrthoEnable(self,value):events.append(('enable',value))
   def SMOrthoInstall(self,instance,*args):
    self.wrapped=clone;live[instance]=clone;events.append(('install',instance));return 0
   def SMOrthoRestore(self,instance):live[instance]=original;events.append(('restore',instance));return 0
  n.helper=Helper();n.instances=lambda:iter(list(live.items()))
  m['c4d'].StopAllThreads=lambda:events.append(('stop',))
  n.update(True);self.assertEqual(live,{1:clone,2:clone})
  events.clear();n.update(True);self.assertEqual(events,[('enable',True)])
  # A document closes; a new one opens. Never touch the closed instance.
  del live[1];live[3]=original;events.clear();n.update(True)
  self.assertEqual([e for e in events if e[0]=='install'],[('install',3)])
  n.update(False);self.assertEqual(live,{2:original,3:original})
  n.update(True);n.close();self.assertEqual(live,{2:original,3:original})

class NativeDrawing(unittest.TestCase):
 def test_orthographic_only_and_reversible_multiple_instances(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'adapter.dylib'
   subprocess.run(['clang','-O2','-dynamiclib','-std=c11',str(Path(__file__).with_name('ortho_draw.c')),'-o',str(path)],check=True)
   lib=C.CDLL(str(path));D=C.CFUNCTYPE(C.c_bool,*([C.c_void_p]*6),C.c_int)
   SC=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_void_p);EC=C.CFUNCTYPE(C.c_void_p,C.c_void_p);P=C.CFUNCTYPE(C.c_int,C.c_void_p)
   state={'projection':0,'result':False,'calls':0}
   @D
   def original(*args):state['calls']+=1;return state['result']
   @SC
   def scene(*args):return 123
   @EC
   def editor(*args):return 123
   @P
   def projection(*args):return state['projection']
   storage=(C.c_uint64*34)();vt=C.addressof(storage)+16;storage[29]=C.cast(original,C.c_void_p).value
   first=C.c_uint64(vt);second=C.c_uint64(vt)
   lib.SMOrthoInstall.argtypes=[C.c_void_p,C.c_uint64,C.c_uint64,C.c_void_p,C.c_void_p,C.c_void_p]
   lib.SMOrthoRestore.argtypes=[C.c_void_p];lib.SMOrthoEnable.argtypes=[C.c_bool]
   self.assertEqual(lib.SMOrthoInstall(C.byref(first),vt+8,storage[29],scene,editor,projection),-2)
   for instance in (first,second):self.assertEqual(lib.SMOrthoInstall(C.byref(instance),vt,storage[29],scene,editor,projection),0)
   fn=D(C.c_uint64.from_address(first.value+27*8).value)
   for value,expected in [(0,False),(1,False),(6,True),(3,True),(4,True)]:
    state['projection']=value;self.assertEqual(fn(1,2,3,4,5,6,0),expected)
   self.assertFalse(fn(1,2,3,None,5,6,0))
   lib.SMOrthoEnable(False);self.assertFalse(fn(1,2,3,4,5,6,0))
   lib.SMOrthoEnable(True);state['result']=True;self.assertTrue(fn(1,2,3,4,5,6,0))
   self.assertEqual(state['calls'],8)
   for instance in (first,second):
    self.assertEqual(lib.SMOrthoRestore(C.byref(instance)),0);self.assertEqual(instance.value,vt)

class Setting(unittest.TestCase):
 def test_migrates_enabled_and_preserves_opt_out(self):
  model=runpy.run_path(str(Path(__file__).with_name('preferences_model.py')))
  self.assertTrue(model['normalise']({})['fixOrthographicHover'])
  settings=model['normalise']({'fixOrthographicHover':False})
  self.assertFalse(settings['fixOrthographicHover'])
  model['set_value'](settings,1005,True);self.assertTrue(settings['fixOrthographicHover'])
