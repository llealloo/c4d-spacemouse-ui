"""Generate native description resources from the single settings schema."""
from pathlib import Path
import runpy

def generate(destination):
    model=runpy.run_path(str(Path(__file__).with_name('preferences_model.py')))
    root=Path(destination);description=root/'description';strings=root/'strings_en-US/description'
    description.mkdir(parents=True,exist_ok=True);strings.mkdir(parents=True,exist_ok=True)
    symbols=['#ifndef SPACEMOUSE_UI_DESCRIPTION_H','#define SPACEMOUSE_UI_DESCRIPTION_H','enum { SMUI_ROOT=999,']
    labels=['STRINGTABLE spacemouseui','{',' spacemouseui "SpaceMouse UI";']
    resource=['CONTAINER spacemouseui','{',' NAME spacemouseui;',' GROUP SMUI_ROOT',' {','  DEFAULT 1;']
    for group,label in model['GROUPS']:
        group_name='SMUI_GROUP_'+str(group)
        symbols.append(' '+group_name+'='+str(group)+',')
        labels.append(' '+group_name+' "'+label+'";')
        resource.extend(['  GROUP '+group_name,'  {','   DEFAULT 1;'])
        for identifier,parent,path,caption,default in model['FIELDS']:
            if parent!=group:continue
            name='SMUI_PARAMETER_'+str(identifier)
            symbols.append(' '+name+'='+str(identifier)+',')
            labels.append(' '+name+' "'+caption+'";')
            if isinstance(default,bool):resource.append('   BOOL '+name+' { }')
            # Percent resource literals use displayed percentages, not ratios.
            else:resource.append('   REAL '+name+' { UNIT PERCENT; MIN 5.0; MAX 1000.0; STEP 5.0; }')
        resource.append('  }')
    resource.extend([' }','}']);symbols.extend(['};','#endif']);labels.append('}')
    (description/'spacemouseui.h').write_text('\n'.join(symbols)+'\n')
    (description/'spacemouseui.res').write_text('\n'.join(resource)+'\n')
    (strings/'spacemouseui.str').write_text('\n'.join(labels)+'\n')
    (root/'c4d_symbols.h').write_text('enum { SMUI_RESOURCE_DUMMY=10000 };\n')
