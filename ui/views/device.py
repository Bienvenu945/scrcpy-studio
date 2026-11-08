"""Vue Device : carte appareil, préréglages rapides, paramètres d'écran, connexion."""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QInputDialog, QLineEdit, QListWidget, QListWidgetItem, QMenu, QWidget

from config.profiles import all_presets, custom_from_settings, preset_matches
from core.process import run_async
from ui.context import Context
from ui.rows import CardSpec, Row, radio, segment, slider, text
from ui.views.base_view import BaseView
from ui.widgets.controls import GlassButton, IconButton
from ui.widgets.device_card import DeviceCard
from ui.widgets.glass import GlassCard
from ui.widgets.preset_card import PresetCard
from ui.widgets.quick_actions import PhonePreview, QuickActions

CODECS_MAIN = (("h264", "H.264"), ("h265", "H.265"), ("av1", "AV1"))


def save_preset_dialog(ctx: Context, parent: QWidget | None = None) -> bool:
    """Demande un nom et enregistre les réglages courants comme préréglage personnalisé."""
    name, ok = QInputDialog.getText(parent, "Nouveau préréglage", "Nom du préréglage :")
    if not ok or not name.strip():
        return False
    customs = list(ctx.pref("custom_presets"))
    entry = custom_from_settings(name, ctx.settings(), len(customs))
    customs = [c for c in customs if c.get("key") != entry["key"]] + [entry]
    ctx.set_pref("custom_presets", customs)
    ctx.notify("success", f"Préréglage « {name.strip()} » enregistré.")
    return True


