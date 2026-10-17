"""Activate experimental transport on our existing Python message plugin."""
import builtins
import runpy
import time
import json
import os
import c4d
from pathlib import Path

path='/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-navigation/timeline_transport.py'
module=runpy.run_path(path,run_name='spacemouse_timeline_transport')
previous=getattr(builtins,'_spacemouse_timeline_transport',None)
if previous: previous.close()
transport=module['TimelineTransport']()
builtins._spacemouse_timeline_transport=transport
reload_path=Path('/Users/leah/Documents/Projects/SpaceMouse/.build/timeline-reload.request')
reload_stamp=reload_path.stat().st_mtime_ns if reload_path.exists() else 0
try:
    transport.direct['refresh_registry'](True)
    transport.direct['probe']()
except Exception as error:
    print('Timeline input diagnostic:',error)
service=builtins._spacemouse_layout_service
cls=type(service)
if not hasattr(cls,'_layout_core_message'):
    cls._layout_core_message=cls.CoreMessage

def timer(self):
    return 8 if self.enabled else 0

def core(self,message,data):
    if message!=c4d.MSG_TIMER or not self.enabled: return True
    if reload_path.exists() and reload_path.stat().st_mtime_ns>reload_stamp:
        runpy.run_path('/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-navigation/activate_timeline_transport.py',run_name='spacemouse_timeline_activation')
        return True
    transport.pump()
    now=time.monotonic()
    if now-getattr(self,'_last_layout',0)>=.08:
        self._last_layout=now
        result=self._layout_core_message(message,data)
        try:
            output=reload_path.parent/'live-layout.json'
            payload=json.loads(output.read_text())
            payload['timelines']=transport.direct['public_regions']()
            temporary=output.with_suffix('.timeline.tmp')
            temporary.write_text(json.dumps(payload))
            os.replace(str(temporary),str(output))
        except Exception as error:
            if str(error)!=getattr(self,'_timeline_layout_error',None):
                print('Timeline live layout:',error);self._timeline_layout_error=str(error)
        return result
    return True

cls.GetTimer=timer
cls.CoreMessage=core
print('Experimental Timeline native-gesture transport ready; layout bridge retained.')
