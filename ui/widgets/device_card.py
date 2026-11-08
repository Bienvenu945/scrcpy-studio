"""Carte appareil enrichie (nom, état, liaison, FPS / latence / batterie)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.metrics import Metrics
from core.models import Device
from ui import theme
from ui.widgets import icons
from ui.widgets.controls import IconButton
from ui.widgets.glass import Dot, make_label


def _icon_box(name: str, size: int = 28) -> QFrame:
    box = QFrame()
    box.setObjectName("IconBox")
    box.setFixedSize(size + 24, size + 24)
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    glyph = QLabel()
    glyph.setPixmap(icons.pixmap(name, theme.current().accent_a, size))
    glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(glyph)
    return box


def _vdivider() -> QFrame:
    divider = QFrame()
    divider.setObjectName("VDivider")
    divider.setFixedHeight(40)
    return divider


class DeviceCard(QFrame):
    """Appareil courant : identité, statut de connexion et métriques live."""

    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 14, 12, 14)
        row.setSpacing(16)
        row.addWidget(_icon_box("phone"))
        names = QVBoxLayout()
        names.setSpacing(2)
        self._name = make_label("Aucun appareil", object_name="AppTitle")
        self._model = make_label("Branchez un appareil en USB ou connectez-le en Wi-Fi", role="dim")
        names.addWidget(self._name)
        names.addWidget(self._model)
        row.addLayout(names, 1)
        row.addWidget(_vdivider())
        status = QVBoxLayout()
        status.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(0)
        self._dot = Dot(theme.current().text_muted, 8)
        self._status = make_label("Déconnecté")
        head.addWidget(self._dot)
        head.addWidget(self._status)
        head.addStretch(1)
        status.addLayout(head)
        self._link = make_label("—", role="hint")
        status.addWidget(self._link)
        row.addLayout(status)
        row.addWidget(_vdivider())
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("activity", theme.current().success, 22))
        row.addWidget(glyph)
        metrics = QVBoxLayout()
        metrics.setSpacing(2)
        self._fps = make_label("FPS: —")
        self._latency = make_label("Latence: —", role="hint")
        metrics.addWidget(self._fps)
        metrics.addWidget(self._latency)
        row.addLayout(metrics)
        refresh = IconButton("refresh", "Actualiser la liste des appareils", 18)
        refresh.clicked.connect(self.refresh_requested)
        row.addWidget(refresh)

    def set_state(self, device: Device | None, adb_ok: bool | None, running: bool, metrics: Metrics) -> None:
        """Met à jour la carte."""
        pal = theme.current()
        if device is None:
            self._name.setText("Aucun appareil")
            self._model.setText("ADB introuvable" if adb_ok is False else "Branchez un appareil en USB ou connectez-le en Wi-Fi")
            self._dot.set_color(pal.error if adb_ok is False else pal.text_muted)
            self._status.setText("Déconnecté")
            self._link.setText("—")
        else:
            self._name.setText(device.label)
            self._model.setText(device.model or device.serial)
            ok = device.online
            self._dot.set_color(pal.success if ok else pal.warning)
            self._status.setText("Connecté" if ok else device.state.capitalize())
            self._link.setText(f"{device.link} · ADB {'Online' if ok else 'Offline'}")
        self._dot.set_pulsing(running)
        self._fps.setText(f"FPS: {metrics.fps:g}" if metrics.fps is not None else "FPS: —")
        self._latency.setText(f"Latence: {metrics.latency_ms:g}ms" if metrics.latency_ms is not None else "Latence: —")
