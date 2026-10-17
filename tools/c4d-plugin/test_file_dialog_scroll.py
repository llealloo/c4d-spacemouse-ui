import unittest,runpy
from pathlib import Path
DialogScroll=runpy.run_path(str(Path(__file__).with_name('file_dialog_scroll.py')))['DialogScroll']
class Function:
 def __init__(self,call):self.call=call
 def __call__(self,*args):return self.call(*args)
class Helper:
 def __init__(self,errors=()):
  self.calls=[];self.errors=list(errors)
  self.SMFileDialogStart=Function(self.start)
  self.SMFileDialogStop=Function(lambda:self.calls.append(('stop',)))
  self.SMDialogPostAccess=Function(lambda:1)
  self.SMDialogConfigureAxes=Function(lambda x,y:self.calls.append(('gains',x,y)) or 1)
 def start(self,client):
  self.calls.append(('start',client));return self.errors.pop(0) if self.errors else 0
class Lifecycle(unittest.TestCase):
 def make(self,errors=()):
  h=Helper(errors);return DialogScroll('/unused',lambda path:h),h
 def test_waits_for_vendor_and_does_not_reattach_each_tick(self):
  d,h=self.make();d.update(0,False,True,0);self.assertEqual(h.calls,[])
  d.update(7,True,True,.1);d.update(7,True,True,1)
  self.assertEqual(h.calls,[('start',7),('gains',2400,3600)])
 def test_retry_then_reconnect_restores_old_callback_first(self):
  d,h=self.make([-4]);d.update(7,True,True,0);d.update(7,True,True,.1)
  self.assertEqual(len(h.calls),1)
  d.update(7,True,True,.6);d.update(8,True,True,2)
  self.assertEqual(h.calls[-3:],[('stop',),('start',8),('gains',2400,3600)])
 def test_disable_and_shutdown_restore_only_once(self):
  d,h=self.make();d.update(7,True,True,0);d.update(7,True,False,1);d.close()
  self.assertEqual(h.calls.count(('stop',)),1);self.assertEqual(d.client,0)
 def test_disconnect_releases_wrapper(self):
  d,h=self.make();d.update(7,True,True,0);d.update(0,False,True,1)
  self.assertEqual(h.calls[-1],('stop',));self.assertEqual(d.client,0)
