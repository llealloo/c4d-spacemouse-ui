"""A node edit adds an asterisk to the floating editor's title."""
from pathlib import Path
import runpy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'c4d-navigation/inspect_native_views.py'


class FloatingWindowDiscovery(unittest.TestCase):
    def check_title(self, title, guarded=False):
        module = runpy.run_path(str(SOURCE), run_name='test_native_views')
        rect = NS(origin=NS(x=0, y=0), size=NS(width=800, height=600))
        def call(obj, selector, restype=None, args=(), types=()):
            if selector == 'sharedApplication': return 10
            if selector == 'windows': return 20
            if selector == 'screens': return 40
            if selector == 'count': return 1 if obj in (20, 30, 40) else 0
            if selector == 'objectAtIndex:': return {20: 50, 30: 101, 40: 60}[obj]
            if selector == 'title': return title
            if selector == 'windowNumber': return 123
            if selector == 'contentView': return 100
            if selector == 'isHidden': return False
            if selector == 'isVisible': return True
            if selector in ('isMiniaturized', 'isHiddenOrHasHiddenAncestor'): return False
            if selector == 'bounds' or selector == 'frame': return rect
            if selector == 'convertRect:toView:' or selector == 'convertRectToScreen:': return args[0]
            if selector == 'subviews': return 30 if obj == 100 else 31
            raise AssertionError((obj, selector))
        objc = NS(objc_getClass=lambda name: 1, object_getClassName=lambda view: b'MaxonView')
        objc.class_getInstanceVariable = lambda *args: 1
        objc.ivar_getOffset = lambda *args: 8
        globals_ = module['inventory'].__globals__
        with patch.dict(globals_, call=call, objc=objc, text=lambda value: value):
            inventory = module['inventory']()
            graphs = module['read_node_graphs']()
            if guarded:
                geometry = runpy.run_path(str(SOURCE.parent.parent / 'c4d-plugin/docked_node_geometry.py'))
                surface = unittest.mock.Mock(return_value=True)
                with patch.dict(geometry['read_node_graphs'].__globals__, is_node_surface=surface):
                    graphs = geometry['read_node_graphs'](globals_, {'ptr': lambda address: 987})
                surface.assert_called_once_with(987, unittest.mock.ANY, floating=True)
                self.assertEqual(graphs[0]['message'], 987)
        return inventory, graphs

    def test_clean_title_is_discovered(self):
        inventory, graphs = self.check_title('Node Editor')
        self.assertEqual(len(inventory), 1)
        self.assertEqual(graphs[0]['window'], 123)

    def test_modified_title_is_discovered_after_node_creation(self):
        inventory, graphs = self.check_title('Node Editor *')
        self.assertEqual(inventory[0]['title'], 'Node Editor *')
        self.assertEqual(graphs[0]['window'], 123)

    def test_unrelated_window_is_not_treated_as_a_graph(self):
        self.assertEqual(self.check_title('Not a Node Editor *'), ([], []))

    def test_modified_title_retains_floating_surface_recognition(self):
        self.check_title('Node Editor *', guarded=True)


if __name__ == '__main__':
    unittest.main()
