"""Vue Caméra (PRO) : miroir de la caméra de l'appareil (Android 12+)."""
from __future__ import annotations

from ui.rows import CardSpec, choice, number, segment, text, toggle
from ui.views.base_view import BaseView
from ui.widgets.controls import GlassButton
from ui.widgets.glass import GlassCard, make_label

_CAM = lambda s: s.video_source == "camera"  # noqa: E731


class CameraView(BaseView):
    """Source vidéo et réglages de caméra."""

    KEY = "camera"
    TITLE = "Caméra"
    SUBTITLE = "Utiliser la caméra de l'appareil comme source (Android 12 ou plus)"
    CARDS = (
        CardSpec("SOURCE", "camera", (
            segment("video_source", "Source vidéo", "video_source", "--video-source"),
        )),
        CardSpec("CAPTEUR", "film", (
            text("camera_id", "Identifiant de la caméra", "--camera-id", "0", "Voir la liste dans Debug", enabled_if=_CAM),
            choice("camera_facing", "Orientation", "camera_facing", "--camera-facing", enabled_if=_CAM),
            text("camera_size", "Taille de capture", "--camera-size", "1920x1080", enabled_if=_CAM),
            text("camera_ar", "Rapport d'aspect", "--camera-ar", "sensor, 4:3, 1.6", enabled_if=_CAM),
            number("camera_fps", "Fréquence de capture", 0, 240, "--camera-fps", suffix=" fps", special="Défaut (30)", enabled_if=_CAM),
            toggle("camera_high_speed", "Mode haute vitesse", "--camera-high-speed", enabled_if=_CAM),
        )),
        CardSpec("OPTIONS", "bolt", (
            toggle("camera_torch", "Allumer la torche au démarrage", "--camera-torch", enabled_if=_CAM),
            number("camera_zoom", "Zoom initial", 0, 10, "--camera-zoom", step=0.1, decimals=1, special="Défaut", enabled_if=_CAM),
        )),
    )

    def build_extra(self) -> None:
        """Cartes personnalisées placées après les cartes déclaratives."""
        card = GlassCard("AIDE", "info")
        card.add_widget(make_label("Les caméras et tailles disponibles dépendent de l'appareil. "
                                   "Utilisez la vue Debug pour les lister (--list-cameras, --list-camera-sizes).", role="dim", wrap=True))
        button = GlassButton("Ouvrir Debug › listes", "bug")
        button.clicked.connect(lambda: self.ctx.navigate("debug"))
        card.add_widget(button)
        self.column.addWidget(card)
