"""Vue À propos : version, signature, environnement détecté."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt

from config.defaults import APP_NAME, APP_VERSION, APP_YEAR, AUTHOR, SCRCPY_TARGET_VERSION, config_dir
from core.process import run_async, run_command
from ui.views.base_view import BaseView
from ui.widgets.glass import GlassCard, make_label

SHORTCUTS = (
    ("Ctrl+Entrée", "Lancer scrcpy"), ("Ctrl+.", "Arrêter scrcpy"), ("Ctrl+K", "Command Palette"),
    ("Ctrl+B", "Masquer/afficher la barre latérale"), ("Ctrl+D", "Masquer/afficher le panneau contexte"),
    ("F11", "Mode focus"), ("Ctrl+1…9", "Aller à la vue n"), ("Ctrl+T / Ctrl+W", "Nouvelle / fermer l'instance"),
    ("Ctrl+Tab", "Instance suivante"), ("Ctrl+,", "Paramètres"), ("F1", "Rechercher une option scrcpy"),
    ("Ctrl+Q", "Quitter"),
)


class AboutView(BaseView):
    """Informations sur l'application."""

    KEY = "about"
    TITLE = "À propos"
    SUBTITLE = f"{APP_NAME} — lanceur graphique pour scrcpy"
    RESETTABLE = False

    def build_top(self) -> None:
        """Cartes personnalisées placées avant les cartes déclaratives."""
        card = GlassCard(APP_NAME.upper(), "bolt")
        card.add_widget(make_label(f"Version {APP_VERSION}  ·  cible scrcpy {SCRCPY_TARGET_VERSION}"))
        card.add_widget(make_label(f"Conçu par {AUTHOR}  ·  © {APP_YEAR}", role="dim"))
        card.add_widget(make_label("Simple par défaut, complet sur demande : toutes les options de scrcpy "
                                   "sont accessibles en mode PRO.", role="dim", wrap=True))
        self.column.addWidget(card)

        env = GlassCard("ENVIRONNEMENT", "info")
        self.scrcpy_label = make_label("scrcpy : détection…")
        self.adb_label = make_label("adb : détection…")
        folder = make_label(f"Configuration : {config_dir()}", role="dim", wrap=True)
        folder.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        for label in (self.scrcpy_label, self.adb_label, folder):
            env.add_widget(label)
        self.column.addWidget(env)

        keys = GlassCard("RACCOURCIS CLAVIER", "keyboard")
        for combo, meaning in SHORTCUTS:
            keys.add_widget(make_label(f"{combo:<18}{meaning}", role="mono"))
        self.column.addWidget(keys)

    def on_enter(self) -> None:
        """Appelé à chaque affichage de la vue."""
        super().on_enter()
        exe = self.ctx.scrcpy_path()
        adb = self.ctx.adb

        def work() -> tuple[str, str]:
            scrcpy = "introuvable (Paramètres › Chemins)"
            if exe:
                result = run_command([exe, "--version"], timeout=8)
                scrcpy = (result.stdout.splitlines() or [exe])[0] if result.ok else exe
            return scrcpy, adb.version() or "introuvable (Paramètres › Chemins)"

        def done(value: Any, error: BaseException | None) -> None:
            scrcpy, adb_version = value if value else ("erreur", "erreur")
            self.scrcpy_label.setText(f"scrcpy : {scrcpy}")
            self.adb_label.setText(f"adb : {adb_version}")

        run_async(work, done, dispatcher=self.ctx.dispatcher)
