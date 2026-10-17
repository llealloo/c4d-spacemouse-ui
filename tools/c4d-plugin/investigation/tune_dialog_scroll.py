import builtins,ctypes as C
h=builtins._spacemouse_file_dialog_trial['helper']
h.SMDialogConfigureAxes.argtypes=[C.c_double,C.c_double];h.SMDialogConfigureAxes.restype=C.c_int
assert h.SMDialogConfigureAxes(2400,3600)==1
print('Dialog horizontal speed doubled; vertical unchanged.')
