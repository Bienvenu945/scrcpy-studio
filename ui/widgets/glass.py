"""Éléments de base : cartes, lignes de réglage, fond animé, pastilles, notifications."""
from __future__ import annotations

import math
from PySide6.QtCore import QPoint, QPointF, QTimer, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from ui import theme
from ui.widgets import icons
from ui.widgets.animations import Motion


def set_prop(widget: QWidget, name: str, value: object) -> None:
    """Change une propriété dynamique et force la réévaluation du QSS."""
    if widget.property(name) != value:
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


def make_label(text: str = "", role: str = "", object_name: str = "", wrap: bool = False) -> QLabel:
    """QLabel prêt à styler (``role`` : hint, dim, muted, mono, value)."""
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    if object_name:
        label.setObjectName(object_name)
    label.setWordWrap(wrap)
    return label


class ClickableFrame(QFrame):
    """QFrame émettant ``clicked`` lors d'un clic gauche (cartes cliquables)."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Pill(QLabel):
    """Pastille de texte colorée (``tone`` : success, warning, error, accent, neutre)."""

    def __init__(self, text: str = "", tone: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Pill")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        """Change la tonalité."""
        set_prop(self, "tone", tone)


class Dot(QWidget):
    """Point de statut avec halo pulsant optionnel."""

    def __init__(self, color: str = "#10B981", size: int = 10, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self._size = size
        self._phase = 0.0
        self.setFixedSize(size + 14, size + 14)
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(1400)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._on_phase)

    def _on_phase(self, value: object) -> None:
        self._phase = float(value)  # type: ignore[arg-type]
        self.update()

    def set_color(self, color: str) -> None:
        """Couleur du point."""
        self._color = color
        self.update()

    def set_pulsing(self, pulsing: bool) -> None:
        """Active/désactive le halo pulsant."""
        if pulsing and Motion.enabled:
            if self._anim.state() != QVariantAnimation.State.Running:
                self._anim.start()
        else:
            self._anim.stop()
            self._phase = 0.0
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        color = QColor(self._color)
        if self._phase > 0:
            halo = QColor(color)
            halo.setAlphaF(0.45 * (1 - self._phase))
            p.setBrush(halo)
            p.setPen(Qt.PenStyle.NoPen)
            radius = self._size / 2 + 7 * self._phase
            p.drawEllipse(center, radius, radius)
        glow = QColor(color)
        glow.setAlphaF(0.25)
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(center, self._size / 2 + 2, self._size / 2 + 2)
        p.setBrush(color)
        p.drawEllipse(center, self._size / 2, self._size / 2)


class _Header(QWidget):
    """En-tête de carte cliquable (pour les groupes repliables)."""

    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class GlassCard(QFrame):
    """Carte aux coins arrondis, bordure fine, ombre douce et en-tête icône + titre."""

    def __init__(self, title: str = "", icon: str = "", subtitle: str = "", collapsible: bool = False,
                 shadow: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.collapsible = collapsible
        self._collapsed = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(12)

        self.header = _Header()
        head = QHBoxLayout(self.header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(10)
        if icon:
            self.icon_label = QLabel()
            self.icon_label.setPixmap(icons.pixmap(icon, theme.current().accent_a, 18))
            head.addWidget(self.icon_label)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title_label = make_label(title, object_name="CardTitle")
        titles.addWidget(self.title_label)
        if subtitle:
            titles.addWidget(make_label(subtitle, role="hint", wrap=True))
        head.addLayout(titles, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(6)
        head.addLayout(self.actions)
        self._chevron: QToolButton | None = None
        if collapsible:
            self._chevron = QToolButton()
            self._chevron.setIcon(icons.icon("chevron-up", theme.current().text_dim, 16))
            self._chevron.clicked.connect(self.toggle)
            head.addWidget(self._chevron)
            self.header.clicked.connect(self.toggle)
            self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        outer.addWidget(self.header)

        self.body = QWidget()
        self.body.setObjectName("Transparent")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(10)
        outer.addWidget(self.body)
        if shadow and Motion.enabled:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(28)
            effect.setOffset(0, 6)
            effect.setColor(QColor(0, 0, 0, 90))
            self.setGraphicsEffect(effect)

    def add_widget(self, widget: QWidget) -> None:
        """Ajoute un widget au corps de la carte."""
        self.body_layout.addWidget(widget)

    def add_layout(self, layout) -> None:  # noqa: ANN001
        """Ajoute un layout au corps de la carte."""
        self.body_layout.addLayout(layout)

    def add_action(self, widget: QWidget) -> None:
        """Ajoute un widget (bouton) à droite de l'en-tête."""
        self.actions.addWidget(widget)

    @property
    def collapsed(self) -> bool:
        """Vrai si le corps est replié."""
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Replie/déplie le corps de la carte."""
        self._collapsed = collapsed
        self.body.setVisible(not collapsed)
        if self._chevron is not None:
            name = "chevron-down" if collapsed else "chevron-up"
            self._chevron.setIcon(icons.icon(name, theme.current().text_dim, 16))

    def toggle(self) -> None:
        """Inverse l'état replié."""
        self.set_collapsed(not self._collapsed)

    def set_active(self, active: bool) -> None:
        """Bordure d'accent (carte « active »)."""
        set_prop(self, "active", "true" if active else "false")


