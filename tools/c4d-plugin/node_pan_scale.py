"""Read the live Node Editor scale; never invokes or modifies native objects."""
import hashlib
import math
import struct
from pathlib import Path

BUILD_HASHES={
    'c4d_nodeeditor.xlib':'12cafb40c91cb013b017275221245dffc49d804a3a36052075e5fa74ae4c8ef2',
    'gui.module.xlib':'a948e66af8e2a31d570cf9b3392bbc333e59e6f6f950c069ac51311dc64074c2',
    'gui_gluon.module.xlib':'104aa15a262ee806bb46cca3a0ae1d25611bcce9122072bc4424b2d027a1d6c2',
}

class ScaleReader:
    def __init__(self,api):
        self.ptr,self.read=api['ptr'],api['read']
        lib=api['lib'];images={}
        for i in range(lib._dyld_image_count()):
            path=(lib._dyld_get_image_name(i) or b'').decode()
            name=Path(path).name
            if name in BUILD_HASHES:
                if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=BUILD_HASHES[name]:
                    raise RuntimeError('Node scale requires the inspected C4D build')
                images[name]=lib._dyld_get_image_header(i)
        if len(images)!=len(BUILD_HASHES):raise RuntimeError('Node scale modules unavailable')
        self.node=images['c4d_nodeeditor.xlib'];self.gluon=images['gui_gluon.module.xlib']
        # DoZoom's zoom-out path reads the same scalar as its coordinate
        # conversion and zoom setter. The latter bounds it by min/max zoom.
        if self.read(self.node+0x109de4,4)!=bytes.fromhex('604a5abd'):
            raise RuntimeError('Node scale instruction identity mismatch')

    def identity(self,obj):
        return self.read(self.ptr(self.ptr(obj)+16),100).split(b'\0',1)[0]

    def scale(self,message):
        """Resolve fresh from a live NSView; closed graph pointers aren't cached."""
        try:
            if not message or self.identity(message)!=b'net.maxon.ui.oswindowclass.widgetuserdraw':return None
            observable=self.ptr(message+0x110)  # ObservableDraw
            if self.identity(observable)!=b'net.maxon.class.observable':return None
            if self.ptr(observable+0x10)!=message:return None
            entries=self.ptr(observable+0x28);count=self.ptr(observable+0x30)
            if not 0<count<=16:return None
            for index in range(count):
                callback=self.ptr(entries+index*16+8)
                if not callback or self.ptr(callback+0x10)!=self.gluon+0x7a0f0:continue
                # The drawing callback captures a weak Window selfRef. Its
                # wrapper also captures the OS window: check both directions.
                if self.ptr(callback+0x70)!=message:continue
                weak=self.ptr(callback+0x18)
                graph=self.ptr(weak) if weak else 0
                if not graph or graph&1:continue
                if self.identity(graph)!=b'net.maxon.mvp.gluon2.windowclasses.nodegraph':continue
                if self.ptr(graph+0x50)!=message:continue
                info=self.ptr(graph)
                offset=self.ptr(self.node+0x27a9d0+0x40)
                if not 0<offset<0x100000 or self.ptr(info+0x20)<=offset:continue
                method,adjust=struct.unpack('<Qq',self.read(info+offset+0x141,16))
                if method!=self.node+0x109da8 or adjust!=0x638:continue
                component=graph+adjust
                low,high=struct.unpack('<2f',self.read(component+0x600,8))
                value=struct.unpack('<f',self.read(component+0x1a48,4))[0]
                if (all(math.isfinite(v) for v in (low,high,value))
                    and 0<low<=value<=high<=100):return value
        except (RuntimeError,OverflowError,struct.error):pass
        return None

