"""Construction de la ligne de commande scrcpy, validation et exécution."""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from config.defaults import PROJECT_ROOT, TEST_TIME_LIMIT_S
from core.models import Settings
from core.process import Dispatcher, ManagedProcess, run_command

#: Actions « liste » de scrcpy (aucune session de mirroring).
LIST_ACTIONS: dict[str, str] = {
    "apps": "--list-apps",
    "cameras": "--list-cameras",
    "camera-sizes": "--list-camera-sizes",
    "displays": "--list-displays",
    "encoders": "--list-encoders",
}


@dataclass(frozen=True)
class Issue:
    """Problème détecté dans une configuration."""

    level: str  # "error" | "warn" | "info"
    field: str
    message: str


# ───────────────────────── construction des arguments ─────────────────────────

def _flag(a: list[str], cond: bool, name: str) -> None:
    if cond:
        a.append(name)


def _val(a: list[str], name: str, value: object, default: object = "") -> None:
    if value != default and value != "":
        a.append(f"{name}={value}")


def _usb_selected(s: Settings) -> bool:
    return s.conn == "usb" or s.select_usb


def _tcpip_selected(s: Settings) -> bool:
    return s.conn == "tcpip" or s.select_tcpip


def device_args(s: Settings) -> list[str]:
    """Section 1 : sélection de l'appareil (--serial, -d, -e, --tcpip)."""
    a: list[str] = []
    _val(a, "--serial", s.serial)
    _flag(a, _usb_selected(s), "--select-usb")
    _flag(a, _tcpip_selected(s), "--select-tcpip")
    addr = s.tcpip_addr.strip()
    if addr:
        a.append("--tcpip=" + ("+" if s.tcpip_force_reconnect else "") + addr)
    elif s.tcpip:
        a.append("--tcpip")
    return a


def _record(s: Settings, a: list[str]) -> None:
    _val(a, "--record", s.record)
    if s.record or s.rformat:
        _val(a, "--record-format", s.rformat)


def _video(s: Settings, a: list[str]) -> None:
    _val(a, "--video-source", s.video_source, "display")
    if s.bitrate != 8:
        a.append(f"--video-bit-rate={s.bitrate}M")
    if s.max_size:
        a.append(f"--max-size={s.max_size}")
    if s.max_fps:
        a.append(f"--max-fps={s.max_fps}")
    _val(a, "--video-codec", s.codec, "h264")
    if s.vbuf:
        a.append(f"--video-buffer={s.vbuf}")
    _val(a, "--video-encoder", s.video_encoder)
    _val(a, "--video-codec-options", s.video_codec_options)
    _flag(a, s.no_video, "--no-video")
    _flag(a, s.no_video_playback, "--no-video-playback")
    _flag(a, s.no_playback, "--no-playback")
    _flag(a, s.no_downsize_on_error, "--no-downsize-on-error")
    if s.min_size_alignment != 1:
        a.append(f"--min-size-alignment={s.min_size_alignment}")
    _flag(a, s.ignore_video_encoder_constraints, "--ignore-video-encoder-constraints")
    _flag(a, s.no_mipmaps, "--no-mipmaps")


def _audio(s: Settings, a: list[str]) -> None:
    if not s.audio:
        a.append("--no-audio")
        return
    _val(a, "--audio-source", s.asource, "output")
    _val(a, "--audio-codec", s.acodec, "opus")
    if s.abuf != 50:
        a.append(f"--audio-buffer={s.abuf}")
    _flag(a, s.adup, "--audio-dup")
    if s.audio_bitrate != 128:
        a.append(f"--audio-bit-rate={s.audio_bitrate}K")
    _val(a, "--audio-encoder", s.audio_encoder)
    _val(a, "--audio-codec-options", s.audio_codec_options)
    if s.audio_output_buffer != 10:
        a.append(f"--audio-output-buffer={s.audio_output_buffer}")
    _flag(a, s.no_audio_playback, "--no-audio-playback")
    _flag(a, s.require_audio, "--require-audio")


def _camera(s: Settings, a: list[str]) -> None:
    if s.video_source != "camera":
        return
    _val(a, "--camera-id", s.camera_id)
    _val(a, "--camera-facing", s.camera_facing)
    _val(a, "--camera-size", s.camera_size)
    if s.camera_fps:
        a.append(f"--camera-fps={s.camera_fps}")
    _val(a, "--camera-ar", s.camera_ar)
    _flag(a, s.camera_high_speed, "--camera-high-speed")
    _flag(a, s.camera_torch, "--camera-torch")
    if s.camera_zoom:
        a.append(f"--camera-zoom={s.camera_zoom:g}")


