"""Tests de core/metrics.py, core/macros.py et core/scrcpy_help.py."""
import tempfile
import unittest
from pathlib import Path

from config.defaults import HELP_FILE
from core import scrcpy_help as help_
from core.adb import AdbClient
from core.macros import Macro, MacroPlayer, Step, call_in_ui, example_macro
from core.metrics import LiveMetrics, parse_fps, parse_latency
from core.process import AsyncResult, Dispatcher


class MetricsTests(unittest.TestCase):
    def test_parsers(self):
        self.assertEqual(parse_fps("INFO: 60 fps"), 60.0)
        self.assertEqual(parse_fps("INFO: 59.4 fps (not accurate)"), 59.4)
        self.assertIsNone(parse_fps("INFO: Texture: 1080x2400"))
        self.assertEqual(parse_latency("DEBUG: latency: 12.5 ms"), 12.5)
        self.assertIsNone(parse_latency("nothing"))

    def test_feed_line(self):
        m = LiveMetrics()
        self.assertFalse(m.feed_line("INFO: hello"))
        self.assertTrue(m.feed_line("INFO: 58 fps"))
        self.assertEqual(m.snapshot().fps, 58.0)
        m.clear_runtime()
        self.assertIsNone(m.snapshot().fps)

    def test_scrcpy_latency_takes_precedence(self):
        now = [100.0]
        m = LiveMetrics(clock=lambda: now[0])
        m.feed_line("latency 8 ms")
        m.set_adb_latency(40.0)
        self.assertEqual(m.snapshot().latency_ms, 8.0)
        now[0] += 10
        m.set_adb_latency(40.0)
        self.assertEqual(m.snapshot().latency_ms, 40.0)

    def test_tick_schedules_and_throttles(self):
        calls = []

        def runner(cmd, timeout=0, binary=False):
            calls.append(cmd[-2:])
            return AsyncResult(0, "  level: 77\n", duration=0.02)

        now = [0.0]
        d = Dispatcher()
        m = LiveMetrics(clock=lambda: now[0])
        adb = AdbClient("adb", runner)
        updates = []
        self.assertTrue(m.tick(adb, "S", updates.append, d))
        self.assertFalse(m.tick(adb, "S", updates.append, d))  # déjà en cours
        for _ in range(50):
            if d.pending():
                break
            import time; time.sleep(0.02)
        d.drain()
        snap = m.snapshot()
        self.assertEqual((snap.battery, snap.latency_ms), (77, 20.0))
        self.assertEqual(len(updates), 1)
        self.assertFalse(m.tick(adb, "S", updates.append, d))  # trop tôt
        now[0] += 2.5
        self.assertEqual(m.due(), (True, False))  # latence seulement, batterie à 5 s
        self.assertFalse(m.tick(adb, "", updates.append, d))  # pas d'appareil


class HelpTests(unittest.TestCase):
    def test_counts_on_real_file(self):
        self.assertEqual(len(help_.list_long_options()), 108)
        self.assertEqual(len(help_.list_all()), 111)  # + -G, -K, -M
        self.assertGreater(len(help_.load_shortcuts()), 30)

    def test_descriptions(self):
        self.assertTrue(help_.get_description("--max-fps").startswith("Limit the frame rate"))
        self.assertEqual(help_.get_description("-b"), help_.get_description("--video-bit-rate"))
        self.assertEqual(help_.get_description("--max-size=1080"), help_.get_description("-m"))
        self.assertEqual(help_.get_description("--nope"), "")
        self.assertIn("uhid", help_.get_description("-K"))

    def test_multiline_description_joined(self):
        self.assertIn("Possible values are", help_.get_description("--display-ime-policy"))

    def test_search(self):
        self.assertIn("--video-bit-rate", help_.search("bitrate")[:3])
        self.assertEqual(help_.search("--camera")[0].startswith("--camera"), True)
        self.assertIn("--new-display", help_.search("virtual display", 10) + help_.search("new-display", 10))
        self.assertEqual(help_.search("zzzzqqqq"), [])
        self.assertEqual(len(help_.search("", 5)), 5)

    def test_fuzzy(self):
        self.assertIsNone(help_.fuzzy_score("xyz", "abc"))
        self.assertGreater(help_.fuzzy_score("cam", "camera"), help_.fuzzy_score("cmr", "camera"))
        self.assertGreater(help_.fuzzy_score("vid", "video"), help_.fuzzy_score("vid", "a video"))
        self.assertEqual(help_.fuzzy_score("", "x"), 0)

    def test_help_file_untouched(self):
        # le fichier du projet doit rester identique à l'aide scrcpy 4.1 fournie
        text = HELP_FILE.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("scrcpy 4.1"))
        self.assertEqual(HELP_FILE.read_bytes(), (HELP_FILE.parent / "docs" / "scrcpy_aide.txt").read_bytes())

    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(help_.load_help(Path(d) / "absent.txt"), {})


