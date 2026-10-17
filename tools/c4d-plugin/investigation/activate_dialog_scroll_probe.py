import builtins,ctypes as C
p=getattr(builtins,'_sm_dialog_scroll_probe',None)
if p is None:
 p=C.CDLL('/Users/leah/Documents/Projects/SpaceMouse/.build/libSpaceMouseDialogScrollProbe.dylib');builtins._sm_dialog_scroll_probe=p
p.SMDialogProbeStart.argtypes=[C.c_char_p];p.SMDialogProbeStart.restype=C.c_int
print('Passive scroll recorder:',p.SMDialogProbeStart(b'/Users/leah/Documents/Projects/SpaceMouse/.build/dialog-scroll-native-trace.jsonl'))
