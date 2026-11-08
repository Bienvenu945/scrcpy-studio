"""Vue Écran virtuel (PRO) : --new-display et lancement d'application."""
from __future__ import annotations

from core.scrcpy import start_app_value
from ui.rows import CardSpec, choice, number, text, toggle
from ui.views.base_view import BaseView
from ui.widgets.glass import GlassCard, make_label

_VD = lambda s: s.newdisplay  # noqa: E731


class VirtualDisplayView(BaseView):
    """Affichage secondaire virtuel et application à démarrer."""

    KEY = "virtual_display"
    TITLE = "Écran virtuel"
    SUBTITLE = "Créer un écran indépendant sur l'appareil et y lancer une application"
    CARDS = (
        CardSpec("ÉCRAN VIRTUEL", "layers", (
            toggle("newdisplay", "Créer un nouvel écran", "--new-display"),
            text("vd_res", "Résolution / densité", "--new-display", "1920x1080/420, /240",
                 "Vide : taille et densité de l'écran principal", enabled_if=_VD),
            toggle("flex_display", "Écran flexible", "--flex-display", "Redimensionné avec la fenêtre"),
            toggle("no_vd_destroy_content", "Conserver les applications à la fermeture", "--no-vd-destroy-content",
                   "Elles sont déplacées sur l'écran principal", enabled_if=_VD),
            toggle("no_vd_system_decorations", "Sans décorations système", "--no-vd-system-decorations", enabled_if=_VD),
        )),
        CardSpec("AFFICHAGE CIBLE", "monitor", (
            number("display_id", "Identifiant de l'écran à copier", 0, 64, "--display-id", hint="Voir Debug › --list-displays"),
            choice("display_ime_policy", "Clavier à l'écran (IME)", "display_ime_policy", "--display-ime-policy"),
        )),
        CardSpec("APPLICATION", "phone", (
            text("start_app", "Application à lancer", "--start-app", "org.mozilla.firefox", "Nom de paquet exact"),
            toggle("start_app_force_stop", "Forcer l'arrêt avant le lancement", "--start-app", "Préfixe « + »"),
            toggle("start_app_prefix_match", "Correspondance par préfixe de nom", "--start-app", "Préfixe « ? », insensible à la casse"),
        )),
    )

    def build_extra(self) -> None:
        """Cartes personnalisées placées après les cartes déclaratives."""
        card = GlassCard("VALEUR ÉMISE", "terminal")
        self._start_app_label = make_label("", role="mono")
        card.add_widget(self._start_app_label)
        self.column.addWidget(card)

    def refresh_extra(self) -> None:
        """Met à jour les éléments personnalisés de la vue."""
        value = start_app_value(self.ctx.settings())
        self._start_app_label.setText(f"--start-app={value}" if value else "(aucune application)")
