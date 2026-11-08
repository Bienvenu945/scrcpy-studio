"""Vue Rotation (PRO) : orientation, angle, découpe."""
from __future__ import annotations

from ui.rows import CardSpec, choice, number, text, toggle
from ui.views.base_view import BaseView


class RotationView(BaseView):
    """Rotation et recadrage de la vidéo."""

    KEY = "rotation"
    TITLE = "Rotation"
    SUBTITLE = "Orientation de capture, d'affichage et d'enregistrement"
    CARDS = (
        CardSpec("CAPTURE", "rotate", (
            choice("capture_orientation", "Orientation de capture", "capture_orientation", "--capture-orientation"),
            toggle("orientation_locked", "Verrouiller l'orientation", "--capture-orientation",
                   "Préfixe « @ » : relative à l'orientation naturelle de l'appareil"),
            number("angle", "Angle personnalisé", -360, 360, "--angle", step=1, decimals=1, suffix="°", special="Aucun"),
        )),
        CardSpec("AFFICHAGE ET ENREGISTREMENT", "monitor", (
            choice("display_orientation", "Orientation de l'affichage", "display_orientation", "--display-orientation"),
            choice("record_orientation", "Orientation de l'enregistrement", "record_orientation", "--record-orientation"),
            toggle("orientation", "Synchroniser affichage et enregistrement", "--orientation",
                   "Émet --display-orientation et --record-orientation avec la même valeur"),
        )),
        CardSpec("DÉCOUPE", "crop", (
            text("crop", "Zone recadrée", "--crop", "largeur:hauteur:x:y",
                 "Coordonnées dans l'orientation naturelle de l'appareil"),
        )),
    )
