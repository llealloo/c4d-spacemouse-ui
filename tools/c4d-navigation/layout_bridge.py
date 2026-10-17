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

class SpaceMouseLayoutBridge(c4d.gui.GeDialog):
    enabled = True

    def CreateLayout(self):
        self.SetTitle('SpaceMouse Live Layout')
        self.AddStaticText(100, c4d.BFH_SCALEFIT, name='Live viewport tracking — keep this window open')
        self.AddButton(101, c4d.BFH_LEFT, name='Stop layout tracking')
        return True

    def InitValues(self):
        self.SetTimer(80)
        return True

    def Timer(self, message):
        self.CoreMessage(c4d.MSG_TIMER, None)

    def Command(self, command, message):
        if command == 101:
            self.enabled = False
            self.SetTimer(0)
            self.Close()
        return True

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
            payload = {'pid': os.getpid(), 'timestamp': time.time(), 'viewports': frames, 'nodeGraphs': NATIVE['read_node_graphs']()}
            temporary = OUTPUT.with_suffix('.tmp')
            temporary.write_text(json.dumps(payload))
            os.replace(str(temporary), str(OUTPUT))
        except Exception as error:
            self.enabled = False
            print('SpaceMouse layout bridge stopped:', error)
        return True


def main():
    previous = getattr(builtins, '_spacemouse_layout_bridge', None)
    if previous:
        previous.enabled = False
        previous.Close()
    bridge = SpaceMouseLayoutBridge()
    bridge.Open(c4d.DLG_TYPE_ASYNC, defaultw=380, defaulth=80)
    builtins._spacemouse_layout_bridge = bridge
    print('SpaceMouse live layout bridge running for this C4D session.')

if __name__ == '__main__':
    main()