class DeviceView(BaseView):
    """Vue principale : l'essentiel pour lancer scrcpy en trois clics."""

    KEY = "device"
    TITLE = "Device"
    SUBTITLE = "Appareil, préréglages rapides et paramètres d'écran"
    CARDS = (
        CardSpec("CONNEXION", "link", (
            segment("conn", "Mode de connexion", "conn", "--select-usb --select-tcpip"),
            text("serial", "Numéro de série", "--serial", "Auto (le seul appareil connecté)"),
            text("tcpip_addr", "Adresse TCP/IP", "--tcpip", "192.168.1.20:5555",
                 hint="Scrcpy se connecte à cette adresse au lancement"),
        )),
    )

    # ── construction ──
    def build_top(self) -> None:
        """Cartes personnalisées placées avant les cartes déclaratives."""
        self.device_card = DeviceCard()
        self.device_card.refresh_requested.connect(self._refresh_devices)
        self.column.addWidget(self.device_card)

        self.presets_card = GlassCard("PRÉRÉGLAGE RAPIDE", "bolt")
        gear = IconButton("gear", "Gérer les préréglages", 16)
        gear.clicked.connect(self._preset_menu)
        self.presets_card.add_action(gear)
        self._preset_grid = QGridLayout()
        self._preset_grid.setHorizontalSpacing(12)
        self._preset_grid.setVerticalSpacing(12)
        self.presets_card.add_layout(self._preset_grid)
        self.column.addWidget(self.presets_card)
        self._preset_cards: list[PresetCard] = []
        self._presets_signature: tuple = ()

        screen = GlassCard("PARAMÈTRES D'ÉCRAN", "monitor")
        self.add_row(screen, Row("max_size", "Résolution", "resolution", "--max-size"))
        self.add_row(screen, radio("codec", "Codec vidéo", CODECS_MAIN, "--video-codec"))
        self.add_row(screen, slider("bitrate", "Débit", 1, 200, "--video-bit-rate", suffix=" Mbps"))
        split = QHBoxLayout()
        split.setSpacing(14)
        self.preview = PhonePreview(self.ctx)
        self.quick = QuickActions()
        self.quick.fullscreen_toggled.connect(lambda: self.ctx.set_value("fullscreen", not self.ctx.value("fullscreen")))
        self.quick.rotation_chosen.connect(self._rotate)
        self.quick.capture_clicked.connect(self._capture)
        self.quick.advanced_clicked.connect(lambda: self.ctx.navigate("advanced"))
        split.addWidget(self.preview, 3)
        split.addWidget(self.quick, 2)
        screen.add_layout(split)
        self.column.addWidget(screen)

    def build_extra(self) -> None:
        """Cartes personnalisées placées après les cartes déclaratives."""
        card = GlassCard("APPAREILS DÉTECTÉS", "phone", "Double-clic pour utiliser un appareil avec cette instance")
        refresh = IconButton("refresh", "Actualiser", 16)
        refresh.clicked.connect(self._refresh_devices)
        card.add_action(refresh)
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(110)
        self.device_list.itemDoubleClicked.connect(lambda _item: self._use_selected())
        card.add_widget(self.device_list)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        use = GlassButton("Utiliser pour cette instance", "check")
        use.clicked.connect(self._use_selected)
        auto = GlassButton("Automatique", "refresh", "ghost")
        auto.setToolTip("Efface le numéro de série : scrcpy choisit l'appareil")
        auto.clicked.connect(lambda: self.ctx.set_value("serial", ""))
        buttons.addWidget(use)
        buttons.addWidget(auto)
        buttons.addStretch(1)
        card.add_layout(buttons)
        wifi = QHBoxLayout()
        wifi.setSpacing(8)
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("Adresse IP[:port] de l'appareil, ex. 192.168.1.20")
        connect = GlassButton("Connecter", "wifi")
        connect.clicked.connect(self._connect)
        to_wifi = GlassButton("Passer en Wi-Fi", "link")
        to_wifi.setToolTip("Depuis un appareil branché en USB : active adb tcpip puis se connecte à son IP")
        to_wifi.clicked.connect(self._to_wifi)
        wifi.addWidget(self.ip_edit, 1)
        wifi.addWidget(connect)
        wifi.addWidget(to_wifi)
        card.add_layout(wifi)
        self.column.addWidget(card)

    # ── préréglages ──
    def _rebuild_presets(self) -> None:
        presets = all_presets(self.ctx.pref("custom_presets"))
        signature = tuple((p.key, p.label, p.subtitle) for p in presets)
        if signature == self._presets_signature:
            return
        self._presets_signature = signature
        while self._preset_grid.count():
            item = self._preset_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
                item.widget().deleteLater()
        self._preset_cards = []
        for index, preset in enumerate(presets):
            card = PresetCard(preset.key, preset.label, preset.subtitle, preset.color)
            card.chosen.connect(self._apply_preset)
            self._preset_cards.append(card)
            self._preset_grid.addWidget(card, index // 3, index % 3)
        for column in range(3):
            self._preset_grid.setColumnStretch(column, 1)

    def _apply_preset(self, key: str) -> None:
        preset = next((p for p in all_presets(self.ctx.pref("custom_presets")) if p.key == key), None)
        if preset is not None:
            self.ctx.apply_values(preset.values, key)
            self.ctx.notify("info", f"Préréglage « {preset.label} » appliqué.")

    def _preset_menu(self) -> None:
        menu = QMenu(self)
        save = menu.addAction("Enregistrer les réglages actuels comme préréglage…")
        customs = list(self.ctx.pref("custom_presets"))
        deletions = {}
        if customs:
            menu.addSeparator()
            for entry in customs:
                deletions[menu.addAction(f"Supprimer « {entry.get('label', entry.get('key'))} »")] = entry.get("key")
        chosen = menu.exec(self.presets_card.mapToGlobal(self.presets_card.rect().topRight()))
        if chosen is save:
            save_preset_dialog(self.ctx, self)
        elif chosen in deletions:
            self.ctx.set_pref("custom_presets", [c for c in customs if c.get("key") != deletions[chosen]])

    # ── actions rapides ──
    def _rotate(self, value: str) -> None:
        self.ctx.set_value("display_orientation", value)

    def _capture(self) -> None:
        if self.preview.png() is None:
            self.preview.refresh(force=True)
            self.ctx.notify("info", "Capture en cours… recommencez dans un instant.")
            return
        path = self.preview.save_capture()
        self.ctx.notify("success" if path else "error", f"Capture enregistrée : {path}" if path else "Aucune capture disponible.")

    # ── appareils ──
    def _refresh_devices(self) -> None:
        self.ctx.forget_details()
        self.ctx.refresh_devices()

    def _selected_serial(self) -> str:
        item = self.device_list.currentItem()
        if item is not None:
            return str(item.data(Qt.ItemDataRole.UserRole))
        device = self.ctx.inst.device
        return device.serial if device else ""

    def _use_selected(self) -> None:
        serial = self._selected_serial()
        if not serial:
            self.ctx.notify("warning", "Aucun appareil sélectionné.")
            return
        self.ctx.set_value("serial", serial)
        self.ctx.sync_instance_devices()
        self.ctx.emit("devices", self.ctx.devices)

    def _connect(self) -> None:
        address = self.ip_edit.text().strip()
        if not address:
            self.ctx.notify("warning", "Saisissez l'adresse IP de l'appareil.")
            return
        if ":" not in address:
            address += ":5555"

        def done(value: Any, error: BaseException | None) -> None:
            ok, message = value if value else (False, str(error))
            self.ctx.notify("success" if ok else "error", message or "Aucune réponse d'adb.")
            if ok:
                self.ctx.set_value("serial", address)
                self.ctx.forget_details()
                self.ctx.refresh_devices()

        run_async(lambda: self.ctx.adb.connect(address), done, dispatcher=self.ctx.dispatcher)

    def _to_wifi(self) -> None:
        serial = self._selected_serial()
        if not serial or ":" in serial:
            self.ctx.notify("warning", "Sélectionnez un appareil branché en USB.")
            return
        adb = self.ctx.adb

        def work() -> tuple[bool, str, str]:
            ip = adb.device_ip(serial)
            if not ip:
                return False, "Adresse IP introuvable (Wi-Fi activé sur l'appareil ?).", ""
            ok, message = adb.enable_tcpip(serial)
            if not ok:
                return False, message or "adb tcpip a échoué.", ""
            time.sleep(1.5)
            ok, message = adb.connect(f"{ip}:5555")
            return ok, message, f"{ip}:5555"

        def done(value: Any, error: BaseException | None) -> None:
            ok, message, address = value if value else (False, str(error), "")
            self.ctx.notify("success" if ok else "error", message)
            if ok:
                self.ip_edit.setText(address)
                self.ctx.set_value("serial", address)
                self.ctx.forget_details()
                self.ctx.refresh_devices()

        run_async(work, done, dispatcher=self.ctx.dispatcher)

    # ── rafraîchissement ──
    def refresh_extra(self) -> None:
        """Met à jour les éléments personnalisés de la vue."""
        inst = self.ctx.inst
        self.device_card.set_state(inst.device, self.ctx.adb_ok, inst.running, inst.metrics.snapshot())
        self._rebuild_presets()
        settings = self.ctx.settings()
        for card in self._preset_cards:
            preset = next((p for p in all_presets(self.ctx.pref("custom_presets")) if p.key == card.key), None)
            card.set_active(bool(preset and preset_matches(settings, preset)))
        self.quick.set_state(settings.fullscreen, settings.display_orientation)
        self.quick.setVisible(bool(self.ctx.pref("quick_actions_enabled")))
        self.preview.setVisible(bool(self.ctx.pref("preview_enabled")))
        self._fill_device_list()

    def _fill_device_list(self) -> None:
        keep = self._selected_serial_if_any()
        self.device_list.clear()
        chosen = self.ctx.settings().serial or (self.ctx.inst.device.serial if self.ctx.inst.device else "")
        for device in self.ctx.devices:
            marker = "● " if device.serial == chosen else "   "
            item = QListWidgetItem(f"{marker}{device.label} — {device.serial} · {device.link} · {device.state}")
            item.setData(Qt.ItemDataRole.UserRole, device.serial)
            self.device_list.addItem(item)
            if device.serial == keep:
                self.device_list.setCurrentItem(item)
        if not self.ctx.devices:
            self.device_list.addItem(QListWidgetItem("Aucun appareil détecté — branchez un appareil (débogage USB activé)"))

    def _selected_serial_if_any(self) -> str:
        item = self.device_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None and item.data(Qt.ItemDataRole.UserRole) else ""

    def on_ctx_event(self, event: str, payload: Any) -> None:
        """Réagit aux événements du contexte (appareils, exécution, journal…)."""
        if event in ("devices", "running", "metrics"):
            self.refresh_extra()

    def on_enter(self) -> None:
        """Appelé à chaque affichage de la vue."""
        super().on_enter()
        self.refresh_extra()
