"""Tests d'intégration de l'interface.

Avec PySide6 installé : exécution réelle (plateforme « offscreen »). Sans PySide6 : faux Qt
(tests/qt_stub.py) — vérifie imports, construction et couverture, pas le rendu.
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

REAL_QT = importlib.util.find_spec("PySide6") is not None
if REAL_QT:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
else:
    from tests import qt_stub

    qt_stub.install()

from config.settings_store import SettingsStore  # noqa: E402
from core import scrcpy_help  # noqa: E402
from core.adb import AdbClient  # noqa: E402
from core.instances import InstanceManager  # noqa: E402
from core.models import OPTIONS, PREFS_DEFAULTS, AppPrefs, Settings  # noqa: E402
from core.process import AsyncResult, Dispatcher  # noqa: E402
from ui.context import Context  # noqa: E402
from ui.views import VIEWS, load_view_class  # noqa: E402

_APP = None


def setUpModule():  # noqa: N802
    global _APP
    if REAL_QT:
        from PySide6.QtWidgets import QApplication
        _APP = QApplication.instance() or QApplication([])


def make_context(tmp: str) -> Context:
    store = SettingsStore(Path(tmp) / "cfg")
    prefs = AppPrefs()
    manager = InstanceManager(store, prefs)
    manager.load()
    adb = AdbClient("adb", lambda cmd, timeout=0, binary=False: AsyncResult(1, error="adb absent"))
    return Context(prefs, manager, adb, store, Dispatcher())


class CoverageTests(unittest.TestCase):
    """Chaque réglage et chaque option scrcpy doit être joignable depuis l'interface."""

    @classmethod
    def setUpClass(cls):
        cls.classes = [load_view_class(v) for v in VIEWS]

    def test_every_setting_has_a_row(self):
        covered = set().union(*(c.covered_fields() for c in self.classes))
        missing = set(Settings.field_names()) - covered - {"active_preset"}
        self.assertEqual(sorted(missing), [])

    def test_every_scrcpy_option_is_exposed(self):
        covered = set().union(*(c.covered_options() for c in self.classes))
        self.assertEqual(sorted(set(scrcpy_help.list_all()) - covered), [], "options absentes de l'interface")

    def test_all_prefs_are_editable_or_internal(self):
        covered = {row.field for c in self.classes for row in c.row_specs() if row.target == "prefs"}
        internal = {"ui_mode", "macros_list", "custom_presets", "sidebar_visible", "info_visible"}
        self.assertEqual(sorted(set(PREFS_DEFAULTS) - covered - internal), [])

    def test_rows_are_well_formed(self):
        settings_fields = set(Settings.field_names())
        kinds = {"toggle", "choice", "radio", "segment", "resolution", "slider", "number", "float", "text", "path", "textarea"}
        for cls in self.classes:
            for row in cls.row_specs():
                self.assertIn(row.kind, kinds, (cls.KEY, row.field))
                self.assertIn(row.field, settings_fields if row.target == "settings" else PREFS_DEFAULTS, (cls.KEY, row.field))
                if row.kind in ("choice", "radio", "segment") and isinstance(row.options, str):
                    self.assertIn(row.options, OPTIONS, (cls.KEY, row.field))
                if row.kind in ("slider", "number", "float"):
                    self.assertLess(row.min, row.max, (cls.KEY, row.field))
                for name in row.opt.split():
                    self.assertIsNotNone(scrcpy_help.get_entry(name), f"{cls.KEY}: option inconnue {name}")

    def test_choice_values_match_model(self):
        # chaque valeur proposée doit être acceptée par la validation du modèle
        from core.models import CHOICES
        for cls in self.classes:
            for row in cls.row_specs():
                if row.kind in ("choice", "radio", "segment") and row.target == "settings":
                    allowed = CHOICES.get(row.field)
                    if allowed is None:
                        continue
                    for value, _label in (OPTIONS[row.options] if isinstance(row.options, str) else row.options):
                        self.assertIn(str(value), allowed, (cls.KEY, row.field, value))

    def test_view_keys_match_registry(self):
        for info, cls in zip(VIEWS, self.classes):
            self.assertEqual(cls.KEY, info.key)
            self.assertTrue(cls.TITLE)


