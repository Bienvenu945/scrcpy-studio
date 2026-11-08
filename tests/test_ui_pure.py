"""Tests des modules d'interface sans Qt : thème, contexte, registre de vues, palette."""
import re
import tempfile
import unittest
from pathlib import Path

from config.settings_store import SettingsStore
from core.adb import AdbClient
from core.instances import InstanceManager
from core.models import AppPrefs
from core.process import AsyncResult, Dispatcher
from ui import theme
from ui.context import Context, PaletteItem, rank_items
from ui.views import VIEWS, info_for, sidebar_sections, views_for_mode

DUMP = "[ro.product.model]: [Pixel 7]\n[ro.product.manufacturer]: [google]\n===BAT\n  level: 50\n"


def fake_runner(devices_out):
    def run(cmd, timeout=0, binary=False):
        joined = " ".join(cmd)
        if "devices" in joined:
            return AsyncResult(0, devices_out)
        if "version" in joined:
            return AsyncResult(0, "Android Debug Bridge version 1.0.41\n")
        if "getprop" in joined:
            return AsyncResult(0, DUMP)
        return AsyncResult(1, error="?")
    return run


class ThemeTests(unittest.TestCase):
    def test_all_palettes_build_valid_qss(self):
        for key, palette in theme.PALETTES.items():
            qss = theme.build_qss(palette)
            self.assertEqual(re.findall(r"@[A-Z_0-9]+@", qss), [], key)
            self.assertEqual(qss.count("{"), qss.count("}"), key)
            self.assertNotIn("letter-spacing", qss)

    def test_neon_matches_roadmap(self):
        p = theme.PALETTES["neon"]
        self.assertEqual((p.bg, p.bg_secondary, p.bg_card, p.bg_card_alt), ("#0A0E1A", "#0F1420", "#141B2D", "#1A2338"))
        self.assertEqual((p.border, p.border_active, p.accent_a, p.accent_b), ("#1F2A44", "#3B82F6", "#3B82F6", "#8B5CF6"))
        self.assertEqual((p.success, p.warning, p.error), ("#10B981", "#F59E0B", "#EF4444"))
        self.assertEqual((p.text, p.text_dim, p.text_muted), ("#F8FAFC", "#94A3B8", "#64748B"))
        self.assertEqual((p.radius_card, p.radius_btn, p.glass), (12, 8, True))

    def test_glass_alpha_85(self):
        self.assertIn("rgba(20, 27, 45, 217)", theme.build_qss(theme.PALETTES["neon"], True))
        self.assertIn("rgba(20, 27, 45, 255)", theme.build_qss(theme.PALETTES["neon"], False))

    def test_aurora_is_the_animated_one(self):
        self.assertEqual([k for k, p in theme.PALETTES.items() if p.animated], ["aurora"])

    def test_helpers(self):
        self.assertEqual(theme.hex_to_rgb("#abc"), (170, 187, 204))
        self.assertEqual(theme.pick_font(["Inter", "Segoe UI"], ["segoe ui", "Arial"]), "segoe ui")
        self.assertEqual(theme.pick_font(["Inter"], []), "sans-serif")
        self.assertEqual(theme.get_palette("zzz").key, "neon")

    def test_themes_json_matches_palettes(self):
        import json
        from dataclasses import asdict
        path = Path(__file__).resolve().parent.parent / "resources" / "themes.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {k: asdict(p) for k, p in theme.PALETTES.items()})

    def test_current_palette(self):
        theme.set_current(theme.PALETTES["ocean"])
        self.assertEqual(theme.current().key, "ocean")
        theme.set_current(theme.PALETTES["neon"])


class PackagingAssetsTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parent.parent

    def test_icons_exist(self):
        for name in ("scrcpy-studio.png", "scrcpy-studio.ico", "scrcpy-studio.svg", "scrcpy-studio-48.png", "scrcpy-studio-128.png"):
            self.assertTrue((self.ROOT / "resources" / "icons" / name).is_file(), name)
        self.assertTrue((self.ROOT / "resources" / "icons" / "scrcpy-studio.png").read_bytes().startswith(b"\x89PNG"))
        self.assertTrue((self.ROOT / "resources" / "icons" / "scrcpy-studio.ico").read_bytes().startswith(b"\x00\x00\x01\x00"))

    def test_version_is_consistent(self):
        import re
        from config.defaults import APP_VERSION
        pyproject = (self.ROOT / "pyproject.toml").read_text(encoding="utf-8")
        declared = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
        self.assertTrue(declared.startswith(APP_VERSION), (declared, APP_VERSION))


class RegistryTests(unittest.TestCase):
    def test_modes(self):
        base = [v.key for v in views_for_mode("base")]
        pro = [v.key for v in views_for_mode("pro")]
        self.assertEqual(base, ["device", "video", "audio", "display", "control", "record", "advanced", "console"])
        self.assertEqual(len([v for v in VIEWS if v.section == "base"]), 6)
        self.assertGreaterEqual(len([v for v in VIEWS if v.section == "pro"]), 11)
        self.assertTrue(set(base) < set(pro))
        self.assertNotIn("about", pro)

    def test_sections(self):
        self.assertEqual([t for t, _ in sidebar_sections("base")], ["BASE", "OUTILS"])
        self.assertEqual([t for t, _ in sidebar_sections("pro")], ["BASE", "PRO", "OUTILS"])

    def test_keys_unique_and_modules_exist(self):
        keys = [v.key for v in VIEWS]
        self.assertEqual(len(keys), len(set(keys)))
        folder = Path(__file__).resolve().parent.parent / "ui" / "views"
        for v in VIEWS:
            self.assertTrue((folder / f"{v.module}.py").exists(), v.module)
        self.assertEqual(info_for("camera").label, "Caméra")
        self.assertIsNone(info_for("nope"))


