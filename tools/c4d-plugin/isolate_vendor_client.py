"""Temporarily leave only the vendor input client, without persisting settings."""
import builtins,json,time
nav=builtins._spacemouse_ui_navigation
nav._enabled_before_isolation=nav.settings['enabled']
nav.end();nav.settings['enabled']=False
nav.target=None;nav.native.SMUIClaim(0);nav.native.SMUIStop()
(nav.state/'vendor-isolation.json').write_text(json.dumps({'time':time.time(),'status':'UI client unregister requested; settings not saved'}))
print('SpaceMouse UI input temporarily stopped; vendor viewport test ready')
