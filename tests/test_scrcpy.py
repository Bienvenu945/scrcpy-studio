"""Tests de core/scrcpy.py : build_args, validation, formatage, exécution."""
import os
import stat
import tempfile
import unittest
from pathlib import Path

from core import scrcpy_help
from core.models import Settings
from core.scrcpy import (
    LIST_ACTIONS, ScrcpyRunner, analyze_output, build_args, command_lines, device_args, effective_input_mode,
    find_executable, format_command, has_errors, list_args, prepare_test_args, split_extra, start_app_value, validate,
)


def S(**kw) -> Settings:
    return Settings().merged(kw)


class BuildArgsTests(unittest.TestCase):
    def test_defaults_emit_nothing(self):
        self.assertEqual(build_args(Settings()), [])

    def test_mockup_command(self):
        self.assertEqual(build_args(S(max_fps=60, bitrate=16)), ["--video-bit-rate=16M", "--max-fps=60"])

    def test_video_audio_values(self):
        a = build_args(S(max_size=1920, codec="h265", vbuf=30, audio_bitrate=192, abuf=80))
        self.assertIn("--max-size=1920", a)
        self.assertIn("--video-codec=h265", a)
        self.assertIn("--video-buffer=30", a)
        self.assertIn("--audio-bit-rate=192K", a)
        self.assertIn("--audio-buffer=80", a)

    def test_no_audio_hides_other_audio_options(self):
        a = build_args(S(audio=False, abuf=80, acodec="aac"))
        self.assertEqual(a, ["--no-audio"])

    def test_camera_options_only_with_camera_source(self):
        self.assertEqual(build_args(S(camera_id="0")), [])
        a = build_args(S(video_source="camera", camera_facing="back", camera_zoom=2.5, camera_torch=True))
        self.assertEqual(a, ["--video-source=camera", "--camera-facing=back", "--camera-torch", "--camera-zoom=2.5"])

    # ── corrections de la roadmap ──
    def test_orientation_sync_emits_both(self):
        a = build_args(S(orientation=True, display_orientation="90"))
        self.assertEqual(a, ["--display-orientation=90", "--record-orientation=90"])

    def test_orientation_sync_with_flip_only_display(self):
        a = build_args(S(orientation=True, display_orientation="flip90"))
        self.assertEqual(a, ["--display-orientation=flip90"])

    def test_orientation_separate(self):
        a = build_args(S(display_orientation="180", record_orientation="90"))
        self.assertEqual(a, ["--display-orientation=180", "--record-orientation=90"])

    def test_capture_orientation_lock(self):
        self.assertEqual(build_args(S(capture_orientation="90", orientation_locked=True)), ["--capture-orientation=@90"])
        self.assertEqual(build_args(S(orientation_locked=True)), ["--capture-orientation=@"])

    def test_start_app_prefixes(self):
        self.assertEqual(start_app_value(S(start_app="org.mozilla.firefox")), "org.mozilla.firefox")
        self.assertEqual(start_app_value(S(start_app="firefox", start_app_force_stop=True)), "+firefox")
        self.assertEqual(start_app_value(S(start_app="firefox", start_app_prefix_match=True)), "?firefox")
        self.assertEqual(start_app_value(S(start_app="firefox", start_app_force_stop=True, start_app_prefix_match=True)), "+?firefox")
        self.assertEqual(start_app_value(S(start_app="+?firefox")), "+?firefox")
        self.assertEqual(start_app_value(S(start_app="?firefox")), "?firefox")
        self.assertEqual(start_app_value(S(start_app="+?")), "")
        self.assertEqual(start_app_value(S()), "")

    def test_tcpip_variants(self):
        self.assertEqual(device_args(S(tcpip=True)), ["--tcpip"])
        self.assertEqual(device_args(S(tcpip_addr="192.168.1.5:5555")), ["--tcpip=192.168.1.5:5555"])
        self.assertEqual(device_args(S(tcpip_addr="192.168.1.5", tcpip_force_reconnect=True)), ["--tcpip=+192.168.1.5"])
        self.assertEqual(device_args(S(tcpip_force_reconnect=True)), [])

    def test_forced_hid_modes(self):
        a = build_args(S(force_uhid_keyboard=True, force_uhid_mouse=True, force_uhid_gamepad=True))
        self.assertEqual(a, ["--keyboard=uhid", "--mouse=uhid", "--gamepad=uhid"])
        b = build_args(S(otg=True, force_uhid_keyboard=True, force_uhid_mouse=True, force_uhid_gamepad=True))
        self.assertEqual(b, ["--keyboard=aoa", "--mouse=aoa", "--otg", "--gamepad=aoa"])

    def test_explicit_mode_wins_over_force(self):
        self.assertEqual(effective_input_mode(S(keyboard="aoa", force_uhid_keyboard=True), "keyboard"), "aoa")

    def test_no_window(self):
        self.assertEqual(build_args(S(no_window=True)), ["--no-window"])

    def test_pause_on_exit(self):
        self.assertEqual(build_args(S(pause_on_exit="true")), ["--pause-on-exit"])
        self.assertEqual(build_args(S(pause_on_exit="if-error")), ["--pause-on-exit=if-error"])
        self.assertEqual(build_args(S(pause_on_exit="false")), [])

    def test_new_display(self):
        self.assertEqual(build_args(S(newdisplay=True)), ["--new-display"])
        self.assertEqual(build_args(S(newdisplay=True, vd_res="1920x1080/420")), ["--new-display=1920x1080/420"])
        self.assertEqual(build_args(S(vd_res="1920x1080")), [])

    def test_window_position_auto_skipped(self):
        self.assertEqual(build_args(S(window_x="auto", window_y="40")), ["--window-y=40"])

    def test_v4l2_buffer_requires_sink(self):
        self.assertEqual(build_args(S(v4l2_buffer=100)), [])
        self.assertEqual(build_args(S(v4l2_sink="/dev/video2", v4l2_buffer=100)), ["--v4l2-sink=/dev/video2", "--v4l2-buffer=100"])

    def test_extra_is_last_and_shell_split(self):
        a = build_args(S(max_fps=30, extra='--window-title "Mon écran" -V debug'))
        self.assertEqual(a, ["--max-fps=30", "--window-title", "Mon écran", "-V", "debug"])
        self.assertEqual(split_extra("a 'b c'"), ["a", "b c"])
        self.assertEqual(split_extra("a 'b"), ["a", "'b"])

    def test_section_order(self):
        a = build_args(S(serial="X", record="o.mp4", max_fps=60, audio=False, fullscreen=True, readonly=True,
                         screenoff=True, crop="1:2:3:4", port_range="27183", verbosity="debug", extra="--zz"))
        keys = [x.split("=")[0] for x in a]
        expected = ["--serial", "--record", "--max-fps", "--no-audio", "--fullscreen", "--no-control",
                    "--turn-screen-off", "--crop", "--port", "--verbosity", "--zz"]
        self.assertEqual(keys, expected)

    def test_record_format_without_record(self):
        self.assertEqual(build_args(S(rformat="mkv")), ["--record-format=mkv"])

    def test_list_args(self):
        self.assertEqual(list_args(S(serial="AB"), "displays"), ["--serial=AB", "--list-displays"])
        with self.assertRaises(KeyError):
            list_args(S(), "nope")


