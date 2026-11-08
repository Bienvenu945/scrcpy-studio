"""Vue V4L2 (PRO) : sortie vers un périphérique v4l2loopback (Linux)."""
from __future__ import annotations

import sys

from ui.rows import CardSpec, number, text
from ui.views.base_view import BaseView
from ui.widgets.glass import GlassCard, make_label


class V4l2View(BaseView):
    """Webcam virtuelle."""

    KEY = "v4l2"
    TITLE = "V4L2"
    SUBTITLE = "Envoyer la vidéo vers un périphérique v4l2loopback"
    CARDS = (
        CardSpec("SORTIE V4L2", "link", (
            text("v4l2_sink", "Périphérique", "--v4l2-sink", "/dev/video2", mono=True),
            number("v4l2_buffer", "Tampon", 0, 2000, "--v4l2-buffer", step=5, suffix=" ms", special="Aucun",
                   hint="Compense la gigue, au prix de la latence"),
        )),
    )
    EXTRA_OPTS = "--v4l2-buffer"

    def build_extra(self) -> None:
        """Cartes personnalisées placées après les cartes déclaratives."""
        card = GlassCard("PRÉREQUIS", "info")
        note = ("Nécessite le module noyau v4l2loopback (sudo modprobe v4l2loopback). "
                "Combinez avec « Aucune fenêtre » (--no-window) pour une webcam sans affichage.")
        if not sys.platform.startswith("linux"):
            note = "Cette fonction n'est disponible que sous Linux.  " + note
        card.add_widget(make_label(note, role="dim", wrap=True))
        self.column.addWidget(card)
