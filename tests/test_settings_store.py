"""Tests de config/settings_store.py et config/profiles.py."""
import json
import tempfile
import unittest
from pathlib import Path

from config.profiles import PRESETS, all_presets, custom_from_settings, preset_matches, resolution_label
from config.settings_store import SettingsStore
from core.models import AppPrefs, Settings


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = SettingsStore(Path(self._tmp.name) / "cfg")

    def test_defaults_when_missing(self):
        self.assertEqual(self.store.load_prefs(), AppPrefs())
        self.assertEqual(self.store.load_instances(), {"current": "", "instances": []})

    def test_prefs_roundtrip(self):
        prefs = AppPrefs(ui_mode="pro", palette="ocean", macros_list=[{"name": "m", "steps": []}])
        self.store.save_prefs(prefs)
        self.assertEqual(self.store.load_prefs(), prefs)
        self.assertTrue(self.store.prefs_path.name == "settings.json")

    def test_instances_roundtrip(self):
        self.store.save_instances("a", [{"id": "a", "name": "Device 1"}])
        self.assertEqual(self.store.load_instances(), {"current": "a", "instances": [{"id": "a", "name": "Device 1"}]})

    def test_corrupt_file_is_set_aside(self):
        self.store.directory.mkdir(parents=True)
        self.store.prefs_path.write_text("{ not json", encoding="utf-8")
        self.assertEqual(self.store.load_prefs(), AppPrefs())
        self.assertTrue(self.store.prefs_path.with_suffix(".json.bak").exists())

    def test_non_dict_json(self):
        self.store.directory.mkdir(parents=True)
        self.store.config_path.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(self.store.load_instances()["instances"], [])

    def test_atomic_write_leaves_no_tmp(self):
        self.store.save_prefs(AppPrefs())
        self.assertEqual([p.name for p in self.store.directory.iterdir()], ["settings.json"])

    def test_export_import(self):
        out = Path(self._tmp.name) / "export.json"
        prefs = AppPrefs(ui_mode="pro")
        self.store.export_config(out, prefs, {"current": "x", "instances": [{"id": "x"}]})
        got_prefs, got_inst = self.store.import_config(out)
        self.assertEqual(got_prefs.ui_mode, "pro")
        self.assertEqual(got_inst, {"current": "x", "instances": [{"id": "x"}]})

    def test_import_rejects_foreign_file(self):
        bad = Path(self._tmp.name) / "bad.json"
        bad.write_text(json.dumps({"hello": 1}), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.import_config(bad)
        with self.assertRaises(ValueError):
            self.store.import_config(Path(self._tmp.name) / "missing.json")


class PresetTests(unittest.TestCase):
    def test_default_presets(self):
        self.assertEqual([p.label for p in PRESETS], ["Stream Ultra", "Record 4K", "LowLat"])
        self.assertEqual([p.subtitle for p in PRESETS], ["1080p · 60 FPS", "4K · 30 FPS", "720p · 120 FPS"])
        self.assertEqual([p.color for p in PRESETS], ["blue", "violet", "green"])

    def test_preset_values_match_roadmap(self):
        stream, rec, low = PRESETS
        self.assertEqual(stream.values, {"bitrate": 16, "max_size": 1920, "max_fps": 60, "codec": "h264", "abuf": 50})
        self.assertEqual(rec.values["record"], "auto_4k.mp4")
        self.assertEqual((low.values["max_fps"], low.values["abuf"]), (120, 10))

    def test_matches(self):
        s = Settings().merged(PRESETS[0].values)
        self.assertTrue(preset_matches(s, PRESETS[0]))
        self.assertFalse(preset_matches(s.merged({"bitrate": 20}), PRESETS[0]))
        self.assertFalse(preset_matches(Settings(), PRESETS[0]))

    def test_custom_roundtrip(self):
        s = Settings().merged({"bitrate": 24, "max_fps": 90})
        data = custom_from_settings("Mon preset", s, 3)
        presets = all_presets([data, {"broken": True}])
        self.assertEqual(len(presets), 4)
        self.assertEqual(presets[-1].label, "Mon preset")
        self.assertFalse(presets[-1].builtin)
        self.assertTrue(preset_matches(s, presets[-1]))

    def test_resolution_label(self):
        self.assertEqual(resolution_label(1920), "1080p (FHD)")
        self.assertEqual(resolution_label(1234), "Personnalisée")


if __name__ == "__main__":
    unittest.main()
