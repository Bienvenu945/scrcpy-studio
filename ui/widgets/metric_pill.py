"""Tuile de métrique (icône, titre, valeur)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui import theme
from ui.widgets import icons
from ui.widgets.glass import make_label


class MetricPill(QFrame):
    """Tuile « icône + titre + valeur » (verticale dans le panneau, horizontale ailleurs)."""

    def __init__(self, icon: str, title: str, value: str = "—", color: str = "", vertical: bool = True,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Metric")
        pal = theme.current()
        self._icon_name = icon
        self._color = color or pal.accent_a
        self._icon = QLabel()
        self._icon.setPixmap(icons.pixmap(icon, self._color, 22))
        self._title = make_label(title, role="hint")
        self._value = make_label(value, role="value")
        if vertical:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 10, 8, 10)
            layout.setSpacing(2)
            for widget in (self._icon, self._title, self._value):
                layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
        else:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(12, 8, 14, 8)
            layout.setSpacing(10)
            layout.addWidget(self._icon)
            text = QVBoxLayout()
            text.setSpacing(0)
            text.addWidget(self._title)
            text.addWidget(self._value)
            layout.addLayout(text)

    def set_value(self, text: str, color: str = "") -> None:
        """Met à jour la valeur affichée (et éventuellement la couleur de l'icône)."""
        self._value.setText(text)
        if color and color != self._color:
            self._color = color
            self._icon.setPixmap(icons.pixmap(self._icon_name, color, 22))
