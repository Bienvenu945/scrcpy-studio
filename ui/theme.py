"""Palettes, génération de la feuille de style (QSS) et application du thème.

Les fonctions de ce module ne dépendent de PySide6 que dans ``apply_theme`` et
``load_bundled_fonts`` (import différé) : palettes et QSS restent testables sans Qt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from config.defaults import DEFAULT_PALETTE, RESOURCES_DIR

FONT_CANDIDATES = ("Inter", "SF Pro Text", "SF Pro Display", "Segoe UI", "Helvetica Neue", "Ubuntu", "Roboto", "Arial")
MONO_CANDIDATES = ("JetBrains Mono", "Fira Code", "Cascadia Code", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", "Courier New")


@dataclass(frozen=True)
class Palette:
    """Jeu de couleurs complet d'une ambiance."""

    key: str
    label: str
    bg: str
    bg_secondary: str
    bg_card: str
    bg_card_alt: str
    border: str
    border_active: str
    accent_a: str
    accent_b: str
    success: str
    warning: str
    error: str
    text: str
    text_dim: str
    text_muted: str
    text_on_accent: str = "#FFFFFF"
    animated: bool = False
    glass: bool = True
    radius_card: int = 12
    radius_btn: int = 8


PALETTES: dict[str, Palette] = {
    "neon": Palette(
        "neon", "Néon bleu premium", "#0A0E1A", "#0F1420", "#141B2D", "#1A2338", "#1F2A44", "#3B82F6",
        "#3B82F6", "#8B5CF6", "#10B981", "#F59E0B", "#EF4444", "#F8FAFC", "#94A3B8", "#64748B", "#FFFFFF",
        animated=False, glass=True),
    "hyperos": Palette(
        "hyperos", "HyperOS sobre", "#0B0E14", "#0F141C", "#151B25", "#1D2532", "#263042", "#75B9FF",
        "#75B9FF", "#A78BFA", "#7EE2A8", "#FDCB6E", "#FF5C7A", "#F2F5FA", "#9AA7B8", "#6B7789", "#07111F",
        animated=False, glass=False, radius_card=16),
    "aurora": Palette(
        "aurora", "Aurore", "#0B0718", "#120C24", "#181030", "#21183F", "#2E2459", "#22D3EE",
        "#22D3EE", "#F472B6", "#34D399", "#FBBF24", "#FB7185", "#F5F3FF", "#A5A0C8", "#6F69A0", "#06121A",
        animated=True, glass=True),
    "gold": Palette(
        "gold", "Or", "#0E0C08", "#14110B", "#1C170F", "#262014", "#3A3020", "#F5C451",
        "#F5C451", "#E08E2B", "#A3E635", "#FB923C", "#EF4444", "#FBF7EC", "#B8AE96", "#7D745F", "#1A1305",
        animated=False, glass=False),
    "ocean": Palette(
        "ocean", "Océan", "#06141C", "#0A1C27", "#0F2633", "#15323F", "#1D4254", "#2DD4BF",
        "#2DD4BF", "#38BDF8", "#34D399", "#FBBF24", "#F87171", "#ECFEFF", "#8FB7C4", "#5E8795", "#04141A",
        animated=False, glass=True),
}

_CURRENT: Palette = PALETTES[DEFAULT_PALETTE]
_GLASS: bool = _CURRENT.glass


def current() -> Palette:
    """Palette active (utilisée par les widgets dessinés à la main)."""
    return _CURRENT


def glass_enabled() -> bool:
    """Vrai si le verre dépoli est actif."""
    return _GLASS


def set_current(palette: Palette, glass: bool | None = None) -> None:
    """Définit la palette active."""
    global _CURRENT, _GLASS
    _CURRENT = palette
    _GLASS = palette.glass if glass is None else glass


def get_palette(key: str) -> Palette:
    """Palette par clé (néon par défaut si inconnue)."""
    return PALETTES.get(key, PALETTES[DEFAULT_PALETTE])


# ───────────────────────────── couleurs ─────────────────────────────

def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """``#RRGGBB`` ou ``#RGB`` → (r, g, b)."""
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def rgba(color: str, alpha: float) -> str:
    """Couleur QSS ``rgba(r, g, b, a)`` avec ``alpha`` entre 0 et 1 (converti en 0-255)."""
    r, g, b = hex_to_rgb(color)
    return f"rgba({r}, {g}, {b}, {max(0, min(255, round(alpha * 255)))})"


