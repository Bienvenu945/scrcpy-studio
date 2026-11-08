"""Vue Console : sortie de scrcpy en direct et aide contextuelle."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit

from core import scrcpy_help
from ui.views.base_view import BaseView
from ui.widgets.controls import GlassButton
from ui.widgets.glass import GlassCard, make_label


class ConsoleView(BaseView):
    """Journal de l'instance courante."""

    KEY = "console"
    TITLE = "Console"
    SUBTITLE = "Sortie de scrcpy en direct et aide contextuelle"
    RESETTABLE = False

    def build_top(self) -> None:
        """Cartes personnalisées placées avant les cartes déclaratives."""
        self._loaded_id = ""
        card = GlassCard("SORTIE SCRCPY", "terminal")
        clear = GlassButton("Effacer", "trash", "ghost")
        clear.clicked.connect(self._clear)
        copy = GlassButton("Copier", "copy", "ghost")
        copy.clicked.connect(self._copy)
        card.add_action(clear)
        card.add_action(copy)
        self.output = QPlainTextEdit()
        self.output.setObjectName("Mono")
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(2000)
        self.output.setMinimumHeight(380)
        self.output.setPlaceholderText("Lancez scrcpy : sa sortie s'affiche ici en temps réel.")
        card.add_widget(self.output)
        self.status = make_label("", role="hint")
        card.add_widget(self.status)
        self.column.addWidget(card)

        helper = GlassCard("AIDE CONTEXTUELLE", "help", "Tapez une option pour lire sa description (scrcpy_aide.txt)")
        self.help_edit = QLineEdit()
        self.help_edit.setPlaceholderText("--max-fps, bitrate, otg…")
        self.help_edit.textChanged.connect(self._help)
        helper.add_widget(self.help_edit)
        self.help_label = make_label("", role="dim", wrap=True)
        helper.add_widget(self.help_label)
        self.column.addWidget(helper)

    # ── journal ──
    def _reload(self, force: bool = False) -> None:
        inst = self.ctx.inst
        if force or self._loaded_id != inst.id:
            self._loaded_id = inst.id
            self.output.setPlainText("\n".join(inst.log))
        self._update_status()

    def _update_status(self) -> None:
        inst = self.ctx.inst
        if inst.running:
            self.status.setText(f"● scrcpy en cours (PID {inst.process.pid if inst.process else '?'}) — {inst.label}")
        elif inst.last_exit is not None:
            self.status.setText(f"scrcpy terminé (code {inst.last_exit}) — {inst.label}")
        else:
            self.status.setText(f"En attente — {inst.label}")

    def _clear(self) -> None:
        self.ctx.inst.log.clear()
        self.output.clear()

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.output.toPlainText())
        self.ctx.notify("info", "Sortie copiée dans le presse-papiers.")

    def _help(self, query: str) -> None:
        if not query.strip():
            self.help_label.setText("")
            return
        matches = scrcpy_help.search(query, 1)
        entry = scrcpy_help.get_entry(matches[0]) if matches else None
        self.help_label.setText(f"{entry.signature}\n\n{entry.description}" if entry else "Aucune option ne correspond.")

    def refresh_extra(self) -> None:
        """Met à jour les éléments personnalisés de la vue."""
        self._reload()

    def on_ctx_event(self, event: str, payload: Any) -> None:
        """Réagit aux événements du contexte (appareils, exécution, journal…)."""
        inst = self.ctx.inst
        if event == "line" and payload is inst and inst.log:
            self.output.appendPlainText(inst.log[-1])
        elif event == "running":
            self._reload(force=True)
        elif event == "instance":
            self._reload()

    def on_enter(self) -> None:
        """Appelé à chaque affichage de la vue."""
        super().on_enter()
        self._reload()
