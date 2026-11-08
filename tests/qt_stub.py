"""Faux PySide6 minimal : permet d'importer et de construire l'interface sans Qt installé.

Il ne vérifie PAS le rendu ni l'usage réel de l'API Qt : seulement que les modules
s'importent, que les classes se construisent et que la logique Python (signaux relayés,
contexte, couverture des options) fonctionne. Avec PySide6 installé, les tests utilisent Qt.
"""
from __future__ import annotations

import sys
import types

SIGNAL_NAMES = {
    "clicked", "toggled", "textChanged", "textEdited", "valueChanged", "currentIndexChanged", "currentRowChanged",
    "activated", "editingFinished", "timeout", "triggered", "released", "pressed", "stateChanged", "finished",
    "customContextMenuRequested", "itemClicked", "itemActivated", "itemDoubleClicked", "currentItemChanged",
    "returnPressed", "accepted", "rejected", "destroyed", "buttonClicked", "sliderMoved",
}


class _SignalInstance:
    def __init__(self) -> None:
        self.slots: list = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot=None):
        self.slots = [] if slot is None else [s for s in self.slots if s is not slot]

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class _SignalDescriptor:
    def __init__(self, *types_):
        self.name = ""

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.setdefault("_sig_" + self.name, _SignalInstance())


def Signal(*types_):  # noqa: N802
    return _SignalDescriptor(*types_)


#: Méthodes dont le retour doit être réaliste (évite les boucles infinies du type « while layout.count() »).
FIXED_RETURNS = {"count": 0, "currentRow": -1, "isMaximized": False, "isMinimized": False, "isChecked": False,
                 "text": "", "toPlainText": "", "currentIndex": -1, "findData": -1}


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        value = _Dummy()
        type.__setattr__(cls, name, value)
        return value

    def __or__(cls, other):
        return _Dummy()


class _Dummy(metaclass=_Meta):
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        if name in FIXED_RETURNS:
            fixed = FIXED_RETURNS[name]
            value = lambda *args, **kwargs: fixed  # noqa: E731
        else:
            value = _SignalInstance() if name in SIGNAL_NAMES else _Dummy()
        self.__dict__[name] = value
        return value

    def __call__(self, *args, **kwargs):
        return _Dummy()

    def _op(self, *_):
        return _Dummy()

    __or__ = __ror__ = __and__ = __rand__ = __add__ = __radd__ = __sub__ = __rsub__ = _op
    __mul__ = __rmul__ = __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = __neg__ = _op

    def __lt__(self, other):
        return False

    __gt__ = __le__ = __ge__ = __lt__

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __bool__(self):
        return True

    def __int__(self):
        return 0

    __index__ = __int__

    def __float__(self):
        return 0.0

    def __round__(self, ndigits=None):
        return 0

    def __hash__(self):
        return id(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Module(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self._cache: dict = {}

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        if name == "Signal":
            return Signal
        if name == "Qt":
            self._cache.setdefault(name, _Dummy())
        elif name not in self._cache:
            self._cache[name] = _Meta(name, (_Dummy,), {})
        return self._cache[name]


def install() -> None:
    """Enregistre le faux PySide6 dans ``sys.modules`` (sans effet si le vrai est installé)."""
    if "PySide6" in sys.modules and not isinstance(sys.modules["PySide6"], _Module):
        return
    root = _Module("PySide6")
    root.__path__ = []  # type: ignore[attr-defined]
    sys.modules["PySide6"] = root
    for sub in ("QtCore", "QtGui", "QtWidgets", "QtSvg"):
        module = _Module(f"PySide6.{sub}")
        sys.modules[f"PySide6.{sub}"] = module
        setattr(root, sub, module)
