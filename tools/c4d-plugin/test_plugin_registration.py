"""Exercise both registration paths without attaching to Cinema 4D or the driver."""
import builtins
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parent
RUN_PATH = runpy.run_path


class Registration(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.existing = {}
        for name in ('_spacemouse_ui_preferences', '_spacemouse_ui_navigation'):
            if hasattr(builtins, name):
                self.existing[name] = getattr(builtins, name)
                delattr(builtins, name)
        calls = self.calls

        class Resource:
            def Init(self, path):
                return True

        def register(kind, identifier):
            calls.append((kind, identifier))
            return True

        self.c4d = types.SimpleNamespace(plugins=types.SimpleNamespace(
            CommandData=object, MessageData=object, PreferenceData=object,
            GeResource=Resource,
            RegisterCommandPlugin=lambda identifier, *a: register('command', identifier),
            RegisterMessagePlugin=lambda identifier, *a: register('service', identifier),
            RegisterPreferencePlugin=lambda **kw: register('preferences', kw['id']),
        ))
        self.modules = patch.dict(sys.modules, {'c4d': self.c4d})
        self.modules.start()

    def tearDown(self):
        self.modules.stop()
        for name in ('_spacemouse_ui_preferences', '_spacemouse_ui_navigation'):
            if hasattr(builtins, name):
                delattr(builtins, name)
        for name, value in self.existing.items():
            setattr(builtins, name, value)

    def test_startup_registers_all_three_assigned_ids(self):
        def load(path, *args, **kwargs):
            if Path(path).name == 'plugin_runtime.py':
                return {'Navigation': lambda package: object()}
            result = RUN_PATH(path, *args, **kwargs)
            if Path(path).name == 'preferences_ui.py':
                result['mirror'] = lambda: None
            return result

        with patch('runpy.run_path', side_effect=load):
            RUN_PATH(str(PACKAGE / 'SpaceMouseUI.pyp'), run_name='__main__')
        self.assertEqual(self.calls, [
            ('command', 1071577), ('service', 1071578), ('preferences', 1071579)])
        self.assertEqual(builtins._spacemouse_ui_preferences['id'], 1071579)

    def test_standalone_preferences_uses_the_same_assigned_id(self):
        preferences = RUN_PATH(str(PACKAGE / 'preferences_ui.py'))
        self.assertEqual(preferences['register'](), 1071579)
        self.assertEqual(self.calls, [('preferences', 1071579)])

    def test_repeated_standalone_registration_reuses_existing_preferences(self):
        preferences = RUN_PATH(str(PACKAGE / 'preferences_ui.py'))
        preferences['register']()
        preferences['register']()
        self.assertEqual(self.calls, [('preferences', 1071579)])


if __name__ == '__main__':
    unittest.main()
