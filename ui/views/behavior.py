"""Vue Comportement (PRO) : nettoyage, pause, saisie avancée."""
from __future__ import annotations

from ui.rows import CardSpec, choice, text, toggle
from ui.views.base_view import BaseView


class BehaviorView(BaseView):
    """Comportement de scrcpy et détails de saisie."""

    KEY = "behavior"
    TITLE = "Comportement"
    SUBTITLE = "Nettoyage, terminal, fichiers déposés et saisie avancée"
    CARDS = (
        CardSpec("SESSION", "settings", (
            toggle("no_cleanup", "Ne pas nettoyer à la sortie", "--no-cleanup", "Conserve le serveur et l'état de l'appareil"),
            choice("pause_on_exit", "Pause à la fermeture", "pause_on_exit", "--pause-on-exit",
                   "Garde le terminal ouvert pour lire les messages"),
            text("push_target", "Dossier de dépôt de fichiers", "--push-target", "/sdcard/Download/",
                 "Destination du glisser-déposer sur la fenêtre"),
        )),
        CardSpec("SAISIE AVANCÉE", "keyboard", (
            toggle("legacy_paste", "Coller en événements clavier", "--legacy-paste", "Contournement pour certains appareils"),
            toggle("raw_key_events", "Événements de touches bruts", "--raw-key-events"),
            toggle("no_key_repeat", "Ignorer la répétition de touches", "--no-key-repeat"),
            toggle("no_mouse_hover", "Ignorer le survol de la souris", "--no-mouse-hover"),
            text("mouse_bind", "Boutons secondaires", "--mouse-bind", "bhsn:++++",
                 "4 caractères (clic droit, milieu, 4e, 5e) parmi + - b h s n"),
            text("shortcut_mod", "Modificateurs des raccourcis", "--shortcut-mod", "lalt,lsuper",
                 "lctrl, rctrl, lalt, ralt, lsuper, rsuper"),
        )),
    )