def mix(color_a: str, color_b: str, ratio: float) -> str:
    """Mélange ``ratio`` de ``color_b`` dans ``color_a`` (``#RRGGBB``)."""
    a, b = hex_to_rgb(color_a), hex_to_rgb(color_b)
    r, g, bl = (round(x + (y - x) * ratio) for x, y in zip(a, b))
    return f"#{r:02X}{g:02X}{bl:02X}"


def pick_font(candidates: Iterable[str], available: Iterable[str], fallback: str = "sans-serif") -> str:
    """Première police candidate installée (insensible à la casse), sinon ``fallback``."""
    installed = {name.lower(): name for name in available}
    for name in candidates:
        if name.lower() in installed:
            return installed[name.lower()]
    return fallback


# ───────────────────────────── QSS ─────────────────────────────

QSS_TEMPLATE = """
QWidget { color: @TEXT@; font-family: "@FONT@"; font-size: 13px; }
QMainWindow, QWidget#Root { background: @BG@; }
QWidget#Transparent, QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QScrollArea { border: none; }
QLabel { background: transparent; }
QLabel:disabled { color: @TEXT_MUTED@; }
QToolTip { background: @POP@; color: @TEXT@; border: 1px solid @BORDER@; border-radius: 6px; padding: 6px 8px; }

QLabel#PageTitle { font-size: 24px; font-weight: 600; }
QLabel#PageSub, QLabel[role="hint"] { color: @TEXT_DIM@; font-size: 12px; }
QLabel#CardTitle { font-size: 14px; font-weight: 500; }
QLabel[role="dim"] { color: @TEXT_DIM@; }
QLabel[role="muted"] { color: @TEXT_MUTED@; }
QLabel[role="mono"] { font-family: "@MONO@"; font-size: 12px; }
QLabel[role="value"] { font-size: 16px; font-weight: 600; }
QLabel#AppTitle { font-size: 20px; font-weight: 600; }

QFrame#Card { background: @CARD_BG@; border: 1px solid @BORDER@; border-radius: @R_CARD@px; }
QFrame#Card[active="true"] { border: 1px solid @BORDER_ACTIVE@; }
QFrame#Inset { background: @BG@; border: 1px solid @BORDER@; border-radius: @R_BTN@px; }
QFrame#TitleBar { background: @BG_SURFACE@; border: none; border-bottom: 1px solid @BORDER@; }
QFrame#Sidebar { background: @BG_SURFACE@; border: 1px solid @BORDER@; border-radius: @R_CARD@px; }
QFrame#InfoPanel { background: transparent; border: none; }
QFrame#Dock { background: @BG_SURFACE@; border: none; border-top: 1px solid @BORDER@; }
QFrame#Tabs { background: @CARD_BG@; border: 1px solid @BORDER@; border-radius: @R_CARD@px; }
QFrame#Divider { background: @BORDER@; border: none; max-height: 1px; min-height: 1px; }
QFrame#VDivider { background: @BORDER@; border: none; max-width: 1px; min-width: 1px; }
QFrame#PromoCard { background: @CARD_ALT_BG@; border: 1px solid @BORDER@; border-radius: @R_BTN@px; }
QFrame#PromoCard:hover { border: 1px solid @BORDER_ACTIVE@; }
QFrame#IconBox { background: @ACCENT_A_15@; border: 1px solid @ACCENT_A_40@; border-radius: 10px; }
QFrame#Metric { background: @BG_ALT@; border: 1px solid @BORDER@; border-radius: 10px; }

QFrame#Pill { border-radius: 10px; padding: 2px 10px; font-size: 11px; background: @BG_ALT@; border: 1px solid @BORDER@; }
QLabel#Pill { border-radius: 10px; padding: 2px 10px; font-size: 11px; background: @BG_ALT@; border: 1px solid @BORDER@; color: @TEXT_DIM@; }
QLabel#Pill[tone="success"] { background: @SUCCESS_12@; border: 1px solid @SUCCESS_40@; color: @SUCCESS@; }
QLabel#Pill[tone="warning"] { background: @WARNING_12@; border: 1px solid @WARNING_40@; color: @WARNING@; }
QLabel#Pill[tone="error"] { background: @ERROR_12@; border: 1px solid @ERROR_40@; color: @ERROR@; }
QLabel#Pill[tone="accent"] { background: @ACCENT_A_15@; border: 1px solid @ACCENT_A_40@; color: @ACCENT_A@; }

QPushButton { background: @BG_ALT@; border: 1px solid @BORDER@; border-radius: @R_BTN@px; padding: 7px 14px; }
QPushButton:hover { border: 1px solid @BORDER_ACTIVE@; background: @HOVER@; }
QPushButton:pressed { background: @PRESSED@; }
QPushButton:disabled { color: @TEXT_MUTED@; background: @BG_SURFACE@; border: 1px solid @BORDER@; }
QPushButton:focus { border: 1px solid @ACCENT_A@; }
QPushButton#Primary { background: @GRAD@; border: none; color: @ON_ACCENT@; font-weight: 600; padding: 10px 22px; }
QPushButton#Primary:hover { background: @GRAD_HOVER@; }
QPushButton#Primary:disabled { background: @BG_ALT@; color: @TEXT_MUTED@; }
QPushButton#Stop { background: @ERROR_12@; border: 1px solid @ERROR_40@; color: @ERROR@; font-weight: 600; padding: 10px 22px; }
QPushButton#Stop:hover { background: @ERROR_25@; }
QPushButton#Ghost { background: transparent; border: 1px solid transparent; color: @TEXT_DIM@; }
QPushButton#Ghost:hover { color: @TEXT@; background: @HOVER@; border: 1px solid transparent; }
QPushButton#Link { background: transparent; border: none; color: @ACCENT_A@; padding: 2px 4px; text-align: left; }
QPushButton#Link:hover { text-decoration: underline; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: @R_BTN@px; padding: 6px; color: @TEXT_DIM@; }
QToolButton:hover { background: @HOVER@; color: @TEXT@; }
QToolButton:pressed { background: @PRESSED@; }
QToolButton#WinClose:hover { background: @ERROR@; color: #FFFFFF; }
QToolButton::menu-indicator { image: none; }

QPushButton#ActionRow { text-align: left; padding: 10px 12px; background: @BG_ALT@; }
QPushButton#ActionRow[active="true"] { border: 1px solid @ACCENT_A@; background: @ACCENT_A_15@; }
QLineEdit#CommandText { border: none; background: transparent; font-family: "@MONO@"; font-size: 12px; padding: 4px 2px; }
QLineEdit#PaletteInput { border: none; background: transparent; font-size: 16px; padding: 10px 6px; }
QPushButton#SidebarItem { text-align: left; padding: 9px 12px; border: none; background: transparent; color: @TEXT_DIM@; border-radius: @R_BTN@px; }
QPushButton#SidebarItem:hover { color: @TEXT@; background: @HOVER@; }
QPushButton#SidebarItem:checked { color: @TEXT@; font-weight: 600; background: transparent; }
QPushButton#SidebarSection { text-align: left; padding: 6px 8px; border: none; background: transparent; color: @TEXT_MUTED@; font-size: 11px; font-weight: 600; }
QPushButton#SidebarSection:hover { color: @TEXT_DIM@; background: transparent; }
QFrame#SidebarIndicator { background: @ACCENT_A_20@; border: 1px solid @ACCENT_A_40@; border-radius: @R_BTN@px; }

QPushButton#Segment { background: @BG@; border: 1px solid @BORDER@; border-radius: 0px; padding: 6px 14px; color: @TEXT_DIM@; }
QPushButton#Segment[pos="first"] { border-top-left-radius: @R_BTN@px; border-bottom-left-radius: @R_BTN@px; }
QPushButton#Segment[pos="last"] { border-top-right-radius: @R_BTN@px; border-bottom-right-radius: @R_BTN@px; }
QPushButton#Segment[pos="only"] { border-radius: @R_BTN@px; }
QPushButton#Segment:hover { color: @TEXT@; }
QPushButton#Segment:checked { background: @ACCENT_A_20@; border: 1px solid @ACCENT_A@; color: @TEXT@; font-weight: 600; }

QFrame#ModeToggle { background: @BG@; border: 1px solid @BORDER@; border-radius: 14px; }
QPushButton#ModeBtn { background: transparent; border: none; border-radius: 12px; padding: 3px 14px; font-size: 11px; font-weight: 600; color: @TEXT_DIM@; }
QPushButton#ModeBtn:checked { background: @GRAD@; color: @ON_ACCENT@; }
QPushButton#ModeBtn:hover:!checked { color: @TEXT@; }

QFrame#InstTab { background: @BG_ALT@; border: 1px solid @BORDER@; border-radius: @R_BTN@px; }
QFrame#InstTab[active="true"] { background: @ACCENT_A_20@; border: 1px solid @ACCENT_A@; }
QPushButton#TabBtn { background: transparent; border: none; padding: 6px 10px; color: @TEXT_DIM@; }
QPushButton#TabBtn:hover { color: @TEXT@; background: transparent; border: none; }
QPushButton#TabBtn[active="true"] { color: @TEXT@; font-weight: 600; }
QToolButton#TabClose { padding: 3px; border-radius: 6px; }
QPushButton#ProfileTab { background: transparent; border: 1px solid transparent; border-radius: @R_BTN@px; padding: 6px 14px; color: @TEXT_DIM@; }
QPushButton#ProfileTab:hover { color: @TEXT@; background: @HOVER@; }
QPushButton#ProfileTab[active="true"] { color: @TEXT@; background: @ACCENT_A_15@; border: 1px solid @ACCENT_A@; }

QFrame#PresetCard { background: @BG_ALT@; border: 1px solid @BORDER@; border-radius: 10px; }
QFrame#PresetCard:hover { border: 1px solid @TEXT_MUTED@; }
QFrame#PresetCard[tone="blue"] { background: @ACCENT_A_12@; border: 1px solid @ACCENT_A_40@; }
QFrame#PresetCard[tone="violet"] { background: @ACCENT_B_12@; border: 1px solid @ACCENT_B_40@; }
QFrame#PresetCard[tone="green"] { background: @SUCCESS_12@; border: 1px solid @SUCCESS_40@; }
QFrame#PresetCard[tone="orange"] { background: @WARNING_12@; border: 1px solid @WARNING_40@; }
QFrame#PresetCard[tone="blue"][active="true"] { border: 2px solid @ACCENT_A@; }
QFrame#PresetCard[tone="violet"][active="true"] { border: 2px solid @ACCENT_B@; }
QFrame#PresetCard[tone="green"][active="true"] { border: 2px solid @SUCCESS@; }
QFrame#PresetCard[tone="orange"][active="true"] { border: 2px solid @WARNING@; }

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox { background: @BG@; border: 1px solid @BORDER@; border-radius: @R_BTN@px; padding: 6px 10px; selection-background-color: @ACCENT_A@; selection-color: @ON_ACCENT@; }
QLineEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { border: 1px solid @TEXT_MUTED@; }
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid @ACCENT_A@; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QPlainTextEdit:disabled { color: @TEXT_MUTED@; background: @BG_SURFACE@; }
QLineEdit#Search { border-radius: 14px; padding: 8px 14px; }
QPlainTextEdit#Mono, QLineEdit#Mono, QTextEdit#Mono { font-family: "@MONO@"; font-size: 12px; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0px; border: none; }

QComboBox { background: @BG@; border: 1px solid @BORDER@; border-radius: @R_BTN@px; padding: 6px 10px; min-height: 18px; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: none; width: 0px; height: 0px; }
QComboBox QAbstractItemView { background: @POP@; border: 1px solid @BORDER@; selection-background-color: @ACCENT_A_20@; selection-color: @TEXT@; outline: 0; padding: 4px; }

QSlider::groove:horizontal { height: 6px; background: @BG_ALT@; border-radius: 3px; }
QSlider::sub-page:horizontal { background: @GRAD@; border-radius: 3px; }
QSlider::add-page:horizontal { background: @BG_ALT@; border-radius: 3px; }
QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; border-radius: 9px; background: @TEXT@; border: 2px solid @ACCENT_A@; }
QSlider::handle:horizontal:hover { background: @ACCENT_A@; }
QSlider::handle:horizontal:disabled { border: 2px solid @TEXT_MUTED@; background: @TEXT_MUTED@; }

QRadioButton, QCheckBox { spacing: 8px; background: transparent; }
QRadioButton::indicator { width: 16px; height: 16px; border-radius: 9px; border: 2px solid @TEXT_MUTED@; background: transparent; }
QRadioButton::indicator:hover { border: 2px solid @ACCENT_A@; }
QRadioButton::indicator:checked { border: 2px solid @ACCENT_A@; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 @ACCENT_A@, stop:0.5 @ACCENT_A@, stop:0.6 transparent, stop:1 transparent); }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 2px solid @TEXT_MUTED@; background: transparent; }
QCheckBox::indicator:checked { border: 2px solid @ACCENT_A@; background: @ACCENT_A@; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @BORDER@; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @TEXT_MUTED@; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @BORDER@; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QMenu { background: @POP@; border: 1px solid @BORDER@; border-radius: @R_BTN@px; padding: 6px; }
QMenu::item { padding: 7px 22px 7px 14px; border-radius: 6px; }
QMenu::item:selected { background: @ACCENT_A_20@; }
QMenu::separator { height: 1px; background: @BORDER@; margin: 5px 8px; }
QDialog, QMessageBox, QInputDialog { background: @BG_CARD@; }
QDialog#Palette { background: @POP@; border: 1px solid @BORDER_ACTIVE@; border-radius: 14px; }
QListWidget { background: @BG@; border: 1px solid @BORDER@; border-radius: @R_BTN@px; padding: 4px; outline: 0; }
QListWidget::item { padding: 8px 10px; border-radius: 6px; }
QListWidget::item:hover { background: @HOVER@; }
QListWidget::item:selected { background: @ACCENT_A_20@; color: @TEXT@; }
QListWidget#Palette { background: transparent; border: none; }
QFrame#Toast { background: @POP@; border: 1px solid @BORDER_ACTIVE@; border-radius: 10px; }
QFrame#Toast[tone="success"] { border: 1px solid @SUCCESS@; }
QFrame#Toast[tone="warning"] { border: 1px solid @WARNING@; }
QFrame#Toast[tone="error"] { border: 1px solid @ERROR@; }
QSizeGrip { background: transparent; width: 14px; height: 14px; }
"""

