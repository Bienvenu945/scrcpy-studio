"""Point d'entrée de Scrcpy Studio."""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging() -> Path | None:
    """Journal dans ``scrcpy-studio.log`` (dossier de configuration) et capture des exceptions non gérées.

    Indispensable pour l'exécutable Windows sans console. Renvoie le chemin du journal, ou None si
    le dossier n'est pas accessible en écriture.
    """
    from logging.handlers import RotatingFileHandler

    from config.defaults import config_dir

    try:
        folder = config_dir()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "scrcpy-studio.log"
        handler = RotatingFileHandler(path, maxBytes=512_000, backupCount=2, encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    def hook(exc_type, exc, tb) -> None:  # noqa: ANN001
        logging.getLogger("scrcpy-studio").critical("Exception non gérée", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook
    return path


def main(argv: list[str] | None = None) -> int:
    """Démarre l'application ; renvoie le code de sortie."""
    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 est requis : pip install -r requirements.txt", file=sys.stderr)
        return 1

    from config.defaults import APP_ID, APP_NAME, RESOURCES_DIR
    from config.settings_store import SettingsStore
    from core.adb import AdbClient
    from core.instances import InstanceManager
    from core.process import DISPATCHER
    from core.scrcpy import find_executable
    from ui.context import Context
    from ui.widgets import icons
    from ui.window import MainWindow

    setup_logging()
    if sys.platform == "win32":  # regroupe la fenêtre sous sa propre icône dans la barre des tâches
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass

    app = QApplication(list(argv if argv is not None else sys.argv))
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    icon_file = RESOURCES_DIR / "icons" / "scrcpy-studio.png"
    if icon_file.is_file():
        app.setWindowIcon(QIcon(str(icon_file)))

    store = SettingsStore()
    prefs = store.load_prefs()
    manager = InstanceManager(store, prefs, dispatcher=DISPATCHER)
    manager.load()
    adb = AdbClient(find_executable("adb", prefs.adb_path) or "adb")
    ctx = Context(prefs, manager, adb, store, DISPATCHER)

    window = MainWindow(ctx, app)
    window.show()
    code = app.exec()
    icons.clear_cache()  # libère les QPixmap avant la destruction de QApplication
    return code


if __name__ == "__main__":
    sys.exit(main())
