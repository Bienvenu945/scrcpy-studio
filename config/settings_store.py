"""Persistance JSON : préférences (settings.json) et instances (config.json)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config.defaults import APP_VERSION, config_dir
from core.models import AppPrefs


class SettingsStore:
    """Lecture/écriture atomique et tolérante des fichiers de configuration."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = Path(directory) if directory else config_dir()

    @property
    def prefs_path(self) -> Path:
        """Chemin de settings.json."""
        return self.directory / "settings.json"

    @property
    def config_path(self) -> Path:
        """Chemin de config.json (instances)."""
        return self.directory / "config.json"

    def _read(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            try:  # fichier corrompu : on le met de côté et on repart propre
                path.replace(path.with_suffix(path.suffix + ".bak"))
            except OSError:
                pass
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def load_prefs(self) -> AppPrefs:
        """Préférences globales (valeurs par défaut si absentes ou corrompues)."""
        return AppPrefs.from_dict(self._read(self.prefs_path))

    def save_prefs(self, prefs: AppPrefs) -> None:
        """Enregistre les préférences globales."""
        self._write(self.prefs_path, {"version": APP_VERSION, **prefs.to_dict()})

    def load_instances(self) -> dict[str, Any]:
        """``{"current": id, "instances": [dict…]}`` (vide si absent)."""
        data = self._read(self.config_path)
        items = data.get("instances", [])
        return {"current": str(data.get("current", "")),
                "instances": [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []}

    def save_instances(self, current: str, instances: list[dict[str, Any]]) -> None:
        """Enregistre la liste des instances."""
        self._write(self.config_path, {"version": APP_VERSION, "current": current, "instances": instances})

    def export_config(self, path: Path, prefs: AppPrefs, instances: dict[str, Any]) -> None:
        """Exporte préférences et instances dans un seul fichier JSON."""
        self._write(Path(path), {"version": APP_VERSION, "prefs": prefs.to_dict(), **instances})

    def import_config(self, path: Path) -> tuple[AppPrefs, dict[str, Any]]:
        """Lit un export ; lève ``ValueError`` si le fichier n'est pas un export valide."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Fichier illisible : {exc}") from exc
        if not isinstance(data, dict) or "prefs" not in data:
            raise ValueError("Ce fichier n'est pas un export Scrcpy Studio.")
        items = data.get("instances", [])
        return (AppPrefs.from_dict(data.get("prefs")),
                {"current": str(data.get("current", "")), "instances": [i for i in items if isinstance(i, dict)]})
