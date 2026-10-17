"""Ask the installed driver to restore its existing Cinema4d client."""
import builtins,ctypes as C,json,runpy,time
nav=builtins._spacemouse_ui_navigation
_ = runpy.run_path('/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-plugin/inspect_driver_clients.py')
clients=json.loads((nav.state/'driver-clients.json').read_text())['clients']
vendor=next(c for c in clients if c['fields']['clientName']['value']=='Cinema4d')
sdk=C.CDLL('/Library/Frameworks/3DconnexionClient.framework/3DconnexionClient')
sdk.ConnexionClientControl.argtypes=[C.c_ushort,C.c_uint,C.c_int,C.POINTER(C.c_int)]
sdk.ConnexionClientControl.restype=C.c_short
result=C.c_int()
error=sdk.ConnexionClientControl(vendor['id'],0x33646163,0,C.byref(result))
report={'time':time.time(),'client':vendor['id'],'error':error,'result':result.value}
(nav.state/'vendor-restore.json').write_text(json.dumps(report))
print('Vendor activation request:',report)
