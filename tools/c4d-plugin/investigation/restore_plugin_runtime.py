"""Restore the installed runtime after the orthographic hover comparison."""
import builtins,runpy
previous=builtins._spacemouse_ui_navigation
previous.close()
module=runpy.run_path(str(previous.package/'plugin_runtime.py'))
builtins._spacemouse_ui_navigation=module['Navigation'](previous.package)
print('SpaceMouse UI runtime restored')