def _window(s: Settings, a: list[str]) -> None:
    _flag(a, s.fullscreen, "--fullscreen")
    _flag(a, s.ontop, "--always-on-top")
    _flag(a, s.keepactive, "--keep-active")
    _flag(a, s.borderless, "--window-borderless")
    _val(a, "--window-title", s.title)
    for name, value in (("--window-x", s.window_x), ("--window-y", s.window_y)):
        if value and value.lower() != "auto":
            a.append(f"{name}={value}")
    _flag(a, s.no_window_aspect_ratio_lock, "--no-window-aspect-ratio-lock")


def _display(s: Settings, a: list[str]) -> None:
    if s.window_width:
        a.append(f"--window-width={s.window_width}")
    if s.window_height:
        a.append(f"--window-height={s.window_height}")
    _val(a, "--render-driver", s.render_driver)
    _val(a, "--render-fit", s.render_fit)
    _val(a, "--background-color", s.background_color)
    _flag(a, s.no_window, "--no-window")


def start_app_value(s: Settings) -> str:
    """Valeur de --start-app avec préfixes ``+`` (force-stop) puis ``?`` (préfixe de nom)."""
    name = s.start_app.strip()
    if not name:
        return ""
    typed = name[: len(name) - len(name.lstrip("+?"))]
    name = name.lstrip("+?")
    if not name:
        return ""
    force = s.start_app_force_stop or "+" in typed
    prefix = s.start_app_prefix_match or "?" in typed
    return ("+" if force else "") + ("?" if prefix else "") + name


def _vdisplay(s: Settings, a: list[str]) -> None:
    if s.display_id:
        a.append(f"--display-id={s.display_id}")
    if s.newdisplay:
        a.append(f"--new-display={s.vd_res.strip()}" if s.vd_res.strip() else "--new-display")
    _flag(a, s.flex_display, "--flex-display")
    _val(a, "--display-ime-policy", s.display_ime_policy)
    _flag(a, s.no_vd_destroy_content, "--no-vd-destroy-content")
    _flag(a, s.no_vd_system_decorations, "--no-vd-system-decorations")
    _val(a, "--start-app", start_app_value(s))


def effective_input_mode(s: Settings, kind: str) -> str:
    """Mode d'entrée effectif (``keyboard``/``mouse``/``gamepad``) après prise en compte de -K/-M/-G."""
    explicit = getattr(s, kind)
    default = "disabled" if kind == "gamepad" else "sdk"
    if explicit != default:
        return explicit
    if getattr(s, f"force_uhid_{kind}"):
        return "aoa" if s.otg else "uhid"
    return default


def _control(s: Settings, a: list[str]) -> None:
    _flag(a, s.readonly, "--no-control")
    _val(a, "--keyboard", effective_input_mode(s, "keyboard"), "sdk")
    _val(a, "--mouse", effective_input_mode(s, "mouse"), "sdk")
    _flag(a, s.noclip, "--no-clipboard-autosync")
    _flag(a, s.prefertext, "--prefer-text")
    _flag(a, s.raw_key_events, "--raw-key-events")
    _flag(a, s.no_key_repeat, "--no-key-repeat")
    _flag(a, s.no_mouse_hover, "--no-mouse-hover")
    _val(a, "--mouse-bind", s.mouse_bind)


def _otg(s: Settings, a: list[str]) -> None:
    _flag(a, s.otg, "--otg")
    _flag(a, s.no_power_on, "--no-power-on")
    _flag(a, s.power_off_on_close, "--power-off-on-close")
    _val(a, "--gamepad", effective_input_mode(s, "gamepad"), "disabled")


def _phone(s: Settings, a: list[str]) -> None:
    _flag(a, s.screenoff, "--turn-screen-off")
    _flag(a, s.stayawake, "--stay-awake")
    _flag(a, s.touches, "--show-touches")
    _flag(a, s.disable_screensaver, "--disable-screensaver")
    if s.screen_off_timeout:
        a.append(f"--screen-off-timeout={s.screen_off_timeout}")


def _rotation(s: Settings, a: list[str]) -> None:
    if s.angle:
        a.append(f"--angle={s.angle:g}")
    capture = s.capture_orientation
    if s.orientation_locked:
        capture = "@" + capture
    _val(a, "--capture-orientation", capture)
    if s.orientation:
        value = s.display_orientation or s.record_orientation
        if value:
            a.append(f"--display-orientation={value}")
            if not value.startswith("flip"):
                a.append(f"--record-orientation={value}")
    else:
        _val(a, "--display-orientation", s.display_orientation)
        _val(a, "--record-orientation", s.record_orientation)
    _val(a, "--crop", s.crop)


