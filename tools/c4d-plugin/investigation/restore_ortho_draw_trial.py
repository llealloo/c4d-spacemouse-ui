"""Remove the session-only Draw adapter in the same active test document."""
import builtins,c4d
trial=builtins._spacemouse_ortho_draw_trial
api=builtins._spacemouse_ui_navigation.timeline
assert api['active_document']()==trial['doc'], 'Return to the original test document before restoring'
c4d.StopAllThreads()
status=trial['helper'].SMOrthoRestore(trial['instance'])
assert status==0,status
assert api['ptr'](trial['instance'])==trial['original_vtable']
c4d.DrawViews(c4d.DRAWFLAGS_NO_THREAD|c4d.DRAWFLAGS_NO_ANIMATION|c4d.DRAWFLAGS_FORCEFULLREDRAW)
print('Original vendor Draw callback restored')
