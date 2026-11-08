"""Modèles de données : Settings (par instance), AppPrefs (global), Device."""
from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from typing import Any

_ORI = (("", "Défaut"), ("0", "0°"), ("90", "90°"), ("180", "180°"), ("270", "270°"))
_FLIP = (("flip0", "Miroir 0°"), ("flip90", "Miroir 90°"), ("flip180", "Miroir 180°"), ("flip270", "Miroir 270°"))
_INPUT = (("sdk", "SDK"), ("uhid", "UHID"), ("aoa", "AOA"), ("disabled", "Désactivé"))

#: Listes de choix (valeur, libellé) utilisées par la validation et par l'UI.
OPTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "conn": (("auto", "Auto"), ("usb", "USB"), ("tcpip", "Wi-Fi (TCP/IP)")),
    "video_source": (("display", "Écran"), ("camera", "Caméra")),
    "codec": (("h264", "H.264"), ("h265", "H.265"), ("av1", "AV1"), ("vp8", "VP8"), ("vp9", "VP9")),
    "asource": (
        ("output", "Sortie complète"), ("playback", "Lecture (playback)"), ("mic", "Microphone"),
        ("mic-unprocessed", "Micro brut"), ("mic-camcorder", "Micro caméscope"),
        ("mic-voice-recognition", "Micro reconnaissance vocale"),
        ("mic-voice-communication", "Micro communication"), ("voice-call", "Appel vocal"),
        ("voice-call-uplink", "Appel (montant)"), ("voice-call-downlink", "Appel (descendant)"),
        ("voice-performance", "Performance live"),
    ),
    "acodec": (("opus", "Opus"), ("aac", "AAC"), ("flac", "FLAC"), ("raw", "Raw")),
    "camera_facing": (("", "Auto"), ("front", "Avant"), ("back", "Arrière"), ("external", "Externe")),
    "display_ime_policy": (("", "Défaut"), ("local", "Local"), ("fallback", "Fallback"), ("hide", "Masqué")),
    "keyboard": _INPUT,
    "mouse": _INPUT,
    "gamepad": (("disabled", "Désactivé"), ("uhid", "UHID"), ("aoa", "AOA")),
    "capture_orientation": _ORI + _FLIP,
    "display_orientation": _ORI + _FLIP,
    "record_orientation": _ORI,
    "rformat": (
        ("", "Auto (extension)"), ("mp4", "MP4"), ("mkv", "MKV"), ("m4a", "M4A"), ("mka", "MKA"),
        ("opus", "Opus"), ("aac", "AAC"), ("flac", "FLAC"), ("wav", "WAV"),
    ),
    "pause_on_exit": (("false", "Jamais"), ("if-error", "En cas d'erreur"), ("true", "Toujours")),
    "render_driver": (
        ("", "Auto"), ("direct3d", "Direct3D"), ("opengl", "OpenGL"), ("opengles2", "OpenGL ES 2"),
        ("opengles", "OpenGL ES"), ("metal", "Metal"), ("software", "Logiciel"),
    ),
    "render_fit": (("", "Auto"), ("letterbox", "Letterbox"), ("stretched", "Étiré"), ("unscaled", "Sans mise à l'échelle")),
    "verbosity": (("verbose", "Verbose"), ("debug", "Debug"), ("info", "Info"), ("warn", "Warn"), ("error", "Error")),
    "min_size_alignment": (("1", "1"), ("2", "2"), ("4", "4"), ("8", "8"), ("16", "16")),
    "ui_mode": (("base", "BASE"), ("pro", "PRO")),
}
CHOICES: dict[str, tuple[str, ...]] = {k: tuple(v for v, _ in pairs) for k, pairs in OPTIONS.items()}

#: Bornes (min, max) des champs numériques.
RANGES: dict[str, tuple[float, float]] = {
    "bitrate": (1, 200), "max_size": (0, 8192), "max_fps": (0, 240), "vbuf": (0, 2000),
    "tunnel_port": (0, 65535), "abuf": (0, 2000), "audio_bitrate": (8, 512),
    "audio_output_buffer": (1, 500), "camera_fps": (0, 240), "camera_zoom": (0.0, 10.0),
    "display_id": (0, 64), "screen_off_timeout": (0, 86400), "angle": (-360.0, 360.0),
    "time_limit": (0, 86400), "window_width": (0, 16384), "window_height": (0, 16384),
    "v4l2_buffer": (0, 2000),
}