def _network(s: Settings, a: list[str]) -> None:
    _val(a, "--port", s.port_range)
    _val(a, "--tunnel-host", s.tunnel_host)
    if s.tunnel_port:
        a.append(f"--tunnel-port={s.tunnel_port}")
    _flag(a, s.force_adb_forward, "--force-adb-forward")
    _flag(a, s.kill_adb_on_close, "--kill-adb-on-close")


def _v4l2(s: Settings, a: list[str]) -> None:
    _val(a, "--v4l2-sink", s.v4l2_sink)
    if s.v4l2_sink and s.v4l2_buffer:
        a.append(f"--v4l2-buffer={s.v4l2_buffer}")


def _behavior(s: Settings, a: list[str]) -> None:
    _flag(a, s.no_cleanup, "--no-cleanup")
    if s.pause_on_exit == "true":
        a.append("--pause-on-exit")
    elif s.pause_on_exit == "if-error":
        a.append("--pause-on-exit=if-error")
    if s.time_limit:
        a.append(f"--time-limit={s.time_limit}")
    _val(a, "--push-target", s.push_target)


def _debug(s: Settings, a: list[str]) -> None:
    _val(a, "--verbosity", s.verbosity, "info")
    _flag(a, s.print_fps, "--print-fps")
    _flag(a, s.no_terminal_title, "--no-terminal-title")


def _misc(s: Settings, a: list[str]) -> None:
    _val(a, "--shortcut-mod", s.shortcut_mod)
    _flag(a, s.legacy_paste, "--legacy-paste")


def split_extra(text: str) -> list[str]:
    """Découpe le champ libre « extra » comme un shell ; repli sur un simple split."""
    if not text.strip():
        return []
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()


def build_args(s: Settings) -> list[str]:
    """Arguments scrcpy (sans l'exécutable), dans l'ordre officiel en 18 sections.

    Seules les valeurs différentes des défauts de scrcpy sont émises.
    """
    a: list[str] = []
    a += device_args(s)          # 1. sélection appareil
    _record(s, a)                # 2. enregistrement (tôt)
    _video(s, a)                 # 3. vidéo
    _audio(s, a)                 # 4. audio
    _camera(s, a)                # 5. caméra
    _window(s, a)                # 6. fenêtre
    _display(s, a)               # 7. affichage
    _vdisplay(s, a)              # 8. écran virtuel
    _control(s, a)               # 9. contrôle
    _otg(s, a)                   # 10. OTG / gamepad
    _phone(s, a)                 # 11. téléphone
    _rotation(s, a)              # 12. rotation / crop
    _network(s, a)               # 13. réseau
    _v4l2(s, a)                  # 14. V4L2
    _behavior(s, a)              # 15. comportement
    _debug(s, a)                 # 16. debug
    _misc(s, a)                  # 17. divers
    a += split_extra(s.extra)    # 18. options libres
    return a


def list_args(s: Settings, action: str) -> list[str]:
    """Arguments d'une action « liste » (``apps``, ``cameras``…) avec sélection d'appareil."""
    if action not in LIST_ACTIONS:
        raise KeyError(action)
    return device_args(s) + [LIST_ACTIONS[action]]


# ───────────────────────────── mise en forme ─────────────────────────────

def _quote(token: str, windows: bool) -> str:
    return subprocess.list2cmdline([token]) if windows else shlex.quote(token)


def format_command(args: Sequence[str], exe: str = "scrcpy", *, windows: bool | None = None) -> str:
    """Commande complète sur une ligne, quotée pour le shell courant."""
    win = (os.name == "nt") if windows is None else windows
    return " ".join(_quote(t, win) for t in [exe, *args])


def command_lines(args: Sequence[str], exe: str = "scrcpy", *, windows: bool | None = None) -> list[str]:
    """Commande sur plusieurs lignes (``$ scrcpy a \\`` / ``  b``) pour l'aperçu."""
    win = (os.name == "nt") if windows is None else windows
    tokens = [_quote(t, win) for t in args]
    cont = " ^" if win else " \\"
    if not tokens:
        return [f"$ {exe}"]
    lines = [f"$ {exe} {tokens[0]}" + (cont if len(tokens) > 1 else "")]
    for i, tok in enumerate(tokens[1:], start=1):
        lines.append("  " + tok + (cont if i < len(tokens) - 1 else ""))
    return lines


# ───────────────────────────── validation ─────────────────────────────

