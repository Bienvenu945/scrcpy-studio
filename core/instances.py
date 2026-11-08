"""Multi-instances et profils par instance."""
from __future__ import annotations

import collections
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from config.defaults import MAIN_PROFILE, MAX_INSTANCES, default_records_dir
from config.settings_store import SettingsStore
from core.metrics import LiveMetrics
from core.models import AppPrefs, Device, Settings, coerce
from core.process import Dispatcher, ManagedProcess
from core.scrcpy import ScrcpyRunner, build_args, has_errors, validate

Listener = Callable[[str, "Instance | None"], None]


@dataclass
class Profile:
    """Profil : delta de réglages appliqué sur la base de l'instance."""

    name: str
    delta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Instance:
    """Une session indépendante : réglages, profils, appareil et processus."""

    id: str
    name: str
    base: Settings = field(default_factory=Settings)
    profiles: list[Profile] = field(default_factory=list)
    current_profile: str = MAIN_PROFILE
    device: Device | None = field(default=None, repr=False, compare=False)
    process: ManagedProcess | None = field(default=None, repr=False, compare=False)
    log: collections.deque = field(default_factory=lambda: collections.deque(maxlen=2000), repr=False, compare=False)
    metrics: LiveMetrics = field(default_factory=LiveMetrics, repr=False, compare=False)
    last_exit: int | None = field(default=None, repr=False, compare=False)

    # ── état ──
    @property
    def running(self) -> bool:
        """Vrai si scrcpy tourne pour cette instance."""
        return self.process is not None and self.process.running

    @property
    def label(self) -> str:
        """Libellé d'onglet : « Device 1: S23 Ultra »."""
        return f"{self.name}: {self.device.short_name}" if self.device else self.name

    def effective(self) -> Settings:
        """Réglages effectifs (base + delta du profil courant)."""
        profile = self._profile(self.current_profile)
        return self.base.copy() if profile is None else self.base.merged(profile.delta)

    # ── réglages ──
    def set_value(self, name: str, value: Any) -> Any:
        """Modifie un réglage dans la base (profil principal) ou dans le delta du profil courant."""
        value = coerce(name, value)
        profile = self._profile(self.current_profile)
        if profile is None:
            setattr(self.base, name, value)
        elif value == getattr(self.base, name):
            profile.delta.pop(name, None)
        else:
            profile.delta[name] = value
        return value

    def set_values(self, values: dict[str, Any]) -> None:
        """Applique plusieurs réglages."""
        for key, value in values.items():
            self.set_value(key, value)

    # ── profils ──
    def _profile(self, name: str) -> Profile | None:
        if name == MAIN_PROFILE:
            return None
        return next((p for p in self.profiles if p.name == name), None)

    def profile_names(self) -> list[str]:
        """Noms des profils, « Vue principale » en tête."""
        return [MAIN_PROFILE] + [p.name for p in self.profiles]

    def _unique(self, wanted: str) -> str:
        base = wanted.strip() or "Profil"
        if base == MAIN_PROFILE:
            base = "Profil"
        name, n = base, 1
        while name in self.profile_names():
            n += 1
            name = f"{base} {n}"
        return name

    def select_profile(self, name: str) -> None:
        """Active un profil (retombe sur la vue principale si inconnu)."""
        self.current_profile = name if name in self.profile_names() else MAIN_PROFILE

    def add_profile(self, name: str = "", from_current: bool = True) -> Profile:
        """Crée un profil (copie du profil courant ou vide)."""
        delta: dict[str, Any] = {}
        if from_current:
            eff = self.effective()
            delta = {k: v for k, v in eff.to_dict().items() if v != getattr(self.base, k)}
        profile = Profile(self._unique(name or f"Profil {len(self.profiles) + 2}"), delta)
        self.profiles.append(profile)
        return profile

    def rename_profile(self, old: str, new: str) -> bool:
        """Renomme un profil (la vue principale est protégée)."""
        profile = self._profile(old)
        new = new.strip()
        if profile is None or not new or new == MAIN_PROFILE or (new != old and new in self.profile_names()):
            return False
        profile.name = new
        if self.current_profile == old:
            self.current_profile = new
        return True

    def duplicate_profile(self, name: str) -> Profile | None:
        """Duplique un profil (la vue principale donne un profil avec ses valeurs effectives)."""
        if name == MAIN_PROFILE:
            return self.add_profile("Copie de la vue principale", from_current=False)
        source = self._profile(name)
        if source is None:
            return None
        copy = Profile(self._unique(f"{name} (copie)"), dict(source.delta))
        self.profiles.append(copy)
        return copy

    def delete_profile(self, name: str) -> bool:
        """Supprime un profil (la vue principale est protégée)."""
        profile = self._profile(name)
        if profile is None:
            return False
        self.profiles.remove(profile)
        if self.current_profile == name:
            self.current_profile = MAIN_PROFILE
        return True

    # ── journal ──
    def append_log(self, line: str) -> None:
        """Ajoute une ligne au journal (borné)."""
        self.log.append(line)

    # ── persistance ──
    def to_dict(self) -> dict[str, Any]:
        """Représentation JSON de l'instance (réglages en diff)."""
        return {
            "id": self.id, "name": self.name, "base": self.base.diff(),
            "profiles": [{"name": p.name, "delta": p.delta} for p in self.profiles],
            "current_profile": self.current_profile,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Instance":
        """Reconstruit une instance (tolérant aux données partielles)."""
        profiles = []
        for item in data.get("profiles", []):
            if isinstance(item, dict) and item.get("name"):
                delta = {k: coerce(k, v) for k, v in dict(item.get("delta", {})).items() if k in Settings.field_names()}
                profiles.append(Profile(str(item["name"]), delta))
        inst = cls(str(data.get("id") or uuid.uuid4().hex[:8]), str(data.get("name") or "Device 1"),
                   Settings.from_dict(data.get("base")), profiles)
        inst.select_profile(str(data.get("current_profile", MAIN_PROFILE)))
        return inst


class InstanceManager:
    """Gère la liste des instances, leur persistance et le lancement de scrcpy."""

    def __init__(
        self,
        store: SettingsStore | None = None,
        prefs: AppPrefs | None = None,
        runner_factory: Callable[[], ScrcpyRunner] | None = None,
        dispatcher: Dispatcher | None = None,
    ) -> None:
        self.store = store
        self.prefs = prefs or AppPrefs()
        self.dispatcher = dispatcher
        self._runner_factory = runner_factory
        self.instances: list[Instance] = []
        self.current_id = ""
        self._listeners: list[Listener] = []

    # ── événements ──
    def subscribe(self, listener: Listener) -> None:
        """Abonne un rappel ``(événement, instance)``."""
        self._listeners.append(listener)

    def _notify(self, event: str, inst: Instance | None) -> None:
        for listener in list(self._listeners):
            listener(event, inst)

    # ── accès ──
    def runner(self) -> ScrcpyRunner:
        """Runner configuré selon les préférences."""
        if self._runner_factory:
            return self._runner_factory()
        folder = Path(self.prefs.records_dir) if self.prefs.records_dir else default_records_dir()
        return ScrcpyRunner(self.prefs.scrcpy_path, self.prefs.adb_path, folder)

    def get(self, instance_id: str) -> Instance | None:
        """Instance par identifiant."""
        return next((i for i in self.instances if i.id == instance_id), None)

    @property
    def current(self) -> Instance:
        """Instance courante (jamais None après ``load``/``create``)."""
        return self.get(self.current_id) or self.instances[0]

    def index_of(self, instance_id: str) -> int:
        """Position d'une instance (-1 si inconnue)."""
        return next((n for n, i in enumerate(self.instances) if i.id == instance_id), -1)

    def running_instances(self) -> list[Instance]:
        """Instances dont scrcpy tourne."""
        return [i for i in self.instances if i.running]

    # ── cycle de vie ──
    def next_name(self) -> str:
        """Prochain nom libre « Device N »."""
        used = {i.name for i in self.instances}
        n = 1
        while f"Device {n}" in used:
            n += 1
        return f"Device {n}"

    def create(self, settings: Settings | None = None, name: str = "") -> Instance:
        """Crée et sélectionne une instance ; ``ValueError`` si la limite est atteinte."""
        if len(self.instances) >= MAX_INSTANCES:
            raise ValueError(f"Limite de {MAX_INSTANCES} instances atteinte.")
        inst = Instance(uuid.uuid4().hex[:8], name or self.next_name(), settings.copy() if settings else Settings())
        self.instances.append(inst)
        self.current_id = inst.id
        self._notify("created", inst)
        return inst

    def close(self, instance_id: str) -> None:
        """Ferme une instance (arrête scrcpy) ; il en reste toujours au moins une."""
        inst = self.get(instance_id)
        if inst is None:
            return
        self.stop(inst)
        index = self.index_of(instance_id)
        self.instances.remove(inst)
        if not self.instances:
            self.create()
        elif self.current_id == instance_id:
            self.current_id = self.instances[min(index, len(self.instances) - 1)].id
        self._notify("closed", inst)
        self._notify("switched", self.current)

    def set_current(self, instance_id: str) -> None:
        """Sélectionne une instance."""
        if self.get(instance_id) and instance_id != self.current_id:
            self.current_id = instance_id
            self._notify("switched", self.current)

    def cycle(self, step: int = 1) -> None:
        """Passe à l'instance suivante (``step`` = 1) ou précédente (-1)."""
        if len(self.instances) > 1:
            self.set_current(self.instances[(self.index_of(self.current_id) + step) % len(self.instances)].id)

    def attach_device(self, inst: Instance, device: Device | None) -> None:
        """Associe un appareil (pour l'affichage) à une instance."""
        inst.device = device
        self._notify("changed", inst)

    # ── persistance ──
    def load(self) -> None:
        """Charge les instances depuis le store ; crée une instance par défaut si besoin."""
        data = self.store.load_instances() if self.store else {"current": "", "instances": []}
        self.instances = [Instance.from_dict(d) for d in data["instances"]][:MAX_INSTANCES]
        if not self.instances:
            self.instances = [Instance(uuid.uuid4().hex[:8], "Device 1")]
        self.current_id = data["current"] if self.get(data["current"]) else self.instances[0].id

    def save(self) -> None:
        """Écrit les instances dans le store."""
        if self.store:
            self.store.save_instances(self.current_id, [i.to_dict() for i in self.instances])

    def export_data(self) -> dict[str, Any]:
        """Données d'instances pour un export JSON."""
        return {"current": self.current_id, "instances": [i.to_dict() for i in self.instances]}

    def import_data(self, data: dict[str, Any]) -> None:
        """Remplace les instances par celles d'un export (scrcpy arrêté au préalable)."""
        self.stop_all()
        self.instances = [Instance.from_dict(d) for d in data.get("instances", [])][:MAX_INSTANCES]
        if not self.instances:
            self.instances = [Instance(uuid.uuid4().hex[:8], "Device 1")]
        self.current_id = data.get("current") if self.get(str(data.get("current"))) else self.instances[0].id
        self._notify("switched", self.current)

    # ── exécution ──
    def can_launch(self, inst: Instance) -> tuple[bool, str]:
        """Indique si ``inst`` peut démarrer (et pourquoi pas)."""
        if inst.running:
            return False, "Cette instance tourne déjà."
        others = [i for i in self.running_instances() if i.id != inst.id]
        if others and not self.prefs.allow_parallel:
            return False, "Une autre instance tourne déjà (Paramètres › Autoriser le parallèle)."
        serial = inst.effective().serial or (inst.device.serial if inst.device else "")
        for other in others:
            if serial and serial == (other.effective().serial or (other.device.serial if other.device else "")):
                return False, f"L'appareil est déjà utilisé par « {other.name} »."
        return True, ""

    def args_for(self, inst: Instance) -> list[str]:
        """Arguments scrcpy de l'instance (l'appareil associé est utilisé si aucun serial n'est fixé)."""
        s = inst.effective()
        if not s.serial and inst.device and s.conn == "auto" and not (s.select_usb or s.select_tcpip or s.tcpip_addr):
            s = s.merged({"serial": inst.device.serial})
        return build_args(s)

    def launch(self, inst: Instance, extra_args: list[str] | None = None) -> ManagedProcess:
        """Démarre scrcpy ; lève ``ValueError`` / ``FileNotFoundError`` / ``OSError`` en cas de problème."""
        ok, reason = self.can_launch(inst)
        if not ok:
            raise ValueError(reason)
        issues = validate(inst.effective())
        if has_errors(issues):
            raise ValueError(next(i.message for i in issues if i.level == "error"))
        inst.last_exit = None
        inst.log.clear()

        def on_line(line: str) -> None:
            inst.append_log(line)
            if inst.metrics.feed_line(line):
                self._notify("metrics", inst)
            self._notify("line", inst)

        def on_exit(code: int) -> None:
            inst.process = None
            inst.metrics.clear_runtime()
            inst.last_exit = code  # en dernier : les écouteurs de « stopped » le lisent
            self._notify("stopped", inst)

        args = self.args_for(inst) + list(extra_args or [])
        inst.process = self.runner().start(args, on_line, on_exit, self.dispatcher)
        self._notify("started", inst)
        return inst.process

    def stop(self, inst: Instance) -> None:
        """Arrête scrcpy pour une instance."""
        if inst.process is not None:
            inst.process.terminate()

    def stop_all(self) -> None:
        """Arrête toutes les instances."""
        for inst in self.instances:
            self.stop(inst)
