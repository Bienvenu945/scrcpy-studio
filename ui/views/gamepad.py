"""Vue OTG / Game (PRO) : mode OTG et périphériques HID simulés."""
from __future__ import annotations

from ui.rows import CardSpec, choice, toggle
from ui.views.base_view import BaseView


class GamepadView(BaseView):
    """OTG, manettes et entrées HID."""

    KEY = "gamepad"
    TITLE = "OTG / Game"
    SUBTITLE = "Clavier, souris et manettes simulés comme périphériques physiques"
    CARDS = (
        CardSpec("MODE OTG", "gamepad", (
            toggle("otg", "Mode OTG", "--otg", "Pas de mirroring ni d'adb : clavier et souris branchés comme par câble OTG (USB uniquement)"),
            toggle("no_power_on", "Ne pas allumer l'appareil au démarrage", "--no-power-on"),
            toggle("power_off_on_close", "Éteindre l'écran à la fermeture", "--power-off-on-close"),
        )),
        CardSpec("MANETTE", "gamepad", (
            choice("gamepad", "Entrée manette", "gamepad", "--gamepad", "AOA fonctionne surtout en USB"),
        )),
        CardSpec("RACCOURCIS HID", "keyboard", (
            toggle("force_uhid_keyboard", "Clavier HID (-K)", "-K", "UHID, ou AOA en mode OTG"),
            toggle("force_uhid_mouse", "Souris HID (-M)", "-M", "Capture relative : Alt gauche ou Super libère la souris"),
            toggle("force_uhid_gamepad", "Manette HID (-G)", "-G"),
        )),
    )
