"""Native C4D Preferences page, backed by the live navigation settings."""
import builtins
import runpy
from pathlib import Path
import c4d

PACKAGE=Path(__file__).resolve().parent
MODEL=runpy.run_path(str(PACKAGE/'preferences_model.py'),run_name='spacemouse_ui_preferences_schema')
FIELDS=MODEL['FIELDS'];BY_ID=MODEL['BY_ID']
RESOURCE=None
PREFERENCE_ID=None
WORLD_CONTAINER=0x53504D55  # Local preview's distinct preference-data namespace.

def navigation():return getattr(builtins,'_spacemouse_ui_navigation',None)

def container():
    world=c4d.GetWorldContainerInstance()
    data=world.GetContainerInstance(WORLD_CONTAINER)
    if data is None:
        world.SetContainer(WORLD_CONTAINER,c4d.BaseContainer())
        data=world.GetContainerInstance(WORLD_CONTAINER)
    return data

def mirror():
    nav=navigation()
    if not nav:return
    data=container()
    for identifier,group,path,label,default in FIELDS:
        value=MODEL['get'](nav.settings,identifier)
        if isinstance(default,bool):data.SetBool(identifier,value)
        else:data.SetFloat(identifier,value)

class Preferences(c4d.plugins.PreferenceData):
    def Init(self,node,isCloneInit=False):
        mirror();return True
    def GetDDescription(self,node,description,flags):
        if not description.LoadDescription('spacemouseui'):return False
        if flags & c4d.DESCFLAGS_DESC_NEEDDEFAULTVALUE:
            data=container()
            for identifier,group,path,label,default in FIELDS:
                typ=c4d.DTYPE_BOOL if isinstance(default,bool) else c4d.DTYPE_REAL
                self.InitPreferenceValue(identifier,default,description,c4d.DescID(c4d.DescLevel(identifier,typ,0)),data)
        return True,flags|c4d.DESCFLAGS_DESC_LOADED
    def GetDParameter(self,node,identifier,flags):
        key=identifier[0].id
        nav=navigation()
        if key not in BY_ID or nav is None:return False
        return True,MODEL['get'](nav.settings,key),flags|c4d.DESCFLAGS_GET_PARAM_GET
    def SetDParameter(self,node,identifier,value,flags):
        key=identifier[0].id;nav=navigation()
        if key not in BY_ID or nav is None:return False
        MODEL['set_value'](nav.settings,key,value)
        nav.save();mirror()
        return True,flags|c4d.DESCFLAGS_SET_PARAM_SET
    def GetDEnabling(self,node,identifier,data,flags,itemdesc):
        key=identifier[0].id;nav=navigation()
        if nav is None or key not in BY_ID:return True
        if key in (1000,1005):return True
        if not nav.settings['enabled']:return False
        return nav.settings['zoomEnabled'] if BY_ID[key][2] in ('masterZoom','panels.node.zoom','panels.dope.zoom','panels.fcurve.zoom') else True

def register():
    global PREFERENCE_ID,RESOURCE,__res__,__file__
    previous=getattr(builtins,'_spacemouse_ui_preferences',None)
    if previous:return previous['id']
    PREFERENCE_ID=next(i for i in range(1000001,1000200) if not c4d.plugins.FindPlugin(i,c4d.PLUGINTYPE_ANY))
    RESOURCE=c4d.plugins.GeResource()
    if not RESOURCE.Init(str(PACKAGE)):raise RuntimeError('Could not initialize SpaceMouse UI resources')
    __res__=RESOURCE
    __file__=str(PACKAGE/'SpaceMouseUI.pyp')
    if not c4d.plugins.RegisterPreferencePlugin(id=PREFERENCE_ID,g=Preferences,name='SpaceMouse UI',description='spacemouseui',parentid=0,sortid=0):raise RuntimeError('Could not register SpaceMouse UI Preferences')
    mirror()
    builtins._spacemouse_ui_preferences={'id':PREFERENCE_ID,'resource':RESOURCE,'class':Preferences,'model':MODEL}
    return PREFERENCE_ID
