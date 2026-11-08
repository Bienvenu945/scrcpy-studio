"""Fenêtre principale : 5 zones (A titre · B navigation · C vue · D contexte · E action dock)."""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QInputDialog, QDialog, QMenu, QPlainTextEdit, QSizeGrip, QStackedWidget,
    QVBoxLayout, QWidget,
)

from config.defaults import APP_VERSION, MAIN_PROFILE, MAX_INSTANCES
from core import scrcpy_help
from core.process import DISPATCHER, run_async
from core.scrcpy import has_errors
from ui import theme
from ui.context import Context, PaletteItem
from ui.views import VIEWS, info_for, load_view_class, sidebar_sections, views_for_mode
from ui.views.base_view import BaseView, confirm
from ui.views.device import save_preset_dialog
from ui.widgets import icons
from ui.widgets.animations import Motion, fade_in
from ui.widgets.command_bar import CommandBar
from ui.widgets.command_palette import CommandPalette
from ui.widgets.controls import GlassButton
from ui.widgets.glass import AuroraBackground, Toast
from ui.widgets.info_panel import InfoPanel
from ui.widgets.instance_tabs import InstanceTabs
from ui.widgets.profile_tabs import ProfileTabs
from ui.widgets.sidebar import Sidebar
from ui.widgets.status_bar import StatusBar
from ui.widgets.titlebar import TitleBar

APPEARANCE_PREFS = {"palette", "glass", "animated", "reduce_motion"}


