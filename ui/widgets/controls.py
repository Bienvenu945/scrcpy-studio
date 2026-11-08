"""Contrôles de saisie : bouton, interrupteur, choix, segments, curseur+valeur, texte, chemin.

Tous les contrôles de saisie exposent la même API : ``value()``, ``setValue(v)`` (sans
émission) et le signal ``changed(object)`` (émis uniquement sur action de l'utilisateur).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QSize, QTimer, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDoubleSpinBox, QFileDialog, QGraphicsDropShadowEffect, QHBoxLayout, QLineEdit,
    QPlainTextEdit, QPushButton, QRadioButton, QSlider, QSpinBox, QToolButton, QWidget,
)

from core.models import RESOLUTIONS
from ui import theme
from ui.rows import Row, row_options
from ui.widgets import icons
from ui.widgets.animations import Motion


# ───────────────────────────── boutons ─────────────────────────────

class GlassButton(QPushButton):
    """Bouton avec icône ; variantes : default, primary, stop, ghost, link. Halo animé au survol (primary)."""

    def __init__(self, text: str = "", icon: str = "", variant: str = "default", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._icon_name = icon
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_variant(variant)
        self._glow: QGraphicsDropShadowEffect | None = None
        if variant == "primary":
            self._glow = QGraphicsDropShadowEffect(self)
            self._glow.setOffset(0, 0)
            self._glow.setBlurRadius(8)
            self._glow.setColor(QColor(theme.current().accent_a))
            self.setGraphicsEffect(self._glow)

    def set_variant(self, variant: str) -> None:
        """Change l'aspect (``default`` = bouton standard)."""
        self.setObjectName({"primary": "Primary", "stop": "Stop", "ghost": "Ghost", "link": "Link"}.get(variant, ""))
        pal = theme.current()
        color = {"primary": pal.text_on_accent, "stop": pal.error, "link": pal.accent_a}.get(variant, pal.text_dim)
        if self._icon_name:
            self.setIcon(icons.icon(self._icon_name, color, 18))
        self.style().unpolish(self)
        self.style().polish(self)

    def set_icon_name(self, name: str, variant: str | None = None) -> None:
        """Change l'icône (en conservant ou changeant la variante)."""
        self._icon_name = name
        self.set_variant(variant or {"Primary": "primary", "Stop": "stop", "Ghost": "ghost", "Link": "link"}.get(self.objectName(), "default"))

    def _animate_glow(self, radius: float) -> None:
        if self._glow is None or not Motion.enabled:
            return
        anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        anim.setDuration(160)
        anim.setEndValue(radius)
        anim.start()
        self._glow_anim = anim

    def enterEvent(self, event) -> None:  # noqa: N802, ANN001
        self._animate_glow(26)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802, ANN001
        self._animate_glow(8)
        super().leaveEvent(event)


