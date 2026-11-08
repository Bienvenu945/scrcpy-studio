"""Description déclarative des lignes de réglages (Python pur, sans Qt)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.models import OPTIONS, Settings


@dataclass(frozen=True)
class Row:
    """Une ligne de réglage liée à un champ de ``Settings`` (ou d'``AppPrefs`` si ``target='prefs'``).

    ``kind`` : toggle, choice, radio, segment, resolution, slider, number, float, text, path, textarea.
    ``opt`` : option(s) scrcpy documentée(s) par la ligne (séparées par des espaces) ; sert aux
    infobulles et à la vérification de couverture.
    """

    field: str
    label: str
    kind: str = "toggle"
    opt: str = ""
    hint: str = ""
    options: Any = ""
    min: float = 0
    max: float = 100
    step: float = 1
    decimals: int = 0
    suffix: str = ""
    special: str = ""
    placeholder: str = ""
    path_mode: str = "save"
    mono: bool = False
    target: str = "settings"
    enabled_if: Callable[[Settings], bool] | None = None


@dataclass(frozen=True)
class CardSpec:
    """Carte regroupant des lignes."""

    title: str
    icon: str = "info"
    rows: tuple[Row, ...] = ()
    subtitle: str = ""
    collapsed: bool = False


def row_options(row: Row) -> tuple[tuple[Any, str], ...]:
    """Paires (valeur, libellé) d'une ligne à choix."""
    if isinstance(row.options, str):
        return OPTIONS.get(row.options, ())
    return tuple(row.options)


def option_names(row: Row) -> list[str]:
    """Options scrcpy documentées par une ligne."""
    return row.opt.split()


# ── constructeurs courts pour déclarer les vues ──

def toggle(field: str, label: str, opt: str = "", hint: str = "", **kw: Any) -> Row:
    """Interrupteur."""
    return Row(field, label, "toggle", opt, hint, **kw)


def choice(field: str, label: str, options: Any, opt: str = "", hint: str = "", **kw: Any) -> Row:
    """Liste déroulante (``options`` : clé de ``OPTIONS`` ou paires)."""
    return Row(field, label, "choice", opt, hint, options, **kw)


def radio(field: str, label: str, options: Any, opt: str = "", hint: str = "", **kw: Any) -> Row:
    """Boutons radio."""
    return Row(field, label, "radio", opt, hint, options, **kw)


def segment(field: str, label: str, options: Any, opt: str = "", hint: str = "", **kw: Any) -> Row:
    """Segments exclusifs."""
    return Row(field, label, "segment", opt, hint, options, **kw)


def slider(field: str, label: str, minimum: float, maximum: float, opt: str = "", step: float = 1,
           suffix: str = "", special: str = "", hint: str = "", decimals: int = 0, **kw: Any) -> Row:
    """Curseur + valeur."""
    return Row(field, label, "slider", opt, hint, min=minimum, max=maximum, step=step, decimals=decimals,
               suffix=suffix, special=special, **kw)


def number(field: str, label: str, minimum: float, maximum: float, opt: str = "", step: float = 1,
           suffix: str = "", special: str = "", hint: str = "", decimals: int = 0, **kw: Any) -> Row:
    """Champ numérique seul."""
    return Row(field, label, "number", opt, hint, min=minimum, max=maximum, step=step, decimals=decimals,
               suffix=suffix, special=special, **kw)


def text(field: str, label: str, opt: str = "", placeholder: str = "", hint: str = "", mono: bool = False,
         **kw: Any) -> Row:
    """Champ texte."""
    return Row(field, label, "text", opt, hint, placeholder=placeholder, mono=mono, **kw)


def path(field: str, label: str, opt: str = "", placeholder: str = "", mode: str = "save", hint: str = "",
         **kw: Any) -> Row:
    """Champ de chemin avec bouton Parcourir."""
    return Row(field, label, "path", opt, hint, placeholder=placeholder, path_mode=mode, **kw)
