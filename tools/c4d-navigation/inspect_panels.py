"""Read-only live API inventory; run from Cinema 4D Extensions > Run Script."""
import c4d
import json
from pathlib import Path


def main():
    result = {"gui_api": [n for n in dir(c4d.gui) if any(k in n.lower() for k in ("manager", "window", "mouse", "layout"))]}
    doc = c4d.documents.GetActiveDocument()
    result["views"] = []
    for i in range(doc.GetBaseDrawCount()):
        bd = doc.GetBaseDraw(i)
        view = {"index": i, "frame": bd.GetFrame(), "api": [n for n in dir(bd) if any(k in n.lower() for k in ("frame", "window"))]}
        for method in ("GetFrameScreen", "GetEditorWindow"):
            try:
                value = getattr(bd, method)()
                view[method] = repr(value)
                if method == "GetEditorWindow":
                    view["editor_api"] = dir(value)
            except Exception as exc:
                view[method] = str(exc)
        result["views"].append(view)
    Path('/Users/leah/Documents/Projects/SpaceMouse/.build/c4d-panel-inventory.json').write_text(json.dumps(result, indent=2))
    print('SpaceMouse panel inventory saved.')

if __name__ == '__main__':
    main()
