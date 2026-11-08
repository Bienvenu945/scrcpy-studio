"""Aides d'animation (150-300 ms) ; désactivables, jamais bloquantes."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QVariantAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


class Motion:
    """Réglage global : ``Motion.enabled = False`` supprime toutes les animations."""

    enabled: bool = True

    @classmethod
    def duration(cls, ms: int) -> int:
        """Durée effective (0 si les animations sont coupées)."""
        return ms if cls.enabled else 0


def fade_in(widget: QWidget, duration: int = 200) -> None:
    """Fondu d'apparition ; l'effet est retiré à la fin pour ne pas ralentir le rendu."""
    if not Motion.enabled:
        widget.setGraphicsEffect(None)
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._fade_anim = anim  # référence pour éviter la collecte
    anim.start()


def animate_value(
    parent: Any,
    start: float,
    end: float,
    duration: int,
    setter: Callable[[Any], None],
    curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
) -> QVariantAnimation:
    """Anime une valeur numérique en appelant ``setter`` à chaque pas."""
    anim = QVariantAnimation(parent)
    anim.setStartValue(float(start))
    anim.setEndValue(float(end))
    anim.setDuration(Motion.duration(duration))
    anim.setEasingCurve(curve)
    anim.valueChanged.connect(setter)
    anim.start()
    return anim


def animate_geometry(widget: QWidget, target, duration: int = 260,
                     curve: QEasingCurve.Type = QEasingCurve.Type.OutBack) -> None:
    """Déplace/redimensionne ``widget`` vers ``target`` (QRect) avec un effet « liquide »."""
    if not Motion.enabled or not widget.isVisible():
        widget.setGeometry(target)
        return
    anim = QPropertyAnimation(widget, b"geometry", widget)
    anim.setDuration(duration)
    anim.setStartValue(widget.geometry())
    anim.setEndValue(target)
    anim.setEasingCurve(curve)
    widget._geo_anim = anim
    anim.start()
