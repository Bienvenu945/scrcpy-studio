"""Zone B3 : onglets de profils (delta de réglages par instance)."""
from __future__ import annotations

from typing import Sequence

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QPushButton, QScrollArea, QWidget

from config.defaults import MAIN_PROFILE
from ui import theme
from ui.widgets import icons
from ui.widgets.controls import IconButton
from ui.widgets.glass import set_prop


class ProfileTabs(QFrame):
    """[Vue principale] [Profil 2] … [+] ; clic droit : renommer, dupliquer, supprimer."""

    selected = Signal(str)
    add_requested = Signal()
    rename_requested = Signal(str)
    duplicate_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Tabs")
        self.setFixedHeight(48)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 5, 8, 5)
        outer.setSpacing(6)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._holder = QWidget()
        self._holder.setObjectName("Transparent")
        self._row = QHBoxLayout(self._holder)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(6)
        self._scroll.setWidget(self._holder)
        outer.addWidget(self._scroll, 1)
        self.add_button = IconButton("plus", "Nouveau profil", 16)
        self.add_button.clicked.connect(self.add_requested)
        outer.addWidget(self.add_button)

    def set_profiles(self, names: Sequence[str], current: str) -> None:
        """Reconstruit les onglets de profils."""
        pal = theme.current()
        while self._row.count():
            item = self._row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for name in names:
            active = name == current
            button = QPushButton(name)
            button.setObjectName("ProfileTab")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(icons.icon("home" if name == MAIN_PROFILE else "user", pal.accent_a if active else pal.text_dim, 16))
            set_prop(button, "active", "true" if active else "false")
            button.clicked.connect(lambda _c=False, n=name: self.selected.emit(n))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(lambda pos, n=name, b=button: self._menu(n, b.mapToGlobal(pos)))
            self._row.addWidget(button)
        self._row.addStretch(1)

    def _menu(self, name: str, global_pos: QPoint) -> None:
        menu = QMenu(self)
        rename = menu.addAction("Renommer…")
        duplicate = menu.addAction("Dupliquer")
        delete = menu.addAction("Supprimer")
        if name == MAIN_PROFILE:  # la vue principale est protégée
            rename.setEnabled(False)
            delete.setEnabled(False)
        chosen = menu.exec(global_pos)
        if chosen is rename:
            self.rename_requested.emit(name)
        elif chosen is duplicate:
            self.duplicate_requested.emit(name)
        elif chosen is delete:
            self.delete_requested.emit(name)
