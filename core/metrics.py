"""Métriques live : FPS (--print-fps), latence, batterie."""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable

from config.defaults import BATTERY_REFRESH_S, METRICS_REFRESH_S
from core.adb import AdbClient
from core.process import DISPATCHER, Dispatcher, run_async

_FPS = re.compile(r"(\d+(?:[.,]\d+)?)\s*fps", re.I)
_LATENCY = re.compile(r"(?:latency|delay)\D{0,12}?(\d+(?:[.,]\d+)?)\s*ms", re.I)


def parse_fps(line: str) -> float | None:
    """FPS lu dans une ligne de sortie de scrcpy (``INFO: 60 fps``)."""
    m = _FPS.search(line)
    return float(m.group(1).replace(",", ".")) if m else None


def parse_latency(line: str) -> float | None:
    """Latence (ms) lue dans une ligne de sortie de scrcpy, si présente."""
    m = _LATENCY.search(line)
    return float(m.group(1).replace(",", ".")) if m else None


@dataclass(frozen=True)
class Metrics:
    """Instantané des métriques."""

    fps: float | None = None
    latency_ms: float | None = None
    battery: int | None = None
    charging: bool = False


class LiveMetrics:
    """Agrégateur thread-safe ; la latence ADB est utilisée si scrcpy n'en fournit pas."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._m = Metrics()
        self._last_tick = float("-inf")
        self._last_battery = float("-inf")
        self._scrcpy_latency_at = float("-inf")
        self._busy = False

    def snapshot(self) -> Metrics:
        """Dernières valeurs connues."""
        with self._lock:
            return self._m

    def feed_line(self, line: str) -> bool:
        """Analyse une ligne de sortie de scrcpy ; renvoie True si une valeur a changé."""
        fps, lat = parse_fps(line), parse_latency(line)
        if fps is None and lat is None:
            return False
        with self._lock:
            if fps is not None:
                self._m = replace(self._m, fps=fps)
            if lat is not None:
                self._m = replace(self._m, latency_ms=lat)
                self._scrcpy_latency_at = self._clock()
        return True

    def clear_runtime(self) -> None:
        """Efface les valeurs liées à une session scrcpy (à l'arrêt)."""
        with self._lock:
            self._m = replace(self._m, fps=None)

    def set_battery(self, level: int | None, charging: bool) -> None:
        """Met à jour la batterie."""
        with self._lock:
            self._m = replace(self._m, battery=level, charging=charging)

    def set_adb_latency(self, ms: float | None) -> None:
        """Met à jour la latence ADB, sauf si scrcpy en a fourni une récemment."""
        with self._lock:
            if ms is not None and self._clock() - self._scrcpy_latency_at > 6.0:
                self._m = replace(self._m, latency_ms=ms)

    def due(self) -> tuple[bool, bool]:
        """(rafraîchir latence ?, rafraîchir batterie ?) selon les intervalles."""
        now = self._clock()
        with self._lock:
            return (now - self._last_tick >= METRICS_REFRESH_S, now - self._last_battery >= BATTERY_REFRESH_S)

    def tick(
        self,
        adb: AdbClient,
        serial: str,
        on_update: Callable[[Metrics], None] | None = None,
        dispatcher: Dispatcher | None = DISPATCHER,
    ) -> bool:
        """Planifie, si nécessaire, un rafraîchissement asynchrone ; renvoie True s'il est lancé."""
        if not serial:
            return False
        want_latency, want_battery = self.due()
        with self._lock:
            if self._busy or not (want_latency or want_battery):
                return False
            self._busy = True
            now = self._clock()
            self._last_tick = now
            if want_battery:
                self._last_battery = now

        def work() -> tuple[float | None, tuple[int | None, bool] | None]:
            lat = adb.latency_ms(serial) if want_latency else None
            bat = adb.battery(serial) if want_battery else None
            return lat, bat

        def done(value: object, error: BaseException | None) -> None:
            with self._lock:
                self._busy = False
            if error is None and value is not None:
                lat, bat = value  # type: ignore[misc]
                if lat is not None:
                    self.set_adb_latency(lat)
                if bat is not None and bat[0] is not None:
                    self.set_battery(*bat)
            if on_update:
                on_update(self.snapshot())

        run_async(work, done, dispatcher=dispatcher, name="scrcpy-studio-metrics")
        return True
