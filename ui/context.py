"""Contexte applicatif partagé par les vues (Python pur, sans Qt).

``Context`` relie préférences, instances, adb et notifications ; les widgets s'y
abonnent pour se rafraîchir. ``PaletteItem``/``rank_items`` alimentent la Command Palette.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from config.defaults import PREVIEW_REFRESH_S
from config.settings_store import SettingsStore
from core import scrcpy_help
from core.adb import AdbClient
from core.instances import Instance, InstanceManager
from core.models import PREFS_DEFAULTS, AppPrefs, Device, Settings, coerce
from core.process import DISPATCHER, Dispatcher, run_async
from core.scrcpy import Issue, command_lines, find_executable, format_command, validate

Subscriber = Callable[[str, Any], None]
DETAIL_TTL_S = 45.0


@dataclass(frozen=True)
class Notification:
    """Message adressé à l'utilisateur (toast + historique)."""

    when: float
    level: str  # info | success | warning | error
    text: str


class Context:
    """État partagé : préférences, instances, appareils, abonnements."""

    def __init__(
        self,
        prefs: AppPrefs,
        manager: InstanceManager,
        adb: AdbClient,
        store: SettingsStore | None = None,
        dispatcher: Dispatcher | None = DISPATCHER,
    ) -> None:
        self.prefs = prefs
        self.manager = manager
        self.adb = adb
        self.store = store
        self.dispatcher = dispatcher
        self.devices: list[Device] = []
        self.adb_ok: bool | None = None
        self.adb_version = ""
        self.notifications: list[Notification] = []
        self.dirty = False
        self.navigate: Callable[[str], None] = lambda key: None
        #: Actions globales (launch, stop, test, copy…) branchées par la fenêtre principale.
        self.actions: dict[str, Callable[[], None]] = {}
        self._subs: list[Subscriber] = []
        self._details: dict[str, tuple[float, Device]] = {}
        self._refreshing = False
        manager.subscribe(self._on_manager_event)

    # ── abonnements ──
    def subscribe(self, callback: Subscriber) -> None:
        """Abonne ``callback(event, payload)`` ; événements : values, instance, prefs, devices, running, line, metrics, notify."""
        self._subs.append(callback)

    def emit(self, event: str, payload: Any = None) -> None:
        """Diffuse un événement aux abonnés."""
        for callback in list(self._subs):
            try:
                callback(event, payload)
            except RuntimeError as exc:  # widget Qt déjà détruit (vue reconstruite) : on se désabonne
                if "already deleted" not in str(exc):
                    raise
                if callback in self._subs:
                    self._subs.remove(callback)

    def _on_manager_event(self, event: str, inst: Instance | None) -> None:
        mapping = {"created": "instance", "closed": "instance", "switched": "instance",
                   "started": "running", "stopped": "running", "line": "line", "metrics": "metrics",
                   "changed": "devices"}
        self.dirty = self.dirty or event in ("created", "closed", "switched")
        self.emit(mapping.get(event, event), inst)

    # ── instance courante ──
    @property
    def inst(self) -> Instance:
        """Instance courante."""
        return self.manager.current

    def settings(self) -> Settings:
        """Réglages effectifs de l'instance courante."""
        return self.inst.effective()

    def value(self, name: str) -> Any:
        """Valeur effective d'un réglage."""
        return getattr(self.settings(), name)

    def set_value(self, name: str, value: Any) -> Any:
        """Modifie un réglage de l'instance courante (profil courant inclus)."""
        result = self.inst.set_value(name, value)
        if name != "active_preset":
            self.inst.set_value("active_preset", "")
        self.dirty = True
        self.emit("values", (name,))
        return result

    def apply_values(self, values: dict[str, Any], preset_key: str = "") -> None:
        """Applique plusieurs réglages d'un coup (préréglage, réinitialisation…)."""
        self.inst.set_values(values)
        self.inst.set_value("active_preset", preset_key)
        self.dirty = True
        self.emit("values", tuple(values))

    def reset_fields(self, names: list[str]) -> None:
        """Remet des champs à leur valeur par défaut."""
        defaults = Settings()
        self.apply_values({n: getattr(defaults, n) for n in names})

    # ── préférences ──
    def pref(self, name: str) -> Any:
        """Valeur d'une préférence globale."""
        return getattr(self.prefs, name)

    def set_pref(self, name: str, value: Any) -> Any:
        """Modifie une préférence globale et prévient les abonnés."""
        if isinstance(PREFS_DEFAULTS[name], list):
            result = list(value)
        else:
            result = coerce(name, value, PREFS_DEFAULTS)
        setattr(self.prefs, name, result)
        self.dirty = True
        self.emit("prefs", (name,))
        return result

    @property
    def mode(self) -> str:
        """Mode d'interface : ``base`` ou ``pro``."""
        return self.prefs.ui_mode

    def flush(self) -> None:
        """Écrit préférences et instances si nécessaire."""
        if self.store is not None and self.dirty:
            self.store.save_prefs(self.prefs)
            self.manager.save()
        self.dirty = False

    # ── commande ──
    def args(self) -> list[str]:
        """Arguments scrcpy de l'instance courante."""
        return self.manager.args_for(self.inst)

    def command_text(self) -> str:
        """Commande complète sur une ligne."""
        return format_command(self.args())

    def command_lines(self) -> list[str]:
        """Commande sur plusieurs lignes (aperçu)."""
        return command_lines(self.args())

    def issues(self) -> list[Issue]:
        """Incohérences de la configuration courante."""
        return validate(self.settings())

    def scrcpy_path(self) -> str | None:
        """Chemin de scrcpy s'il est trouvé."""
        return find_executable("scrcpy", self.prefs.scrcpy_path)

    # ── appareils ──
    def refresh_devices(self) -> bool:
        """Interroge adb en arrière-plan ; renvoie False si une requête est déjà en cours."""
        if self._refreshing:
            return False
        self._refreshing = True

        def work() -> tuple[list[Device], bool]:
            if self.adb_ok is None:
                self.adb_version = self.adb.version()
            found = self.adb.devices()
            result: list[Device] = []
            now = time.monotonic()
            for dev in found:
                cached = self._details.get(dev.serial)
                if dev.online and cached and now - cached[0] < DETAIL_TTL_S:
                    result.append(cached[1])
                elif dev.online:
                    info = self.adb.details(dev.serial)
                    info.transport = dev.transport
                    info.state = dev.state
                    self._details[dev.serial] = (now, info)
                    result.append(info)
                else:
                    result.append(dev)
            return result, bool(self.adb_version) or bool(found)

        def done(value: Any, error: BaseException | None) -> None:
            self._refreshing = False
            if error is not None or value is None:
                self.adb_ok = False
            else:
                self.devices, self.adb_ok = value
                self.sync_instance_devices()
            self.emit("devices", self.devices)

        run_async(work, done, dispatcher=self.dispatcher, name="scrcpy-studio-devices")
        return True

    def forget_details(self, serial: str = "") -> None:
        """Invalide le cache de détails (un seul appareil ou tous)."""
        if serial:
            self._details.pop(serial, None)
        else:
            self._details.clear()

    def online_devices(self) -> list[Device]:
        """Appareils prêts à l'emploi."""
        return [d for d in self.devices if d.online]

    def sync_instance_devices(self) -> None:
        """Associe à chaque instance l'appareil qui correspond à son serial (ou un appareil libre)."""
        online = {d.serial: d for d in self.online_devices()}
        taken: set[str] = set()
        for inst in self.manager.instances:
            wanted = inst.effective().serial
            if wanted and wanted in online:
                inst.device = online[wanted]
                taken.add(wanted)
            elif inst.device is not None and inst.device.serial in online and not wanted:
                inst.device = online[inst.device.serial]
                taken.add(inst.device.serial)
            else:
                inst.device = None
        for inst in self.manager.instances:
            if inst.device is None and not inst.effective().serial:
                free = next((d for d in online.values() if d.serial not in taken), None)
                if free is not None:
                    inst.device = free
                    taken.add(free.serial)

    def adb_status(self) -> tuple[str, str]:
        """(tonalité, texte) de l'état global : ADB Ready, scrcpy actif, aucun appareil…"""
        running = len(self.manager.running_instances())
        if running:
            return "running", "scrcpy actif" if running == 1 else f"{running} instances actives"
        if self.adb_ok is False:
            return "error", "ADB introuvable"
        if self.adb_ok is None:
            return "warning", "ADB…"
        return ("success", "ADB Ready") if self.online_devices() else ("warning", "Aucun appareil")

    def run_action(self, name: str) -> None:
        """Déclenche une action globale enregistrée par la fenêtre (sans effet si absente)."""
        action = self.actions.get(name)
        if action is not None:
            action()

    # ── notifications ──
    def notify(self, level: str, text: str) -> None:
        """Enregistre et diffuse un message utilisateur."""
        note = Notification(time.time(), level, text)
        self.notifications = (self.notifications + [note])[-50:]
        self.emit("notify", note)

    @property
    def preview_interval_ms(self) -> int:
        """Période de rafraîchissement de l'aperçu (ms)."""
        return int(PREVIEW_REFRESH_S * 1000)


# ───────────────────────────── Command Palette ─────────────────────────────

@dataclass
class PaletteItem:
    """Entrée de la Command Palette."""

    kind: str  # action | nav | option
    title: str
    subtitle: str = ""
    icon: str = "bolt"
    payload: Any = None
    keywords: str = field(default="", repr=False)


_KIND_BONUS = {"action": 30, "nav": 20, "option": 0}


def rank_items(items: list[PaletteItem], query: str, limit: int = 60) -> list[PaletteItem]:
    """Filtre et classe les entrées (recherche floue sur le titre, sous-chaîne sur le reste)."""
    q = query.strip()
    if not q:
        return [i for i in items if i.kind != "option"][:limit]
    scored: list[tuple[int, int, PaletteItem]] = []
    for order, item in enumerate(items):
        score = scrcpy_help.fuzzy_score(q, item.title)
        if score is None and not q.startswith("-"):
            haystack = f"{item.keywords} {item.subtitle}".lower()
            if q.lower() in haystack:
                score = 150
        if score is not None:
            scored.append((-(score + _KIND_BONUS.get(item.kind, 0)), order, item))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [item for _, _, item in scored[:limit]]
