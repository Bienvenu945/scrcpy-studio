"""Constantes et valeurs par défaut de Scrcpy Studio."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Scrcpy Studio"
APP_ID = "scrcpy-studio"
APP_VERSION = "4.0"
APP_YEAR = 2026
AUTHOR = "Bienvenu K.K"
SIGNATURE = "@Bienvenu K.K"
SCRCPY_TARGET_VERSION = "4.1"

MAX_INSTANCES = 8
MAIN_PROFILE = "Vue principale"
DEFAULT_PALETTE = "neon"
DEFAULT_UI_MODE = "base"

METRICS_REFRESH_S = 2.0
BATTERY_REFRESH_S = 5.0
PREVIEW_REFRESH_S = 3.0
TEST_TIME_LIMIT_S = 3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HELP_FILE = PROJECT_ROOT / "scrcpy_aide.txt"
RESOURCES_DIR = PROJECT_ROOT / "resources"


def config_dir() -> Path:
    """Dossier de configuration utilisateur (créé à la demande par le store)."""
    override = os.environ.get("SCRCPY_STUDIO_HOME")
    if override:
        return Path(override)
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "ScrcpyStudio"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ScrcpyStudio"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_ID


def default_records_dir() -> Path:
    """Dossier par défaut des enregistrements et captures."""
    videos = Path.home() / "Videos"
    if not videos.exists():
        videos = Path.home() / "Movies"
    return (videos if videos.exists() else Path.home()) / "ScrcpyStudio"
