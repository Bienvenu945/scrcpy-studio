"""Préréglages visuels (presets) et utilitaires de profils."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.models import RESOLUTIONS, Settings

_RES_LABEL = {1280: "720p", 1920: "1080p", 2560: "1440p", 3840: "4K"}


@dataclass(frozen=True)
class Preset:
    """Ensemble de réglages applicable en un clic."""

    key: str
    label: str
    color: str  # blue | violet | green | orange
    values: dict[str, Any] = field(default_factory=dict)
    builtin: bool = True

    @property
    def subtitle(self) -> str:
        """Résumé « 1080p · 60 FPS »."""
        return describe_values(self.values)


def describe_values(values: dict[str, Any]) -> str:
    """Résumé lisible d'un jeu de valeurs (résolution · fréquence)."""
    size = int(values.get("max_size", 0) or 0)
    fps = int(values.get("max_fps", 0) or 0)
    res = _RES_LABEL.get(size, f"{size}px" if size else "Natif")
    return f"{res} · {fps} FPS" if fps else f"{res} · FPS auto"


PRESETS: tuple[Preset, ...] = (
    Preset("stream_ultra", "Stream Ultra", "blue",
           {"bitrate": 16, "max_size": 1920, "max_fps": 60, "codec": "h264", "abuf": 50}),
    Preset("record_4k", "Record 4K", "violet",
           {"bitrate": 32, "max_size": 3840, "max_fps": 30, "codec": "h265", "record": "auto_4k.mp4"}),
    Preset("lowlat", "LowLat", "green",
           {"bitrate": 8, "max_size": 1280, "max_fps": 120, "codec": "h264", "vbuf": 0, "abuf": 10}),
)
#: Alias historique (roadmap v3.1) : les préréglages par défaut.
PROFILES = PRESETS

_COLORS = ("blue", "violet", "green", "orange")


def slugify(name: str) -> str:
    """Identifiant stable dérivé d'un nom."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "preset"


def custom_from_settings(name: str, settings: Settings, index: int = 0) -> dict[str, Any]:
    """Sérialise les réglages courants en préréglage personnalisé (valeurs ≠ défauts)."""
    return {"key": "custom_" + slugify(name), "label": name.strip() or "Preset",
            "color": _COLORS[index % len(_COLORS)], "values": settings.diff()}


def preset_from_dict(data: dict[str, Any]) -> Preset | None:
    """Préréglage depuis un dict persistant ; None si invalide."""
    try:
        key, label = str(data["key"]), str(data["label"])
    except (KeyError, TypeError):
        return None
    values = {k: v for k, v in dict(data.get("values", {})).items() if k in Settings.field_names()}
    color = data.get("color") if data.get("color") in _COLORS else "orange"
    return Preset(key, label, color, values, builtin=False)


def all_presets(custom: list[dict[str, Any]]) -> list[Preset]:
    """Préréglages par défaut suivis des personnalisés valides."""
    result = list(PRESETS)
    result += [p for p in (preset_from_dict(d) for d in custom) if p is not None]
    return result


def preset_matches(settings: Settings, preset: Preset) -> bool:
    """Vrai si ``settings`` contient déjà toutes les valeurs du préréglage."""
    merged = Settings().merged(preset.values)
    return all(getattr(settings, k) == getattr(merged, k) for k in preset.values)


def resolution_label(max_size: int) -> str:
    """Libellé de résolution pour ``max_size`` (« Personnalisée » si hors liste)."""
    for value, label in RESOLUTIONS:
        if value == max_size:
            return label
    return "Personnalisée"
