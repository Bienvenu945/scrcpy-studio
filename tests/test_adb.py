"""Tests de core/adb.py avec un runner factice."""
import unittest

from core.adb import (
    AdbClient, parse_battery, parse_devices, parse_ip, parse_props, parse_refresh_rate, parse_wm_size, split_sections,
)
from core.process import AsyncResult

DEVICES = """List of devices attached
R5CW61A7Z8R            device usb:1-2 product:dm3qxxx model:SM_S918B device:dm3q transport_id:1
192.168.1.20:5555      device product:x model:Pixel_7 device:panther transport_id:2
emulator-5554          offline

"""

DUMP = """[ro.product.manufacturer]: [samsung]
[ro.product.model]: [SM-S918B]
[ro.product.marketname]: [Galaxy S23 Ultra]
[ro.build.version.release]: [14]
[ro.build.version.sdk]: [34]
===WM
Physical size: 1440x3080
===BAT
Current Battery Service state:
  AC powered: false
  USB powered: true
  status: 2
  level: 88
===DISP
  mActiveModeId=2
    DisplayModeRecord{mMode={id=1, width=1440, height=3080, fps=60.0, alternativeRefreshRates=[]}}
    DisplayModeRecord{mMode={id=2, width=1440, height=3080, fps=120.00001, alternativeRefreshRates=[]}}
"""


class FakeRunner:
    def __init__(self, outputs):
        self.outputs, self.calls = outputs, []

    def __call__(self, cmd, timeout=0, binary=False):
        self.calls.append(cmd)
        for key, result in self.outputs.items():
            if key in " ".join(cmd):
                return result
        return AsyncResult(returncode=1, error="no match")


class ParserTests(unittest.TestCase):
    def test_devices(self):
        d = parse_devices(DEVICES)
        self.assertEqual([x.serial for x in d], ["R5CW61A7Z8R", "192.168.1.20:5555", "emulator-5554"])
        self.assertEqual((d[0].transport, d[0].model, d[0].state), ("usb", "SM S918B", "device"))
        self.assertEqual(d[1].transport, "tcpip")
        self.assertFalse(d[2].online)

    def test_daemon_noise_ignored(self):
        self.assertEqual(parse_devices("* daemon not running; starting now\n* daemon started successfully\nList of devices attached\n"), [])

    def test_props_and_sections(self):
        sec = split_sections(DUMP)
        self.assertEqual(parse_props(sec["props"])["ro.product.model"], "SM-S918B")
        self.assertEqual(parse_wm_size(sec["wm"]), "1440x3080")
        self.assertEqual(parse_battery(sec["bat"]), (88, True))
        self.assertEqual(parse_refresh_rate(sec["disp"]), 120)

    def test_refresh_fallbacks(self):
        self.assertEqual(parse_refresh_rate("mRefreshRate=90.0"), 90)
        self.assertIsNone(parse_refresh_rate("nothing"))
        self.assertEqual(parse_refresh_rate("{id=1, width=1, height=2, fps=60.0} {id=2, width=1, height=2, fps=90.0}"), 90)

    def test_battery_edge(self):
        self.assertEqual(parse_battery("garbage"), (None, False))
        self.assertEqual(parse_battery("  level: 5\n  AC powered: false\n  USB powered: false\n"), (5, False))

    def test_ip(self):
        self.assertEqual(parse_ip("    inet 192.168.1.23/24 brd 192.168.1.255 scope global wlan0"), "192.168.1.23")
        self.assertEqual(parse_ip("192.168.1.0/24 dev wlan0 proto kernel scope link src 192.168.1.23"), "192.168.1.23")
        self.assertIsNone(parse_ip(""))

    def test_wm_size_override(self):
        self.assertEqual(parse_wm_size("Physical size: 1080x2400\nOverride size: 720x1600"), "1080x2400")


class ClientTests(unittest.TestCase):
    def client(self, outputs):
        runner = FakeRunner(outputs)
        return AdbClient("adb", runner), runner

    def test_devices_and_command_line(self):
        c, r = self.client({"devices": AsyncResult(0, DEVICES)})
        self.assertEqual(len(c.devices()), 3)
        self.assertEqual(r.calls[0], ["adb", "devices", "-l"])

    def test_devices_error(self):
        c, _ = self.client({})
        self.assertEqual(c.devices(), [])
        self.assertTrue(c.last_error)

    def test_details(self):
        c, r = self.client({"getprop": AsyncResult(0, DUMP)})
        d = c.details("R5CW61A7Z8R")
        self.assertEqual(r.calls[0][:4], ["adb", "-s", "R5CW61A7Z8R", "shell"])
        self.assertEqual((d.name, d.model, d.android, d.sdk), ("Samsung Galaxy S23 Ultra", "SM-S918B", "14", "34"))
        self.assertEqual((d.battery, d.charging, d.display), (88, True, "1440x3080 @ 120Hz"))
        self.assertEqual(d.short_name, "S23 Ultra")

    def test_details_offline(self):
        c, _ = self.client({})
        self.assertFalse(c.details("X").online)

    def test_connect_messages(self):
        c, _ = self.client({"connect": AsyncResult(0, "connected to 192.168.1.20:5555\n")})
        self.assertEqual(c.connect("192.168.1.20:5555")[0], True)
        c, _ = self.client({"connect": AsyncResult(0, "failed to connect to '1.2.3.4:5555'\n")})
        self.assertEqual(c.connect("1.2.3.4:5555")[0], False)
        c, _ = self.client({"connect": AsyncResult(0, "cannot connect to 1.2.3.4:5555\n")})
        self.assertEqual(c.connect("1.2.3.4:5555")[0], False)

    def test_screencap_validates_png(self):
        c, _ = self.client({"screencap": AsyncResult(0, data=b"\x89PNG\r\n....")})
        self.assertTrue(c.screencap("S").startswith(b"\x89PNG"))
        c, _ = self.client({"screencap": AsyncResult(0, data=b"not a png")})
        self.assertIsNone(c.screencap("S"))

    def test_latency_and_battery(self):
        c, _ = self.client({"echo": AsyncResult(0, "1\n", duration=0.0123), "dumpsys battery": AsyncResult(0, "  level: 42\n")})
        self.assertEqual(c.latency_ms("S"), 12.3)
        self.assertEqual(c.battery("S"), (42, False))

    def test_device_ip_fallback(self):
        c, _ = self.client({"addr show": AsyncResult(1, error="x"), "ip route": AsyncResult(0, "10.0.0.0/24 src 10.0.0.9")})
        self.assertEqual(c.device_ip("S"), "10.0.0.9")

    def test_version(self):
        c, _ = self.client({"version": AsyncResult(0, "Android Debug Bridge version 1.0.41\n")})
        self.assertEqual(c.version(), "adb version 1.0.41")
        self.assertTrue(c.available())
        c, _ = self.client({})
        self.assertFalse(c.available())


if __name__ == "__main__":
    unittest.main()