class IconButton(QToolButton):
    """Bouton icône seule avec infobulle."""

    def __init__(self, icon: str, tooltip: str = "", size: int = 18, color: str = "", object_name: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(icons.icon(icon, color or theme.current().text_dim, size))
        self.setIconSize(QSize(size, size))
        self.setToolTip(tooltip)
        if object_name:
            self.setObjectName(object_name)


# ───────────────────────────── interrupteur ─────────────────────────────

class Toggle(QWidget):
    """Interrupteur animé (clic, Espace ou Entrée)."""

    changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._checked = False
        self._pos = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, value: object) -> None:
        self._pos = float(value)  # type: ignore[arg-type]
        self.update()

    def value(self) -> bool:
        """État courant."""
        return self._checked

    def setValue(self, value: Any) -> None:  # noqa: N802
        """Définit l'état sans émettre."""
        self._set(bool(value), animate=self.isVisible())

    def _set(self, checked: bool, animate: bool) -> None:
        self._checked = checked
        target = 1.0 if checked else 0.0
        self._anim.stop()
        if animate and Motion.enabled:
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._pos = target
            self.update()

    def _user_toggle(self) -> None:
        self._set(not self._checked, animate=True)
        self.changed.emit(self._checked)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self._user_toggle()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802, ANN001
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.isEnabled():
            self._user_toggle()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        pal = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        track = QColor(theme.mix(pal.border, pal.accent_a, self._pos))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(self.rect().adjusted(1, 3, -1, -3), 9, 9)
        if self.hasFocus():
            p.setPen(QPen(QColor(pal.accent_a), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(self.rect().adjusted(0, 2, 0, -2), 10, 10)
        knob_x = 4 + (self.width() - 8 - 16) * self._pos
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(knob_x + 8, self.height() / 2), 8, 8)


# ───────────────────────────── choix ─────────────────────────────

class ChoiceBox(QComboBox):
    """Liste déroulante (valeur, libellé) avec chevron dessiné."""

    changed = Signal(object)

    def __init__(self, options: Sequence[tuple[Any, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        for value, label in options:
            self.addItem(label, value)
        self.activated.connect(self._on_activated)

    def _on_activated(self, index: int) -> None:
        self.changed.emit(self.itemData(index))

    def value(self) -> Any:
        """Valeur sélectionnée."""
        return self.currentData()

    def setValue(self, value: Any) -> None:  # noqa: N802
        """Sélectionne ``value`` (sans émettre) ; tente aussi sa forme texte."""
        index = self.findData(value)
        if index < 0:
            index = self.findData(str(value))
        if index >= 0:
            self.setCurrentIndex(index)

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(theme.current().text_dim), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx, cy = self.width() - 16, self.height() / 2
        p.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2))
        p.drawLine(QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2))


class ResolutionBox(ChoiceBox):
    """Choix de résolution (--max-size) ; « Personnalisée » est informatif."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__([(v, label) for v, label in RESOLUTIONS] + [(-1, "Personnalisée")], parent)
        self._last = 0

    def _on_activated(self, index: int) -> None:
        data = self.itemData(index)
        if data == -1:
            self.setValue(self._last)  # « Personnalisée » ne se choisit pas : la valeur exacte se règle ailleurs
            return
        self._last = int(data)
        self.changed.emit(data)

    def setValue(self, value: Any) -> None:  # noqa: N802
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = 0
        self._last = number
        index = self.findData(number)
        self.setCurrentIndex(index if index >= 0 else self.findData(-1))


class RadioGroup(QWidget):
    """Boutons radio horizontaux (ex. codec vidéo)."""

    changed = Signal(object)

    def __init__(self, options: Sequence[tuple[Any, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        self._group = QButtonGroup(self)
        self._buttons: dict[Any, QRadioButton] = {}
        self._loading = False
        for value, label in options:
            button = QRadioButton(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.toggled.connect(lambda on, v=value: self._on_toggled(on, v))
            self._group.addButton(button)
            self._buttons[value] = button
            layout.addWidget(button)
        layout.addStretch(1)

    def _on_toggled(self, on: bool, value: Any) -> None:
        if on and not self._loading:
            self.changed.emit(value)

    def value(self) -> Any:
        """Valeur cochée (None si aucune)."""
        return next((v for v, b in self._buttons.items() if b.isChecked()), None)

    def setValue(self, value: Any) -> None:  # noqa: N802
        """Coche ``value`` sans émettre."""
        self._loading = True
        button = self._buttons.get(value) or self._buttons.get(str(value))
        if button is not None:
            button.setChecked(True)
        self._loading = False


class Segmented(QWidget):
    """Groupe de boutons exclusifs (segments)."""

    changed = Signal(object)

    def __init__(self, options: Sequence[tuple[Any, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[Any, QPushButton] = {}
        self._loading = False
        count = len(options)
        for i, (value, label) in enumerate(options):
            button = QPushButton(label)
            button.setObjectName("Segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("pos", "only" if count == 1 else "first" if i == 0 else "last" if i == count - 1 else "mid")
            button.toggled.connect(lambda on, v=value: self._on_toggled(on, v))
            self._group.addButton(button)
            self._buttons[value] = button
            layout.addWidget(button)
        layout.addStretch(1)

    def _on_toggled(self, on: bool, value: Any) -> None:
        if on and not self._loading:
            self.changed.emit(value)

    def value(self) -> Any:
        """Valeur sélectionnée."""
        return next((v for v, b in self._buttons.items() if b.isChecked()), None)

    def setValue(self, value: Any) -> None:  # noqa: N802
        """Sélectionne ``value`` sans émettre."""
        self._loading = True
        button = self._buttons.get(value) or self._buttons.get(str(value))
        if button is not None:
            button.setChecked(True)
        self._loading = False


# ───────────────────────────── nombres ─────────────────────────────

class SliderSpin(QWidget):
    """Curseur + champ numérique synchronisés (entier ou décimal)."""

    changed = Signal(object)

    def __init__(self, minimum: float, maximum: float, step: float = 1, decimals: int = 0, suffix: str = "",
                 special: str = "", slider: bool = True, spin_width: int = 104, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scale = 10 ** decimals
        self._decimals = decimals
        self._busy = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.slider: QSlider | None = None
        if slider:
            self.slider = QSlider(Qt.Orientation.Horizontal)
            self.slider.setRange(int(round(minimum * self._scale)), int(round(maximum * self._scale)))
            self.slider.setSingleStep(max(1, int(round(step * self._scale))))
            self.slider.setMinimumWidth(140)
            self.slider.valueChanged.connect(self._on_slider)
            layout.addWidget(self.slider, 1)
        if decimals:
            self.spin: QSpinBox | QDoubleSpinBox = QDoubleSpinBox()
            self.spin.setDecimals(decimals)
        else:
            self.spin = QSpinBox()
        if decimals:
            self.spin.setRange(float(minimum), float(maximum))
            self.spin.setSingleStep(float(step))
        else:
            self.spin.setRange(int(minimum), int(maximum))
            self.spin.setSingleStep(int(step))
        if suffix:
            self.spin.setSuffix(suffix)
        if special:
            self.spin.setSpecialValueText(special)
        self.spin.setFixedWidth(spin_width)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.spin.valueChanged.connect(self._on_spin)
        layout.addWidget(self.spin)
        if not slider:
            layout.addStretch(1)

    def _number(self, raw: float) -> int | float:
        return round(raw, self._decimals) if self._decimals else int(round(raw))

    def _on_slider(self, raw: int) -> None:
        if self._busy:
            return
        self._busy = True
        self.spin.setValue(raw / self._scale if self._decimals else raw)
        self._busy = False
        self.changed.emit(self._number(raw / self._scale))

    def _on_spin(self, value: float) -> None:
        if self._busy:
            return
        self._busy = True
        if self.slider is not None:
            self.slider.setValue(int(round(value * self._scale)))
        self._busy = False
        self.changed.emit(self._number(value))

    def value(self) -> int | float:
        """Valeur courante."""
        return self._number(self.spin.value())

    def setValue(self, value: Any) -> None:  # noqa: N802
        """Définit la valeur sans émettre."""
        self._busy = True
        number = float(value)
        self.spin.setValue(number if self._decimals else int(round(number)))
        if self.slider is not None:
            self.slider.setValue(int(round(number * self._scale)))
        self._busy = False


# ───────────────────────────── texte ─────────────────────────────

class TextField(QLineEdit):
    """Champ texte ; ``changed`` après 350 ms d'inactivité ou à la validation."""

    changed = Signal(object)

    def __init__(self, placeholder: str = "", mono: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        if mono:
            self.setObjectName("Mono")
        self._last = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._emit)
        self.textEdited.connect(lambda _text: self._timer.start())
        self.editingFinished.connect(self._emit)

    def _emit(self) -> None:
        self._timer.stop()
        text = self.text()
        if text != self._last:
            self._last = text
            self.changed.emit(text)

    def value(self) -> str:
        """Texte courant."""
        return self.text()

    def setValue(self, value: Any) -> None:  # noqa: N802
        """Définit le texte sans émettre (n'écrase pas une saisie en cours identique)."""
        text = "" if value is None else str(value)
        self._last = text
        if self.text() != text:
            self.setText(text)


class TextAreaField(QPlainTextEdit):
    """Zone de texte multiligne avec la même API."""

    changed = Signal(object)

    def __init__(self, placeholder: str = "", mono: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        if mono:
            self.setObjectName("Mono")
        self.setFixedHeight(84)
        self._last = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(450)
        self._timer.timeout.connect(self._emit)
        self.textChanged.connect(self._on_text)
        self._loading = False

    def _on_text(self) -> None:
        if not self._loading:
            self._timer.start()

    def _emit(self) -> None:
        text = self.toPlainText()
        if text != self._last:
            self._last = text
            self.changed.emit(text)

    def value(self) -> str:
        """Texte courant."""
        return self.toPlainText()

    def setValue(self, value: Any) -> None:  # noqa: N802
        """Définit le texte sans émettre."""
        text = "" if value is None else str(value)
        self._last = text
        if self.toPlainText() != text:
            self._loading = True
            self.setPlainText(text)
            self._loading = False


class PathField(QWidget):
    """Champ de chemin avec bouton « Parcourir » (modes : save, open, dir)."""

    changed = Signal(object)

    def __init__(self, mode: str = "save", placeholder: str = "", filters: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.filters = filters
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.edit = TextField(placeholder)
        self.edit.changed.connect(self.changed)
        layout.addWidget(self.edit, 1)
        self.button = IconButton("folder", "Parcourir…")
        self.button.clicked.connect(self._browse)
        layout.addWidget(self.button)

    def _browse(self) -> None:
        start = self.edit.text() or str(Path.home())
        if self.mode == "dir":
            path = QFileDialog.getExistingDirectory(self, "Choisir un dossier", start)
        elif self.mode == "open":
            path, _ = QFileDialog.getOpenFileName(self, "Choisir un fichier", start, self.filters)
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Choisir un fichier", start, self.filters)
        if path:
            self.edit.setText(path)
            self.edit._emit()

    def value(self) -> str:
        """Chemin saisi."""
        return self.edit.text()

    def setValue(self, value: Any) -> None:  # noqa: N802
        """Définit le chemin sans émettre."""
        self.edit.setValue(value)


# ───────────────────────────── fabrique ─────────────────────────────

def make_control(row: Row) -> QWidget:
    """Construit le contrôle adapté à ``row.kind`` (même API pour tous)."""
    kind = row.kind
    if kind == "toggle":
        return Toggle()
    if kind == "choice":
        return ChoiceBox(row_options(row))
    if kind == "resolution":
        return ResolutionBox()
    if kind == "radio":
        return RadioGroup(row_options(row))
    if kind == "segment":
        return Segmented(row_options(row))
    if kind == "slider":
        return SliderSpin(row.min, row.max, row.step, row.decimals, row.suffix, row.special, slider=True)
    if kind in ("number", "float"):
        return SliderSpin(row.min, row.max, row.step, row.decimals, row.suffix, row.special, slider=False)
    if kind == "path":
        return PathField(row.path_mode, row.placeholder)
    if kind == "textarea":
        return TextAreaField(row.placeholder, row.mono)
    if kind == "text":
        return TextField(row.placeholder, row.mono)
    raise ValueError(f"Type de ligne inconnu : {kind!r} ({row.field})")
