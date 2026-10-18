"""SpaceMouse UI local preview plugin for Cinema 4D 2027 on Apple Silicon."""
import builtins
import runpy
from pathlib import Path
import c4d

PACKAGE=Path(__file__).resolve().parent
IDS=runpy.run_path(str(PACKAGE/'plugin_ids.py'))
runtime=runpy.run_path(str(PACKAGE/'plugin_runtime.py'),run_name='spacemouse_ui_runtime')

def register_preferences():
    global __res__
    preferences=runpy.run_path(str(PACKAGE/'preferences_ui.py'))
    __res__=c4d.plugins.GeResource()
    if not __res__.Init(str(PACKAGE)):raise RuntimeError('Could not initialize settings resources')
    identifier=preferences['PREFERENCE_ID']
    if not c4d.plugins.RegisterPreferencePlugin(id=identifier,g=preferences['Preferences'],name='SpaceMouse UI',description='spacemouseui',parentid=0,sortid=0):
        raise RuntimeError('Could not register Preferences')
    builtins._spacemouse_ui_preferences={'id':identifier,'resource':__res__,'class':preferences['Preferences']}
    preferences['mirror']()
    return identifier

def open_settings():
    preferences=getattr(builtins,'_spacemouse_ui_preferences',None)
    if preferences:
        c4d.PrefsLib_OpenDialog(preferences['id'])
        return True
    return runpy.run_path(str(PACKAGE/'settings_dialog.py'))['open_settings']()

class Command(c4d.plugins.CommandData):
    def Execute(self,doc):
        return open_settings()


class Service(c4d.plugins.MessageData):
    def GetTimer(self):return 8
    def CoreMessage(self,message,data):
        if message==c4d.MSG_TIMER:
            navigation=getattr(builtins,'_spacemouse_ui_navigation',None)
            if navigation:navigation.tick()
        return True

COMMAND_ID=IDS['COMMAND_ID']
SERVICE_ID=IDS['SERVICE_ID']

if __name__=='__main__':
    try:
        if not c4d.plugins.RegisterCommandPlugin(COMMAND_ID,'SpaceMouse UI',0,None,'Smooth SpaceMouse panel navigation and settings',Command()):raise RuntimeError('Could not register settings command')
        if not c4d.plugins.RegisterMessagePlugin(SERVICE_ID,'SpaceMouse UI input',0,Service()):raise RuntimeError('Could not register input service')
        navigation=runtime['Navigation'](PACKAGE)
        builtins._spacemouse_ui_navigation=navigation
        try:register_preferences()
        except Exception as error:print('SpaceMouse UI: Preferences unavailable; using settings dialog:',error)
        print('SpaceMouse UI loaded. Settings: Preferences > SpaceMouse UI.')
    except Exception as error:print('SpaceMouse UI initialization failed:',error)

def PluginMessage(message,data):
    if message==c4d.C4DPL_ENDPROGRAM:
        navigation=getattr(builtins,'_spacemouse_ui_navigation',None)
        if navigation:navigation.close()
    return True
