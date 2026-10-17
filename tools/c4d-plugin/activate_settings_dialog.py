import builtins,gc,runpy
from pathlib import Path
PACKAGE=Path('/Users/leah/Library/Preferences/Maxon/Maxon Cinema 4D 2027_40C4A9CA/plugins/SpaceMouseUI')
old=getattr(builtins,'_spacemouse_ui_settings_dialog',None)
if old:old.Close()
builtins._spacemouse_ui_settings_dialog=None
module=runpy.run_path(str(PACKAGE/'settings_dialog.py'))
def execute(self,doc):return module['open_settings']()
for obj in gc.get_objects():
    if isinstance(obj,type) and obj.__name__=='Command' and 'SpaceMouseUI.pyp' in getattr(getattr(obj,'Execute',None),'__code__',type('X',(),{'co_filename':''})).co_filename:
        obj.Execute=execute
module['open_settings']()
