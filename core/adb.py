"""Client adb : appareils, propriétés, batterie, capture d'écran, connexion TCP/IP."""
from __future__ import annotations

import re
from typing import Callable, Sequence

from core.models import Device
from core.process import AsyncResult, run_command

Runner = Callable[..., AsyncResult]

_PROP = re.compile(r"^\[([^\]]+)\]: \[(.*)\]$")
_MARKERS = ("===WM", "===BAT", "===DISP")


def parse_devices(text: str) -> list[Device]:
    """Analyse la sortie de ``adb devices -l``."""
    devices: list[Device] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("List of devices", "*")):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        extras = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        transport = "usb" if "usb" in extras else "tcpip"
        if ":" in serial or re.match(r"^\d+\.\d+\.\d+\.\d+", serial):
            transport = "tcpip"
        devices.append(Device(serial=serial, state=state, model=extras.get("model", "").replace("_", " "), transport=transport))
    return devices


def parse_props(text: str) -> dict[str, str]:
    """Analyse la sortie de ``getprop`` (``[clé]: [valeur]``)."""
    props: dict[str, str] = {}
    for line in text.splitlines():
        m = _PROP.match(line.strip())
        if m:
            props[m.group(1)] = m.group(2)
    return props


def parse_wm_size(text: str) -> str:
    """Résolution physique depuis ``wm size`` (``1440x3080``) ou chaîne vide."""
    sizes = re.findall(r"(\d+x\d+)", text)
    physical = re.search(r"Physical size:\s*(\d+x\d+)", text)
    return physical.group(1) if physical else (sizes[0] if sizes else "")


def parse_battery(text: str) -> tuple[int | None, bool]:
    """Niveau de batterie et état de charge depuis ``dumpsys battery``."""
    level = re.search(r"^\s*level:\s*(\d+)", text, re.M)
    charging = re.search(r"^\s*(AC|USB|Wireless|Dock) powered:\s*true", text, re.M | re.I) is not None
    status = re.search(r"^\s*status:\s*(\d+)", text, re.M)
    if status and status.group(1) == "2":
        charging = True
    return (int(level.group(1)) if level else None), charging


def parse_refresh_rate(text: str) -> int | None:
    """Fréquence de rafraîchissement active depuis ``dumpsys display`` (Hz)."""
    modes = {
        int(m.group(1)): float(m.group(4))
        for m in re.finditer(r"id=(\d+),\s*width=(\d+),\s*height=(\d+),\s*(?:fps|refreshRate)=([\d.]+)", text)
    }
    active = re.search(r"(?:mActiveModeId|activeModeId)=(\d+)", text)
    if active and int(active.group(1)) in modes:
        return int(round(modes[int(active.group(1))]))
    direct = re.search(r"mRefreshRate=([\d.]+)", text)
    if direct:
        return int(round(float(direct.group(1))))
    return int(round(max(modes.values()))) if modes else None


def parse_ip(text: str) -> str | None:
    """Adresse IPv4 depuis ``ip addr`` ou ``ip route``."""
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", text) or re.search(r"src (\d+\.\d+\.\d+\.\d+)", text)
    return m.group(1) if m else None


def split_sections(text: str) -> dict[str, str]:
    """Découpe la sortie combinée de ``details`` selon les marqueurs ``===XXX``."""
    sections: dict[str, str] = {"props": ""}
    current = "props"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in _MARKERS:
            current = stripped[3:].lower()
            sections[current] = ""
        else:
            sections[current] += line + "\n"
    return sections


