"""Tests de core/instances.py (instances, profils, lancement)."""
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path

from config.defaults import MAIN_PROFILE, MAX_INSTANCES
from config.settings_store import SettingsStore
from core.instances import Instance, InstanceManager
from core.models import AppPrefs, Device, Settings
from core.scrcpy import ScrcpyRunner


def wait_until(cond, timeout: float = 5.0) -> bool:
    """Attend qu'une condition devienne vraie (sondage court)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.inst = Instance("i1", "Device 1")

    def test_main_profile_edits_base(self):
        self.inst.set_value("max_fps", "60")
        self.assertEqual(self.inst.base.max_fps, 60)
        self.assertEqual(self.inst.effective().max_fps, 60)

    def test_profile_stores_delta_only(self):
        self.inst.set_value("bitrate", 16)
        p = self.inst.add_profile("Jeu", from_current=False)
        self.inst.select_profile(p.name)
        self.inst.set_value("max_fps", 120)
        self.assertEqual(p.delta, {"max_fps": 120})
        eff = self.inst.effective()
        self.assertEqual((eff.bitrate, eff.max_fps), (16, 120))
        self.assertEqual(self.inst.base.max_fps, 0)

    def test_setting_back_to_base_value_drops_delta(self):
        p = self.inst.add_profile("P", from_current=False)
        self.inst.select_profile(p.name)
        self.inst.set_value("max_fps", 60)
        self.inst.set_value("max_fps", 0)
        self.assertEqual(p.delta, {})

    def test_main_is_protected(self):
        self.assertFalse(self.inst.rename_profile(MAIN_PROFILE, "x"))
        self.assertFalse(self.inst.delete_profile(MAIN_PROFILE))
        self.assertEqual(self.inst.profile_names(), [MAIN_PROFILE])

    def test_unique_names_rename_duplicate_delete(self):
        a = self.inst.add_profile("Profil", from_current=False)
        b = self.inst.add_profile("Profil", from_current=False)
        self.assertNotEqual(a.name, b.name)
        self.assertFalse(self.inst.rename_profile(b.name, a.name))
        self.assertTrue(self.inst.rename_profile(b.name, "Autre"))
        self.assertFalse(self.inst.rename_profile("Autre", MAIN_PROFILE))
        dup = self.inst.duplicate_profile(a.name)
        self.assertIn("(copie)", dup.name)
        self.inst.select_profile(dup.name)
        self.assertTrue(self.inst.delete_profile(dup.name))
        self.assertEqual(self.inst.current_profile, MAIN_PROFILE)

    def test_add_profile_from_current_copies_difference(self):
        self.inst.set_value("bitrate", 16)
        p = self.inst.add_profile("X")
        self.assertEqual(p.delta, {})  # identique à la base
        self.inst.select_profile(p.name)
        self.inst.set_value("max_fps", 90)
        q = self.inst.add_profile("Y")
        self.assertEqual(q.delta, {"max_fps": 90})

    def test_serialization(self):
        self.inst.set_value("bitrate", 16)
        p = self.inst.add_profile("Jeu", from_current=False)
        self.inst.select_profile(p.name)
        self.inst.set_value("bitrate", 8)  # égal au défaut mais ≠ base : doit rester dans le delta
        clone = Instance.from_dict(self.inst.to_dict())
        self.assertEqual(clone.base.bitrate, 16)
        self.assertEqual(clone.profiles[0].delta, {"bitrate": 8})
        self.assertEqual(clone.current_profile, "Jeu")
        self.assertEqual(clone.effective().bitrate, 8)

    def test_from_dict_is_tolerant(self):
        inst = Instance.from_dict({"name": "Z", "base": {"bitrate": "x", "bogus": 1}, "profiles": [3, {"name": ""}],
                                   "current_profile": "inconnu"})
        self.assertEqual(inst.current_profile, MAIN_PROFILE)
        self.assertEqual(inst.profiles, [])
        self.assertTrue(inst.id)


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.events: list[tuple[str, str]] = []

    def manager(self, **prefs) -> InstanceManager:
        m = InstanceManager(SettingsStore(self.dir / "cfg"), AppPrefs(**prefs),
                            runner_factory=lambda: ScrcpyRunner(str(self.dir / "scrcpy"), cwd=self.dir / "out"))
        m.subscribe(lambda ev, inst: self.events.append((ev, inst.name if inst else "")))
        m.load()
        return m

    def fake_scrcpy(self, body: str):
        exe = self.dir / "scrcpy"
        exe.write_text("#!/bin/sh\n" + body + "\n")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

    def test_load_creates_default(self):
        m = self.manager()
        self.assertEqual([i.name for i in m.instances], ["Device 1"])
        self.assertEqual(m.current.name, "Device 1")

    def test_create_close_and_limit(self):
        m = self.manager()
        for _ in range(MAX_INSTANCES - 1):
            m.create()
        self.assertEqual(len(m.instances), MAX_INSTANCES)
        with self.assertRaises(ValueError):
            m.create()
        victim = m.current
        m.close(victim.id)
        self.assertNotIn(victim, m.instances)
        self.assertEqual(m.next_name(), victim.name)

    def test_closing_last_instance_recreates_one(self):
        m = self.manager()
        m.close(m.current.id)
        self.assertEqual(len(m.instances), 1)

    def test_persistence(self):
        m = self.manager()
        m.current.set_value("bitrate", 24)
        second = m.create()
        second.set_value("max_fps", 90)
        m.save()
        again = self.manager()
        self.assertEqual([i.base.bitrate for i in again.instances], [24, 8])
        self.assertEqual(again.current.id, second.id)

    def test_cycle(self):
        m = self.manager()
        a = m.current
        b = m.create()
        m.cycle(1)
        self.assertEqual(m.current_id, a.id)
        m.cycle(-1)
        self.assertEqual(m.current_id, b.id)

    @unittest.skipIf(os.name == "nt", "script shell requis")
    def test_launch_and_stop(self):
        self.fake_scrcpy('echo "args: $@"\nexec sleep 30')
        m = self.manager()
        inst = m.current
        inst.set_value("max_fps", 60)
        proc = m.launch(inst)
        self.assertTrue(inst.running)
        self.assertIn(("started", "Device 1"), self.events)
        self.assertEqual(m.can_launch(inst)[0], False)
        self.assertTrue(wait_until(lambda: "args: --max-fps=60" in list(inst.log)))
        m.stop(inst)
        self.assertTrue(proc.wait(5))
        self.assertFalse(inst.running)

    @unittest.skipIf(os.name == "nt", "script shell requis")
    def test_exit_event_and_metrics(self):
        self.fake_scrcpy('echo "INFO: 58 fps"\nexit 2')
        m = self.manager()
        inst = m.current
        proc = m.launch(inst)
        self.assertTrue(wait_until(lambda: ("stopped", "Device 1") in self.events))
        self.assertEqual(inst.last_exit, 2)
        self.assertIsNone(inst.process)
        self.assertIsNone(inst.metrics.snapshot().fps)  # effacé à l'arrêt
        self.assertIn(("stopped", "Device 1"), self.events)

    @unittest.skipIf(os.name == "nt", "script shell requis")
    def test_parallel_rules(self):
        self.fake_scrcpy("exec sleep 30")
        m = self.manager(allow_parallel=False)
        a = m.current
        b = m.create()
        m.launch(a)
        ok, reason = m.can_launch(b)
        self.assertFalse(ok)
        self.assertIn("autre instance", reason)
        m.stop_all()
        m.prefs.allow_parallel = True
        self.assertTrue(wait_until(lambda: not a.running and a.process is None))
        a.set_value("serial", "ABC")
        b.set_value("serial", "ABC")
        m.launch(a)
        ok, reason = m.can_launch(b)
        self.assertFalse(ok)
        self.assertIn("déjà utilisé", reason)
        b.set_value("serial", "XYZ")
        self.assertTrue(m.can_launch(b)[0])
        m.stop_all()

    def test_launch_refuses_invalid_settings(self):
        m = self.manager()
        m.current.set_value("crop", "bad")
        with self.assertRaises(ValueError):
            m.launch(m.current)

    def test_attached_device_serial_is_used(self):
        m = self.manager()
        inst = m.current
        m.attach_device(inst, Device("R5CW61A7Z8R", name="Samsung Galaxy S23 Ultra", manufacturer="Samsung"))
        self.assertEqual(m.args_for(inst), ["--serial=R5CW61A7Z8R"])
        self.assertEqual(inst.label, "Device 1: S23 Ultra")
        inst.set_value("conn", "usb")
        self.assertEqual(m.args_for(inst), ["--select-usb"])

    def test_export_import(self):
        m = self.manager()
        m.current.set_value("bitrate", 32)
        data = m.export_data()
        other = self.manager()
        other.import_data(data)
        self.assertEqual(other.current.base.bitrate, 32)


if __name__ == "__main__":
    unittest.main()
