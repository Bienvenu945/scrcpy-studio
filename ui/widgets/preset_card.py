"""Carte de préréglage coloré (clic = application immédiate)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui import theme
from ui.widgets import icons
from ui.widgets.glass import ClickableFrame, make_label, set_prop

_ICON = {"stream_ultra": "bolt", "record_4k": "camera", "lowlat": "rocket"}


class PresetCard(ClickableFrame):
    """Préréglage : icône ronde, nom et résumé ; bordure d'accent quand il est actif."""

    chosen = Signal(str)

    def __init__(self, key: str, label: str, subtitle: str, tone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setObjectName("PresetCard")
        self.setMinimumHeight(64)
        pal = theme.current()
        set_prop(self, "tone", tone)
        set_prop(self, "active", "false")
        color = {"blue": pal.accent_a, "violet": pal.accent_b, "green": pal.success, "orange": pal.warning}.get(tone, pal.accent_a)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(12)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(_ICON.get(key, "sliders"), color, 24))
        glyph.setFixedSize(40, 40)
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(glyph)
        text = QVBoxLayout()
        text.setSpacing(1)
        self._title = make_label(label)
        self._subtitle = make_label(subtitle, role="hint")
        for widget in (self._title, self._subtitle):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            text.addWidget(widget)
        row.addLayout(text, 1)
        self.clicked.connect(lambda: self.chosen.emit(self.key))
        self.setToolTip(f"Appliquer « {label} » ({subtitle})")

    def set_active(self, active: bool) -> None:
        """Met en avant le préréglage actif."""
        set_prop(self, "active", "true" if active else "false")
