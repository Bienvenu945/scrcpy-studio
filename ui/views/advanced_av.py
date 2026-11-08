"""Vue Audio/Vidéo avancé (PRO) : encodeurs et options de codec."""
from __future__ import annotations

from ui.rows import CardSpec, choice, number, text, toggle
from ui.views.base_view import BaseView
from ui.widgets.controls import GlassButton
from ui.widgets.glass import GlassCard


class AdvancedAvView(BaseView):
    """Réglages fins d'encodage."""

    KEY = "advanced_av"
    TITLE = "Audio / Vidéo avancé"
    SUBTITLE = "Encodeurs, options de codec et contraintes"
    CARDS = (
        CardSpec("VIDÉO", "film", (
            choice("codec", "Codec vidéo (tous)", "codec", "--video-codec"),
            text("video_encoder", "Encodeur vidéo", "--video-encoder", "OMX.qcom.video.encoder.avc", "Voir Debug › --list-encoders"),
            text("video_codec_options", "Options du codec vidéo", "--video-codec-options", "i-frame-interval=2,bitrate-mode:int=2", mono=True),
            number("max_size", "Taille maximale exacte", 0, 8192, "--max-size", suffix=" px", special="Native"),
            choice("min_size_alignment", "Alignement minimal des dimensions", "min_size_alignment", "--min-size-alignment"),
            toggle("ignore_video_encoder_constraints", "Ignorer les contraintes de l'encodeur", "--ignore-video-encoder-constraints"),
            toggle("no_downsize_on_error", "Ne pas réduire la définition en cas d'erreur", "--no-downsize-on-error"),
            toggle("no_mipmaps", "Désactiver les mipmaps", "--no-mipmaps"),
        )),
        CardSpec("AUDIO", "volume", (
            text("audio_encoder", "Encodeur audio", "--audio-encoder", "c2.android.opus.encoder"),
            text("audio_codec_options", "Options du codec audio", "--audio-codec-options", "", mono=True),
            number("audio_output_buffer", "Tampon de sortie SDL", 1, 500, "--audio-output-buffer", suffix=" ms",
                   hint="À ne changer que pour une bonne raison"),
            toggle("adup", "Dupliquer l'audio (capture + lecture sur l'appareil)", "--audio-dup", "Source « Lecture (playback) » requise"),
            toggle("require_audio", "Exiger l'audio", "--require-audio", "Échoue si la capture audio ne fonctionne pas"),
        )),
    )

    def build_extra(self) -> None:
        """Cartes personnalisées placées après les cartes déclaratives."""
        card = GlassCard("ENCODEURS DISPONIBLES", "bug")
        button = GlassButton("Lister les encodeurs de l'appareil", "list")
        button.clicked.connect(lambda: self.ctx.navigate("debug"))
        card.add_widget(button)
        self.column.addWidget(card)
