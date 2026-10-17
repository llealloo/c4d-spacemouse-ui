"""Own the dialog callback wrapper for the lifetime of the navigation service."""
import ctypes as C
from pathlib import Path

class DialogScroll:
    def __init__(self,package,loader=None):
        self.path=Path(package)/'libSpaceMouseUIDialog.dylib'
        self.loader=loader or C.CDLL
        self.helper=None;self.client=0;self.next_try=0;self.last_error=None
        self.permission_warned=False

    def update(self,client,ready,enabled,now):
        client=int(client) if ready else 0
        if self.client and (self.client!=client or not enabled):self.close()
        if not client or not enabled or self.client==client or now<self.next_try:return
        self.next_try=now+.5
        try:
            if self.helper is None:
                helper=self.loader(str(self.path))
                for name,args,result in (
                    ('SMFileDialogStart',[C.c_uint16],C.c_int),
                    ('SMFileDialogStop',[],None),
                    ('SMDialogPostAccess',[],C.c_int),
                    ('SMDialogConfigureAxes',[C.c_double,C.c_double],C.c_int)):
                    function=getattr(helper,name);function.argtypes=args;function.restype=result
                self.helper=helper
            error=self.helper.SMFileDialogStart(client)
            if error:
                # Startup/reconnection can briefly precede the vendor callback.
                if error!=self.last_error:
                    print('SpaceMouse UI: file-dialog input waiting (%s)'%error)
                self.last_error=error
                return
            self.client=client;self.last_error=None
            if not self.helper.SMDialogConfigureAxes(2400,3600):
                self.close();raise RuntimeError('Could not apply file-dialog scroll tuning')
            if not self.helper.SMDialogPostAccess() and not self.permission_warned:
                print('SpaceMouse UI: enable Cinema 4D in Privacy & Security > Device Control and Data Access for file-dialog scrolling.')
                self.permission_warned=True
        except Exception as error:
            message=str(error)
            if message!=self.last_error:print('SpaceMouse UI: file-dialog scrolling unavailable:',message)
            self.last_error=message

    def close(self):
        # Always restore this wrapper before the input bridge restores its callback.
        if self.helper is not None and self.client:self.helper.SMFileDialogStop()
        self.client=0
