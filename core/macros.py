"""Macros : séquences d'étapes (lancer, attendre, adb, capture, arrêter)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.adb import AdbClient
from core.process import Dispatcher

STEP_TYPES: dict[str, str] = {
    "launch": "Lancer scrcpy",
    "wait": "Attendre (secondes)",
    "adb": "Commande adb shell",
    "screenshot": "Capture d'écran",
    "stop": "Fermer scrcpy",
}


@dataclass
class Step:
    """Étape d'une macro."""

    type: str
    value: str = ""

    def describe(self) -> str:
        """Description lisible."""
        label = STEP_TYPES.get(self.type, self.type)
        return f"{label} : {self.value}" if self.value else label


@dataclass
class Macro:
    """Séquence nommée d'étapes."""

    name: str
    steps: list[Step] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Représentation JSON."""
        return {"name": self.name, "steps": [{"type": s.type, "value": s.value} for s in self.steps]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Macro":
        """Reconstruit une macro (étapes inconnues ignorées)."""
        steps = [Step(str(s["type"]), str(s.get("value", ""))) for s in data.get("steps", [])
                 if isinstance(s, dict) and s.get("type") in STEP_TYPES]
        return cls(str(data.get("name") or "Macro"), steps)


def example_macro() -> Macro:
    """Macro d'exemple « Test app » de la roadmap."""
    return Macro("Test app", [
        Step("launch"), Step("wait", "2"), Step("adb", "am start -n com.example.app"),
        Step("screenshot"), Step("stop"),
    ])


@dataclass
class MacroResult:
    """Résultat d'exécution."""

    ok: bool
    log: list[str] = field(default_factory=list)
    captures: list[Path] = field(default_factory=list)
    error: str = ""


def call_in_ui(dispatcher: Dispatcher | None, fn: Callable[[], Any], timeout: float = 10.0) -> Any:
    """Exécute ``fn`` dans le thread graphique (via le dispatcher) et attend son résultat."""
    if dispatcher is None:
        return fn()
    box: dict[str, Any] = {}
    done = threading.Event()

    def runner() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001 - relayé à l'appelant
            box["error"] = exc
        done.set()

    dispatcher.post(runner)
    if not done.wait(timeout):
        raise TimeoutError("Le thread graphique ne répond pas.")
    if "error" in box:
        raise box["error"]
    return box.get("value")


class MacroPlayer:
    """Exécute une macro dans un thread de travail ; annulable."""

    def __init__(
        self,
        launch: Callable[[], None],
        stop: Callable[[], None],
        adb: AdbClient,
        serial: Callable[[], str],
        captures_dir: Path,
        dispatcher: Dispatcher | None = None,
        on_log: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._launch, self._stop, self._adb, self._serial = launch, stop, adb, serial
        self.captures_dir = Path(captures_dir)
        self.dispatcher = dispatcher
        self.on_log = on_log
        self._sleep = sleep
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Demande l'arrêt de la macro en cours."""
        self._cancel.set()

    def _log(self, result: MacroResult, text: str) -> None:
        result.log.append(text)
        if self.on_log:
            self.on_log(text)

    def _wait(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self._cancel.is_set() and time.monotonic() < end:
            self._sleep(min(0.1, max(0.0, end - time.monotonic())))

    def run(self, macro: Macro) -> MacroResult:
        """Exécute les étapes ; s'arrête à la première erreur."""
        self._cancel.clear()
        result = MacroResult(True)
        for number, step in enumerate(macro.steps, start=1):
            if self._cancel.is_set():
                result.ok, result.error = False, "Macro annulée."
                self._log(result, "⏹ annulée")
                break
            self._log(result, f"{number}. {step.describe()}")
            try:
                self._execute(step, result)
            except Exception as exc:  # noqa: BLE001 - consigné dans le résultat
                result.ok, result.error = False, f"Étape {number} : {exc}"
                self._log(result, f"✗ {exc}")
                break
        if result.ok:
            self._log(result, "✓ terminée")
        return result

    def _execute(self, step: Step, result: MacroResult) -> None:
        if step.type == "launch":
            call_in_ui(self.dispatcher, self._launch)
        elif step.type == "stop":
            call_in_ui(self.dispatcher, self._stop)
        elif step.type == "wait":
            try:
                seconds = max(0.0, float(step.value.replace(",", ".") or 1))
            except ValueError as exc:
                raise ValueError(f"durée invalide : {step.value!r}") from exc
            self._wait(seconds)
        elif step.type == "adb":
            if not step.value.strip():
                raise ValueError("commande adb vide")
            out = self._adb.shell(self._serial(), step.value)
            if not out.ok:
                raise RuntimeError(out.error or out.stderr.strip() or f"code {out.returncode}")
        elif step.type == "screenshot":
            data = self._adb.screencap(self._serial())
            if data is None:
                raise RuntimeError("capture impossible (appareil non connecté ?)")
            self.captures_dir.mkdir(parents=True, exist_ok=True)
            path = self.captures_dir / f"capture_{time.strftime('%Y%m%d_%H%M%S')}.png"
            path.write_bytes(data)
            result.captures.append(path)
            self._log(result, f"   → {path}")
        else:
            raise ValueError(f"étape inconnue : {step.type}")
