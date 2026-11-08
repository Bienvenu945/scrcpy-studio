"""Tests de core/process.py."""
import contextlib
import io
import os
import sys
import threading
import time
import unittest

from core.process import DISPATCHER, AsyncResult, Dispatcher, ManagedProcess, run_async, run_command

PY = sys.executable


class RunCommandTests(unittest.TestCase):
    def test_ok(self):
        r = run_command([PY, "-c", "print('salut')"])
        self.assertTrue(r.ok)
        self.assertEqual(r.stdout.strip(), "salut")
        self.assertEqual(r.text.strip(), "salut")

    def test_binary(self):
        r = run_command([PY, "-c", "import sys; sys.stdout.buffer.write(b'\\x89PNG\\x00')"], binary=True)
        self.assertEqual(r.data, b"\x89PNG\x00")

    def test_missing_executable(self):
        r = run_command(["/definitely/not/here"])
        self.assertFalse(r.ok)
        self.assertIn("introuvable", r.error)

    def test_timeout(self):
        r = run_command([PY, "-c", "import time; time.sleep(5)"], timeout=0.3)
        self.assertTrue(r.timed_out)
        self.assertFalse(r.ok)

    def test_nonzero(self):
        r = run_command([PY, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"])
        self.assertEqual((r.returncode, r.stderr), (3, "boom"))
        self.assertFalse(r.ok)


class DispatcherTests(unittest.TestCase):
    def test_drain_in_calling_thread(self):
        d = Dispatcher()
        seen = []
        t = threading.Thread(target=lambda: d.post(lambda: seen.append(threading.current_thread().name)))
        t.start()
        t.join()
        self.assertEqual(d.pending(), 1)
        self.assertEqual(d.drain(), 1)
        self.assertEqual(seen, [threading.current_thread().name])

    def test_errors_do_not_stop_drain(self):
        d = Dispatcher()
        out = []
        d.post(lambda: 1 / 0)
        d.post(out.append, 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(d.drain(), 2)
        self.assertEqual(out, [1])

    def test_limit(self):
        d = Dispatcher()
        for _ in range(5):
            d.post(lambda: None)
        self.assertEqual(d.drain(limit=2), 2)
        self.assertEqual(d.pending(), 3)


class RunAsyncTests(unittest.TestCase):
    def test_value_and_error_through_dispatcher(self):
        d = Dispatcher()
        results = []
        run_async(lambda: 42, lambda v, e: results.append((v, e)), dispatcher=d).join(2)
        run_async(lambda: 1 / 0, lambda v, e: results.append((v, type(e))), dispatcher=d).join(2)
        self.assertEqual(results, [])  # rien tant que le thread graphique n'a pas vidé la file
        d.drain()
        self.assertEqual(results, [(42, None), (None, ZeroDivisionError)])

    def test_default_dispatcher_exists(self):
        self.assertIsInstance(DISPATCHER, Dispatcher)

    def test_no_callback(self):
        run_async(lambda: 1, None).join(2)


@unittest.skipIf(os.name == "nt", "scripts POSIX")
class ManagedProcessTests(unittest.TestCase):
    def test_lines_and_exit_code(self):
        lines, codes = [], []
        p = ManagedProcess([PY, "-c", "print('a'); print('b')"], on_line=lines.append, on_exit=codes.append)
        p.start()
        self.assertTrue(p.wait(5))
        self.assertEqual(lines, ["a", "b"])
        self.assertEqual(codes, [0])
        self.assertEqual(list(p.lines), ["a", "b"])
        self.assertFalse(p.running)

    def test_stderr_is_merged(self):
        lines = []
        p = ManagedProcess([PY, "-c", "import sys; sys.stderr.write('err\\n')"], on_line=lines.append)
        p.start()
        p.wait(5)
        self.assertEqual(lines, ["err"])

    def test_terminate(self):
        p = ManagedProcess([PY, "-c", "import time; print('x', flush=True); time.sleep(60)"])
        p.start()
        self.assertTrue(p.running)
        self.assertIsNotNone(p.pid)
        p.terminate()
        self.assertTrue(p.wait(5))
        self.assertFalse(p.running)
        self.assertNotEqual(p.returncode, 0)

    def test_orphan_child_does_not_block_exit(self):
        # le fils orphelin garde le tube ouvert : on_exit doit quand même arriver rapidement
        codes = []
        script = "import subprocess, sys; subprocess.Popen(['sleep', '3']); print('parent done', flush=True)"
        p = ManagedProcess([PY, "-c", script], on_exit=codes.append)
        t0 = time.monotonic()
        p.start()
        self.assertTrue(p.wait(2.5))
        self.assertLess(time.monotonic() - t0, 2.5)
        self.assertEqual(codes, [0])

    def test_dispatcher_delivery(self):
        d = Dispatcher()
        lines = []
        p = ManagedProcess([PY, "-c", "print('z')"], on_line=lines.append, dispatcher=d)
        p.start()
        p.wait(5)
        self.assertEqual(lines, [])
        d.drain()
        self.assertEqual(lines, ["z"])

    def test_start_failure_raises(self):
        with self.assertRaises(OSError):
            ManagedProcess(["/definitely/not/here"]).start()


class AsyncResultTests(unittest.TestCase):
    def test_ok_property(self):
        self.assertTrue(AsyncResult(returncode=0).ok)
        self.assertFalse(AsyncResult(returncode=0, error="x").ok)
        self.assertFalse(AsyncResult().ok)


if __name__ == "__main__":
    unittest.main()
