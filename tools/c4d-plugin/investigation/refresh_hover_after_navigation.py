"""Request a normal, non-navigation viewport redraw without editing scene data."""
import c4d
flags=c4d.DRAWFLAGS_NO_THREAD|c4d.DRAWFLAGS_NO_ANIMATION|c4d.DRAWFLAGS_FORCEFULLREDRAW
c4d.DrawViews(flags)
print('Normal full viewport redraw completed, without INMOVE flag')
