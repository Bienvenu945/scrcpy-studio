"""Vue Vidéo : qualité, latence, lecture."""
from __future__ import annotations

from ui.rows import CardSpec, Row, number, radio, slider, toggle
from ui.views.base_view import BaseView


class VideoView(BaseView):
    """Réglages vidéo essentiels."""

    KEY = "video"
    TITLE = "Vidéo"
    SUBTITLE = "Résolution, débit, fluidité et latence"
    CARDS = (
        CardSpec("QUALITÉ", "film", (
            Row("max_size", "Résolution maximale", "resolution", "--max-size", "Limite la largeur et la hauteur de l'image"),
            slider("bitrate", "Débit vidéo", 1, 200, "--video-bit-rate", suffix=" Mbps"),
            slider("max_fps", "Images par seconde", 0, 240, "--max-fps", suffix=" fps", special="Auto"),
            radio("codec", "Codec vidéo", (("h264", "H.264"), ("h265", "H.265"), ("av1", "AV1")), "--video-codec"),
        )),
        CardSpec("LATENCE", "activity", (
            number("vbuf", "Tampon d'affichage", 0, 2000, "--video-buffer", step=5, suffix=" ms", special="Aucun",
                   hint="Lisse les saccades au prix d'une latence plus élevée"),
        )),
        CardSpec("LECTURE", "monitor", (
            toggle("no_video", "Désactiver la vidéo", "--no-video"),
            toggle("no_video_playback", "Ne pas afficher la vidéo", "--no-video-playback",
                   "La vidéo est reçue (enregistrement) mais pas affichée"),
            toggle("no_playback", "Aucune lecture (vidéo et audio)", "--no-playback"),
        )),
    )
