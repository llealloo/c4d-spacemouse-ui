"""Scale conversion and native ownership/identity guard regressions."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec=importlib.util.spec_from_file_location('node_pan_scale',Path(__file__).with_name('node_pan_scale.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class NodeScale(unittest.TestCase):
    def setUp(self):
        self.memory={};self.reader=m.ScaleReader.__new__(m.ScaleReader)
        self.reader.node=0x10000000;self.reader.gluon=0x20000000
        def read(address,size):
            try:return bytes(self.memory[address+i] for i in range(size))
            except KeyError:raise RuntimeError('Unmapped')
        self.reader.read=read;self.reader.ptr=lambda p:struct.unpack('<Q',read(p,8))[0]
        self.message=0x1000;self.observable=0x2000;self.entries=0x3000
        self.callback=0x4000;self.weak=0x5000;self.graph=0x6000;self.info=0xa000
        for obj,name,info in [(self.message,b'net.maxon.ui.oswindowclass.widgetuserdraw',0xb000),
            (self.observable,b'net.maxon.class.observable',0xc000),
            (self.graph,b'net.maxon.mvp.gluon2.windowclasses.nodegraph',self.info)]:
            self.q(obj,info);self.q(info+16,info+0x800);self.write(info+0x800,name+b'\0'*(100-len(name)))
        self.q(self.message+0x110,self.observable);self.q(self.observable+16,self.message)
        self.q(self.observable+0x28,self.entries);self.q(self.observable+0x30,1)
        self.q(self.entries+8,self.callback);self.q(self.callback+16,self.reader.gluon+0x7a0f0)
        self.q(self.callback+0x70,self.message);self.q(self.callback+0x18,self.weak)
        self.q(self.weak,self.graph);self.q(self.graph+0x50,self.message)
        self.q(self.reader.node+0x27a9d0+0x40,0x100);self.q(self.info+0x20,0x1000)
        self.write(self.info+0x100+0x141,struct.pack('<Qq',self.reader.node+0x109da8,0x638))
        self.write(self.graph+0x638+0x600,struct.pack('<2f',.05,2))
        self.scale(1)
    def write(self,address,data):self.memory.update({address+i:v for i,v in enumerate(data)})
    def q(self,address,value):self.write(address,struct.pack('<Q',value))
    def scale(self,value):self.write(self.graph+0x638+0x1a48,struct.pack('<f',value))
    def test_scale_follows_live_changes(self):
        for value in (.125,.5,1,2):
            self.scale(value);self.assertEqual(self.reader.scale(self.message),value)
    def test_surface_identity_survives_detached_renderer(self):
        import runpy
        geometry=runpy.run_path(str(Path(__file__).with_name('docked_node_geometry.py')))
        api={'read':self.reader.read,'ptr':self.reader.ptr}
        self.assertTrue(geometry['is_node_surface'](self.message,api,floating=True))
        self.assertTrue(geometry['is_node_surface'](self.message,api,floating=False))
    def test_stale_weak_reference_falls_back(self):
        self.q(self.weak,0);self.assertIsNone(self.reader.scale(self.message))
        self.assertIsNone(self.reader.scale(self.message))
    def test_wrong_owner_or_method_rejected(self):
        self.q(self.graph+0x50,self.message+1);self.assertIsNone(self.reader.scale(self.message))
        self.q(self.graph+0x50,self.message)
        self.q(self.info+0x100+0x141,self.reader.node+0x109dac)
        self.assertIsNone(self.reader.scale(self.message))
    def test_invalid_scale_or_subscriber_count_rejected(self):
        for value in (0,-1,float('nan'),float('inf'),3):
            self.scale(value);self.assertIsNone(self.reader.scale(self.message))
        self.scale(.5);self.q(self.observable+0x30,100000)
        self.assertIsNone(self.reader.scale(self.message))

if __name__=='__main__':unittest.main()
