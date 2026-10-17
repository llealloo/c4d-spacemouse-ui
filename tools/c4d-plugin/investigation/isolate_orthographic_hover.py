"""Temporarily stop our runtime, restoring the original vendor callback."""
import builtins
nav=builtins._spacemouse_ui_navigation
nav.close()
assert nav.closed
print('SpaceMouse UI runtime stopped; local hover monitor removed; original vendor callback restored')
