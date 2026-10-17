"""Apply quiet runtime without restarting or replacing native input."""
import builtins,runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('apply_docked_node_update.py')))
nav=builtins._spacemouse_ui_navigation
if nav.timeline:nav.timeline['flush_redraw']()
nav.timeline=runpy.run_path(str(nav.package/'runtime/timeline_direct.py'),init_globals={'SPACEMOUSE_STATE':str(nav.state)})
nav.diagnostics=False
nav.last_geometry=0;nav.refresh_geometry()
print('SpaceMouse UI: routine diagnostic writes disabled; settings and error reporting retained')