class SettingRow(QWidget):
    """Ligne « libellé (+ aide) à gauche, contrôle à droite »."""

    def __init__(self, label: str, control: QWidget, hint: str = "", tooltip: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.control = control
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(16)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.label = QLabel(label)
        text.addWidget(self.label)
        if hint:
            text.addWidget(make_label(hint, role="hint", wrap=True))
        holder = QWidget()
        holder.setLayout(text)
        holder.setMinimumWidth(170)
        holder.setMaximumWidth(280)
        layout.addWidget(holder, 4)
        layout.addWidget(control, 6, Qt.AlignmentFlag.AlignVCenter)
        if tooltip:
            self.setToolTip(_wrap_tooltip(tooltip))


def _wrap_tooltip(text: str, width: int = 70) -> str:
    """Rend une infobulle riche à largeur raisonnable."""
    import html
    return f'<div style="max-width:420px">{html.escape(text)}</div>' if len(text) > width else html.escape(text)


class AuroraBackground(QWidget):
    """Racine de la fenêtre : fond uni, ou fond « aurore » animé si la palette l'active."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Root")
        self._animated = False
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def set_animated(self, animated: bool) -> None:
        """Active le fond animé (sans effet si les animations sont coupées)."""
        self._animated = animated and Motion.enabled
        if self._animated:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        window = self.window()
        if window is not None and window.isActiveWindow() and self.isVisible():
            self._t += 0.012
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        pal = theme.current()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(pal.bg))
        if not self._animated:
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        blobs = ((pal.accent_a, 0.25, 0.30, 0.0), (pal.accent_b, 0.75, 0.65, 2.1), (pal.success, 0.5, 0.9, 4.2))
        for color, fx, fy, phase in blobs:
            cx = w * (fx + 0.12 * math.sin(self._t + phase))
            cy = h * (fy + 0.12 * math.cos(self._t * 0.8 + phase))
            radius = max(w, h) * 0.55
            grad = QRadialGradient(QPointF(cx, cy), radius)
            c0, c1 = QColor(color), QColor(color)
            c0.setAlphaF(0.16)
            c1.setAlphaF(0.0)
            grad.setColorAt(0.0, c0)
            grad.setColorAt(1.0, c1)
            p.fillRect(self.rect(), QBrush(grad))


class Toast(QFrame):
    """Message éphémère affiché en bas de la fenêtre."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 16, 10)
        self._label = QLabel()
        self._label.setWordWrap(True)
        row.addWidget(self._label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def show_message(self, text: str, tone: str = "info", duration_ms: int = 3500) -> None:
        """Affiche ``text`` ; ``tone`` : info, success, warning, error."""
        self._label.setText(text)
        set_prop(self, "tone", tone)
        self.setMaximumWidth(max(300, int(self.parentWidget().width() * 0.6)))
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(duration_ms)

    def reposition(self) -> None:
        """Replace le toast en bas au centre du parent."""
        parent = self.parentWidget()
        if parent is not None:
            self.move(QPoint(max(0, (parent.width() - self.width()) // 2), max(0, parent.height() - self.height() - 110)))