_RE_MOUSE_BIND = re.compile(r"^[+\-bhsn]{4}(:[+\-bhsn]{4})?$")
_RE_CROP = re.compile(r"^\d+:\d+:\d+:\d+$")
_RE_SIZE = re.compile(r"^\d+x\d+$")
_RE_COLOR = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RE_VD = re.compile(r"^(\d+x\d+)?(/\d+)?$")
_RE_PORTS = re.compile(r"^\d+(:\d+)?$")
_RE_POS = re.compile(r"^-?\d+$")


def validate(s: Settings, *, platform: str | None = None) -> list[Issue]:
    """Liste les incohérences de ``s`` (erreurs bloquantes, avertissements, infos)."""
    platform = platform or sys.platform
    out: list[Issue] = []

    def add(level: str, name: str, msg: str) -> None:
        out.append(Issue(level, name, msg))

    if _usb_selected(s) and _tcpip_selected(s):
        add("error", "conn", "--select-usb (-d) et --select-tcpip (-e) sont incompatibles.")
    if s.serial and (_usb_selected(s) or _tcpip_selected(s)):
        add("warn", "serial", "Un numéro de série est déjà précisé : -d / -e sont redondants.")
    if s.tcpip_force_reconnect and not s.tcpip_addr.strip():
        add("warn", "tcpip_force_reconnect", "Le préfixe « + » nécessite une adresse TCP/IP.")
    if s.video_source != "camera" and any(
        (s.camera_id, s.camera_facing, s.camera_size, s.camera_fps, s.camera_ar,
         s.camera_high_speed, s.camera_torch, s.camera_zoom)
    ):
        add("warn", "video_source", "Les options caméra sont ignorées : la source vidéo n'est pas « Caméra ».")
    if s.adup and s.asource != "playback":
        add("warn", "adup", "--audio-dup n'est disponible qu'avec --audio-source=playback.")
    if s.newdisplay and s.display_id:
        add("error", "newdisplay", "--new-display et --display-id sont incompatibles.")
    if s.no_video and not s.audio and not s.otg:
        add("warn", "no_video", "Ni vidéo ni audio : seule la session de contrôle sera active.")
    if s.otg:
        add("info", "otg", "Le mode OTG désactive le mirroring ; adb n'est pas nécessaire.")
    if s.orientation and s.display_orientation.startswith("flip"):
        add("warn", "orientation", "L'orientation d'enregistrement n'accepte pas les miroirs : seule l'affichage sera modifié.")
    if s.mouse_bind and not _RE_MOUSE_BIND.match(s.mouse_bind):
        add("error", "mouse_bind", "--mouse-bind : 4 caractères parmi + - b h s n (optionnellement « : » + 4 autres).")
    if s.crop and not _RE_CROP.match(s.crop):
        add("error", "crop", "--crop : format largeur:hauteur:x:y.")
    if s.camera_size and not _RE_SIZE.match(s.camera_size):
        add("error", "camera_size", "--camera-size : format LARGEURxHAUTEUR.")
    if s.background_color and not _RE_COLOR.match(s.background_color):
        add("error", "background_color", "--background-color : #RGB ou #RRGGBB.")
    if s.vd_res and not _RE_VD.match(s.vd_res.strip()):
        add("error", "vd_res", "--new-display : LxH, LxH/dpi ou /dpi.")
    if s.port_range and not _RE_PORTS.match(s.port_range):
        add("error", "port_range", "--port : port ou plage port:port.")
    for name, value in (("window_x", s.window_x), ("window_y", s.window_y)):
        if value and value.lower() != "auto" and not _RE_POS.match(value):
            add("error", name, "Position de fenêtre : entier ou « auto ».")
    if s.v4l2_sink and not platform.startswith("linux"):
        add("warn", "v4l2_sink", "--v4l2-sink n'est disponible que sous Linux.")
    if s.keyboard == "sdk" and s.otg and not s.force_uhid_keyboard:
        add("info", "keyboard", "En mode OTG, le clavier utilise AOA par défaut.")
    return out


def has_errors(issues: Sequence[Issue]) -> bool:
    """Vrai si au moins une ``Issue`` est bloquante."""
    return any(i.level == "error" for i in issues)


# ───────────────────────────── exécution ─────────────────────────────

def bundled_dirs() -> list[Path]:
    """Dossiers où chercher un scrcpy/adb livré avec l'application (installeur, paquet autonome, sources)."""
    dirs: list[Path] = []
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        dirs.append(Path(bundle) / "scrcpy")
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).resolve().parent / "scrcpy")
    dirs.append(PROJECT_ROOT / "vendor" / "scrcpy")
    return dirs


