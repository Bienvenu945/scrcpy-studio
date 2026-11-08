"""Parser de ``scrcpy_aide.txt`` : descriptions d'options, raccourcis et recherche floue."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from config.defaults import HELP_FILE

_LONG = re.compile(r"--[a-z0-9][a-z0-9-]*")
_SHORT = re.compile(r"(?<![\w-])-[A-Za-z](?![\w-])")


@dataclass(frozen=True)
class HelpEntry:
    """Une option documentée."""

    key: str
    names: tuple[str, ...]
    signature: str
    description: str


@dataclass(frozen=True)
class Shortcut:
    """Un raccourci clavier / souris documenté."""

    keys: tuple[str, ...]
    description: str


class _Parsed:
    def __init__(self, entries: list[HelpEntry], shortcuts: list[Shortcut]) -> None:
        self.entries = entries
        self.shortcuts = shortcuts
        self.by_name: dict[str, HelpEntry] = {}
        for entry in entries:
            for name in entry.names:
                self.by_name[name] = entry


_CACHE: dict[Path, _Parsed] = {}


def _parse(text: str) -> _Parsed:
    entries: list[HelpEntry] = []
    shortcuts: list[Shortcut] = []
    section = ""
    header: str | None = None
    desc: list[str] = []
    keys: list[str] = []

    def flush_option() -> None:
        nonlocal header, desc
        if header is not None:
            longs = _LONG.findall(header)
            shorts = _SHORT.findall(header)
            names = tuple(longs + shorts)
            if names:
                entries.append(HelpEntry(names[0], names, header.strip(), " ".join(desc).strip()))
        header, desc = None, []

    def flush_shortcut() -> None:
        nonlocal keys, desc
        if keys:
            shortcuts.append(Shortcut(tuple(keys), " ".join(desc).strip()))
        keys, desc = [], []

    for line in text.splitlines():
        stripped = line.strip()
        if line and not line.startswith(" ") and stripped.endswith(":"):
            flush_option()
            flush_shortcut()
            section = stripped[:-1].lower()
            continue
        if section == "options":
            if line.startswith("    ") and not line.startswith("     ") and stripped.startswith("-"):
                flush_option()
                header = stripped
            elif header is not None and line.startswith("        ") and stripped:
                desc.append(stripped)
            elif not stripped:
                flush_option()
        elif section == "shortcuts":
            if line.startswith("    ") and not line.startswith("     ") and stripped:
                if desc:
                    flush_shortcut()
                keys.append(stripped)
            elif keys and line.startswith("        ") and stripped:
                desc.append(stripped)
    flush_option()
    flush_shortcut()
    return _Parsed(entries, shortcuts)


def _load(path: Path | str | None = None) -> _Parsed:
    target = Path(path) if path else HELP_FILE
    if target not in _CACHE:
        try:
            text = target.read_text(encoding="utf-8")
        except OSError:
            text = ""
        _CACHE[target] = _parse(text)
    return _CACHE[target]


def load_help(path: Path | str | None = None) -> dict[str, str]:
    """Charge l'aide : ``{option: description}`` (clé = nom long, ou court s'il n'existe pas de long)."""
    return {e.key: e.description for e in _load(path).entries}


def get_entry(option: str, path: Path | str | None = None) -> HelpEntry | None:
    """Entrée d'une option (``--max-size``, ``--max-size=1080``, ``-m``…)."""
    name = option.split("=", 1)[0].strip()
    return _load(path).by_name.get(name)


def get_description(option: str, path: Path | str | None = None) -> str:
    """Description d'une option, ou chaîne vide si inconnue."""
    entry = get_entry(option, path)
    return entry.description if entry else ""


def list_all(path: Path | str | None = None) -> list[str]:
    """Toutes les options (clés canoniques) dans l'ordre de l'aide."""
    return [e.key for e in _load(path).entries]


def list_long_options(path: Path | str | None = None) -> list[str]:
    """Toutes les options longues (``--xxx``) de l'aide."""
    return sorted({n for e in _load(path).entries for n in e.names if n.startswith("--")})


def load_shortcuts(path: Path | str | None = None) -> list[Shortcut]:
    """Raccourcis scrcpy documentés dans l'aide."""
    return list(_load(path).shortcuts)


def fuzzy_score(query: str, text: str) -> int | None:
    """Score de correspondance floue (None si ``query`` n'est pas une sous-séquence de ``text``)."""
    q, t = query.lower().strip(), text.lower()
    if not q:
        return 0
    idx = t.find(q)
    if idx >= 0:
        return 1000 - idx * 2 - (len(t) - len(q)) // 4 + (200 if idx == 0 else 0)
    pos, prev, score = -1, -2, 0
    for ch in q:
        pos = t.find(ch, pos + 1)
        if pos < 0:
            return None
        score += 10 + (15 if pos == prev + 1 else 0) + (10 if pos == 0 or t[pos - 1] in " -_/:" else 0)
        prev = pos
    return score - (len(t) - len(q)) // 10


def search(query: str, limit: int = 50, path: Path | str | None = None) -> list[str]:
    """Options correspondant à ``query`` (nom d'abord, puis description), meilleures en tête."""
    entries = _load(path).entries
    q = query.strip()
    if not q:
        return [e.key for e in entries][:limit]
    scored: list[tuple[int, int, str]] = []
    for order, entry in enumerate(entries):
        best = max((s for s in (fuzzy_score(q, n) for n in entry.names) if s is not None), default=None)
        if best is None and not q.startswith("-") and q.lower() in entry.description.lower():
            best = 200
        if best is not None:
            scored.append((-best, order, entry.key))
    scored.sort()
    return [key for _, _, key in scored[:limit]]
