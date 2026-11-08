"""Tests de core/models.py."""
import unittest

from core.models import CHOICES, OPTIONS, AppPrefs, Device, Settings, coerce


class CoerceTests(unittest.TestCase):
    def test_bool_from_strings(self):
        self.assertTrue(coerce("audio", "oui"))
        self.assertFalse(coerce("audio", "false"))
        self.assertFalse(coerce("audio", 0))

    def test_int_clamped_and_parsed(self):
        self.assertEqual(coerce("max_fps", "999"), 240)
        self.assertEqual(coerce("bitrate", "0"), 1)
        self.assertEqual(coerce("max_size", "1 080".replace(" ", "")), 1080)
        self.assertEqual(coerce("max_size", "abc"), 0)

    def test_float_with_comma(self):
        self.assertEqual(coerce("angle", "12,5"), 12.5)
        self.assertEqual(coerce("camera_zoom", 99), 10.0)

    def test_choice_rejects_unknown(self):
        self.assertEqual(coerce("codec", "h265"), "h265")
        self.assertEqual(coerce("codec", "mp3"), "h264")
        self.assertEqual(coerce("min_size_alignment", "4"), 4)
        self.assertEqual(coerce("min_size_alignment", "3"), 3)  # int : seule la plage est vérifiée

    def test_text_is_stripped(self):
        self.assertEqual(coerce("title", "  hello "), "hello")
        self.assertEqual(coerce("title", None), "")

    def test_unknown_field(self):
        with self.assertRaises(KeyError):
            coerce("nope", 1)


class SettingsTests(unittest.TestCase):
    def test_field_count(self):
        self.assertGreaterEqual(len(Settings.field_names()), 100)

    def test_defaults_match_scrcpy(self):
        s = Settings()
        self.assertEqual((s.bitrate, s.abuf, s.audio_bitrate, s.audio_output_buffer), (8, 50, 128, 10))
        self.assertEqual((s.codec, s.acodec, s.asource, s.verbosity), ("h264", "opus", "output", "info"))
        self.assertEqual(s.diff(), {})

    def test_roundtrip_and_unknown_keys(self):
        s = Settings.from_dict({"bitrate": 16, "title": "x", "bogus": 1, "codec": "zzz"})
        self.assertEqual(s.diff(), {"bitrate": 16, "title": "x"})
        self.assertEqual(Settings.from_dict(s.to_dict()), s)

    def test_merged_is_a_copy(self):
        base = Settings()
        merged = base.merged({"max_fps": 60})
        self.assertEqual(base.max_fps, 0)
        self.assertEqual(merged.max_fps, 60)

    def test_every_choice_field_has_valid_default(self):
        defaults = Settings().to_dict()
        for name, values in CHOICES.items():
            if name in defaults:
                self.assertIn(str(defaults[name]), values, name)

    def test_options_pairs(self):
        for name, pairs in OPTIONS.items():
            self.assertTrue(all(len(p) == 2 for p in pairs), name)


class AppPrefsTests(unittest.TestCase):
    def test_defaults_neon(self):
        p = AppPrefs()
        self.assertEqual((p.palette, p.ui_mode, p.glass, p.animated), ("neon", "base", True, False))

    def test_from_dict_filters(self):
        p = AppPrefs.from_dict({"ui_mode": "pro", "macros_list": [{"a": 1}, 3], "bogus": 1, "ui_mode_x": 2})
        self.assertEqual(p.ui_mode, "pro")
        self.assertEqual(p.macros_list, [{"a": 1}])
        self.assertEqual(AppPrefs.from_dict({"ui_mode": "zzz"}).ui_mode, "base")

    def test_lists_not_shared(self):
        a, b = AppPrefs(), AppPrefs()
        a.macros_list.append({"x": 1})
        self.assertEqual(b.macros_list, [])


class DeviceTests(unittest.TestCase):
    def test_short_name(self):
        d = Device("R5", name="Samsung Galaxy S23 Ultra", manufacturer="Samsung", model="SM-S918B")
        self.assertEqual(d.short_name, "S23 Ultra")
        self.assertEqual(Device("X").short_name, "X")
        self.assertEqual(Device("1.2.3.4:5555", transport="tcpip").link, "Wi-Fi")


if __name__ == "__main__":
    unittest.main()
