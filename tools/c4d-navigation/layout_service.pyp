"""Session-only read-only viewport bridge. Execute in C4D's Python console.
Re-executing stops the previous instance. No scene or layout mutations.
"""
import c4d
import json
import os
import time
from pathlib import Path
import builtins
import runpy

NATIVE = runpy.run_path("/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-navigation/inspect_native_views.py", run_name="spacemouse_native_geometry")

OUTPUT = Path('/Users/leah/Documents/Projects/SpaceMouse/.build/live-layout.json')

class SpaceMouseLayoutBridge(c4d.plugins.MessageData):
    enabled = True

    def GetTimer(self):
        return 80 if self.enabled else 0

    def CoreMessage(self, message, data):
        if message != c4d.MSG_TIMER or not self.enabled:
            return True
        try:
            doc = c4d.documents.GetActiveDocument()
            frames = []
            if doc:
                for index in range(doc.GetBaseDrawCount()):
                    frame = doc.GetBaseDraw(index).GetFrameScreen()
                    if frame and frame['cr'] - frame['cl'] > 10 and frame['cb'] - frame['ct'] > 10:
                        frames.append(frame)
            payload = {'pid': os.getpid(), 'timestamp': time.time(), 'service': 'message-plugin', 'viewports': frames, 'nodeGraphs': NATIVE['read_node_graphs']()}
            temporary = OUTPUT.with_suffix('.tmp')
            temporary.write_text(json.dumps(payload))
            os.replace(str(temporary), str(OUTPUT))
        except Exception as error:
            # Layout rebuilding can transiently invalidate view geometry.
            # Leave the timer alive; the companion rejects stale snapshots.
            if str(error) != getattr(self, 'last_error', None):
                print('SpaceMouse layout service retrying:', error)
                self.last_error = str(error)
        return True


def main():
    previous = getattr(builtins, '_spacemouse_layout_service', None)
    if previous:
        previous.enabled = False
    plugin_id = next((i for i in range(1000001, 1000100) if not c4d.plugins.FindPlugin(i, c4d.PLUGINTYPE_ANY)), None)
    if plugin_id is None:
        raise RuntimeError('No free temporary plugin ID')
    bridge = SpaceMouseLayoutBridge()
    if not c4d.plugins.RegisterMessagePlugin(plugin_id, 'SpaceMouse layout service trial', 0, bridge):
        raise RuntimeError('Layout service registration failed')
    builtins._spacemouse_layout_service = bridge
    previous_dialog = getattr(builtins, '_spacemouse_layout_bridge', None)
    if previous_dialog:
        previous_dialog.enabled = False
        try:
            previous_dialog.Close()
        except RuntimeError:
            pass  # A layout change may already have destroyed this dialog.
    print('SpaceMouse layout service running without a dialog.')
    try:
        runpy.run_path('/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-navigation/activate_timeline_transport.py', run_name='spacemouse_timeline_activation')
    except Exception as error:
        print('Timeline transport unavailable; layout service remains active:', error)

if __name__ == '__main__':
    main()
