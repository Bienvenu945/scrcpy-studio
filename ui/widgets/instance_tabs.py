"""Zone B2 : onglets d'instances (une session indépendante par onglet)."""
from __future__ import annotations

from typing import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QScrollArea, QWidget

from ui import theme
from ui.widgets import icons
from ui.widgets.controls import GlassButton, IconButton
from ui.widgets.glass import set_prop

InstanceInfo = tuple[str, str, bool]  # (id, libellé, en cours d'exécution)


class _Tab(QFrame):
    def __init__(self, instance_id: str, label: str, running: bool, active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InstTab")
        set_prop(self, "active", "true" if active else "false")
        pal = theme.current()
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 4, 0)
        row.setSpacing(2)
        self.button = QPushButton(("● " if running else "") + label)
        self.button.setObjectName("TabBtn")
        self.button.setIcon(icons.icon("phone", pal.accent_a if active else pal.text_dim, 18))
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_prop(self.button, "active", "true" if active else "false")
        self.close_button = IconButton("x", "Fermer cette instance (Ctrl+W)", 14, object_name="TabClose")
        row.addWidget(self.button)
        row.addWidget(self.close_button)
        self.instance_id = instance_id


class InstanceTabs(QFrame):
    """Rangée d'onglets : sélection, fermeture et « + New Instance »."""

    selected = Signal(str)
    closed = Signal(str)
    new_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Tabs")
        self.setFixedHeight(60)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._holder = QWidget()
        self._holder.setObjectName("Transparent")
        self._row = QHBoxLayout(self._holder)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(8)
        self._scroll.setWidget(self._holder)
        outer.addWidget(self._scroll, 1)
        self.new_button = GlassButton("New Instance", "plus")
        self.new_button.clicked.connect(self.new_requested)
        outer.addWidget(self.new_button)

    def set_instances(self, instances: Sequence[InstanceInfo], current_id: str, can_add: bool = True) -> None:
        """Reconstruit les onglets."""
        while self._row.count():
            item = self._row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for instance_id, label, running in instances:
            tab = _Tab(instance_id, label, running, instance_id == current_id)
            tab.button.clicked.connect(lambda _c=False, i=instance_id: self.selected.emit(i))
            tab.close_button.clicked.connect(lambda _c=False, i=instance_id: self.closed.emit(i))
            self._row.addWidget(tab)
        self._row.addStretch(1)
        self.new_button.setEnabled(can_add)
        self.new_button.setToolTip("Nouvelle instance (Ctrl+T)" if can_add else "Limite d'instances atteinte")