#: Résolutions proposées (valeur de --max-size, libellé).
RESOLUTIONS: tuple[tuple[int, str], ...] = (
    (0, "Native"), (1280, "720p (HD)"), (1920, "1080p (FHD)"), (2560, "1440p (QHD)"), (3840, "4K (UHD)"),
)


@dataclass
class Settings:
    """Réglages scrcpy d'une instance (une valeur par défaut = comportement scrcpy)."""

    # ── Appareil / connexion ──
    serial: str = ""
    conn: str = "auto"
    select_usb: bool = False
    select_tcpip: bool = False
    tcpip: bool = False
    tcpip_addr: str = ""
    tcpip_force_reconnect: bool = False
    port_range: str = ""
    tunnel_host: str = ""
    tunnel_port: int = 0
    force_adb_forward: bool = False
    kill_adb_on_close: bool = False
    # ── Vidéo ──
    video_source: str = "display"
    bitrate: int = 8
    max_size: int = 0
    max_fps: int = 0
    codec: str = "h264"
    vbuf: int = 0
    video_encoder: str = ""
    video_codec_options: str = ""
    no_video: bool = False
    no_video_playback: bool = False
    no_playback: bool = False
    no_downsize_on_error: bool = False
    min_size_alignment: int = 1
    ignore_video_encoder_constraints: bool = False
    no_mipmaps: bool = False
    # ── Audio ──
    audio: bool = True
    asource: str = "output"
    acodec: str = "opus"
    abuf: int = 50
    adup: bool = False
    audio_bitrate: int = 128
    audio_encoder: str = ""
    audio_codec_options: str = ""
    audio_output_buffer: int = 10
    no_audio_playback: bool = False
    require_audio: bool = False
    # ── Caméra ──
    camera_id: str = ""
    camera_facing: str = ""
    camera_size: str = ""
    camera_fps: int = 0
    camera_ar: str = ""
    camera_high_speed: bool = False
    camera_torch: bool = False
    camera_zoom: float = 0.0
    # ── Fenêtre ──
    fullscreen: bool = False
    ontop: bool = False
    keepactive: bool = False
    borderless: bool = False
    title: str = ""
    window_x: str = ""
    window_y: str = ""
    no_window_aspect_ratio_lock: bool = False
    # ── Écran virtuel ──
    newdisplay: bool = False
    vd_res: str = ""
    flex_display: bool = False
    display_id: int = 0
    display_ime_policy: str = ""
    no_vd_destroy_content: bool = False
    no_vd_system_decorations: bool = False
    start_app: str = ""
    start_app_force_stop: bool = False
    start_app_prefix_match: bool = False
    # ── Contrôle / input ──
    readonly: bool = False
    keyboard: str = "sdk"
    mouse: str = "sdk"
    gamepad: str = "disabled"
    noclip: bool = False
    prefertext: bool = False
    raw_key_events: bool = False
    no_key_repeat: bool = False
    no_mouse_hover: bool = False
    mouse_bind: str = ""
    # ── OTG ──
    otg: bool = False
    no_power_on: bool = False
    power_off_on_close: bool = False
    force_uhid_keyboard: bool = False
    force_uhid_mouse: bool = False
    force_uhid_gamepad: bool = False
    # ── Téléphone ──
    screenoff: bool = False
    stayawake: bool = False
    touches: bool = False
    disable_screensaver: bool = False
    screen_off_timeout: int = 0
    # ── Rotation / crop ──
    angle: float = 0.0
    capture_orientation: str = ""
    orientation_locked: bool = False
    display_orientation: str = ""
    record_orientation: str = ""
    orientation: bool = False
    crop: str = ""
    # ── Enregistrement / comportement ──
    record: str = ""
    rformat: str = ""
    push_target: str = ""
    no_cleanup: bool = False
    pause_on_exit: str = "false"
    time_limit: int = 0
    # ── Fenêtre avancée ──
    window_width: int = 0
    window_height: int = 0
    render_driver: str = ""
    render_fit: str = ""
    background_color: str = ""
    no_window: bool = False
    # ── V4L2 / debug / divers ──
    v4l2_sink: str = ""
    v4l2_buffer: int = 0
    verbosity: str = "info"
    print_fps: bool = False
    no_terminal_title: bool = False
    shortcut_mod: str = ""
    legacy_paste: bool = False
    extra: str = ""
    active_preset: str = ""

    @classmethod
    def field_names(cls) -> tuple[str, ...]:
        """Noms de tous les champs."""
        return tuple(f.name for f in fields(cls))

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Settings":
        """Construit des Settings depuis un dict (clés inconnues ignorées, valeurs coercées)."""
        s = cls()
        for key, value in (data or {}).items():
            if key in _SETTINGS_DEFAULTS:
                setattr(s, key, coerce(key, value))
        return s

    def to_dict(self) -> dict[str, Any]:
        """Tous les champs sous forme de dict."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def diff(self) -> dict[str, Any]:
        """Champs différents des valeurs par défaut."""
        return {k: v for k, v in self.to_dict().items() if v != _SETTINGS_DEFAULTS[k]}

    def copy(self) -> "Settings":
        """Copie indépendante."""
        return Settings.from_dict(self.to_dict())

    def merged(self, delta: dict[str, Any]) -> "Settings":
        """Copie avec application d'un delta (profil, préréglage)."""
        s = self.copy()
        for key, value in delta.items():
            if key in _SETTINGS_DEFAULTS:
                setattr(s, key, coerce(key, value))
        return s


