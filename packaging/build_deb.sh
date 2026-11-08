#!/usr/bin/env bash
# Construit le paquet Debian de Scrcpy Studio.
#
#   packaging/build_deb.sh             paquet léger  : Python + PySide6 du système (architecture « all »)
#   packaging/build_deb.sh --bundled   paquet autonome : exécutable PyInstaller dans /opt (aucun PySide6 système requis)
#
# Résultat : dist/scrcpy-studio_<version>_<arch>.deb
# Variables : MAINTAINER="Nom <mail>"  OUT_DIR=<dossier de sortie>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"
MAINTAINER="${MAINTAINER:-Bienvenu K.K <bienvenu@localhost>}"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"
[[ -n "$VERSION" ]] || { echo "Version introuvable dans pyproject.toml" >&2; exit 1; }

MODE="light"
[[ "${1:-}" == "--bundled" ]] && MODE="bundled"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/pkg"
mkdir -p "$PKG/DEBIAN" "$PKG/usr/bin" "$PKG/usr/share/applications" "$PKG/usr/share/doc/scrcpy-studio"

if [[ "$MODE" == "light" ]]; then
    ARCH="all"
    DEPENDS="python3 (>= 3.11), python3-pyside6.qtcore, python3-pyside6.qtgui, python3-pyside6.qtwidgets, python3-pyside6.qtsvg"
    LIB="$PKG/usr/lib/scrcpy-studio"
    mkdir -p "$LIB"
    cp -r "$ROOT/main.py" "$ROOT/config" "$ROOT/core" "$ROOT/ui" "$ROOT/resources" "$ROOT/scrcpy_aide.txt" "$LIB/"
    find "$LIB" -name '__pycache__' -type d -prune -exec rm -rf {} +
    printf '#!/bin/sh\nexec python3 /usr/lib/scrcpy-studio/main.py "$@"\n' > "$PKG/usr/bin/scrcpy-studio"

    cat > "$PKG/DEBIAN/postinst" <<'SCRIPT'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    python3 -m compileall -q /usr/lib/scrcpy-studio >/dev/null 2>&1 || true
    if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database -q /usr/share/applications || true; fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true; fi
fi
exit 0
SCRIPT
    cat > "$PKG/DEBIAN/prerm" <<'SCRIPT'
#!/bin/sh
set -e
case "$1" in
    remove|upgrade|deconfigure)
        find /usr/lib/scrcpy-studio -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true ;;
esac
exit 0
SCRIPT
else
    ARCH="$(dpkg --print-architecture)"
    DEPENDS="libc6, libgl1, libfontconfig1, libdbus-1-3, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xkb1"
    command -v pyinstaller >/dev/null 2>&1 || python3 -m PyInstaller --version >/dev/null 2>&1 \
        || { echo "PyInstaller est requis : pip install pyinstaller PySide6" >&2; exit 1; }
    (cd "$ROOT" && python3 -m PyInstaller --noconfirm --clean --distpath "$STAGE/dist" --workpath "$STAGE/build" \
        --specpath "$STAGE/spec" "$ROOT/packaging/scrcpy_studio.spec") || exit 1
    mkdir -p "$PKG/opt"
    cp -a "$STAGE/dist/ScrcpyStudio" "$PKG/opt/scrcpy-studio"
    ln -s /opt/scrcpy-studio/ScrcpyStudio "$PKG/usr/bin/scrcpy-studio"
    cat > "$PKG/DEBIAN/postinst" <<'SCRIPT'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database -q /usr/share/applications || true; fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true; fi
fi
exit 0
SCRIPT
fi

# ── intégration bureau : lanceur, icônes ──
cp "$ROOT/packaging/scrcpy-studio.desktop" "$PKG/usr/share/applications/scrcpy-studio.desktop"
for size in 48 128 256; do
    mkdir -p "$PKG/usr/share/icons/hicolor/${size}x${size}/apps"
done
cp "$ROOT/resources/icons/scrcpy-studio-48.png"  "$PKG/usr/share/icons/hicolor/48x48/apps/scrcpy-studio.png"
cp "$ROOT/resources/icons/scrcpy-studio-128.png" "$PKG/usr/share/icons/hicolor/128x128/apps/scrcpy-studio.png"
cp "$ROOT/resources/icons/scrcpy-studio.png"     "$PKG/usr/share/icons/hicolor/256x256/apps/scrcpy-studio.png"
mkdir -p "$PKG/usr/share/icons/hicolor/scalable/apps"
cp "$ROOT/resources/icons/scrcpy-studio.svg" "$PKG/usr/share/icons/hicolor/scalable/apps/scrcpy-studio.svg"

# ── documentation Debian ──
cat > "$PKG/usr/share/doc/scrcpy-studio/copyright" <<COPYRIGHT
Scrcpy Studio
Copyright (C) 2026 Bienvenu K.K. Tous droits réservés.

Scrcpy Studio pilote scrcpy (projet distinct de Genymobile) sans en inclure le code.
COPYRIGHT
{
    echo "scrcpy-studio ($VERSION) unstable; urgency=low"
    echo
    echo "  * Version $VERSION : lanceur graphique PySide6 pour scrcpy 4.1 (modes BASE/PRO, multi-instances,"
    echo "    profils, préréglages, Command Palette, macros)."
    echo
    echo " -- $MAINTAINER  Mon, 19 Oct 2026 12:00:00 +0000"
} | gzip -9n > "$PKG/usr/share/doc/scrcpy-studio/changelog.gz"

# ── métadonnées ──
INSTALLED_SIZE="$(du -sk --exclude=DEBIAN "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<CONTROL
Package: scrcpy-studio
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: $DEPENDS
Recommends: scrcpy, adb
Maintainer: $MAINTAINER
Installed-Size: $INSTALLED_SIZE
Description: Lanceur graphique pour scrcpy
 Scrcpy Studio rend scrcpy accessible sans ligne de commande : mode BASE
 simplifié, mode PRO couvrant toutes les options de scrcpy 4.1,
 multi-instances, profils, préréglages, aperçu de l'appareil et
 palette de commandes.
CONTROL

# ── permissions ──
find "$PKG" -type d -exec chmod 755 {} +
if [[ "$MODE" == "light" ]]; then
    find "$PKG" -type f -exec chmod 644 {} +
fi
chmod 755 "$PKG/DEBIAN/postinst"
[[ -f "$PKG/DEBIAN/prerm" ]] && chmod 755 "$PKG/DEBIAN/prerm"
[[ "$MODE" == "light" ]] && chmod 755 "$PKG/usr/bin/scrcpy-studio"

mkdir -p "$OUT_DIR"
DEB="$OUT_DIR/scrcpy-studio_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$PKG" "$DEB" >/dev/null
echo "Paquet construit : $DEB"
