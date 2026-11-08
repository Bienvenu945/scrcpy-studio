"""Zone D : panneau contexte (état connexion, aperçu de commande, infos appareil)."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.metrics import Metrics
from core.models import Device
from ui import theme
from ui.widgets.controls import GlassButton, IconButton
from ui.widgets.glass import GlassCard, Pill, make_label
from ui.widgets.metric_pill import MetricPill

MAX_PREVIEW_LINES = 12


def preview_html(lines: list[str]) -> str:
    """Aperçu de commande en HTML (numéros de ligne, ``$ scrcpy`` coloré)."""
    pal = theme.current()
    shown = lines[:MAX_PREVIEW_LINES]
    rows = []
    for number, line in enumerate(shown, start=1):
        text = html.escape(line).replace(" ", "&nbsp;")
        if line.startswith("$ scrcpy"):
            text = text.replace("$", f'<span style="color:{pal.accent_a}">$</span>', 1).replace(
                "scrcpy", f'<span style="color:{pal.accent_b}">scrcpy</span>', 1)
        rows.append(f'<tr><td align="right" style="color:{pal.text_muted}">{number}&nbsp;&nbsp;</td><td>{text}</td></tr>')
    if len(lines) > len(shown):
        rows.append(f'<tr><td></td><td style="color:{pal.text_muted}">… +{len(lines) - len(shown)} ligne(s)</td></tr>')
    return f'<table cellspacing="2">{"".join(rows)}</table>'


class InfoPanel(QFrame):
    """Panneau de droite (280 px), masquable avec Ctrl+D."""

    copy_requested = Signal()
    preset_requested = Signal()
    more_info_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InfoPanel")
        self.setFixedWidth(280)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)
        pal = theme.current()

        # ── état connexion ──
        self.connection = GlassCard("ÉTAT CONNEXION", "phone")
        self._status = Pill("Déconnecté")
        self.connection.add_widget(self._status)
        tiles = QHBoxLayout()
        tiles.setSpacing(8)
        self.fps = MetricPill("bolt", "FPS", color=pal.accent_a)
        self.latency = MetricPill("wifi", "Latence", color=pal.accent_b)
        self.battery = MetricPill("battery", "Batterie", color=pal.success)
        for tile in (self.fps, self.latency, self.battery):
            tiles.addWidget(tile, 1)
        self.connection.add_layout(tiles)
        column.addWidget(self.connection)

        # ── aperçu de commande ──
        self.command = GlassCard("COMMAND PREVIEW", "terminal")
        copy = IconButton("copy", "Copier la commande", 16)
        copy.clicked.connect(self.copy_requested)
        self.command.add_action(copy)
        inset = QFrame()
        inset.setObjectName("Inset")
        inset_layout = QVBoxLayout(inset)
        inset_layout.setContentsMargins(10, 8, 10, 8)
        self._code = QLabel()
        self._code.setObjectName("Mono")
        self._code.setProperty("role", "mono")
        self._code.setTextFormat(Qt.TextFormat.RichText)
        self._code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inset_layout.addWidget(self._code)
        self.command.add_widget(inset)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        copy_button = GlassButton("Copier", "copy")
        copy_button.clicked.connect(self.copy_requested)
        preset_button = GlassButton("Preset", "save")
        preset_button.setToolTip("Enregistrer les réglages actuels comme préréglage")
        preset_button.clicked.connect(self.preset_requested)
        buttons.addWidget(copy_button)
        buttons.addWidget(preset_button)
        self.command.add_layout(buttons)
        column.addWidget(self.command)

        # ── infos appareil ──
        self.device = GlassCard("INFOS APPAREIL", "phone")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self._fields: dict[str, QLabel] = {}
        for row, (key, label) in enumerate((("model", "Model:"), ("android", "Android:"), ("battery", "Battery:"),
                                            ("display", "Display:"), ("serial", "Serial:"))):
            grid.addWidget(make_label(label, role="dim"), row, 0)
            value = make_label("—")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._fields[key] = value
            grid.addWidget(value, row, 1)
        grid.setColumnStretch(1, 1)
        self.device.add_layout(grid)
        more = GlassButton("Plus d'infos", "chevron-right", "ghost")
        more.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        more.clicked.connect(self.more_info_requested)
        self.device.add_widget(more)
        column.addWidget(self.device)
        column.addStretch(1)
        self.set_command(["$ scrcpy"])

    def set_connection(self, text: str, tone: str) -> None:
        """Pastille d'état (ex. « USB · ADB Online »)."""
        self._status.setText(text)
        self._status.set_tone(tone)

    def set_metrics(self, metrics: Metrics) -> None:
        """Met à jour FPS, latence et batterie."""
        self.fps.set_value(f"{metrics.fps:g}" if metrics.fps is not None else "—")
        self.latency.set_value(f"{metrics.latency_ms:g}ms" if metrics.latency_ms is not None else "—")
        self.battery.set_value(f"{metrics.battery}%" if metrics.battery is not None else "—")

    def set_command(self, lines: list[str]) -> None:
        """Aperçu de la commande générée."""
        self._code.setText(preview_html(lines))
        self._code.setToolTip("\n".join(lines))

    def set_device(self, device: Device | None) -> None:
        """Informations détaillées de l'appareil (— si aucun)."""
        if device is None:
            for label in self._fields.values():
                label.setText("—")
            return
        self._fields["model"].setText(device.model or "—")
        self._fields["android"].setText(f"{device.android} (API {device.sdk})" if device.android else "—")
        battery = "—" if device.battery is None else f"{device.battery}%" + (" ⚡" if device.charging else "")
        self._fields["battery"].setText(battery)
        self._fields["display"].setText(device.display or "—")
        self._fields["serial"].setText(device.serial)
