"""Refresh Preferences' reference gains without changing actual motion settings."""
import builtins,copy,hashlib,json,runpy,time,c4d
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;before=copy.deepcopy(nav.settings);saved=nav.settings_path.read_bytes()
model=runpy.run_path(str(nav.package/'preferences_model.py'))
assert model['normalise'](before)==before,'Actual tuning would change'
values={str(f[0]):model['get'](before,f[0]) for f in model['FIELDS'] if not isinstance(f[4],bool)}
assert all(v==1 for v in values.values()),values
nav.preference_model=model
prefs=builtins._spacemouse_ui_preferences
namespace=prefs['class'].GetDParameter.__globals__
namespace['MODEL']=model;namespace['FIELDS']=model['FIELDS'];namespace['BY_ID']=model['BY_ID']
prefs['model']=model
namespace['mirror']()
container=namespace['container']()
assert all(container.GetFloat(int(identifier))==1 for identifier in values)
dialog=getattr(builtins,'_spacemouse_ui_settings_dialog',None)
if dialog:
 type(dialog).Command.__globals__['MODEL']=model
 dialog.InitValues()
assert nav.settings==before and nav.settings_path.read_bytes()==saved
c4d.EventAdd()
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/calibrated-preferences-check.json').write_text(json.dumps({'time':time.time(),'displayedSensitivities':values,'physicalSettingsUnchanged':True,'settingsFileUnchanged':True,'settingsSHA256':hashlib.sha256(saved).hexdigest(),'settings':before},indent=2))
print('All sensitivity controls now show 100%; actual gains and settings file unchanged')
