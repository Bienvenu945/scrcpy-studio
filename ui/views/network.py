"""Vue Réseau (PRO) : sélection d'appareil, TCP/IP, tunnel adb."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import QHBoxLayout

from core.process import run_async
from ui.rows import CardSpec, number, text, toggle
from ui.views.base_view import BaseView
from ui.widgets.controls import GlassButton
from ui.widgets.glass import GlassCard


class NetworkView(BaseView):
    """Connexion adb avancée."""

    KEY = "network"
    TITLE = "Réseau"
    SUBTITLE = "Sélection de l'appareil, TCP/IP et tunnel adb"
    CARDS = (
        CardSpec("SÉLECTION", "link", (
            toggle("select_usb", "Appareil USB uniquement", "--select-usb", "Équivalent de adb -d"),
            toggle("select_tcpip", "Appareil TCP/IP uniquement", "--select-tcpip", "Équivalent de adb -e"),
            toggle("tcpip", "Activer le mode TCP/IP automatiquement", "--tcpip",
                   "Détecte l'IP de l'appareil USB, active adb tcpip puis se connecte"),
            toggle("tcpip_force_reconnect", "Forcer la reconnexion", "--tcpip", "Préfixe « + » (nécessite une adresse dans Device)"),
        )),
        CardSpec("TUNNEL", "wifi", (
            text("port_range", "Plage de ports locaux", "--port", "27183:27199"),
            text("tunnel_host", "Hôte du tunnel", "--tunnel-host", "localhost", "Active automatiquement --force-adb-forward"),
            number("tunnel_port", "Port du tunnel", 0, 65535, "--tunnel-port", special="Auto"),
            toggle("force_adb_forward", "Forcer adb forward", "--force-adb-forward", "N'utilise pas « adb reverse »"),
            toggle("kill_adb_on_close", "Arrêter adb à la fermeture", "--kill-adb-on-close"),
        )),
    )
    EXTRA_OPTS = "--tcpip"

    def build_extra(self) -> None:
        """Cartes personnalisées placées après les cartes déclaratives."""
        card = GlassCard("OUTILS ADB", "terminal")
        layout = QHBoxLayout()
        layout.setSpacing(8)
        for label, icon, handler in (("Redémarrer adb", "refresh", self._restart_adb),
                                     ("Tout déconnecter", "x", self._disconnect_all)):
            button = GlassButton(label, icon)
            button.clicked.connect(handler)
            layout.addWidget(button)
        layout.addStretch(1)
        card.add_layout(layout)
        self.column.addWidget(card)

    def _run(self, work: Callable[[], bool], success: str) -> None:
        def done(value: Any, error: BaseException | None) -> None:
            ok = bool(value) and error is None
            self.ctx.notify("success" if ok else "error", success if ok else "L'opération adb a échoué.")
            self.ctx.forget_details()
            self.ctx.refresh_devices()

        run_async(work, done, dispatcher=self.ctx.dispatcher)

    def _restart_adb(self) -> None:
        adb = self.ctx.adb

        def restart() -> bool:
            adb.kill_server()
            return adb.start_server()

        self._run(restart, "Serveur adb redémarré.")

    def _disconnect_all(self) -> None:
        adb = self.ctx.adb
        self._run(lambda: adb.disconnect()[0], "Appareils TCP/IP déconnectés.")