def kitchen_sink() -> Settings:
    """Réglages où tout est activé / non défaut (audio actif, source caméra)."""
    values = {name: True for name, default in Settings().to_dict().items() if default is False}
    values.update(
        serial="ABC", conn="usb", tcpip_addr="10.0.0.2:5555", port_range="27183:27199", tunnel_host="127.0.0.1",
        tunnel_port=1234, video_source="camera", bitrate=16, max_size=1920, max_fps=60, codec="h265", vbuf=20,
        video_encoder="OMX.x", video_codec_options="i-frame-interval=2", min_size_alignment=4, audio=True,
        asource="playback", acodec="aac", abuf=80, audio_bitrate=192, audio_encoder="c2.x", audio_codec_options="a=1",
        audio_output_buffer=20, camera_id="0", camera_facing="back", camera_size="1920x1080", camera_fps=30,
        camera_ar="16:9", camera_zoom=2.0, title="t", window_x="10", window_y="20", vd_res="1920x1080/420",
        display_id=2, display_ime_policy="local", start_app="firefox", keyboard="uhid", mouse="aoa",
        gamepad="uhid", mouse_bind="bhsn:++++", screen_off_timeout=30, angle=15.0, capture_orientation="90",
        display_orientation="90", record_orientation="270", orientation=False, crop="100:100:0:0", record="o.mp4",
        rformat="mkv", push_target="/sdcard/X/", pause_on_exit="true", time_limit=10, window_width=800,
        window_height=600, render_driver="opengl", render_fit="stretched", background_color="#123456",
        v4l2_sink="/dev/video2", v4l2_buffer=50, verbosity="debug", shortcut_mod="lctrl", extra="",
    )
    return Settings().merged(values)