class AdbClient:
    """Enveloppe fine autour de l'exécutable adb ; ``runner`` est injectable pour les tests."""

    def __init__(self, adb_path: str = "adb", runner: Runner | None = None, timeout: float = 8.0) -> None:
        self.path = adb_path or "adb"
        self.timeout = timeout
        self._runner: Runner = runner or run_command
        self.last_error = ""

    def run(self, args: Sequence[str], *, serial: str | None = None, timeout: float | None = None,
            binary: bool = False) -> AsyncResult:
        """Exécute ``adb [-s serial] args…``."""
        cmd = [self.path] + (["-s", serial] if serial else []) + list(args)
        result = self._runner(cmd, timeout=timeout or self.timeout, binary=binary)
        self.last_error = result.error or ("" if result.returncode == 0 else result.stderr.strip())
        return result

    def version(self) -> str:
        """Version d'adb, ou chaîne vide si adb est injoignable."""
        result = self.run(["version"], timeout=4)
        first = result.stdout.splitlines()[0] if result.stdout.strip() else ""
        return first.replace("Android Debug Bridge", "adb").strip() if result.ok else ""

    def available(self) -> bool:
        """Vrai si adb répond."""
        return bool(self.version())

    def devices(self) -> list[Device]:
        """Appareils connus d'adb."""
        result = self.run(["devices", "-l"])
        return parse_devices(result.stdout) if result.ok else []

    def details(self, serial: str) -> Device:
        """Informations détaillées sur un appareil (un seul aller-retour adb)."""
        script = "getprop; echo ===WM; wm size; echo ===BAT; dumpsys battery; echo ===DISP; dumpsys display"
        result = self.run(["shell", script], serial=serial, timeout=15)
        device = Device(serial=serial, state="device" if result.ok else "offline")
        if not result.ok:
            return device
        sec = split_sections(result.stdout)
        props = parse_props(sec["props"])
        device.props = props
        device.manufacturer = props.get("ro.product.manufacturer", "").strip().title()
        device.model = props.get("ro.product.model", "")
        device.name = next(
            (props[k] for k in ("ro.product.marketname", "ro.config.marketing_name", "ro.product.vendor.marketname") if props.get(k)),
            "",
        )
        if device.name and device.manufacturer and not device.name.lower().startswith(device.manufacturer.lower()):
            device.name = f"{device.manufacturer} {device.name}"
        device.android = props.get("ro.build.version.release", "")
        device.sdk = props.get("ro.build.version.sdk", "")
        device.battery, device.charging = parse_battery(sec.get("bat", ""))
        size = parse_wm_size(sec.get("wm", ""))
        hz = parse_refresh_rate(sec.get("disp", ""))
        device.display = f"{size} @ {hz}Hz" if size and hz else size
        device.transport = "tcpip" if ":" in serial else "usb"
        return device

    def battery(self, serial: str) -> tuple[int | None, bool]:
        """Niveau de batterie et charge."""
        result = self.run(["shell", "dumpsys", "battery"], serial=serial, timeout=5)
        return parse_battery(result.stdout) if result.ok else (None, False)

    def latency_ms(self, serial: str) -> float | None:
        """Aller-retour adb en millisecondes (indicateur de latence de liaison)."""
        result = self.run(["shell", "echo", "1"], serial=serial, timeout=4)
        return round(result.duration * 1000, 1) if result.ok else None

    def device_ip(self, serial: str) -> str | None:
        """Adresse IP Wi-Fi de l'appareil."""
        result = self.run(["shell", "ip", "-f", "inet", "addr", "show", "wlan0"], serial=serial, timeout=5)
        ip = parse_ip(result.stdout) if result.ok else None
        if ip:
            return ip
        route = self.run(["shell", "ip", "route"], serial=serial, timeout=5)
        return parse_ip(route.stdout) if route.ok else None

    def connect(self, address: str) -> tuple[bool, str]:
        """``adb connect`` ; renvoie (succès, message)."""
        result = self.run(["connect", address], timeout=10)
        text = (result.stdout + result.stderr).strip() or result.error
        return ("connected" in text.lower() and "cannot" not in text.lower() and "failed" not in text.lower()), text

    def disconnect(self, address: str = "") -> tuple[bool, str]:
        """``adb disconnect`` (tout si ``address`` est vide)."""
        result = self.run(["disconnect", *([address] if address else [])], timeout=6)
        return result.ok, (result.stdout + result.stderr).strip() or result.error

    def enable_tcpip(self, serial: str, port: int = 5555) -> tuple[bool, str]:
        """``adb tcpip`` sur un appareil branché en USB."""
        result = self.run(["tcpip", str(port)], serial=serial, timeout=8)
        return result.ok, (result.stdout + result.stderr).strip() or result.error

    def shell(self, serial: str | None, command: str, timeout: float = 15.0) -> AsyncResult:
        """Exécute une commande ``adb shell``."""
        return self.run(["shell", command], serial=serial or None, timeout=timeout)

    def screencap(self, serial: str | None) -> bytes | None:
        """Capture d'écran PNG (``exec-out screencap -p``), ou None en cas d'échec."""
        result = self.run(["exec-out", "screencap", "-p"], serial=serial or None, timeout=8, binary=True)
        if result.ok and result.data.startswith(b"\x89PNG"):
            return result.data
        return None

    def kill_server(self) -> bool:
        """Arrête le serveur adb."""
        return self.run(["kill-server"], timeout=6).ok

    def start_server(self) -> bool:
        """Démarre le serveur adb."""
        return self.run(["start-server"], timeout=10).ok
