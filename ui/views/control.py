"""Vue Contrôle : clavier, souris, presse-papiers."""
from __future__ import annotations

from ui.rows import CardSpec, segment, toggle
from ui.views.base_view import BaseView


class ControlView(BaseView):
    """Contrôle de l'appareil depuis l'ordinateur."""

    KEY = "control"
    TITLE = "Contrôle"
    SUBTITLE = "Clavier, souris et presse-papiers"
    CARDS = (
        CardSpec("SAISIE", "gamepad", (
            toggle("readonly", "Lecture seule", "--no-control", "Mirroring sans contrôle de l'appareil"),
            segment("keyboard", "Clavier", "keyboard", "--keyboard",
                    "SDK : API Android · UHID/AOA : clavier physique simulé"),
            segment("mouse", "Souris", "mouse", "--mouse"),
            toggle("prefertext", "Saisie en mode texte", "--prefer-text", "Évite les problèmes de caractères spéciaux"),
            toggle("noclip", "Ne pas synchroniser le presse-papiers", "--no-clipboard-autosync"),
        )),
    )
