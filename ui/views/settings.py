"""Vue Paramètres : ambiance, interface, chemins, import/export."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout

from config.defaults import config_dir
from core.models import AppPrefs
from ui.rows import CardSpec, choice, path, toggle
from ui.theme import PALETTES
from ui.views.base_view import BaseView, confirm
from ui.widgets.controls import GlassButton
from ui.widgets.glass import GlassCard

PALETTE_OPTIONS = tuple((key, palette.label) for key, palette in PALETTES.items())


class SettingsView(BaseView):
    """Préférences globales de l'application."""

    KEY = "settings"
    TITLE = "Paramètres"
    SUBTITLE = "Ambiance, interface, chemins et configuration"
    RESETTABLE = False
    CARDS = (
        CardSpec("AMBIANCE", "palette", (
            choice("palette", "Palette", PALETTE_OPTIONS, target="prefs"),
            toggle("animated", "Fond animé (aurore)", hint="Visible avec la palette Aurore ; désactivé par défaut ailleurs", target="prefs"),
            toggle("glass", "Verre dépoli", hint="Cartes translucides (opacité 85 %)", target="prefs"),
            toggle("reduce_motion", "Réduire les animations", hint="Coupe fondus, halos et indicateur animé", target="prefs"),
        )),
        CardSpec("INTERFACE", "sliders", (
            toggle("instances_enabled", "Multi-instances (onglets)", target="prefs"),
            toggle("profiles_enabled", "Profils par instance", target="prefs"),
            toggle("metrics_live", "Métriques en direct (FPS, latence, batterie)", target="prefs"),
            toggle("preview_enabled", "Aperçu du téléphone", hint="Capture adb toutes les 3 s si scrcpy est arrêté", target="prefs"),
            toggle("quick_actions_enabled", "Actions rapides", target="prefs"),
            toggle("macros_enabled", "Macros (mode PRO)", target="prefs"),
        )),
        CardSpec("EXÉCUTION", "terminal", (
            toggle("allow_parallel", "Autoriser plusieurs scrcpy en parallèle", hint="Un appareil ne peut servir qu'à une instance à la fois", target="prefs"),
            path("scrcpy_path", "Chemin de scrcpy", placeholder="Vide : recherche dans le PATH", mode="open", target="prefs"),
            path("adb_path", "Chemin d'adb", placeholder="Vide : recherche dans le PATH", mode="open", target="prefs"),
            path("records_dir", "Dossier des enregistrements", placeholder="Par défaut : Vidéos/ScrcpyStudio", mode="dir", target="prefs"),
        )),
    )

    def build_extra(self) -> None:
        """Cartes personnalisées placées après les cartes déclaratives."""
        card = GlassCard("CONFIGURATION", "save")
        row = QHBoxLayout()
        row.setSpacing(8)
        for label, icon, handler in (("Exporter…", "upload", self._export), ("Importer…", "download", self._import),
                                     ("Ouvrir le dossier", "folder", self._open_folder), ("Tout réinitialiser", "refresh", self._reset_all)):
            button = GlassButton(label, icon, "stop" if label.startswith("Tout") else "default")
            button.clicked.connect(lambda _c=False, h=handler: h())
            row.addWidget(button)
        row.addStretch(1)
        card.add_layout(row)
        self.column.addWidget(card)

    def _export(self) -> None:
        target, _ = QFileDialog.getSaveFileName(self, "Exporter la configuration", str(Path.home() / "scrcpy_studio_config.json"), "JSON (*.json)")
        if target and self.ctx.store is not None:
            self.ctx.flush()
            self.ctx.store.export_config(Path(target), self.ctx.prefs, self.ctx.manager.export_data())
            self.ctx.notify("success", f"Configuration exportée : {target}")

    def _import(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Importer une configuration", str(Path.home()), "JSON (*.json)")
        if not source or self.ctx.store is None:
            return
        try:
            prefs, data = self.ctx.store.import_config(Path(source))
        except ValueError as exc:
            self.ctx.notify("error", str(exc))
            return
        for name, value in prefs.to_dict().items():
            setattr(self.ctx.prefs, name, value)
        self.ctx.manager.import_data(data)
        self.ctx.dirty = True
        self.ctx.emit("prefs", tuple(prefs.to_dict()))
        self.ctx.emit("instance", None)
        self.ctx.notify("success", "Configuration importée.")

    def _open_folder(self) -> None:
        folder = config_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _reset_all(self) -> None:
        if confirm(self, "Tout réinitialiser", "Remettre toutes les préférences à zéro (les instances sont conservées) ?"):
            for name, value in AppPrefs().to_dict().items():
                setattr(self.ctx.prefs, name, value)
            self.ctx.dirty = True
            self.ctx.emit("prefs", tuple(AppPrefs().to_dict()))
            self.ctx.notify("info", "Préférences réinitialisées.")
