"""Keep a disproven XPresso transport from returning during investigation."""
from pathlib import Path
import unittest


class XPressoRejectedTransport(unittest.TestCase):
    def test_bridge_does_not_reintroduce_wheel_or_magnify_delivery(self):
        source=(Path(__file__).parents[1]/'c4d-native/source/main.cpp').read_text()
        body=source.split('Int32 SMGvNavigate(',2)[-1]
        self.assertNotIn('InputEvent(',body)
        self.assertNotIn('BFM_INPUT_MOUSEWHEEL',body)
        self.assertNotIn('BFM_INPUT_MAGNIFY',body)

    def test_bridge_uses_guarded_direct_translation_for_pan(self):
        source=(Path(__file__).parents[1]/'c4d-native/source/main.cpp').read_text()
        self.assertIn('kSetTranslationSignature',source)
        self.assertIn('kGetTranslationSignature',source)
        self.assertIn('gui->GetZoom(root, zoom)',source)
        self.assertIn('x + deltaX / zoom, y + deltaY / zoom',source)
        self.assertIn('gui->Redraw()',source)

    def test_bridge_uses_node_editors_reciprocal_zoom_curve(self):
        source=(Path(__file__).parents[1]/'c4d-native/source/main.cpp').read_text()
        self.assertIn('kSetZoomSignature',source)
        self.assertIn('std::min(std::abs(delta) * 0.002, 0.95)',source)
        self.assertIn('delta > 0.0 ? 1.0 / (1.0 - amount) : 1.0 - amount',source)
        self.assertIn('api.setZoom(helper, gui, root, target)',source)

    def test_bridge_resolves_private_api_without_fixed_image_offsets(self):
        source=(Path(__file__).parents[1]/'c4d-native/source/main.cpp').read_text()
        self.assertIn('dladdr(address, &image)',source)
        self.assertIn('FindUniqueSignature',source)
        self.assertIn('ResolveHelperLayout',source)
        self.assertNotIn('kGetZoomOffset',source)
        self.assertNotIn('kSetTranslationOffset',source)
        self.assertNotIn('kGetTranslationOffset',source)
        self.assertNotIn('kSetZoomOffset',source)
        self.assertNotIn('kRootViewHelperOffset',source)


if __name__=='__main__':unittest.main()