def find_executable(name: str, configured: str = "") -> str | None:
    """Chemin d'un exécutable : chemin configuré (fichier ou dossier), dossiers livrés, puis PATH."""
    if configured.strip():
        path = Path(configured.strip()).expanduser()
        if path.is_dir():
            for candidate in (name, name + ".exe"):
                if (path / candidate).is_file():
                    return str(path / candidate)
        elif path.is_file():
            return str(path)
    for folder in bundled_dirs():
        for candidate in (name, name + ".exe"):
            if (folder / candidate).is_file():
                return str(folder / candidate)
    return shutil.which(name)


@dataclass
class TestReport:
    """Résumé d'un lancement de test (--time-limit)."""

    __test__ = False  # empêche pytest de collecter cette classe

    ok: bool
    returncode: int
    output: str
    errors: list[str] = field(default_factory=list)
    duration: float = 0.0

    @property
    def summary(self) -> str:
        """Résumé lisible : OK ou nombre d'erreurs."""
        if self.ok:
            return f"OK — scrcpy a démarré et s'est fermé proprement ({self.duration:.1f} s)"
        if self.errors:
            return f"{len(self.errors)} erreur(s) : {self.errors[0]}"
        return f"Échec (code {self.returncode})"


_STRIP_FOR_TEST = ("--time-limit", "--record", "--record-format", "--pause-on-exit", "--v4l2-sink", "--v4l2-buffer")


def prepare_test_args(args: Sequence[str], seconds: int = TEST_TIME_LIMIT_S) -> list[str]:
    """Arguments d'un test : sans enregistrement ni pause, avec --time-limit=<seconds>."""
    kept = [a for a in args if a.split("=", 1)[0] not in _STRIP_FOR_TEST]
    return kept + [f"--time-limit={seconds}"]


def analyze_output(lines: Sequence[str], returncode: int, duration: float = 0.0) -> TestReport:
    """Construit un ``TestReport`` à partir de la sortie de scrcpy."""
    errors = [ln.strip() for ln in lines if ln.lstrip().startswith("ERROR:")]
    ok = returncode == 0 and not errors
    return TestReport(ok, returncode, "\n".join(lines), errors, duration)


class ScrcpyRunner:
    """Lance scrcpy et ses tests ; l'exécutable est résolu à chaque appel."""

    def __init__(self, scrcpy_path: str = "", adb_path: str = "", cwd: Path | None = None) -> None:
        self.scrcpy_path = scrcpy_path
        self.adb_path = adb_path
        self.cwd = cwd

    def executable(self) -> str | None:
        """Chemin de scrcpy, ou None s'il est introuvable."""
        return find_executable("scrcpy", self.scrcpy_path)

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        adb = find_executable("adb", self.adb_path) if self.adb_path else None
        if adb:
            env["ADB"] = adb
        return env

    def _cwd(self) -> str | None:
        if self.cwd is None:
            return None
        self.cwd.mkdir(parents=True, exist_ok=True)
        return str(self.cwd)

    def start(
        self,
        args: Sequence[str],
        on_line: Callable[[str], None] | None = None,
        on_exit: Callable[[int], None] | None = None,
        dispatcher: Dispatcher | None = None,
    ) -> ManagedProcess:
        """Démarre scrcpy ; lève ``FileNotFoundError`` si l'exécutable est introuvable."""
        exe = self.executable()
        if exe is None:
            raise FileNotFoundError("scrcpy est introuvable (vérifiez le PATH ou Paramètres › Chemins).")
        proc = ManagedProcess([exe, *args], cwd=self._cwd(), env=self._env(),
                              on_line=on_line, on_exit=on_exit, dispatcher=dispatcher)
        proc.start()
        return proc

    def run_test(self, args: Sequence[str], timeout: float = 25.0) -> TestReport:
        """Lance scrcpy avec --time-limit (bloquant : à appeler depuis un thread)."""
        exe = self.executable()
        if exe is None:
            return TestReport(False, -1, "", ["ERROR: scrcpy est introuvable."])
        started = time.monotonic()
        result = run_command([exe, *prepare_test_args(args)], timeout=timeout, env=self._env(), cwd=self._cwd())
        if result.error:
            return TestReport(False, result.returncode, "", [f"ERROR: {result.error}"], result.duration)
        text = (result.stdout + "\n" + result.stderr).strip().splitlines()
        return analyze_output(text, result.returncode, time.monotonic() - started)

    def run_list(self, s: Settings, action: str, timeout: float = 30.0) -> str:
        """Exécute ``--list-*`` et renvoie le texte (bloquant)."""
        exe = self.executable()
        if exe is None:
            return "scrcpy est introuvable."
        result = run_command([exe, *list_args(s, action)], timeout=timeout, env=self._env())
        return (result.stdout + result.stderr).strip() or result.error
