"""Explicit read-only viewport snapshot for plugin-free/vendor comparisons."""
import c4d, json, time
from pathlib import Path

def capture(label):
    doc = c4d.documents.GetActiveDocument()
    names = [n for n in dir(c4d) if n.startswith(('BASEDRAW_DISPLAYFILTER_', 'BASEDRAW_DATA_'))]
    result = {'label': label, 'time': time.time(), 'document': doc.GetDocumentName(),
              'mode': doc.GetMode(), 'tool': doc.GetAction(), 'views': []}
    for i in range(doc.GetBaseDrawCount()):
        view = doc.GetBaseDraw(i)
        values = {}
        for name in names:
            try:
                value = view[getattr(c4d, name)]
                values[name] = value if isinstance(value, (str, int, float, bool, type(None))) else repr(value)
            except Exception:
                pass
        result['views'].append({'index': i, 'active': view == doc.GetActiveBaseDraw(), 'values': values})
    path = Path('/Users/leah/Documents/Projects/SpaceMouse/.build') / ('hover-baseline-' + label + '.json')
    path.write_text(json.dumps(result, indent=2))
    print('Read-only hover baseline saved:', label)

if __name__ == '__main__':
    capture('plugin-free')
