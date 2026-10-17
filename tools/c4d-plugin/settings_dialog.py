"""Live settings fallback; shares the native Preferences schema and storage."""
import builtins
import runpy
from pathlib import Path
import c4d
MODEL=runpy.run_path(str(Path(__file__).with_name('preferences_model.py')))
class SettingsDialog(c4d.gui.GeDialog):
    def CreateLayout(self):
        self.SetTitle('SpaceMouse UI Settings')
        self.ScrollGroupBegin(9000,c4d.BFH_SCALEFIT|c4d.BFV_SCALEFIT,c4d.SCROLLGROUP_VERT,600,650)
        self.GroupBegin(9001,c4d.BFH_SCALEFIT|c4d.BFV_TOP,1,0,'',0)
        for group,label in MODEL['GROUPS']:
            self.GroupBegin(group,c4d.BFH_SCALEFIT,2,0,label,0)
            self.GroupBorder(c4d.BORDER_GROUP_IN)
            self.GroupBorderSpace(12,8,12,12)
            for identifier,parent,path,title,default in MODEL['FIELDS']:
                if parent!=group:continue
                if isinstance(default,bool):
                    self.AddCheckbox(identifier,c4d.BFH_LEFT,0,0,title)
                    self.AddStaticText(identifier+20000,c4d.BFH_LEFT,0,0,name='')
                else:
                    self.AddStaticText(identifier+20000,c4d.BFH_LEFT,0,0,name=title)
                    self.AddEditNumberArrows(identifier,c4d.BFH_SCALEFIT)
            self.GroupEnd()
        self.GroupEnd()
        self.GroupEnd()
        return True
    def InitValues(self):
        nav=builtins._spacemouse_ui_navigation
        for identifier,parent,path,title,default in MODEL['FIELDS']:
            value=MODEL['get'](nav.settings,identifier)
            if isinstance(default,bool):self.SetBool(identifier,value)
            else:self.SetFloat(identifier,value,min=.05,max=10.,step=.05,format=c4d.FORMAT_PERCENT)
        return True
    def Command(self,identifier,message):
        if identifier not in MODEL['BY_ID']:return True
        nav=builtins._spacemouse_ui_navigation
        default=MODEL['BY_ID'][identifier][4]
        value=self.GetBool(identifier) if isinstance(default,bool) else self.GetFloat(identifier)
        MODEL['set_value'](nav.settings,identifier,value);nav.save()
        return True

def open_settings():
    dialog=getattr(builtins,'_spacemouse_ui_settings_dialog',None)
    if dialog is None:
        dialog=SettingsDialog();builtins._spacemouse_ui_settings_dialog=dialog
    return dialog.Open(c4d.DLG_TYPE_ASYNC,defaultw=600,defaulth=720)
