"""Command Palette (Ctrl+K) : recherche floue sur actions, navigation et options scrcpy."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, QTimer, Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)

from ui import theme
from ui.context import PaletteItem, rank_items
from ui.widgets import icons
from ui.widgets.glass import Pill, make_label

MAX_RESULTS = 40
_KIND_LABEL = {"action": "Action", "nav": "Aller à", "option": "Option"}


class CommandPalette(QDialog):
    """Fenêtre flottante : ↑/↓ naviguer, Entrée valider, Échap fermer."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("Palette")
        self.resize(660, 440)
        self._items: list[PaletteItem] = []
        self._shown: list[PaletteItem] = []
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 10, 14, 10)
        column.setSpacing(6)
        head = QHBoxLayout()
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("search", theme.current().accent_a, 20))
        head.addWidget(glyph)
        self._edit = QLineEdit()
        self._edit.setObjectName("PaletteInput")
        self._edit.setPlaceholderText("Actions, vues, options scrcpy (--max-fps)…")
        self._edit.textChanged.connect(self._refilter)
        self._edit.installEventFilter(self)
        head.addWidget(self._edit, 1)
        head.addWidget(Pill("Échap"))
        column.addLayout(head)
        self._list = QListWidget()
        self._list.setObjectName("Palette")
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.itemActivated.connect(self._on_item)
        self._list.itemClicked.connect(self._on_item)
        column.addWidget(self._list, 1)
        column.addWidget(make_label("↑ ↓ naviguer  ·  Entrée valider  ·  tapez « -- » pour chercher une option", role="hint"))

    def open_palette(self, items: list[PaletteItem], initial: str = "") -> None:
        """Affiche la palette centrée sur la fenêtre parente."""
        self._items = items
        self._edit.setText(initial)
        self._refilter()
        parent = self.parentWidget().window() if self.parentWidget() else None
        if parent is not None:
            origin = parent.mapToGlobal(QPoint(0, 0))
            self.move(origin.x() + (parent.width() - self.width()) // 2, origin.y() + int(parent.height() * 0.14))
        self.show()
        self._edit.setFocus()

    def _refilter(self) -> None:
        self._shown = rank_items(self._items, self._edit.text(), MAX_RESULTS)
        self._list.clear()
        pal = theme.current()
        for entry in self._shown:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 48))
            self._list.addItem(item)
            self._list.setItemWidget(item, self._row_widget(entry, pal.accent_a))
        if self._shown:
            self._list.setCurrentRow(0)

    def _row_widget(self, entry: PaletteItem, color: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(10)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(entry.icon, color, 18))
        layout.addWidget(glyph)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(QLabel(entry.title))
        if entry.subtitle:
            subtitle = entry.subtitle if len(entry.subtitle) <= 90 else entry.subtitle[:87] + "…"
            text.addWidget(make_label(subtitle, role="hint"))
        layout.addLayout(text, 1)
        layout.addWidget(Pill(_KIND_LABEL.get(entry.kind, entry.kind)))
        row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return row

    def _move(self, step: int) -> None:
        count = self._list.count()
        if count:
            self._list.setCurrentRow((self._list.currentRow() + step) % count)

    def _on_item(self, item: QListWidgetItem) -> None:
        self._run(self._list.row(item))

    def _run(self, row: int) -> None:
        if not 0 <= row < len(self._shown):
            return
        action = self._shown[row].payload
        self.close()
        if callable(action):
            QTimer.singleShot(0, action)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self._edit and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._move(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move(-1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._run(self._list.currentRow())
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, event)
