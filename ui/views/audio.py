"""Vue Audio : transfert, source, codec, tampon."""
from __future__ import annotations

from ui.rows import CardSpec, choice, number, slider, toggle
from ui.views.base_view import BaseView

_ON = lambda s: s.audio  # noqa: E731


class AudioView(BaseView):
    """Réglages audio essentiels."""

    KEY = "audio"
    TITLE = "Audio"
    SUBTITLE = "Le son de l'appareil sur votre ordinateur"
    CARDS = (
        CardSpec("AUDIO", "volume", (
            toggle("audio", "Transférer l'audio", "--no-audio", "Désactivé : scrcpy est lancé avec --no-audio"),
            choice("asource", "Source audio", "asource", "--audio-source", enabled_if=_ON),
            choice("acodec", "Codec audio", "acodec", "--audio-codec", enabled_if=_ON),
            slider("audio_bitrate", "Débit audio", 8, 512, "--audio-bit-rate", step=8, suffix=" kbps", enabled_if=_ON),
            number("abuf", "Tampon audio", 0, 2000, "--audio-buffer", step=5, suffix=" ms",
                   hint="Plus bas = moins de latence, plus de risques de craquements", enabled_if=_ON),
            toggle("no_audio_playback", "Ne pas lire l'audio sur l'ordinateur", "--no-audio-playback", enabled_if=_ON),
        )),
    )
