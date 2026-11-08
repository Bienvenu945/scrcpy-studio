"""Vue Avancé : options libres, commande générée, validation, raccourcis scrcpy."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QPlainTextEdit

from core import scrcpy_help
from ui.rows import CardSpec, Row
from ui.views.base_view import BaseView
from ui.widgets.controls import GlassButton
from ui.widgets.glass import GlassCard, make_label


class AdvancedView(BaseView):
    """Échappatoire : tout ce que l'interface ne couvre pas, et la commande finale."""

    KEY = "advanced"
    TITLE = "Avancé"
    SUBTITLE = "Options libres, commande générée et raccourcis scrcpy"
    CARDS = (
        CardSpec("OPTIONS LIBRES", "terminal", (
            Row("extra", "Arguments supplémentaires", "textarea", "", "Ajoutés à la fin de la commande, analysés comme dans un shell",
                placeholder='--window-title "Mon écran" -V debug', mono=True),
        )),
    )

    def build_extra(self) -> None:
        """Cartes personnalisées placées après les cartes déclaratives."""
        command = GlassCard("COMMANDE GÉNÉRÉE", "terminal")
        copy = GlassButton("Copier", "copy")
        copy.clicked.connect(lambda: self.ctx.run_action("copy"))
        command.add_action(copy)
        self.command_view = QPlainTextEdit()
        self.command_view.setObjectName("Mono")
        self.command_view.setReadOnly(True)
        self.command_view.setFixedHeight(130)
        command.add_widget(self.command_view)
        self.issues_label = make_label("", wrap=True)
        command.add_widget(self.issues_label)
        self.column.addWidget(command)

        shortcuts = GlassCard("RACCOURCIS SCRCPY", "keyboard", "MOD = Alt gauche ou Super gauche (modifiable dans Comportement)")
        lines = [f"{'  /  '.join(s.keys):<34} {s.description}" for s in scrcpy_help.load_shortcuts()]
        view = QPlainTextEdit("\n".join(lines))
        view.setObjectName("Mono")
        view.setReadOnly(True)
        view.setMinimumHeight(260)
        shortcuts.add_widget(view)
        self.column.addWidget(shortcuts)

    def refresh_extra(self) -> None:
        """Met à jour les éléments personnalisés de la vue."""
        self.command_view.setPlainText("\n".join(self.ctx.command_lines()))
        issues = self.ctx.issues()
        marks = {"error": "✗", "warn": "⚠", "info": "ℹ"}
        self.issues_label.setText("\n".join(f"{marks.get(i.level, '•')} {i.message}" for i in issues))
        self.issues_label.setVisible(bool(issues))

    def on_ctx_event(self, event: str, payload: Any) -> None:
        """Réagit aux événements du contexte (appareils, exécution, journal…)."""
        if event == "values" and self.isVisible():
            self.refresh_extra()
