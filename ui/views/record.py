"""Vue Enregistrement."""
from __future__ import annotations

from ui.rows import CardSpec, choice, number, path
from ui.views.base_view import BaseView


class RecordView(BaseView):
    """Enregistrement de la session."""

    KEY = "record"
    TITLE = "Enregistrement"
    SUBTITLE = "Sauvegarder la vidéo (et l'audio) de la session"
    CARDS = (
        CardSpec("FICHIER", "record", (
            path("record", "Fichier de sortie", "--record", "Vide = pas d'enregistrement",
                 hint="Un nom relatif est créé dans le dossier d'enregistrements"),
            choice("rformat", "Format", "rformat", "--record-format"),
            number("time_limit", "Durée maximale", 0, 86400, "--time-limit", suffix=" s", special="Illimitée"),
        )),
    )
