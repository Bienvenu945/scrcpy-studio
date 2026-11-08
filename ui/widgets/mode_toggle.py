"""Bascule BASE / PRO."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget


class ModeToggle(QFrame):
    """Segment [BASE | PRO] ; ``changed`` n'est émis que sur action de l'utilisateur."""

    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModeToggle")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._buttons: dict[str, QPushButton] = {}
        self._loading = False
        for mode, label in (("base", "BASE"), ("pro", "PRO")):
            button = QPushButton(label)
            button.setObjectName("ModeBtn")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.toggled.connect(lambda on, m=mode: self._on_toggled(on, m))
            self._group.addButton(button)
            self._buttons[mode] = button
            layout.addWidget(button)
        self._buttons["base"].setChecked(True)

    def _on_toggled(self, on: bool, mode: str) -> None:
        if on and not self._loading:
            self.changed.emit(mode)

    def mode(self) -> str:
        """Mode actif."""
        return "pro" if self._buttons["pro"].isChecked() else "base"

    def set_mode(self, mode: str) -> None:
        """Sélectionne un mode sans émettre."""
        self._loading = True
        self._buttons.get(mode, self._buttons["base"]).setChecked(True)
        self._loading = False
