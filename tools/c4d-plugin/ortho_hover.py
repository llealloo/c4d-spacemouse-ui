"""Exact-build, per-document vendor drawing compatibility correction."""
import builtins
import ctypes as C
import hashlib
import struct
from pathlib import Path
import c4d

VENDOR_SHA='780162c4f48dc402dbddb1a6feb8367fb371d268372112f3242164727fc4090f'
CORE_SHA='1c0e204bc48bee5c7898b4e72e353a0f15304ea9b1036412434675f7ec848b62'
HOOK_ID=0x075bccbc

class Correction:
    def __init__(self,api,package):
        self.api=api;self.ptr=api['ptr'];self.read=api['read']
        lib=api['lib']
        images={lib._dyld_get_image_name(i).decode():lib._dyld_get_image_header(i) for i in range(lib._dyld_image_count())}
        vendor=next(p for p in images if p.endswith('/3DxCinema4D.xlib'))
        core='/Applications/Maxon Cinema 4D 2027/corelibs/c4d_base.xlib'
        if hashlib.sha256(Path(vendor).read_bytes()).hexdigest()!=VENDOR_SHA or hashlib.sha256(Path(core).read_bytes()).hexdigest()!=CORE_SHA:
            raise RuntimeError('Orthographic hover correction requires the verified vendor and C4D builds')
        self.base=images[vendor];corebase=images[core]
        for offset,code in [(0x5c98,'eb2bb96de923016d'),(0x5d48,'1f04007121110054'),(0x5f70,'00008052')]:
            if self.read(self.base+offset,len(bytes.fromhex(code)))!=bytes.fromhex(code):raise RuntimeError('Vendor Draw identity mismatch')
        doc_table=self.ptr(self.base+0x58b60)
        if doc_table!=self.ptr(api['BASE']+0x5b8b10):raise RuntimeError('Document SDK identity mismatch')
        self.find=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int)(self.ptr(doc_table+0x108))
        general=self.ptr(api['BASE']+0x5b8a80)
        self.first=C.CFUNCTYPE(C.c_void_p)(self.ptr(general+0x130))
        atom=self.ptr(api['BASE']+0x5b8b88)
        self.next_member=struct.unpack('<Qq',self.read(atom+0xb0,16))
        bd=self.ptr(self.base+0x58b90);obj=self.ptr(self.base+0x58b58)
        self.functions=[self.ptr(bd+0xb0),self.ptr(bd+8),self.ptr(obj+0x3a0)]
        if self.functions!=[corebase+v for v in (0x76be50,0x76be58,0x1e2964)]:raise RuntimeError('Camera SDK identity mismatch')
        library=str(Path(package)/'libSpaceMouseUIOrtho.dylib')
        if not hasattr(builtins,'_spacemouse_ortho_libraries'):builtins._spacemouse_ortho_libraries={}
        self.helper=builtins._spacemouse_ortho_libraries.setdefault(library,C.CDLL(library))
        self.helper.SMOrthoInstall.argtypes=[C.c_void_p,C.c_uint64,C.c_uint64,C.c_void_p,C.c_void_p,C.c_void_p]
        self.helper.SMOrthoInstall.restype=C.c_int
        self.helper.SMOrthoRestore.argtypes=[C.c_void_p];self.helper.SMOrthoRestore.restype=C.c_int
        self.helper.SMOrthoEnable.argtypes=[C.c_bool];self.helper.SMOrthoEnable.restype=None
        self.helper.SMOrthoVTable.argtypes=[];self.helper.SMOrthoVTable.restype=C.c_uint64
        self.helper.SMOrthoEnable(False)

    def documents(self):
        # Resolve live SDK links afresh. Never retain pointers to closed documents.
        doc=self.first();seen=set()
        while doc:
            if doc in seen:raise RuntimeError('Document list cycle')
            seen.add(doc);yield doc
            fn,adjust=self.next_member;node=doc+(adjust>>1)
            if adjust&1:fn=self.ptr(self.ptr(node)+fn)
            doc=C.CFUNCTYPE(C.c_void_p,C.c_void_p)(fn)(node)

    def instances(self):
        wrapped=self.helper.SMOrthoVTable()
        for doc in self.documents():
            hook=self.find(doc,HOOK_ID)
            if not hook:continue
            wrapper=self.ptr(hook+0x50)
            if not wrapper:continue
            instance=self.ptr(wrapper+0x10)
            if not instance:continue
            vtable=self.ptr(instance)
            if vtable not in (self.base+0x50530,wrapped):raise RuntimeError('Unexpected vendor drawing instance')
            if struct.unpack('<Qq',self.read(self.ptr(wrapper)+0x2a8,16))!=(216,1):raise RuntimeError('Unexpected vendor Draw registration')
            if self.ptr(vtable+27*8)!=self.base+0x5c98 and vtable!=wrapped:raise RuntimeError('Unexpected Draw callback')
            yield instance,vtable

    def update(self,enabled):
        self.helper.SMOrthoEnable(enabled)
        wrapped=self.helper.SMOrthoVTable()
        pending=[p for p,v in self.instances() if (v!=wrapped if enabled else v==wrapped)]
        if not pending:return
        c4d.StopAllThreads()
        # Enumerate again after stopping workers; do not use stale document pointers.
        for instance,vtable in self.instances():
            if enabled and vtable!=self.helper.SMOrthoVTable():
                result=self.helper.SMOrthoInstall(instance,self.base+0x50530,self.base+0x5c98,*self.functions)
                if result not in (0,1):raise RuntimeError('Could not adapt vendor Draw: %s'%result)
            elif not enabled and vtable==self.helper.SMOrthoVTable():
                result=self.helper.SMOrthoRestore(instance)
                if result:raise RuntimeError('Could not restore vendor Draw: %s'%result)

    def close(self):
        self.update(False)