# Options qui ne sont pas des réglages de session : actions « liste », aide, version, alias.
NON_SESSION = {"--help", "--version", "--orientation", *LIST_ACTIONS.values()}


class OptionCoverageTests(unittest.TestCase):
    def test_all_scrcpy_options_reachable(self):
        emitted: set[str] = set()
        variants = [
            kitchen_sink(),
            S(audio=False, tcpip=True, pause_on_exit="if-error", orientation=True, display_orientation="90"),
        ]
        for variant in variants:
            emitted |= {a.split("=", 1)[0] for a in build_args(variant)}
        wanted = set(scrcpy_help.list_long_options()) - NON_SESSION
        self.assertEqual(sorted(wanted - emitted), [], "options non couvertes par build_args")

    def test_non_session_options_are_known(self):
        self.assertTrue(NON_SESSION <= set(scrcpy_help.list_long_options()))

    def test_short_only_options_documented(self):
        for opt in ("-G", "-K", "-M"):
            self.assertIsNotNone(scrcpy_help.get_entry(opt))

    def test_orientation_alias_expansion(self):
        self.assertEqual(
            build_args(S(orientation=True, record_orientation="180")),
            ["--display-orientation=180", "--record-orientation=180"],
        )


class ValidateTests(unittest.TestCase):
    def levels(self, **kw):
        return {(i.level, i.field) for i in validate(S(**kw), platform="linux")}

    def test_clean(self):
        self.assertEqual(validate(Settings(), platform="linux"), [])

    def test_usb_and_tcpip_conflict(self):
        self.assertIn(("error", "conn"), self.levels(select_usb=True, conn="tcpip"))

    def test_formats(self):
        self.assertIn(("error", "crop"), self.levels(crop="1:2"))
        self.assertIn(("error", "mouse_bind"), self.levels(mouse_bind="xx"))
        self.assertIn(("error", "background_color"), self.levels(background_color="red"))
        self.assertIn(("error", "camera_size"), self.levels(camera_size="big"))
        self.assertIn(("error", "port_range"), self.levels(port_range="a"))
        self.assertEqual(self.levels(crop="1:2:3:4", mouse_bind="bhsn:++++", background_color="#fff"), set())

    def test_warnings(self):
        self.assertIn(("warn", "adup"), self.levels(adup=True))
        self.assertIn(("warn", "video_source"), self.levels(camera_id="1"))
        self.assertIn(("warn", "tcpip_force_reconnect"), self.levels(tcpip_force_reconnect=True))

    def test_new_display_vs_display_id(self):
        self.assertIn(("error", "newdisplay"), self.levels(newdisplay=True, display_id=1))

    def test_v4l2_platform(self):
        self.assertTrue(any(i.field == "v4l2_sink" for i in validate(S(v4l2_sink="/dev/video0"), platform="win32")))
        self.assertFalse(any(i.field == "v4l2_sink" for i in validate(S(v4l2_sink="/dev/video0"), platform="linux")))

    def test_has_errors(self):
        self.assertTrue(has_errors(validate(S(crop="x"), platform="linux")))
        self.assertFalse(has_errors(validate(S(adup=True), platform="linux")))


