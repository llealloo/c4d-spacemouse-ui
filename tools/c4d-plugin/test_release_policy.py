"""Static regressions for release architecture and deployment compatibility."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ReleasePolicy(unittest.TestCase):
    def test_native_helpers_target_macos_14(self):
        source = (ROOT / 'tools/c4d-plugin/build.py').read_text()
        self.assertIn("deployment_target='14.0'", source)
        self.assertGreaterEqual(source.count("f'-mmacosx-version-min={deployment_target}'"), 5)

    def test_packager_checks_every_native_library(self):
        source = (ROOT / 'tools/c4d-plugin/package_release.py').read_text()
        self.assertIn("package.glob('*.dylib')", source)
        self.assertIn("package.glob('*.xlib')", source)
        self.assertIn("['vtool', '-show-build'", source)
        self.assertIn("Expected macOS 14.0-compatible library", source)


if __name__ == '__main__':
    unittest.main()