class ViewConstructionTests(unittest.TestCase):
    def test_every_view_builds_and_refreshes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            for info in VIEWS:
                view = load_view_class(info)(ctx)
                view.on_enter()
                view.refresh()

    def test_row_change_reaches_the_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            view = load_view_class(next(v for v in VIEWS if v.key == "video"))(ctx)
            row, _setting_row, control = next(r for r in view._rows if r[0].field == "max_fps")
            view._on_changed(row, 60)
            self.assertEqual(ctx.value("max_fps"), 60)
            self.assertEqual(ctx.command_text(), "scrcpy --max-fps=60")
            view._on_changed(next(r for r in view._rows if r[0].field == "codec")[0], "h265")
            self.assertEqual(ctx.value("codec"), "h265")

    def test_prefs_row_updates_prefs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            view = load_view_class(next(v for v in VIEWS if v.key == "settings"))(ctx)
            row = next(r for r in view._rows if r[0].field == "allow_parallel")[0]
            view._on_changed(row, False)
            self.assertFalse(ctx.prefs.allow_parallel)

    def test_conditional_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            view = load_view_class(next(v for v in VIEWS if v.key == "camera"))(ctx)
            ctx.set_value("video_source", "camera")
            self.assertTrue(any(r[0].enabled_if(ctx.settings()) for r in view._rows if r[0].enabled_if))
            ctx.set_value("video_source", "display")
            self.assertFalse(any(r[0].enabled_if(ctx.settings()) for r in view._rows if r[0].enabled_if))


class WindowTests(unittest.TestCase):
    def test_main_window_navigation(self):
        from ui.window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            window = MainWindow(ctx, _APP)
            for key in ("device", "video", "audio", "display", "control", "record", "advanced", "console", "settings", "about"):
                window.show_view(key, animate=False)
                self.assertEqual(window._current_key, key)
            window.show_view("camera", animate=False)  # bascule automatique en PRO
            self.assertEqual(ctx.mode, "pro")
            for info in VIEWS:
                window.show_view(info.key, animate=False)
            window.set_mode("base")
            self.assertEqual(ctx.mode, "base")
            self.assertIn(window._current_key, {"device", "video", "audio", "display", "control", "record", "advanced", "console", "about", "settings"})

    def test_palette_items(self):
        from ui.window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            window = MainWindow(make_context(tmp), _APP)
            items = window.palette_items()
            kinds = [i.kind for i in items]
            self.assertEqual(kinds.count("option"), len(scrcpy_help.list_all()))
            self.assertEqual(kinds.count("nav"), len(VIEWS))
            self.assertGreaterEqual(kinds.count("action"), 10)
            self.assertTrue(all(callable(i.payload) for i in items))

    def test_instances_and_profiles_from_ui_layer(self):
        from ui.window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            window = MainWindow(ctx, _APP)
            window.new_instance()
            self.assertEqual(len(ctx.manager.instances), 2)
            profile = ctx.inst.add_profile("Jeu")
            window._select_profile(profile.name)
            ctx.set_value("max_fps", 120)
            self.assertEqual(profile.delta, {"max_fps": 120})
            self.assertEqual(ctx.manager.instances[0].effective().max_fps, 0)

    def test_rebuild_ui_keeps_current_view(self):
        from ui.window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            window = MainWindow(ctx, _APP)
            window.show_view("audio", animate=False)
            ctx.prefs.palette = "ocean"
            window.rebuild_ui()
            self.assertEqual(window._current_key, "audio")

    def test_launch_without_scrcpy_reports_error(self):
        from ui.window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            ctx.prefs.scrcpy_path = "/nonexistent/scrcpy"
            if ctx.scrcpy_path() is None:
                window = MainWindow(ctx, _APP)
                window.launch()
                self.assertEqual(ctx.notifications[-1].level, "error")
                self.assertFalse(ctx.inst.running)


if __name__ == "__main__":
    unittest.main()
