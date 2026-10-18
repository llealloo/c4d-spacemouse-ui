"""Regression policy for adaptive, fail-closed Timeline navigation."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class TimelineNativePolicy(unittest.TestCase):
    def test_timeline_has_no_whole_binary_hash_or_fixed_manager_addresses(self):
        source = (ROOT / 'tools/c4d-navigation/timeline_direct.py').read_text()
        self.assertNotIn('hashlib.sha256', source)
        for value in ('0x670b4', '0x478a4', '0x5c900', '0x5774f0', '0x5b8a80', '0x5b8ad8', '0x5b8ae0'):
            self.assertNotIn(value, source)

    def test_native_bridge_resolves_timeline_and_wraps_sdk_gui_calls(self):
        source = (ROOT / 'tools/c4d-native/source/main.cpp').read_text()
        for marker in ('ResolveTimelinePrivateApi', 'FindTimelineRegistry', 'kTimelineRangeSignature',
                       'kTimelineVerticalSignature', 'kTimelineRedrawSignature',
                       'SMTimelineDialogVisible', 'SMTimelineDialogRect',
                       'SMTimelineDialogSetVisible', 'SMTimelineAreaConvert',
                       'SMTimelineAreaRedraw'):
            self.assertIn(marker, source)

    def test_timeline_scroll_uses_live_visible_rectangle(self):
        source = (ROOT / 'tools/c4d-native/source/main.cpp').read_text()
        start = source.rindex('Int32 SMTimelineDialogRect(')
        body = source[start:source.index('Int32 SMTimelineDialogSetVisible(', start)]
        self.assertIn('GetVisibleArea(', body)
        self.assertNotIn('return dialog->GetItemDim(', body)

    def test_timeline_discovers_live_embedded_user_area_layout(self):
        source = (ROOT / 'tools/c4d-navigation/timeline_direct.py').read_text()
        self.assertIn('def resolve_layout()', source)
        self.assertIn("ptr(area+0x18)==parent", source)
        self.assertIn('len(matches)>=2', source)
        self.assertNotIn('area=parent+0x228', source)

if __name__ == '__main__':
    unittest.main()
