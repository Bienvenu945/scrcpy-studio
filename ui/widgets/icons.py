"""Icônes SVG inline (style outline, trait homogène) rendues via QtSvg."""
from __future__ import annotations

from functools import lru_cache

_P = {
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    "bell": '<path d="M6 17v-6a6 6 0 0112 0v6l2 2H4z"/><path d="M10 21h4"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
    "settings": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    "minus": '<path d="M5 12h14"/>',
    "square": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "restore": '<rect x="4" y="8" width="12" height="12" rx="2"/><path d="M8 8V6a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2h-2"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "camera": '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
    "film": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 9.5v5l4.5-2.5z"/>',
    "volume": '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16.5 9a4 4 0 010 6M19 6.5a8 8 0 010 11"/>',
    "monitor": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "gamepad": '<rect x="2.5" y="7" width="19" height="10" rx="5"/><path d="M7 10v4M5 12h4"/><circle cx="16" cy="11" r="1"/><circle cx="18" cy="13" r="1"/>',
    "record": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5" fill="currentColor"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "wifi": '<path d="M2.5 9a14 14 0 0119 0M5.5 12.5a9.5 9.5 0 0113 0M8.7 16a5 5 0 016.6 0"/><circle cx="12" cy="19.2" r="1" fill="currentColor"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "chevron-up": '<path d="M6 15l6-6 6 6"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
    "copy": '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 012-2h9"/>',
    "save": '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v6h8V3M8 21v-7h8v7"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "flask": '<path d="M9 3h6M10 3v6l-5.5 9.5A1.5 1.5 0 005.8 21h12.4a1.5 1.5 0 001.3-2.5L14 9V3"/><path d="M7.5 15h9"/>',
    "rocket": '<path d="M14 4c3 0 6 1 6 1s1 3 1 6l-5.5 5.5-6-6z"/><path d="M8.5 11.5L4 13l2.5 2.5M12.5 15.5L11 20l-2.5-2.5"/><circle cx="15.5" cy="8.5" r="1.5"/>',
    "play": '<path d="M7 4.5v15l12-7.5z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "rotate": '<path d="M20 12a8 8 0 11-2.6-5.9"/><path d="M20 4v5h-5"/>',
    "fullscreen": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "terminal": '<path d="M4 6l5 5-5 5M12 18h8"/>',
    "home": '<path d="M4 11l8-7 8 7"/><path d="M6 10v10h12V10"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0116 0"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 114 2c-.9.6-1.5 1-1.5 2.2M12 17v.5"/>',
    "battery": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10.5v3"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "edit": '<path d="M4 20l1-4L16 5l3 3L8 19z"/>',
    "refresh": '<path d="M20 12a8 8 0 11-2.6-5.9"/><path d="M20 4v5h-5"/>',
    "folder": '<path d="M3 6h6l2 2h10v11H3z"/>',
    "bug": '<rect x="8" y="8" width="8" height="11" rx="4"/><path d="M12 8V5M5 12h3M16 12h3M6 18l2.5-2M18 18l-2.5-2M8 6l2 2M16 6l-2 2"/>',
    "cube": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12L4 7.5M12 12v9"/>',
    "sliders": '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="currentColor"/><circle cx="15" cy="12" r="2" fill="currentColor"/><circle cx="8" cy="18" r="2" fill="currentColor"/>',
    "link": '<path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1"/>',
    "window": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/>',
    "crop": '<path d="M6 2v14a2 2 0 002 2h14M2 6h14a2 2 0 012 2v14"/>',
    "download": '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
    "upload": '<path d="M12 16V5M7 9l5-5 5 5M5 20h14"/>',
    "list": '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
    "palette": '<path d="M12 3a9 9 0 100 18c1.5 0 2-1 1.5-2-.6-1.2.2-2.5 1.6-2.5H17a4 4 0 004-4A9 9 0 0012 3z"/><circle cx="8" cy="10" r="1"/><circle cx="12" cy="7.5" r="1"/><circle cx="16" cy="10" r="1"/>',
    "keyboard": '<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0013 0M12 17.5V21"/>',
}

ICON_NAMES = tuple(_P)


def svg_markup(name: str, color: str = "#FFFFFF", stroke: float = 1.8) -> str:
    """Document SVG complet de l'icône ``name`` (icône « info » si inconnue)."""
    inner = _P.get(name, _P["info"]).replace("currentColor", color)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>')


@lru_cache(maxsize=512)
def pixmap(name: str, color: str = "#FFFFFF", size: int = 20, stroke: float = 1.8):
    """``QPixmap`` net sur écrans HiDPI."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QGuiApplication, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    screen = QGuiApplication.primaryScreen()
    dpr = max(1.0, screen.devicePixelRatio()) if screen else 1.0
    side = int(round(size * dpr))
    pm = QPixmap(side, side)
    pm.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg_markup(name, color, stroke).encode("utf-8")))
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


@lru_cache(maxsize=512)
def icon(name: str, color: str = "#FFFFFF", size: int = 20, stroke: float = 1.8):
    """``QIcon`` correspondant à ``pixmap``."""
    from PySide6.QtGui import QIcon

    return QIcon(pixmap(name, color, size, stroke))


def clear_cache() -> None:
    """Vide les caches (après un changement de palette)."""
    pixmap.cache_clear()
    icon.cache_clear()