class ContextTests(unittest.TestCase):
    def make(self, devices_out="", **prefs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = SettingsStore(Path(tmp.name))
        p = AppPrefs(**prefs)
        d = Dispatcher()
        manager = InstanceManager(store, p)
        manager.load()
        ctx = Context(p, manager, AdbClient("adb", fake_runner(devices_out)), store, d)
        events = []
        ctx.subscribe(lambda ev, payload: events.append(ev))
        return ctx, d, events, store

    def test_set_value_emits_and_clears_preset(self):
        ctx, _, events, _ = self.make()
        ctx.inst.set_value("active_preset", "stream_ultra")
        ctx.set_value("max_fps", 60)
        self.assertEqual(ctx.value("max_fps"), 60)
        self.assertEqual(ctx.value("active_preset"), "")
        self.assertIn("values", events)
        self.assertTrue(ctx.dirty)

    def test_apply_and_reset(self):
        ctx, _, _, _ = self.make()
        ctx.apply_values({"bitrate": 16, "max_fps": 60}, "stream_ultra")
        self.assertEqual((ctx.value("bitrate"), ctx.value("active_preset")), (16, "stream_ultra"))
        ctx.reset_fields(["bitrate"])
        self.assertEqual(ctx.value("bitrate"), 8)

    def test_commands(self):
        ctx, _, _, _ = self.make()
        ctx.set_value("max_fps", 60)
        ctx.set_value("bitrate", 16)
        self.assertEqual(ctx.command_text(), "scrcpy --video-bit-rate=16M --max-fps=60")
        self.assertEqual(len(ctx.command_lines()), 2)
        self.assertEqual(ctx.issues(), [])

    def test_prefs(self):
        ctx, _, events, store = self.make()
        self.assertEqual(ctx.set_pref("ui_mode", "pro"), "pro")
        self.assertEqual(ctx.set_pref("ui_mode", "bad"), "base")
        ctx.set_pref("macros_list", [{"name": "x"}])
        self.assertEqual(ctx.pref("macros_list"), [{"name": "x"}])
        self.assertIn("prefs", events)
        ctx.flush()
        self.assertEqual(store.load_prefs().macros_list, [{"name": "x"}])
        self.assertFalse(ctx.dirty)

    def test_refresh_devices_async_through_dispatcher(self):
        out = "List of devices attached\nSER1 device usb:1 model:Pixel_7\nSER2 offline\n"
        ctx, d, events, _ = self.make(out)
        self.assertTrue(ctx.refresh_devices())
        self.assertFalse(ctx.refresh_devices())  # déjà en cours
        for _ in range(200):
            if d.pending():
                break
            import time; time.sleep(0.01)
        d.drain()
        self.assertEqual([x.serial for x in ctx.devices], ["SER1", "SER2"])
        self.assertEqual(ctx.inst.device.serial, "SER1")
        self.assertEqual(ctx.adb_status(), ("success", "ADB Ready"))
        self.assertIn("devices", events)

    def test_status_variants(self):
        ctx, d, _, _ = self.make("List of devices attached\n")
        self.assertEqual(ctx.adb_status()[0], "warning")
        ctx.refresh_devices()
        import time
        for _ in range(200):
            if d.pending():
                break
            time.sleep(0.01)
        d.drain()
        self.assertEqual(ctx.adb_status(), ("warning", "Aucun appareil"))

    def test_second_instance_gets_free_device(self):
        out = "List of devices attached\nA device usb:1\nB device usb:2\n"
        ctx, d, _, _ = self.make(out)
        ctx.manager.create()
        ctx.refresh_devices()
        import time
        for _ in range(200):
            if d.pending():
                break
            time.sleep(0.01)
        d.drain()
        self.assertEqual([i.device.serial for i in ctx.manager.instances], ["A", "B"])

    def test_notify(self):
        ctx, _, events, _ = self.make()
        ctx.notify("error", "boom")
        self.assertEqual(ctx.notifications[-1].text, "boom")
        self.assertIn("notify", events)


class PaletteRankingTests(unittest.TestCase):
    ITEMS = [
        PaletteItem("action", "Lancer scrcpy", "Ctrl+Entrée"),
        PaletteItem("action", "Arrêter scrcpy"),
        PaletteItem("nav", "Aller à Vidéo", "bitrate fps codec", keywords="résolution"),
        PaletteItem("nav", "Aller à Caméra"),
        PaletteItem("option", "--video-bit-rate", "Encode the video at the given bit rate"),
        PaletteItem("option", "--camera-id", "Specify the device camera id to mirror."),
    ]

    def test_empty_query_hides_options(self):
        self.assertEqual([i.kind for i in rank_items(self.ITEMS, "")], ["action", "action", "nav", "nav"])

    def test_fuzzy_title(self):
        self.assertEqual(rank_items(self.ITEMS, "lanc")[0].title, "Lancer scrcpy")
        self.assertEqual(rank_items(self.ITEMS, "cam")[0].title, "Aller à Caméra")

    def test_keywords_and_subtitle(self):
        self.assertEqual(rank_items(self.ITEMS, "résolution")[0].title, "Aller à Vidéo")
        self.assertEqual(rank_items(self.ITEMS, "mirror")[0].title, "--camera-id")

    def test_dash_query_matches_titles_only(self):
        titles = [i.title for i in rank_items(self.ITEMS, "--cam")]
        self.assertEqual(titles, ["--camera-id"])

    def test_no_match(self):
        self.assertEqual(rank_items(self.ITEMS, "zzzzqq"), [])


if __name__ == "__main__":
    unittest.main()
