"""Aperçu du téléphone (capture adb en cache) et actions rapides."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QMenu, QPushButton, QVBoxLayout, QWidget

from config.defaults import default_records_dir
from core.process import run_async
from ui import theme
from ui.context import Context
from ui.widgets import icons
from ui.widgets.glass import set_prop


class PhonePreview(QFrame):
    """Capture d'écran de l'appareil (adb exec-out screencap), rafraîchie toutes les 3 s si scrcpy est inactif."""

    def __init__(self, ctx: Context, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("Inset")
        self.setMinimumSize(220, 280)
        self._png: bytes | None = None
        self._pixmap: QPixmap | None = None
        self._caption = "Aperçu indisponible"
        self._busy = False
        self._timer = QTimer(self)
        self._timer.setInterval(ctx.preview_interval_ms)
        self._timer.timeout.connect(self.refresh)

    def png(self) -> bytes | None:
        """Dernière capture PNG en cache."""
        return self._png

    def set_png(self, data: bytes | None) -> None:
        """Définit l'image affichée (None : espace réservé)."""
        self._png = data
        self._pixmap = None
        if data:
            pixmap = QPixmap()
            if pixmap.loadFromData(data, "PNG"):
                self._pixmap = pixmap
        self.update()

    def refresh(self, force: bool = False) -> None:
        """Lance une capture asynchrone si l'aperçu est utile (visible, appareil libre)."""
        if not (self.isVisible() or force):
            return
        if not self.ctx.pref("preview_enabled"):
            self._caption = "Aperçu désactivé"
            self.set_png(None)
            return
        inst = self.ctx.inst
        serial = inst.device.serial if inst.device else ""
        if not serial:
            self._caption = "Aucun appareil"
            self.set_png(None)
            return
        if inst.running and not force:
            return  # scrcpy affiche déjà l'écran : on garde la dernière image
        if self._busy:
            return
        self._busy = True

        def done(value: object, error: BaseException | None) -> None:
            self._busy = False
            if value:
                self.set_png(value)  # type: ignore[arg-type]
            elif self._png is None:
                self._caption = "Capture impossible"
                self.update()

        run_async(lambda: self.ctx.adb.screencap(serial), done, dispatcher=self.ctx.dispatcher, name="scrcpy-studio-preview")

    def save_capture(self, folder: Path | None = None) -> Path | None:
        """Enregistre la capture en cache en PNG horodaté ; renvoie le chemin."""
        if not self._png:
            return None
        base = folder or (Path(self.ctx.prefs.records_dir) if self.ctx.prefs.records_dir else default_records_dir())
        target = base / "captures"
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"capture_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path.write_bytes(self._png)
        return path

    def showEvent(self, event) -> None:  # noqa: N802, ANN001
        super().showEvent(event)
        self._timer.start()
        QTimer.singleShot(0, self.refresh)

    def hideEvent(self, event) -> None:  # noqa: N802, ANN001
        super().hideEvent(event)
        self._timer.stop()

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        super().paintEvent(event)
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area = self.rect().adjusted(14, 14, -14, -14)
        if self._pixmap is not None and not self._pixmap.isNull():
            size = self._pixmap.size().scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
            rect = QRect(QPoint(area.x() + (area.width() - size.width()) // 2, area.y() + (area.height() - size.height()) // 2), size)
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), 16, 16)
            p.setClipPath(path)
            p.drawPixmap(rect, self._pixmap)
            p.setClipping(False)
            p.setPen(QPen(QColor(pal.border_active), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(rect), 16, 16)
            return
        width = min(area.width(), int(area.height() * 0.48))
        height = int(width / 0.48)
        phone = QRect(area.center().x() - width // 2, area.center().y() - height // 2, width, height)
        pen = QPen(QColor(pal.text_muted), 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(phone), 16, 16)
        p.setPen(QColor(pal.text_dim))
        flags = int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap)
        p.drawText(phone, flags, self._caption)


class QuickActions(QFrame):
    """Colonne d'actions : plein écran, rotation, capture, paramètres avancés."""

    fullscreen_toggled = Signal()
    rotation_chosen = Signal(str)
    capture_clicked = Signal()
    advanced_clicked = Signal()

    ROTATIONS = (("", "Orientation par défaut"), ("90", "Rotation 90°"), ("180", "Rotation 180°"), ("270", "Rotation 270°"))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Transparent")
        pal = theme.current()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        self._rotation = ""
        self._buttons: dict[str, QPushButton] = {}
        for key, label, icon in (("fullscreen", "Plein écran", "fullscreen"), ("rotation", "Rotation", "rotate"),
                                 ("capture", "Capture d'écran", "camera"), ("advanced", "Paramètres avancés", "gear")):
            button = QPushButton(label)
            button.setObjectName("ActionRow")
            button.setIcon(icons.icon(icon, pal.text_dim, 18))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            column.addWidget(button)
            self._buttons[key] = button
        column.addStretch(1)
        self._buttons["fullscreen"].clicked.connect(self.fullscreen_toggled)
        self._buttons["rotation"].clicked.connect(self._open_rotation_menu)
        self._buttons["capture"].clicked.connect(self.capture_clicked)
        self._buttons["advanced"].clicked.connect(self.advanced_clicked)

    def set_state(self, fullscreen: bool, rotation: str) -> None:
        """Reflète l'état courant (plein écran actif, rotation choisie)."""
        set_prop(self._buttons["fullscreen"], "active", "true" if fullscreen else "false")
        set_prop(self._buttons["rotation"], "active", "true" if rotation else "false")
        self._rotation = rotation

    def _open_rotation_menu(self) -> None:
        menu = QMenu(self)
        actions = {}
        for value, label in self.ROTATIONS:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == self._rotation)
            actions[action] = value
        button = self._buttons["rotation"]
        chosen = menu.exec(button.mapToGlobal(QPoint(0, button.height())))
        if chosen in actions:
            self.rotation_chosen.emit(actions[chosen])