_PLAIN_TOKENS = {
    "@BG@": "bg", "@BG_SURFACE@": "bg_secondary", "@BG_CARD@": "bg_card", "@BG_ALT@": "bg_card_alt",
    "@BORDER@": "border", "@BORDER_ACTIVE@": "border_active", "@ACCENT_A@": "accent_a", "@ACCENT_B@": "accent_b",
    "@SUCCESS@": "success", "@WARNING@": "warning", "@ERROR@": "error", "@TEXT@": "text",
    "@TEXT_DIM@": "text_dim", "@TEXT_MUTED@": "text_muted", "@ON_ACCENT@": "text_on_accent",
}


def qss_tokens(p: Palette, glass: bool, font: str = "Inter", mono: str = "Consolas") -> dict[str, str]:
    """Table complète ``@TOKEN@ → valeur`` pour une palette."""
    tokens = {token: getattr(p, attr) for token, attr in _PLAIN_TOKENS.items()}
    tokens.update({
        "@FONT@": font, "@MONO@": mono,
        "@CARD_BG@": rgba(p.bg_card, 0.85 if glass else 1.0),
        "@CARD_ALT_BG@": rgba(p.bg_card_alt, 0.85 if glass else 1.0),
        "@POP@": mix(p.bg_card, "#FFFFFF", 0.07), "@INK@": p.text_on_accent,
        "@HOVER@": rgba("#FFFFFF", 0.05), "@PRESSED@": rgba("#FFFFFF", 0.09),
        "@R_CARD@": str(p.radius_card), "@R_BTN@": str(p.radius_btn),
        "@GRAD@": f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.accent_a}, stop:1 {p.accent_b})",
        "@GRAD_HOVER@": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %s, stop:1 %s)"
                        % (mix(p.accent_a, "#FFFFFF", 0.15), mix(p.accent_b, "#FFFFFF", 0.15)),
    })
    for name, color in (("ACCENT_A", p.accent_a), ("ACCENT_B", p.accent_b), ("SUCCESS", p.success),
                        ("WARNING", p.warning), ("ERROR", p.error)):
        for pct, alpha in ((12, 0.12), (15, 0.15), (20, 0.20), (25, 0.25), (40, 0.40)):
            tokens[f"@{name}_{pct}@"] = rgba(color, alpha)
    return tokens


