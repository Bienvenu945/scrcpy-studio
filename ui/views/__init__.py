"""Registre des vues : clé, module, classe, libellé, icône, section."""
from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ViewInfo:
    """Description d'une vue de l'application."""

    key: str
    module: str
    cls: str
    label: str
    icon: str
    section: str  # base | pro | tools | hidden
    keywords: str = ""


VIEWS: tuple[ViewInfo, ...] = (
    # ─── BASE ───
    ViewInfo("device", "device", "DeviceView", "Device", "phone", "base", "appareil connexion usb wifi préréglage"),
    ViewInfo("video", "video", "VideoView", "Vidéo", "film", "base", "résolution bitrate fps codec latence"),
    ViewInfo("audio", "audio", "AudioView", "Audio", "volume", "base", "son micro opus"),
    ViewInfo("display", "display", "DisplayView", "Affichage", "monitor", "base", "fenêtre plein écran écran veille"),
    ViewInfo("control", "control", "ControlView", "Contrôle", "gamepad", "base", "clavier souris presse-papiers"),
    ViewInfo("record", "record", "RecordView", "Enreg.", "record", "base", "enregistrement vidéo mp4 mkv"),
    # ─── PRO ───
    ViewInfo("camera", "camera", "CameraView", "Caméra", "camera", "pro", "caméra torch zoom"),
    ViewInfo("virtual_display", "virtual_display", "VirtualDisplayView", "Virtuel", "layers", "pro", "écran virtuel new-display app"),
    ViewInfo("gamepad", "gamepad", "GamepadView", "OTG / Game", "gamepad", "pro", "otg gamepad uhid aoa manette"),
    ViewInfo("macros", "macros", "MacrosView", "Macros", "cube", "pro", "macro séquence automatisation"),
    ViewInfo("network", "network", "NetworkView", "Réseau", "wifi", "pro", "tcpip tunnel port adb"),
    ViewInfo("window_position", "window_position", "WindowPositionView", "Fenêtre", "window", "pro", "position taille rendu"),
    ViewInfo("rotation", "rotation", "RotationView", "Rotation", "rotate", "pro", "orientation crop angle"),
    ViewInfo("advanced_av", "advanced_av", "AdvancedAvView", "Audio/Vidéo+", "sliders", "pro", "encodeur options codec avancé"),
    ViewInfo("behavior", "behavior", "BehaviorView", "Comportement", "settings", "pro", "cleanup pause saisie raccourcis"),
    ViewInfo("v4l2", "v4l2", "V4l2View", "V4L2", "link", "pro", "v4l2loopback webcam"),
    ViewInfo("debug", "debug", "DebugView", "Debug", "bug", "pro", "debug liste encodeurs caméras options"),
    # ─── Toujours accessibles ───
    ViewInfo("advanced", "advanced", "AdvancedView", "Avancé", "sliders", "tools", "options libres extra commande"),
    ViewInfo("console", "console", "ConsoleView", "Console", "terminal", "tools", "sortie journal logs aide"),
    # ─── Hors barre latérale ───
    ViewInfo("about", "about", "AboutView", "À propos", "info", "hidden", "signature version auteur"),
    ViewInfo("settings", "settings", "SettingsView", "Paramètres", "gear", "hidden", "ambiance palette chemins import export"),
)

SECTION_TITLES = {"base": "BASE", "pro": "PRO", "tools": "OUTILS"}


def info_for(key: str) -> ViewInfo | None:
    """Description d'une vue par clé."""
    return next((v for v in VIEWS if v.key == key), None)


def views_for_mode(mode: str) -> list[ViewInfo]:
    """Vues visibles dans la barre latérale pour ``mode`` (base ou pro)."""
    sections = ("base", "tools") if mode == "base" else ("base", "pro", "tools")
    return [v for v in VIEWS if v.section in sections]


def sidebar_sections(mode: str) -> list[tuple[str, list[ViewInfo]]]:
    """Sections ordonnées ``(titre, vues)`` de la barre latérale."""
    result = []
    for section in ("base", "pro", "tools"):
        views = [v for v in views_for_mode(mode) if v.section == section]
        if views:
            result.append((SECTION_TITLES[section], views))
    return result


def load_view_class(info: ViewInfo) -> type:
    """Importe et renvoie la classe de vue (import différé)."""
    module = importlib.import_module(f"ui.views.{info.module}")
    return getattr(module, info.cls)
