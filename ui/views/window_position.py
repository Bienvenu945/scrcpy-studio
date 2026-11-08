"""Vue Fenêtre (PRO) : position, taille, rendu."""
from __future__ import annotations

from ui.rows import CardSpec, choice, number, text, toggle
from ui.views.base_view import BaseView


class WindowPositionView(BaseView):
    """Géométrie et rendu de la fenêtre scrcpy."""

    KEY = "window_position"
    TITLE = "Fenêtre"
    SUBTITLE = "Position, taille initiale et rendu"
    CARDS = (
        CardSpec("POSITION ET TAILLE", "window", (
            text("window_x", "Position X", "--window-x", "auto"),
            text("window_y", "Position Y", "--window-y", "auto"),
            number("window_width", "Largeur initiale", 0, 16384, "--window-width", suffix=" px", special="Auto"),
            number("window_height", "Hauteur initiale", 0, 16384, "--window-height", suffix=" px", special="Auto"),
            toggle("no_window_aspect_ratio_lock", "Ne pas verrouiller le rapport d'aspect", "--no-window-aspect-ratio-lock"),
        )),
        CardSpec("RENDU", "monitor", (
            choice("render_driver", "Pilote de rendu", "render_driver", "--render-driver"),
            choice("render_fit", "Ajustement", "render_fit", "--render-fit"),
            text("background_color", "Couleur de fond", "--background-color", "#222", "Format #RGB ou #RRGGBB"),
            toggle("no_window", "Aucune fenêtre", "--no-window", "Utile avec l'enregistrement ou V4L2 (implique --no-video-playback)"),
        )),
    )
