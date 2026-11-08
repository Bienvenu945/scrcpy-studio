"""Vue Debug (PRO) : niveau de log, listes scrcpy, validation, recherche dans l'aide."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit

from core import scrcpy_help
from core.process import run_async
from core.scrcpy import LIST_ACTIONS
from ui.rows import CardSpec, choice, toggle
from ui.views.base_view import BaseView
from ui.widgets.controls import GlassButton
from ui.widgets.glass import GlassCard, make_label

_LISTS = (("apps", "Applications", "list"), ("cameras", "Caméras", "camera"), ("camera-sizes", "Tailles caméra", "crop"),
          ("displays", "Écrans", "monitor"), ("encoders", "Encodeurs", "film"))


class DebugView(BaseView):
    """Diagnostic et exploration de l'aide scrcpy."""

    KEY = "debug"
    TITLE = "Debug"
    SUBTITLE = "Journaux, listes de l'appareil, validation et aide des options"
    CARDS = (
        CardSpec("JOURNAUX", "bug", (
            choice("verbosity", "Niveau de détail", "verbosity", "--verbosity"),
            toggle("print_fps", "Afficher les FPS dans la console", "--print-fps", "Alimente aussi l'indicateur FPS de l'interface"),
            toggle("no_terminal_title", "Ne pas modifier le titre du terminal", "--no-terminal-title"),
        )),
    )
    EXTRA_OPTS = "--list-apps --list-cameras --list-camera-sizes --list-displays --list-encoders --help --version"

    def build_extra(self) -> None:
        # ── listes scrcpy ──
        """Cartes personnalisées placées après les cartes déclaratives."""
        lists = GlassCard("LISTES SCRCPY", "list", "Exécute scrcpy --list-… pour l'appareil de cette instance")
        row = QHBoxLayout()
        row.setSpacing(8)
        for action, label, icon in _LISTS:
            button = GlassButton(label, icon)
            button.setToolTip(LIST_ACTIONS[action])
            button.clicked.connect(lambda _c=False, a=action: self._run_list(a))
            row.addWidget(button)
        for label, flag in (("Version", "--version"), ("Aide", "--help")):
            button = GlassButton(label, "info", "ghost")
            button.clicked.connect(lambda _c=False, f=flag: self._run_flag(f))
            row.addWidget(button)
        row.addStretch(1)
        lists.add_layout(row)
        self.output = QPlainTextEdit()
        self.output.setObjectName("Mono")
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(220)
        self.output.setPlaceholderText("La sortie apparaît ici…")
        lists.add_widget(self.output)
        self.column.addWidget(lists)

        # ── validation ──
        check = GlassCard("VALIDATION DE LA CONFIGURATION", "check")
        self.issues_label = make_label("", wrap=True)
        check.add_widget(self.issues_label)
        self.column.addWidget(check)

        # ── recherche ──
        search = GlassCard("RECHERCHE DANS L'AIDE SCRCPY", "search", "Les 108 options de scrcpy 4.1, avec leur description")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Ex. bitrate, camera, --otg…")
        self.search_edit.textChanged.connect(self._search)
        search.add_widget(self.search_edit)
        self.results = QListWidget()
        self.results.setMinimumHeight(150)
        self.results.currentItemChanged.connect(self._show_description)
        search.add_widget(self.results)
        self.description = make_label("", role="dim", wrap=True)
        self.description.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        search.add_widget(self.description)
        self.column.addWidget(search)
        self._search("")

    # ── listes ──
    def _run_list(self, action: str) -> None:
        runner = self.ctx.manager.runner()
        settings = self.ctx.settings()
        self.output.setPlainText(f"scrcpy {LIST_ACTIONS[action]} …")
        self._execute(lambda: runner.run_list(settings, action))

    def _run_flag(self, flag: str) -> None:
        from core.process import run_command
        exe = self.ctx.scrcpy_path()
        self.output.setPlainText(f"scrcpy {flag} …")
        if exe is None:
            self.output.setPlainText("scrcpy est introuvable (Paramètres › Chemins).")
            return

        def work() -> str:
            result = run_command([exe, flag], timeout=15)
            return (result.stdout + result.stderr).strip() or result.error

        self._execute(work)

    def _execute(self, work: Any) -> None:
        def done(value: Any, error: BaseException | None) -> None:
            self.output.setPlainText(str(value) if error is None else f"Erreur : {error}")

        run_async(work, done, dispatcher=self.ctx.dispatcher)

    # ── recherche ──
    def _search(self, query: str) -> None:
        self.results.clear()
        for key in scrcpy_help.search(query, 60):
            entry = scrcpy_help.get_entry(key)
            item = QListWidgetItem(entry.signature if entry else key)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)
        else:
            self.description.setText("Aucune option ne correspond.")

    def _show_description(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        entry = scrcpy_help.get_entry(str(item.data(Qt.ItemDataRole.UserRole)))
        self.description.setText(entry.description if entry else "")

    # ── validation ──
    def refresh_extra(self) -> None:
        """Met à jour les éléments personnalisés de la vue."""
        issues = self.ctx.issues()
        if not issues:
            self.issues_label.setText("✓ Aucune incohérence détectée.")
            return
        marks = {"error": "✗", "warn": "⚠", "info": "ℹ"}
        self.issues_label.setText("\n".join(f"{marks.get(i.level, '•')} {i.message}" for i in issues))