@dataclass
class AppPrefs:
    """Préférences globales de l'application (settings.json)."""

    palette: str = "neon"
    animated: bool = False
    glass: bool = True
    ui_mode: str = "base"
    instances_enabled: bool = True
    profiles_enabled: bool = True
    metrics_live: bool = True
    preview_enabled: bool = True
    quick_actions_enabled: bool = True
    macros_enabled: bool = True
    macros_list: list = field(default_factory=list)
    custom_presets: list = field(default_factory=list)
    scrcpy_path: str = ""
    adb_path: str = ""
    allow_parallel: bool = True
    records_dir: str = ""
    sidebar_visible: bool = True
    info_visible: bool = True
    reduce_motion: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppPrefs":
        """Construit des préférences depuis un dict (tolérant)."""
        p = cls()
        for key, value in (data or {}).items():
            if key not in _PREFS_DEFAULTS:
                continue
            if isinstance(_PREFS_DEFAULTS[key], list):
                setattr(p, key, [x for x in value if isinstance(x, dict)] if isinstance(value, list) else [])
            else:
                setattr(p, key, coerce(key, value, _PREFS_DEFAULTS))
        return p

    def to_dict(self) -> dict[str, Any]:
        """Dict sérialisable."""
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class Device:
    """Appareil Android vu par adb."""

    serial: str
    state: str = "device"
    model: str = ""
    name: str = ""
    manufacturer: str = ""
    android: str = ""
    sdk: str = ""
    transport: str = "usb"
    battery: int | None = None
    charging: bool = False
    display: str = ""
    props: dict = field(default_factory=dict)

    @property
    def online(self) -> bool:
        """Vrai si l'appareil est prêt à l'usage."""
        return self.state == "device"

    @property
    def label(self) -> str:
        """Nom complet affichable."""
        if self.name:
            return self.name
        full = f"{self.manufacturer} {self.model}".strip()
        return full or self.serial

    @property
    def short_name(self) -> str:
        """Nom court (sans marque ni « Galaxy »)."""
        text = self.label
        for prefix in (self.manufacturer, "Galaxy"):
            if prefix and text.lower().startswith(prefix.lower() + " "):
                text = text[len(prefix) + 1:]
        return text.strip() or self.serial

    @property
    def link(self) -> str:
        """Type de liaison lisible."""
        return "USB" if self.transport == "usb" else "Wi-Fi"


def _default_of(f: Any) -> Any:
    """Valeur par défaut d'un champ dataclass (valeur ou fabrique)."""
    return f.default if f.default is not MISSING else f.default_factory()


_SETTINGS_DEFAULTS: dict[str, Any] = {f.name: _default_of(f) for f in fields(Settings)}
_PREFS_DEFAULTS: dict[str, Any] = {f.name: _default_of(f) for f in fields(AppPrefs)}
PREFS_DEFAULTS = _PREFS_DEFAULTS


def _to_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "oui", "on")
    return bool(value)


def coerce(name: str, value: Any, defaults: dict[str, Any] | None = None) -> Any:
    """Convertit ``value`` au type du champ ``name`` (bornes et choix appliqués)."""
    table = defaults if defaults is not None else _SETTINGS_DEFAULTS
    if name not in table:
        raise KeyError(name)
    default = table[name]
    if isinstance(default, bool):
        return _to_bool(value)
    if isinstance(default, (int, float)):
        try:
            num = float(value) if not isinstance(value, str) else float(value.strip().replace(",", ".") or default)
        except (TypeError, ValueError):
            return default
        low, high = RANGES.get(name, (None, None))
        if low is not None:
            num = max(low, min(high, num))
        return int(round(num)) if isinstance(default, int) else float(num)
    text = "" if value is None else str(value).strip()
    if name in CHOICES and text not in CHOICES[name]:
        return default
    return text