def build_qss(p: Palette, glass: bool | None = None, font: str = "Inter", mono: str = "Consolas") -> str:
    """Feuille de style complète pour ``p`` (``glass=None`` : réglage de la palette)."""
    tokens = qss_tokens(p, p.glass if glass is None else glass, font, mono)
    qss = QSS_TEMPLATE
    for token in sorted(tokens, key=len, reverse=True):  # les plus longs d'abord (@ACCENT_A_20@ avant @ACCENT_A@)
        qss = qss.replace(token, tokens[token])
    return qss


def load_bundled_fonts() -> int:
    """Enregistre les polices de ``resources/fonts`` ; renvoie le nombre chargé."""
    from PySide6.QtGui import QFontDatabase

    loaded = 0
    folder = RESOURCES_DIR / "fonts"
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() in (".ttf", ".otf") and QFontDatabase.addApplicationFont(str(path)) >= 0:
                loaded += 1
    return loaded


def apply_theme(app, key: str, glass: bool | None = None) -> Palette:  # noqa: ANN001 - QApplication
    """Applique palette, police et QSS à l'application ; renvoie la palette active."""
    from PySide6.QtGui import QFont, QFontDatabase

    palette = get_palette(key)
    set_current(palette, glass)
    load_bundled_fonts()
    families = QFontDatabase.families()
    font = pick_font(FONT_CANDIDATES, families)
    mono = pick_font(MONO_CANDIDATES, families, "monospace")
    qfont = QFont(font)
    qfont.setPixelSize(13)
    app.setFont(qfont)
    app.setStyleSheet(build_qss(palette, glass_enabled(), font, mono))
    return palette