class FormatTests(unittest.TestCase):
    def test_posix_quoting(self):
        self.assertEqual(format_command(["--window-title=Mon écran"], windows=False), "scrcpy '--window-title=Mon écran'")

    def test_windows_quoting(self):
        self.assertEqual(format_command(["--window-title=Mon écran"], windows=True), 'scrcpy "--window-title=Mon écran"')

    def test_lines(self):
        lines = command_lines(["--max-fps=60", "--video-bit-rate=16M", "--max-size=1080"], windows=False)
        self.assertEqual(lines, ["$ scrcpy --max-fps=60 \\", "  --video-bit-rate=16M \\", "  --max-size=1080"])
        self.assertEqual(command_lines([], windows=False), ["$ scrcpy"])
        self.assertEqual(command_lines(["-f"], windows=False), ["$ scrcpy -f"])


class RunnerTests(unittest.TestCase):
    def test_prepare_test_args(self):
        out = prepare_test_args(["--record=a.mp4", "--time-limit=99", "--pause-on-exit", "--max-fps=60"], 3)
        self.assertEqual(out, ["--max-fps=60", "--time-limit=3"])

    def test_analyze(self):
        ok = analyze_output(["INFO: scrcpy 4.1", "INFO: Device: x"], 0, 3.2)
        self.assertTrue(ok.ok)
        bad = analyze_output(["ERROR: Could not find any ADB device"], 1)
        self.assertFalse(bad.ok)
        self.assertIn("ADB device", bad.errors[0])
        self.assertIn("1 erreur", bad.summary)

    def test_bundled_scrcpy_is_found_before_path(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "scrcpy"
            folder.mkdir()
            (folder / "scrcpy.exe").write_text("")
            with mock.patch("core.scrcpy.bundled_dirs", return_value=[folder]):
                self.assertEqual(find_executable("scrcpy"), str(folder / "scrcpy.exe"))
            # le chemin configuré garde la priorité
            exe = Path(d) / "custom"
            exe.write_text("")
            with mock.patch("core.scrcpy.bundled_dirs", return_value=[folder]):
                self.assertEqual(find_executable("scrcpy", str(exe)), str(exe))

    def test_bundled_dirs_include_frozen_locations(self):
        from unittest import mock
        import core.scrcpy as mod
        with mock.patch.object(mod.sys, "_MEIPASS", "/tmp/meipass", create=True), \
                mock.patch.object(mod.sys, "frozen", True, create=True):
            dirs = [str(p) for p in mod.bundled_dirs()]
        self.assertIn(str(Path("/tmp/meipass") / "scrcpy"), dirs)
        self.assertTrue(any(d.endswith("vendor/scrcpy") or d.endswith("vendor\\scrcpy") for d in dirs))

    def test_find_executable(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / "scrcpy"
            exe.write_text("#!/bin/sh\n")
            self.assertEqual(find_executable("scrcpy", str(exe)), str(exe))
            self.assertEqual(find_executable("scrcpy", d), str(exe))
        self.assertIsNone(find_executable("definitely-not-a-binary-xyz", "/nonexistent"))

    @unittest.skipIf(os.name == "nt", "script shell requis")
    def test_runner_with_fake_scrcpy(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / "scrcpy"
            exe.write_text('#!/bin/sh\necho "INFO: args: $@"\necho "INFO: 60 fps"\nexit 0\n')
            exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
            runner = ScrcpyRunner(str(exe), cwd=Path(d) / "out")
            lines: list[str] = []
            codes: list[int] = []
            proc = runner.start(["--max-fps=60"], lines.append, codes.append)
            self.assertTrue(proc.wait(5))
            self.assertEqual(codes, [0])
            self.assertIn("INFO: args: --max-fps=60", lines)
            report = runner.run_test(["--max-fps=60", "--record=x.mp4"])
            self.assertTrue(report.ok, report.summary)
            self.assertIn("--time-limit=3", report.output)
            self.assertNotIn("--record", report.output)
            self.assertTrue((Path(d) / "out").is_dir())

    def test_missing_scrcpy(self):
        runner = ScrcpyRunner("/nonexistent/scrcpy-xyz")
        if runner.executable() is None:
            with self.assertRaises(FileNotFoundError):
                runner.start([])
            self.assertFalse(runner.run_test([]).ok)


if __name__ == "__main__":
    unittest.main()
