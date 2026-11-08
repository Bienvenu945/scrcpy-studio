"""Zone A : barre supérieure (72 px) — menu, logo, titre, mode, recherche, état, fenêtre."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from config.defaults import APP_NAME
from ui import theme
from ui.widgets import icons
from ui.widgets.controls import IconButton
from ui.widgets.glass import ClickableFrame, Pill, make_label
from ui.widgets.mode_toggle import ModeToggle


class LogoMark(QWidget):
    """Pastille dégradée avec éclair."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(42, 42)

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor(pal.accent_a))
        grad.setColorAt(1.0, QColor(pal.accent_b))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)
        pm = icons.pixmap("bolt", pal.text_on_accent, 24, 2.0)
        p.drawPixmap((self.width() - 24) // 2, (self.height() - 24) // 2, pm)


class SearchBox(ClickableFrame):
    """Faux champ de recherche qui ouvre la Command Palette."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Inset")
        self.setMinimumWidth(300)
        self.setMaximumWidth(560)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(44)
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 10, 0)
        row.setSpacing(10)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("search", theme.current().text_dim, 18))
        row.addWidget(glyph)
        row.addWidget(make_label("Search / Command Palette...", role="dim"), 1)
        row.addWidget(Pill("Ctrl+K"))


class TitleBar(QFrame):
    """Barre supérieure : déplacement de la fenêtre, boutons système, mode BASE/PRO."""

    menu_clicked = Signal()
    search_clicked = Signal()
    settings_clicked = Signal()
    bell_clicked = Signal()
    mode_changed = Signal(str)

    def __init__(self, version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(72)
        pal = theme.current()
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(14)

        menu = IconButton("menu", "Afficher/masquer la barre latérale (Ctrl+B)", 20)
        menu.clicked.connect(self.menu_clicked)
        row.addWidget(menu)
        row.addWidget(LogoMark())
        row.addWidget(make_label(APP_NAME, object_name="AppTitle"))
        row.addWidget(Pill(f"v{version}", "accent"))
        self.mode_toggle = ModeToggle()
        self.mode_toggle.changed.connect(self.mode_changed)
        row.addWidget(self.mode_toggle)
        row.addStretch(1)
        self.search = SearchBox()
        self.search.clicked.connect(self.search_clicked)
        row.addWidget(self.search, 3)
        row.addStretch(1)

        self.live = Pill("● Live", "success")
        row.addWidget(self.live)
        self.bell = IconButton("bell", "Notifications", 20)
        self.bell.clicked.connect(self.bell_clicked)
        row.addWidget(self.bell)
        gear = IconButton("gear", "Paramètres (Ctrl+,)", 20)
        gear.clicked.connect(self.settings_clicked)
        row.addWidget(gear)
        divider = QFrame()
        divider.setObjectName("VDivider")
        divider.setFixedHeight(28)
        row.addWidget(divider)
        self._min = IconButton("minus", "Réduire", 18)
        self._max = IconButton("square", "Agrandir", 16)
        self._close = IconButton("x", "Fermer", 18, object_name="WinClose")
        self._min.clicked.connect(lambda: self.window().showMinimized())
        self._max.clicked.connect(self.toggle_maximized)
        self._close.clicked.connect(lambda: self.window().close())
        for button in (self._min, self._max, self._close):
            row.addWidget(button)
        self._pal_text_dim = pal.text_dim

    # ── état ──
    def set_live(self, live: bool) -> None:
        """Indicateur « Live » (métriques en cours de mise à jour)."""
        self.live.setText("● Live" if live else "○ Idle")
        self.live.set_tone("success" if live else "")

    def set_unread(self, count: int) -> None:
        """Colore la cloche s'il y a des notifications non lues."""
        pal = theme.current()
        self.bell.setIcon(icons.icon("bell", pal.warning if count else pal.text_dim, 20))
        self.bell.setToolTip(f"Notifications ({count} nouvelle(s))" if count else "Notifications")

    def set_maximized(self, maximized: bool) -> None:
        """Adapte l'icône agrandir/restaurer."""
        self._max.setIcon(icons.icon("restore" if maximized else "square", self._pal_text_dim, 16))

    def toggle_maximized(self) -> None:
        """Agrandit ou restaure la fenêtre."""
        window = self.window()
        window.showNormal() if window.isMaximized() else window.showMaximized()

    # ── déplacement de la fenêtre ──
    def mousePressEvent(self, event) -> None:  # noqa: N802, ANN001
        if event.button() == Qt.MouseButton.LeftButton and not self.window().isMaximized():
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802, ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
        super().mouseDoubleClickEvent(event)
