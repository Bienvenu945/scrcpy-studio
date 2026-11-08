"""Vue Affichage : fenêtre scrcpy et comportement de l'écran du téléphone."""
from __future__ import annotations

from ui.rows import CardSpec, number, text, toggle
from ui.views.base_view import BaseView


class DisplayView(BaseView):
    """Fenêtre et écran de l'appareil."""

    KEY = "display"
    TITLE = "Affichage"
    SUBTITLE = "La fenêtre scrcpy et l'écran du téléphone"
    CARDS = (
        CardSpec("FENÊTRE", "window", (
            toggle("fullscreen", "Démarrer en plein écran", "--fullscreen"),
            toggle("ontop", "Toujours au premier plan", "--always-on-top"),
            toggle("borderless", "Fenêtre sans bordure", "--window-borderless"),
            text("title", "Titre de la fenêtre", "--window-title", "scrcpy"),
        )),
        CardSpec("ÉCRAN DU TÉLÉPHONE", "phone", (
            toggle("screenoff", "Éteindre l'écran de l'appareil", "--turn-screen-off", "L'affichage continue sur l'ordinateur"),
            toggle("stayawake", "Garder l'appareil éveillé", "--stay-awake", "Uniquement s'il est branché"),
            toggle("keepactive", "Simuler une activité", "--keep-active"),
            toggle("touches", "Afficher les appuis", "--show-touches"),
            toggle("disable_screensaver", "Désactiver l'économiseur d'écran", "--disable-screensaver", "Sur l'ordinateur, pendant la session"),
            number("screen_off_timeout", "Délai d'extinction", 0, 86400, "--screen-off-timeout", suffix=" s", special="Inchangé"),
        )),
    )
