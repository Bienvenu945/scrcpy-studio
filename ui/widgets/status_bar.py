"""Zone E (partie gauche) : pastille d'état ADB / scrcpy et bouton d'arrêt."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QFrame, QWidget

from ui import theme
from ui.widgets.controls import IconButton
from ui.widgets.glass import Dot, make_label


class StatusBar(QFrame):
    """« ● ADB Ready  [✕] » ; la pastille pulse pendant l'exécution."""

    stop_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Transparent")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._dot = Dot(theme.current().warning, 12)
        self._label = make_label("ADB…", object_name="AppTitle")
        self.stop_button = IconButton("x", "Arrêter scrcpy (Ctrl+.)", 18)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_clicked)
        row.addWidget(self._dot)
        row.addWidget(self._label)
        row.addSpacing(10)
        row.addWidget(self.stop_button)

    def set_state(self, tone: str, text: str) -> None:
        """``tone`` : success, warning, error ou running (pulsation)."""
        pal = theme.current()
        color = {"success": pal.success, "warning": pal.warning, "error": pal.error, "running": pal.accent_a}.get(tone, pal.text_muted)
        self._dot.set_color(color)
        self._dot.set_pulsing(tone == "running")
        self._label.setText(text)
        self.stop_button.setEnabled(tone == "running")
