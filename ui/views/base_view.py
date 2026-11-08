"""BaseView : page défilante à cartes déclaratives, liée au Context."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFrame, QHBoxLayout, QMessageBox, QScrollArea, QVBoxLayout, QWidget

from core import scrcpy_help
from ui.context import Context
from ui.rows import CardSpec, Row, option_names
from ui.widgets.controls import GlassButton, make_control
from ui.widgets.glass import GlassCard, SettingRow, make_label

__all__ = ["BaseView", "Context", "CardSpec", "Row", "confirm"]


def confirm(parent: QWidget, title: str, text: str) -> bool:
    """Boîte de confirmation Oui/Non (Non par défaut)."""
    box = QMessageBox.question(parent, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                               QMessageBox.StandardButton.No)
    return box == QMessageBox.StandardButton.Yes


class BaseView(QWidget):
    """Page : titre, sous-titre, cartes générées depuis ``CARDS`` puis cartes personnalisées.

    Hooks : ``build_top`` (avant les cartes déclaratives), ``build_extra`` (après),
    ``refresh_extra`` (après chaque rafraîchissement), ``on_ctx_event`` (événements du contexte).
    """

    KEY = ""
    TITLE = ""
    SUBTITLE = ""
    CARDS: tuple[CardSpec, ...] = ()
    #: Options scrcpy accessibles via des boutons (non couvertes par des lignes) — pour la vérification de couverture.
    EXTRA_OPTS = ""
    #: Montrer le bouton « Réinitialiser » si la vue a des réglages de session.
    RESETTABLE = True

    def __init__(self, ctx: Context, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._rows: list[tuple[Row, SettingRow, QWidget]] = []
        self._busy = False
        self._stale = False
        self._build()
        ctx.subscribe(self._on_event)
        self.refresh()

    # ── introspection (sans Qt) ──
    @classmethod
    def row_specs(cls) -> list[Row]:
        """Toutes les lignes déclarées."""
        return [row for card in cls.CARDS for row in card.rows]

    @classmethod
    def covered_options(cls) -> set[str]:
        """Options scrcpy documentées par cette vue (lignes + boutons)."""
        names = {name for row in cls.row_specs() for name in option_names(row)}
        return names | set(cls.EXTRA_OPTS.split())

    @classmethod
    def covered_fields(cls) -> set[str]:
        """Champs de ``Settings`` modifiés par cette vue."""
        return {row.field for row in cls.row_specs() if row.target == "settings"}

    # ── construction ──
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner.setObjectName("Transparent")
        self.column = QVBoxLayout(inner)
        self.column.setContentsMargins(4, 6, 12, 18)
        self.column.setSpacing(14)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(make_label(self.TITLE, object_name="PageTitle"))
        if self.SUBTITLE:
            titles.addWidget(make_label(self.SUBTITLE, object_name="PageSub", wrap=True))
        head.addLayout(titles, 1)
        self.reset_button = GlassButton("Réinitialiser", "refresh", "ghost")
        self.reset_button.setToolTip("Remet les réglages de cette vue à leurs valeurs par défaut")
        self.reset_button.clicked.connect(self.reset_view)
        self.reset_button.setVisible(self.RESETTABLE and any(r.target == "settings" for r in self.row_specs()))
        head.addWidget(self.reset_button)
        self.column.addLayout(head)

        self.build_top()
        for spec in self.CARDS:
            self.column.addWidget(self.add_card(spec))
        self.build_extra()
        self.column.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll)

    def add_card(self, spec: CardSpec) -> GlassCard:
        """Construit une carte (repliable) depuis ``spec`` et ses lignes."""
        card = GlassCard(spec.title, spec.icon, spec.subtitle, collapsible=True)
        for row in spec.rows:
            self.add_row(card, row)
        if spec.collapsed:
            card.set_collapsed(True)
        return card

    def add_row(self, card: GlassCard, row: Row) -> SettingRow:
        """Ajoute une ligne de réglage à ``card`` et la relie au contexte."""
        control = make_control(row)
        setting_row = SettingRow(row.label, control, row.hint, self._tooltip(row))
        card.add_widget(setting_row)
        control.changed.connect(lambda value, r=row: self._on_changed(r, value))
        self._rows.append((row, setting_row, control))
        return setting_row

    @staticmethod
    def _tooltip(row: Row) -> str:
        names = option_names(row)
        if not names:
            return ""
        description = scrcpy_help.get_description(names[0])
        return f"{' '.join(names)}\n{description}" if description else " ".join(names)

    # ── hooks ──
    def build_top(self) -> None:
        """Cartes personnalisées placées avant les cartes déclaratives."""

    def build_extra(self) -> None:
        """Cartes personnalisées placées après les cartes déclaratives."""

    def refresh_extra(self) -> None:
        """Mise à jour des éléments personnalisés."""

    def on_ctx_event(self, event: str, payload: Any) -> None:
        """Événements du contexte non gérés par la base (devices, running, line, metrics…)."""

    # ── valeurs ──
    def _read(self, row: Row) -> Any:
        return self.ctx.pref(row.field) if row.target == "prefs" else self.ctx.value(row.field)

    def _on_changed(self, row: Row, value: Any) -> None:
        self._busy = True
        try:
            result = self.ctx.set_pref(row.field, value) if row.target == "prefs" else self.ctx.set_value(row.field, value)
        finally:
            self._busy = False
        if row.kind not in ("text", "path", "textarea"):
            for r, _sr, control in self._rows:
                if r is row:
                    control.setValue(result)  # reflète une éventuelle correction (bornes)
        self.update_state()
        self.refresh_extra()

    def refresh(self) -> None:
        """Recharge toutes les valeurs depuis le contexte."""
        self._stale = False
        for row, _setting_row, control in self._rows:
            control.setValue(self._read(row))
        self.update_state()
        self.refresh_extra()

    def update_state(self) -> None:
        """Active/désactive les lignes conditionnelles."""
        settings = self.ctx.settings()
        for row, setting_row, _control in self._rows:
            if row.enabled_if is not None:
                setting_row.setEnabled(bool(row.enabled_if(settings)))

    def on_enter(self) -> None:
        """Appelé à chaque affichage de la vue."""
        if self._stale:
            self.refresh()

    def _on_event(self, event: str, payload: Any) -> None:
        if event in ("values", "instance", "prefs"):
            if self._busy:
                self.update_state()
            elif self.isVisible():
                self.refresh()
            else:
                self._stale = True
        self.on_ctx_event(event, payload)

    # ── réinitialisation ──
    def reset_view(self) -> None:
        """Remet les réglages de la vue à leurs valeurs par défaut (après confirmation)."""
        fields = sorted({r.field for r, _s, _c in self._rows if r.target == "settings"})
        if fields and confirm(self, "Réinitialiser", f"Remettre les {len(fields)} réglages de « {self.TITLE} » à leurs valeurs par défaut ?"):
            self.ctx.reset_fields(fields)