class MainWindow(QWidget):
    """Fenêtre sans cadre système, composée des zones A à E."""

    def __init__(self, ctx: Context, app: QApplication | None = None) -> None:
        super().__init__()
        self.ctx = ctx
        self.app = app
        self.setWindowTitle("Scrcpy Studio")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self._views: dict[str, BaseView] = {}
        self._current_key = ""
        self._focus_saved: tuple[bool, bool] | None = None
        self._test_running = False
        self._sidebar_sig: tuple | None = None
        self._tabs_sig: tuple | None = None
        self._profiles_sig: tuple | None = None
        self._rebuild_pending = False
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)

        self._apply_theme()
        self._assemble()
        self._install_hooks()
        self._timers()
        self.refresh_all()
        ctx.refresh_devices()
        self.show_view("device", animate=False)

    def _assemble(self) -> None:
        """Crée la racine et les cinq zones (appelé aussi lors d'un changement de palette)."""
        self.root = AuroraBackground(self)
        self._outer.addWidget(self.root)
        self._build()
        self._wire_widgets()
        self._apply_background()

    def _build(self) -> None:
        column = QVBoxLayout(self.root)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self.titlebar = TitleBar(APP_VERSION)  # A
        column.addWidget(self.titlebar)

        middle = QHBoxLayout()
        middle.setContentsMargins(14, 14, 14, 14)
        middle.setSpacing(14)
        self.sidebar = Sidebar()  # B
        middle.addWidget(self.sidebar)

        center = QVBoxLayout()  # C
        center.setSpacing(10)
        self.instance_tabs = InstanceTabs()
        self.profile_tabs = ProfileTabs()
        self.stack = QStackedWidget()
        center.addWidget(self.instance_tabs)
        center.addWidget(self.profile_tabs)
        center.addWidget(self.stack, 1)
        middle.addLayout(center, 1)

        self.info_panel = InfoPanel()  # D
        middle.addWidget(self.info_panel)
        column.addLayout(middle, 1)

        self.dock = QFrame()  # E
        self.dock.setObjectName("Dock")
        self.dock.setFixedHeight(84)
        dock_row = QHBoxLayout(self.dock)
        dock_row.setContentsMargins(20, 0, 20, 0)
        dock_row.setSpacing(16)
        self.status = StatusBar()
        self.command_bar = CommandBar()
        self.test_button = GlassButton("Test", "flask")
        self.test_button.setToolTip("Lance scrcpy 3 secondes pour vérifier la configuration")
        self.launch_button = GlassButton("LAUNCH SCRCPY", "rocket", "primary")
        self.launch_button.setMinimumWidth(190)
        dock_row.addWidget(self.status)
        dock_row.addWidget(self.command_bar, 1)
        dock_row.addWidget(self.test_button)
        dock_row.addWidget(self.launch_button)
        column.addWidget(self.dock)

        self.grip = QSizeGrip(self)
        self.toast = Toast(self)
        self.command_palette = CommandPalette(self)

    def _wire_widgets(self) -> None:
        ctx = self.ctx
        self.titlebar.menu_clicked.connect(self.toggle_sidebar)
        self.titlebar.search_clicked.connect(self.open_palette)
        self.titlebar.settings_clicked.connect(lambda: self.show_view("settings"))
        self.titlebar.bell_clicked.connect(self._show_notifications)
        self.titlebar.mode_changed.connect(self.set_mode)
        self.sidebar.navigate.connect(self.show_view)
        self.sidebar.promo_clicked.connect(lambda: self.set_mode("pro"))
        self.sidebar.about_clicked.connect(lambda: self.show_view("about"))

        self.instance_tabs.selected.connect(ctx.manager.set_current)
        self.instance_tabs.closed.connect(self.close_instance)
        self.instance_tabs.new_requested.connect(self.new_instance)
        self.profile_tabs.selected.connect(self._select_profile)
        self.profile_tabs.add_requested.connect(self._add_profile)
        self.profile_tabs.rename_requested.connect(self._rename_profile)
        self.profile_tabs.duplicate_requested.connect(self._duplicate_profile)
        self.profile_tabs.delete_requested.connect(self._delete_profile)

        self.info_panel.copy_requested.connect(self.copy_command)
        self.info_panel.preset_requested.connect(lambda: save_preset_dialog(ctx, self))
        self.info_panel.more_info_requested.connect(self._device_details)
        self.status.stop_clicked.connect(self.stop)
        self.test_button.clicked.connect(self.test)
        self.launch_button.clicked.connect(self.toggle_launch)

    def _install_hooks(self) -> None:
        """Branchements uniques : actions globales, abonnement au contexte, raccourcis clavier."""
        ctx = self.ctx
        ctx.navigate = self.show_view
        ctx.actions.update({"launch": self.launch, "stop": self.stop, "test": self.test, "copy": self.copy_command})
        ctx.subscribe(self._on_ctx_event)

        def shortcut(keys: str, handler: Any) -> None:
            QShortcut(QKeySequence(keys), self).activated.connect(handler)

        shortcut("Ctrl+Return", self.launch)
        shortcut("Ctrl+Enter", self.launch)
        shortcut("Ctrl+.", self.stop)
        shortcut("Ctrl+K", self.open_palette)
        shortcut("Ctrl+B", self.toggle_sidebar)
        shortcut("Ctrl+D", self.toggle_info)
        shortcut("F11", self.toggle_focus)
        shortcut("Ctrl+,", lambda: self.show_view("settings"))
        shortcut("F1", lambda: self.open_palette("--"))
        shortcut("Ctrl+T", self.new_instance)
        shortcut("Ctrl+W", lambda: self.close_instance(ctx.manager.current_id))
        shortcut("Ctrl+Tab", lambda: ctx.manager.cycle(1))
        shortcut("Ctrl+Shift+Tab", lambda: ctx.manager.cycle(-1))
        shortcut("Ctrl+Q", self.close)
        for number in range(1, 10):
            shortcut(f"Ctrl+{number}", lambda n=number: self._goto_index(n - 1))

    def _timers(self) -> None:
        self._pump = QTimer(self)  # vide la file d'événements des threads de travail
        self._pump.setInterval(40)
        self._pump.timeout.connect(lambda: DISPATCHER.drain())
        self._pump.start()
        self._metrics = QTimer(self)
        self._metrics.setInterval(2000)
        self._metrics.timeout.connect(self._tick_metrics)
        self._metrics.start()
        self._devices = QTimer(self)
        self._devices.setInterval(5000)
        self._devices.timeout.connect(self._poll_devices)
        self._devices.start()
        self._autosave = QTimer(self)
        self._autosave.setInterval(4000)
        self._autosave.timeout.connect(self.ctx.flush)
        self._autosave.start()

    # ───────────────────────── apparence ─────────────────────────
    def _apply_theme(self) -> None:
        prefs = self.ctx.prefs
        Motion.enabled = not prefs.reduce_motion
        icons.clear_cache()
        if self.app is not None:
            theme.apply_theme(self.app, prefs.palette, prefs.glass)
        else:
            theme.set_current(theme.get_palette(prefs.palette), prefs.glass)

    def _apply_background(self) -> None:
        palette = theme.current()
        self.root.set_animated(bool(self.ctx.prefs.animated or palette.animated) and Motion.enabled)

    def rebuild_ui(self) -> None:
        """Reconstruit toute l'interface avec la palette courante (icônes et QSS recolorés)."""
        self._rebuild_pending = False
        current = self._current_key
        self._apply_theme()
        self._outer.removeWidget(self.root)
        self.root.hide()
        self.root.setParent(None)
        self.root.deleteLater()
        self._views.clear()
        self._current_key = ""
        self._sidebar_sig = self._tabs_sig = self._profiles_sig = None
        self._assemble()
        self.refresh_all()
        self.show_view(current or "device", animate=False)

    # ───────────────────────── navigation ─────────────────────────
    def _entries(self) -> list[tuple[str, list[tuple[str, str, str]]]]:
        mode = self.ctx.mode
        sections = []
        for title, views in sidebar_sections(mode):
            entries = [(v.key, v.label, v.icon) for v in views if not (v.key == "macros" and not self.ctx.pref("macros_enabled"))]
            if entries:
                sections.append((title, entries))
        return sections

    def _view(self, key: str) -> BaseView | None:
        if key not in self._views:
            info = info_for(key)
            if info is None:
                return None
            view = load_view_class(info)(self.ctx)
            self._views[key] = view
            self.stack.addWidget(view)
        return self._views[key]

    def show_view(self, key: str, animate: bool = True) -> None:
        """Affiche la vue ``key`` (bascule en PRO si elle l'exige)."""
        info = info_for(key)
        if info is None:
            return
        if info.section == "pro" and self.ctx.mode != "pro":
            self.set_mode("pro", keep=key)
        view = self._view(key)
        if view is None:
            return
        self._current_key = key
        self.stack.setCurrentWidget(view)
        view.on_enter()
        self.sidebar.select(key, animate)
        if animate:
            fade_in(view, 200)

    def _goto_index(self, index: int) -> None:
        views = [v for v in views_for_mode(self.ctx.mode)]
        if 0 <= index < len(views):
            self.show_view(views[index].key)

    def _sync_sidebar(self, force: bool = False) -> None:
        entries = self._entries()
        signature = tuple((title, tuple(e[0] for e in items)) for title, items in entries)
        if force or signature != self._sidebar_sig:
            self._sidebar_sig = signature
            self.sidebar.set_entries(entries, self._current_key)

    def set_mode(self, mode: str, keep: str = "") -> None:
        """Bascule BASE ↔ PRO (instantanée, mémorisée) ; ``keep`` : vue à conserver."""
        if mode == self.ctx.mode and not keep:
            return
        self.ctx.set_pref("ui_mode", mode)
        self.titlebar.mode_toggle.set_mode(mode)
        self._sync_sidebar(force=True)
        available = {v.key for v in views_for_mode(mode)} | {"about", "settings"}
        target = keep or self._current_key
        if target not in available:
            target = views_for_mode(mode)[0].key
        if keep:
            self.sidebar.select(keep, animate=False)
        else:
            self.show_view(target, animate=False)

    # ───────────────────────── panneaux ─────────────────────────
    def toggle_sidebar(self) -> None:
        """Ctrl+B."""
        visible = not self.sidebar.isVisible()
        self.sidebar.setVisible(visible)
        self.ctx.set_pref("sidebar_visible", visible)

    def toggle_info(self) -> None:
        """Ctrl+D."""
        visible = not self.info_panel.isVisible()
        self.info_panel.setVisible(visible)
        self.ctx.set_pref("info_visible", visible)

    def toggle_focus(self) -> None:
        """F11 : masque B et D d'un coup, puis les restaure."""
        if self._focus_saved is None:
            self._focus_saved = (self.sidebar.isVisible(), self.info_panel.isVisible())
            self.sidebar.hide()
            self.info_panel.hide()
        else:
            sidebar, info = self._focus_saved
            self._focus_saved = None
            self.sidebar.setVisible(sidebar)
            self.info_panel.setVisible(info)

    # ───────────────────────── instances & profils ─────────────────────────
    def new_instance(self) -> None:
        """Ctrl+T."""
        if not self.ctx.pref("instances_enabled"):
            return
        try:
            self.ctx.manager.create()
        except ValueError as exc:
            self.toast.show_message(str(exc), "warning")
            return
        self.ctx.sync_instance_devices()

    def close_instance(self, instance_id: str) -> None:
        """Ferme une instance (confirmation si scrcpy tourne)."""
        inst = self.ctx.manager.get(instance_id)
        if inst is None:
            return
        if inst.running and not confirm(self, "Fermer l'instance", f"scrcpy tourne pour « {inst.name} ». Le fermer ?"):
            return
        self.ctx.manager.close(instance_id)

    def _select_profile(self, name: str) -> None:
        self.ctx.inst.select_profile(name)
        self.ctx.dirty = True
        self.ctx.emit("values", ("profile",))
        self.refresh_all()

    def _ask_name(self, title: str, current: str = "") -> str:
        name, ok = QInputDialog.getText(self, title, "Nom du profil :", text=current)
        return name.strip() if ok else ""

    def _add_profile(self) -> None:
        name = self._ask_name("Nouveau profil")
        if name:
            profile = self.ctx.inst.add_profile(name)
            self._select_profile(profile.name)

    def _rename_profile(self, old: str) -> None:
        new = self._ask_name("Renommer le profil", old)
        if new and not self.ctx.inst.rename_profile(old, new):
            self.toast.show_message("Nom de profil invalide ou déjà utilisé.", "warning")
        self.ctx.dirty = True
        self.refresh_all()

    def _duplicate_profile(self, name: str) -> None:
        profile = self.ctx.inst.duplicate_profile(name)
        if profile is not None:
            self._select_profile(profile.name)

    def _delete_profile(self, name: str) -> None:
        if name != MAIN_PROFILE and confirm(self, "Supprimer le profil", f"Supprimer « {name} » ?"):
            self.ctx.inst.delete_profile(name)
            self.ctx.dirty = True
            self.ctx.emit("values", ("profile",))
            self.refresh_all()

    # ───────────────────────── exécution ─────────────────────────
    def toggle_launch(self) -> None:
        """Bouton principal : lance ou arrête selon l'état."""
        self.stop() if self.ctx.inst.running else self.launch()

    def launch(self) -> None:
        """Lance scrcpy pour l'instance courante."""
        inst = self.ctx.inst
        try:
            self.ctx.manager.launch(inst)
        except (ValueError, OSError) as exc:
            self.ctx.notify("error", str(exc))
            return
        self.ctx.notify("success", f"scrcpy lancé — {inst.label}")

    def stop(self) -> None:
        """Arrête scrcpy pour l'instance courante."""
        if self.ctx.inst.running:
            self.ctx.manager.stop(self.ctx.inst)
            self.ctx.notify("info", "scrcpy arrêté.")

    def test(self) -> None:
        """Lance un test de 3 secondes et affiche le résultat."""
        if self._test_running:
            return
        issues = self.ctx.issues()
        if has_errors(issues):
            self.ctx.notify("error", next(i.message for i in issues if i.level == "error"))
            return
        runner = self.ctx.manager.runner()
        args = self.ctx.args()
        inst = self.ctx.inst
        self._test_running = True
        self.test_button.setEnabled(False)
        self.toast.show_message("Test en cours (3 s)…", "info", 3500)

        def done(value: Any, error: BaseException | None) -> None:
            self._test_running = False
            self.test_button.setEnabled(True)
            if error is not None or value is None:
                self.ctx.notify("error", f"Test impossible : {error}")
                return
            inst.append_log("── Test ──")
            for line in value.output.splitlines():
                inst.append_log(line)
            self.ctx.emit("running", inst)
            self.ctx.notify("success" if value.ok else "error", value.summary)

        run_async(lambda: runner.run_test(args), done, dispatcher=DISPATCHER, name="scrcpy-studio-test")

    def copy_command(self) -> None:
        """Copie la commande dans le presse-papiers."""
        QApplication.clipboard().setText(self.ctx.command_text())
        self.ctx.notify("info", "Commande copiée dans le presse-papiers.")

    def _tick_metrics(self) -> None:
        if not self.ctx.pref("metrics_live") or not self.isVisible() or self.isMinimized():
            return
        inst = self.ctx.inst
        if inst.device is not None:
            inst.metrics.tick(self.ctx.adb, inst.device.serial, lambda _m: self.ctx.emit("metrics", inst), DISPATCHER)

    def _poll_devices(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.ctx.refresh_devices()

    # ───────────────────────── Command Palette ─────────────────────────
    def palette_items(self) -> list[PaletteItem]:
        """Actions, vues et options scrcpy proposées par la palette."""
        items = [
            PaletteItem("action", "Lancer scrcpy", "Ctrl+Entrée", "rocket", self.launch, "start run"),
            PaletteItem("action", "Arrêter scrcpy", "Ctrl+.", "stop", self.stop, "stop kill"),
            PaletteItem("action", "Tester la configuration", "Lance scrcpy 3 secondes", "flask", self.test),
            PaletteItem("action", "Copier la commande", "Presse-papiers", "copy", self.copy_command),
            PaletteItem("action", "Enregistrer comme préréglage", "Réglages courants", "save", lambda: save_preset_dialog(self.ctx, self)),
            PaletteItem("action", "Nouvelle instance", "Ctrl+T", "plus", self.new_instance),
            PaletteItem("action", "Fermer l'instance", "Ctrl+W", "x", lambda: self.close_instance(self.ctx.manager.current_id)),
            PaletteItem("action", "Basculer en mode PRO", "Toutes les options scrcpy", "sliders", lambda: self.set_mode("pro")),
            PaletteItem("action", "Basculer en mode BASE", "Interface simplifiée", "sliders", lambda: self.set_mode("base")),
            PaletteItem("action", "Masquer / afficher la barre latérale", "Ctrl+B", "menu", self.toggle_sidebar),
            PaletteItem("action", "Masquer / afficher le panneau contexte", "Ctrl+D", "info", self.toggle_info),
            PaletteItem("action", "Mode focus", "F11", "fullscreen", self.toggle_focus),
            PaletteItem("action", "Actualiser les appareils", "adb devices", "refresh", lambda: (self.ctx.forget_details(), self.ctx.refresh_devices())),
        ]
        for view in VIEWS:
            items.append(PaletteItem("nav", f"Aller à {view.label}", "PRO" if view.section == "pro" else "", view.icon,
                                     lambda k=view.key: self.show_view(k), view.keywords))
        for key in scrcpy_help.list_all():
            entry = scrcpy_help.get_entry(key)
            items.append(PaletteItem("option", key, (entry.description if entry else "")[:160], "terminal",
                                     lambda k=key: self._goto_option(k)))
        return items

    def open_palette(self, initial: str = "") -> None:
        """Ctrl+K (F1 pré-remplit « -- » pour chercher une option)."""
        self.command_palette.open_palette(self.palette_items(), initial if isinstance(initial, str) else "")

    def _goto_option(self, option: str) -> None:
        for view in VIEWS:
            if view.section == "hidden":
                continue
            cls = load_view_class(view)
            if option in cls.covered_options():
                self.show_view(view.key)
                self.toast.show_message(f"{option} : {scrcpy_help.get_description(option)[:110]}", "info", 5000)
                return
        self.show_view("debug")

    # ───────────────────────── rafraîchissement ─────────────────────────
    def _on_ctx_event(self, event: str, payload: Any) -> None:
        if event == "notify":
            tone = payload.level if payload.level in ("success", "warning", "error") else "info"
            self.toast.show_message(payload.text, tone)
            self.titlebar.set_unread(sum(1 for n in self.ctx.notifications if time.time() - n.when < 3600))
            return
        if event == "prefs" and set(payload or ()) & APPEARANCE_PREFS and not self._rebuild_pending:
            self._rebuild_pending = True
            QTimer.singleShot(0, self.rebuild_ui)  # différé : la vue émettrice est encore sur la pile
            return
        if event in ("values", "instance", "devices", "running", "metrics", "prefs"):
            self.refresh_all()

    def refresh_all(self) -> None:
        """Met à jour onglets, panneau contexte, dock et barre de titre (reconstruction seulement si nécessaire)."""
        ctx = self.ctx
        manager = ctx.manager
        inst = ctx.inst
        self.instance_tabs.setVisible(bool(ctx.pref("instances_enabled")))
        tabs_sig = (tuple((i.id, i.label, i.running) for i in manager.instances), manager.current_id, len(manager.instances) < MAX_INSTANCES)
        if tabs_sig != self._tabs_sig:
            self._tabs_sig = tabs_sig
            self.instance_tabs.set_instances(list(tabs_sig[0]), manager.current_id, can_add=tabs_sig[2])
        self.profile_tabs.setVisible(bool(ctx.pref("profiles_enabled")))
        profiles_sig = (tuple(inst.profile_names()), inst.current_profile)
        if profiles_sig != self._profiles_sig:
            self._profiles_sig = profiles_sig
            self.profile_tabs.set_profiles(inst.profile_names(), inst.current_profile)
        self._sync_sidebar()
        self.sidebar.setVisible(bool(ctx.pref("sidebar_visible")) and self._focus_saved is None)
        self.info_panel.setVisible(bool(ctx.pref("info_visible")) and self._focus_saved is None)
        self.titlebar.mode_toggle.set_mode(ctx.mode)

        self.info_panel.set_command(ctx.command_lines())
        self.command_bar.set_text(ctx.command_text())
        self.info_panel.set_metrics(inst.metrics.snapshot())
        self.info_panel.set_device(inst.device)
        if inst.device is None:
            missing = ctx.adb_ok is False
            self.info_panel.set_connection("ADB introuvable" if missing else "Aucun appareil", "error" if missing else "warning")
        else:
            online = inst.device.online
            self.info_panel.set_connection(f"{inst.device.link} · ADB {'Online' if online else 'Offline'}", "success" if online else "warning")

        tone, text = ctx.adb_status()
        self.status.set_state(tone, text)
        running = inst.running
        self.launch_button.setText("STOP SCRCPY" if running else "LAUNCH SCRCPY")
        self.launch_button.set_icon_name("stop" if running else "rocket", "stop" if running else "primary")
        self.titlebar.set_live(bool(ctx.pref("metrics_live")) and (running or inst.device is not None))

    def _show_notifications(self) -> None:
        menu = QMenu(self)
        notes = self.ctx.notifications[-10:][::-1]
        if not notes:
            menu.addAction("Aucune notification").setEnabled(False)
        for note in notes:
            menu.addAction(f"{time.strftime('%H:%M', time.localtime(note.when))}  {note.text}"[:110])
        menu.exec(self.titlebar.bell.mapToGlobal(self.titlebar.bell.rect().bottomLeft()))
        self.titlebar.set_unread(0)

    def _device_details(self) -> None:
        device = self.ctx.inst.device
        dialog = QDialog(self)
        dialog.setWindowTitle("Informations de l'appareil")
        dialog.resize(640, 520)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setObjectName("Mono")
        view.setReadOnly(True)
        if device is None:
            view.setPlainText("Aucun appareil connecté.")
        else:
            rows = [f"{k} = {v}" for k, v in sorted(device.props.items())] or ["(propriétés indisponibles)"]
            view.setPlainText(f"{device.label}  ·  {device.serial}\n\n" + "\n".join(rows))
        layout.addWidget(view)
        dialog.exec()

    # ───────────────────────── événements Qt ─────────────────────────
    def resizeEvent(self, event) -> None:  # noqa: N802, ANN001
        super().resizeEvent(event)
        grip, toast = getattr(self, "grip", None), getattr(self, "toast", None)
        if grip is not None:  # Qt peut émettre cet événement avant la fin de la construction
            grip.move(self.width() - grip.width() - 2, self.height() - grip.height() - 2)
        if toast is not None:
            toast.reposition()

    def changeEvent(self, event) -> None:  # noqa: N802, ANN001
        super().changeEvent(event)
        titlebar = getattr(self, "titlebar", None)
        if titlebar is not None:  # setWindowTitle() déclenche cet événement dès __init__
            titlebar.set_maximized(self.isMaximized())

    def closeEvent(self, event) -> None:  # noqa: N802, ANN001
        running = self.ctx.manager.running_instances()
        if running and not confirm(self, "Quitter", f"{len(running)} instance(s) scrcpy en cours seront arrêtées. Quitter ?"):
            event.ignore()
            return
        for timer in (self._pump, self._metrics, self._devices, self._autosave):
            timer.stop()
        self.ctx.manager.stop_all()
        self.ctx.dirty = True
        self.ctx.flush()
        super().closeEvent(event)
