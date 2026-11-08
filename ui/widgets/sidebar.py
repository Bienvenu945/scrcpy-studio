"""Navigation latérale : sections repliables, indicateur « liquide », carte promo, signature."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from config.defaults import SIGNATURE
from ui import theme
from ui.widgets import icons
from ui.widgets.animations import animate_geometry
from ui.widgets.glass import ClickableFrame, make_label

Entry = tuple[str, str, str]  # (clé, libellé, icône)


class SidebarItem(QPushButton):
    """Entrée de navigation (cochable, exclusive)."""

    def __init__(self, key: str, label: str, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.key = key
        self.setObjectName("SidebarItem")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        pal = theme.current()
        icon_obj = icons.icon(icon, pal.text_dim, 20)
        self.setIcon(icon_obj)
        self.setIconSize(QSize(20, 20))
        self.setMinimumHeight(40)

    def set_icon_color(self, color: str, name: str) -> None:
        """Recolore l'icône (entrée active en accent)."""
        self.setIcon(icons.icon(name, color, 20))


class Sidebar(QFrame):
    """Barre latérale (260 px) avec sections BASE / PRO / OUTILS repliables."""

    navigate = Signal(str)
    promo_clicked = Signal()
    about_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(260)
        self._items: dict[str, SidebarItem] = {}
        self._icon_of: dict[str, str] = {}
        self._current = ""
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 12, 10, 12)
        outer.setSpacing(10)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._container = QWidget()
        self._container.setObjectName("Transparent")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 4, 0)
        self._layout.setSpacing(2)
        self._indicator = QFrame(self._container)  # créé en premier : reste sous les boutons
        self._indicator.setObjectName("SidebarIndicator")
        self._indicator.hide()
        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll, 1)

        promo = ClickableFrame()
        promo.setObjectName("PromoCard")
        row = QHBoxLayout(promo)
        row.setContentsMargins(10, 10, 12, 10)
        row.setSpacing(10)
        box = QFrame()
        box.setObjectName("IconBox")
        box.setFixedSize(40, 40)
        box_layout = QHBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("wifi", theme.current().accent_a, 22))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(glyph)
        row.addWidget(box)
        row.addWidget(make_label("Plus de possibilités avec Scrcpy !", role="dim", wrap=True), 1)
        chevron = QLabel()
        chevron.setPixmap(icons.pixmap("chevron-right", theme.current().text_dim, 16))
        row.addWidget(chevron)
        promo.clicked.connect(self.promo_clicked)
        outer.addWidget(promo)

        signature = QPushButton(SIGNATURE)
        signature.setObjectName("Link")
        signature.setToolTip("À propos de Scrcpy Studio")
        signature.setCursor(Qt.CursorShape.PointingHandCursor)
        signature.clicked.connect(self.about_clicked)
        outer.addWidget(signature, 0, Qt.AlignmentFlag.AlignHCenter)

    # ── contenu ──
    def set_entries(self, sections: list[tuple[str, list[Entry]]], current: str = "") -> None:
        """Remplace les sections ; ``current`` est sélectionné s'il existe."""
        for button in list(self._group.buttons()):
            self._group.removeButton(button)
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._items.clear()
        self._icon_of.clear()
        for title, entries in sections:
            header = QPushButton(title)
            header.setObjectName("SidebarSection")
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            header.setIcon(icons.icon("chevron-up", theme.current().text_muted, 14))
            holder = QWidget()
            holder.setObjectName("Transparent")
            holder_layout = QVBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 6)
            holder_layout.setSpacing(2)
            for key, label, icon in entries:
                item = SidebarItem(key, label, icon)
                item.clicked.connect(lambda _checked=False, k=key: self._on_clicked(k))
                self._group.addButton(item)
                self._items[key] = item
                self._icon_of[key] = icon
                holder_layout.addWidget(item)
            header.clicked.connect(lambda _checked=False, h=header, w=holder: self._toggle(h, w))
            self._layout.addWidget(header)
            self._layout.addWidget(holder)
        self._layout.addStretch(1)
        self._indicator.hide()
        if current:
            self.select(current, animate=False)

    def _toggle(self, header: QPushButton, holder: QWidget) -> None:
        visible = not holder.isVisible()
        holder.setVisible(visible)
        header.setIcon(icons.icon("chevron-up" if visible else "chevron-down", theme.current().text_muted, 14))
        QTimer.singleShot(0, lambda: self._sync_indicator(False))

    def _on_clicked(self, key: str) -> None:
        self.select(key, animate=True)
        self.navigate.emit(key)

    # ── sélection ──
    def current(self) -> str:
        """Clé sélectionnée."""
        return self._current

    def select(self, key: str, animate: bool = True) -> None:
        """Sélectionne ``key`` (sans émettre) et déplace l'indicateur."""
        pal = theme.current()
        for k, item in self._items.items():
            item.set_icon_color(pal.accent_a if k == key else pal.text_dim, self._icon_of[k])
        item = self._items.get(key)
        if item is None:
            self._indicator.hide()
            self._current = ""
            return
        item.setChecked(True)
        self._current = key
        self._sync_indicator(animate)

    def _sync_indicator(self, animate: bool = False) -> None:
        item = self._items.get(self._current)
        if item is None or not item.isVisible():
            self._indicator.hide()
            return
        top_left = item.mapTo(self._container, QPoint(0, 0))
        target = QRect(top_left, item.size())
        first_time = not self._indicator.isVisible()
        self._indicator.show()
        if animate and not first_time:
            animate_geometry(self._indicator, target)
        else:
            self._indicator.setGeometry(target)
        self._indicator.lower()

    def resizeEvent(self, event) -> None:  # noqa: N802, ANN001
        super().resizeEvent(event)
        QTimer.singleShot(0, lambda: self._sync_indicator(False))

    def showEvent(self, event) -> None:  # noqa: N802, ANN001
        super().showEvent(event)
        QTimer.singleShot(0, lambda: self._sync_indicator(False))
