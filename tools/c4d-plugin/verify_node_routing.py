"""Read-only routing check against the currently visible graph and viewports."""
import builtins,json
nav=builtins._spacemouse_ui_navigation
Context=nav.__class__.__init__.__globals__['Context']
nav.refresh_geometry()
results=[]
for graph in nav.graphs:
 c=Context();c.active=1;c.window=graph['window'];c.title=b'Test - Main'
 c.x=graph['x']+graph['width']/2;c.y=graph['y']+graph['height']/2
 target=nav.route(c);assert target and target[0]=='node'
 results.append({'graph':graph,'route':target[0]})
for frame in nav.viewports:
 c=Context();c.active=1;c.window=nav.graphs[0]['window'] if nav.graphs else 0;c.title=b'Test - Main'
 c.x=frame[0]+frame[2]/2;c.y=frame[1]+frame[3]/2
 assert nav.route(c) is None
(nav.state/'node-routing-verification.json').write_text(json.dumps({'graphs':results,'viewportExclusions':len(nav.viewports)}))
print('Graph routing and viewport exclusion verified')