class MacroTests(unittest.TestCase):
    def player(self, runner, tmp, launched):
        adb = AdbClient("adb", runner)
        return MacroPlayer(lambda: launched.append("launch"), lambda: launched.append("stop"), adb,
                           lambda: "SER", Path(tmp), sleep=lambda s: None)

    def test_example_runs(self):
        seen = []

        def runner(cmd, timeout=0, binary=False):
            seen.append(cmd)
            return AsyncResult(0, data=b"\x89PNG....") if binary else AsyncResult(0, "ok")

        with tempfile.TemporaryDirectory() as tmp:
            launched = []
            result = self.player(runner, tmp, launched).run(example_macro())
            self.assertTrue(result.ok, result.error)
            self.assertEqual(launched, ["launch", "stop"])
            self.assertEqual(len(result.captures), 1)
            self.assertTrue(result.captures[0].read_bytes().startswith(b"\x89PNG"))
            self.assertTrue(any("am start -n com.example.app" in " ".join(c) for c in seen))
            self.assertEqual(result.log[-1], "✓ terminée")

    def test_stops_at_first_error(self):
        runner = lambda cmd, timeout=0, binary=False: AsyncResult(1, stderr="device offline")  # noqa: E731
        with tempfile.TemporaryDirectory() as tmp:
            launched = []
            macro = Macro("m", [Step("adb", "ls"), Step("launch")])
            result = self.player(runner, tmp, launched).run(macro)
            self.assertFalse(result.ok)
            self.assertIn("Étape 1", result.error)
            self.assertEqual(launched, [])

    def test_invalid_steps(self):
        runner = lambda cmd, timeout=0, binary=False: AsyncResult(0)  # noqa: E731
        with tempfile.TemporaryDirectory() as tmp:
            p = self.player(runner, tmp, [])
            self.assertFalse(p.run(Macro("a", [Step("wait", "abc")])).ok)
            self.assertFalse(p.run(Macro("b", [Step("adb", "  ")])).ok)
            self.assertFalse(p.run(Macro("c", [Step("screenshot")])).ok)  # screencap sans PNG

    def test_cancel(self):
        runner = lambda cmd, timeout=0, binary=False: AsyncResult(0)  # noqa: E731
        with tempfile.TemporaryDirectory() as tmp:
            launched = []
            p = self.player(runner, tmp, launched)
            p._sleep = lambda s: p.cancel()
            result = p.run(Macro("m", [Step("wait", "5"), Step("launch")]))
            self.assertFalse(result.ok)
            self.assertEqual(launched, [])

    def test_serialization(self):
        macro = example_macro()
        again = Macro.from_dict(macro.to_dict())
        self.assertEqual(again, macro)
        self.assertEqual(Macro.from_dict({"steps": [{"type": "zzz"}, 5]}).steps, [])
        self.assertIn("Attendre", Step("wait", "2").describe())

    def test_call_in_ui_runs_on_dispatcher_thread(self):
        import threading
        d = Dispatcher()
        out = []
        t = threading.Thread(target=lambda: out.append(call_in_ui(d, lambda: threading.current_thread().name)))
        t.start()
        for _ in range(100):
            if d.drain():
                break
            import time; time.sleep(0.01)
        t.join(2)
        self.assertEqual(out, [threading.current_thread().name])
        with self.assertRaises(ZeroDivisionError):
            t2 = threading.Thread(target=lambda: None)
            call_in_ui(None, lambda: 1 / 0)


if __name__ == "__main__":
    unittest.main()
