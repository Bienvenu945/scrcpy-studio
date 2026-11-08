"""Zone E (partie centrale) : commande générée en direct."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QWidget

from ui import theme
from ui.widgets import icons
from ui.widgets.glass import make_label


class CommandBar(QFrame):
    """Champ « >_ Command: "scrcpy …" » en lecture seule (texte sélectionnable)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Inset")
        self.setFixedHeight(48)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(10)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("terminal", theme.current().accent_a, 18))
        row.addWidget(glyph)
        row.addWidget(make_label("Command:", role="dim"))
        self._edit = QLineEdit()
        self._edit.setObjectName("CommandText")
        self._edit.setReadOnly(True)
        row.addWidget(self._edit, 1)

    def set_text(self, command: str) -> None:
        """Affiche la commande entre guillemets."""
        self._edit.setText(f'"{command}"')
        self._edit.setCursorPosition(0)
        self._edit.setToolTip(command)

    def text(self) -> str:
        """Commande affichée (sans guillemets)."""
        return self._edit.text().strip('"')
