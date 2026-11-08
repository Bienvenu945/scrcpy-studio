"""Exécution asynchrone : commandes ponctuelles, processus suivis, file d'événements UI.

Aucun code Qt ici : les threads de travail postent leurs résultats dans un
``Dispatcher`` que le thread graphique vide à intervalle régulier (QTimer).
"""
from __future__ import annotations

import collections
import logging
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


class Dispatcher:
    """File thread-safe de callables à exécuter dans le thread appelant de ``drain``."""

    def __init__(self) -> None:
        self._queue: queue.SimpleQueue = queue.SimpleQueue()

    def post(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Planifie ``fn(*args, **kwargs)``."""
        self._queue.put((fn, args, kwargs))

    def drain(self, limit: int = 200) -> int:
        """Exécute au plus ``limit`` callables ; renvoie le nombre exécuté."""
        done = 0
        while done < limit:
            try:
                fn, args, kwargs = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args, **kwargs)
            except Exception:  # un rappel fautif ne doit jamais tuer l'interface
                logging.getLogger(__name__).exception("Rappel en échec dans le thread graphique")
            done += 1
        return done

    def pending(self) -> int:
        """Nombre approximatif d'éléments en attente."""
        return self._queue.qsize()


DISPATCHER = Dispatcher()


@dataclass
class AsyncResult:
    """Résultat d'une commande externe."""

    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    data: bytes = b""
    error: str = ""
    timed_out: bool = False
    duration: float = 0.0

    @property
    def ok(self) -> bool:
        """Vrai si la commande s'est terminée avec le code 0 sans erreur."""
        return self.returncode == 0 and not self.error and not self.timed_out

    @property
    def text(self) -> str:
        """Sortie standard, puis erreur standard si la première est vide."""
        return self.stdout if self.stdout.strip() else self.stderr


def run_command(
    args: Sequence[str],
    timeout: float = 10.0,
    *,
    binary: bool = False,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> AsyncResult:
    """Exécute une commande (bloquant) et renvoie un ``AsyncResult`` sans jamais lever."""
    started = time.monotonic()
    try:
        proc = subprocess.run(
            list(args), capture_output=True, timeout=timeout, env=env, cwd=cwd,
            stdin=subprocess.DEVNULL, creationflags=_NO_WINDOW,
        )
    except FileNotFoundError:
        return AsyncResult(error=f"Exécutable introuvable : {args[0]}", duration=time.monotonic() - started)
    except subprocess.TimeoutExpired:
        return AsyncResult(timed_out=True, error="Délai dépassé", duration=time.monotonic() - started)
    except OSError as exc:
        return AsyncResult(error=str(exc), duration=time.monotonic() - started)
    result = AsyncResult(returncode=proc.returncode, duration=time.monotonic() - started)
    result.stderr = proc.stderr.decode("utf-8", "replace")
    if binary:
        result.data = proc.stdout
    else:
        result.stdout = proc.stdout.decode("utf-8", "replace")
    return result


def run_async(
    func: Callable[[], Any],
    on_done: Callable[[Any, BaseException | None], None] | None = None,
    *,
    dispatcher: Dispatcher | None = DISPATCHER,
    name: str = "scrcpy-studio-worker",
) -> threading.Thread:
    """Exécute ``func`` dans un thread ; ``on_done(valeur, erreur)`` est posté sur le dispatcher."""

    def worker() -> None:
        value: Any = None
        error: BaseException | None = None
        try:
            value = func()
        except BaseException as exc:  # noqa: BLE001 - remonté via on_done
            error = exc
        if on_done is None:
            return
        if dispatcher is None:
            on_done(value, error)
        else:
            dispatcher.post(on_done, value, error)

    thread = threading.Thread(target=worker, name=name, daemon=True)
    thread.start()
    return thread


class ManagedProcess:
    """Processus de longue durée dont la sortie est lue ligne par ligne."""

    def __init__(
        self,
        args: Sequence[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        on_line: Callable[[str], None] | None = None,
        on_exit: Callable[[int], None] | None = None,
        dispatcher: Dispatcher | None = None,
        keep_lines: int = 2000,
    ) -> None:
        self.args = list(args)
        self.cwd = cwd
        self.env = env
        self.on_line = on_line
        self.on_exit = on_exit
        self.dispatcher = dispatcher
        self.lines: collections.deque[str] = collections.deque(maxlen=keep_lines)
        self.finished = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def _emit(self, fn: Callable[..., Any] | None, *args: Any) -> None:
        if fn is None:
            return
        if self.dispatcher is not None:
            self.dispatcher.post(fn, *args)
        else:
            fn(*args)

    def start(self) -> None:
        """Démarre le processus ; lève ``OSError`` s'il est impossible à lancer."""
        self._proc = subprocess.Popen(
            self.args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            cwd=self.cwd, env=self.env, creationflags=_NO_WINDOW,
        )
        self._thread = threading.Thread(target=self._wait_and_notify, name="scrcpy-studio-waiter", daemon=True)
        self._thread.start()

    def _read(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        for raw in iter(proc.stdout.readline, ""):
            line = raw.rstrip("\r\n")
            self.lines.append(line)
            self._emit(self.on_line, line)
        proc.stdout.close()

    def _wait_and_notify(self) -> None:
        """Lit la sortie dans un thread dédié ; la fin du processus ne dépend pas de l'EOF du tube
        (un processus fils orphelin pourrait le garder ouvert)."""
        proc = self._proc
        assert proc is not None
        reader = threading.Thread(target=self._read, name="scrcpy-studio-reader", daemon=True)
        reader.start()
        code = proc.wait()
        reader.join(1.0)
        self._emit(self.on_exit, code)  # avant ``finished`` : ``wait()`` ne rend la main qu'une fois le rappel exécuté
        self.finished.set()

    @property
    def pid(self) -> int | None:
        """PID du processus, s'il a démarré."""
        return self._proc.pid if self._proc else None

    @property
    def running(self) -> bool:
        """Vrai tant que le processus tourne."""
        return self._proc is not None and self._proc.poll() is None

    @property
    def returncode(self) -> int | None:
        """Code de sortie (None tant qu'il tourne)."""
        return self._proc.poll() if self._proc else None

    def terminate(self, grace: float = 2.0) -> None:
        """Demande l'arrêt, puis force après ``grace`` secondes."""
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()

    def wait(self, timeout: float | None = None) -> bool:
        """Attend la fin (et la lecture complète de la sortie) ; renvoie True si terminé."""
        return self.finished.wait(timeout)
