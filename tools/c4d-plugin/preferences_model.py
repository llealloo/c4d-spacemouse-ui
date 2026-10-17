"""Shared settings schema. Multipliers preserve the accepted feel at 100%."""
import math
from copy import deepcopy

# Calibrated physical gains. Settings retain these actual gains for backwards
# compatibility; the UI expresses adjustments relative to this tuning.
PROFILES={
 'node':{'panX':1.85,'panY':1.85,'zoom':.8},
 'dope':{'panX':3.,'panY':3.,'zoom':1.},
 'fcurve':{'panX':3.,'panY':3.,'zoom':1.},
 'tracks':{'panX':0.,'panY':3.,'zoom':0.},
 'lists':{'panX':6.,'panY':6.,'zoom':0.},
}
GROUPS=[(2000,'General'),(2001,'Overall sensitivity'),(2002,'Node Editor graphs'),
        (2003,'Dope Sheet'),(2004,'F-Curve graphs'),(2005,'Timeline track lists'),(2006,'Lists and inspectors')]
FIELDS=[
 (1000,2000,'enabled','Enable panel navigation',True),
 (1005,2000,'fixOrthographicHover','Restore orthographic component hover',True),
 (1004,2000,'suppressComponentHover','Prevent component-mode navigation stutter',True),
 (1001,2000,'zoomEnabled','Enable forward/back zoom',True),
 (1002,2000,'invertHorizontal','Invert horizontal pan',False),
 (1003,2000,'invertVertical','Invert vertical pan',True),
 (1010,2001,'panGain','Pan and scroll',1.),
 (1011,2001,'masterZoom','Zoom',1.),
]
for profile,group,start in [('node',2002,1100),('dope',2003,1120),('fcurve',2004,1140),('tracks',2005,1160),('lists',2006,1180)]:
 for offset,(axis,label) in enumerate([('panX','Horizontal pan' if profile not in ('tracks','lists') else 'Horizontal scroll'),
                                      ('panY','Vertical pan' if profile not in ('tracks','lists') else 'Vertical scroll'),('zoom','Zoom')]):
  if PROFILES[profile][axis]:FIELDS.append((start+offset,group,'panels.'+profile+'.'+axis,label,1.))
BY_ID={field[0]:field for field in FIELDS}

def gain(value,default=1.,low=.05,high=10.):
 try:result=float(value)
 except (TypeError,ValueError):return default
 return max(low,min(high,result)) if math.isfinite(result) else default

def normalise(settings):
 out=deepcopy(settings)
 for key,default in [('fixOrthographicHover',True),('suppressComponentHover',True),('enabled',True),('zoomEnabled',True),('invertHorizontal',False),('invertVertical',True)]:out[key]=bool(out.get(key,default))
 out['zoomGain']=gain(out.get('zoomGain',6.),6.,.25,80.)
 out['zoomReference']=gain(out.get('zoomReference',out['zoomGain']),out['zoomGain'],.25,8.)
 out['panGain']=gain(out.get('panGain',1.))
 old=out.get('panels',{});old=old if isinstance(old,dict) else {}
 out['panels']=deepcopy(PROFILES)
 for profile,axes in out['panels'].items():
  previous=old.get(profile,{});previous=previous if isinstance(previous,dict) else {}
  for axis,default in axes.items():
   if default:axes[axis]=gain(previous.get(axis,default),default,default*.05,default*10.)
 return out

def get(settings,identifier):
 path=BY_ID[identifier][2]
 if path=='masterZoom':return settings['zoomGain']/settings['zoomReference']
 value=settings
 for key in path.split('.'):value=value[key]
 if path.startswith('panels.'):
  _,profile,axis=path.split('.')
  value/=PROFILES[profile][axis]
 return value

def set_value(settings,identifier,value):
 field=BY_ID[identifier];path=field[2]
 value=bool(value) if isinstance(field[4],bool) else gain(value)
 if path=='masterZoom':settings['zoomGain']=settings['zoomReference']*value;return
 if path.startswith('panels.'):
  _,profile,axis=path.split('.')
  value*=PROFILES[profile][axis]
 destination=settings;keys=path.split('.')
 for key in keys[:-1]:destination=destination[key]
 destination[keys[-1]]=value
