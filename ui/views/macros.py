"""Vue Macros (PRO) : séquences d'étapes enregistrées dans les préférences."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QListWidget, QMenu, QPlainTextEdit

from config.defaults import default_records_dir
from core.macros import STEP_TYPES, Macro, MacroPlayer, MacroResult, Step, example_macro
from core.process import run_async
from ui.views.base_view import BaseView, confirm
from ui.widgets.controls import GlassButton
from ui.widgets.glass import GlassCard

_NEEDS_VALUE = {"wait": ("Attendre", "Durée en secondes :", "2"), "adb": ("Commande adb", "Commande adb shell :", "am start -n com.example.app")}


class MacrosView(BaseView):
    """Éditeur et lanceur de macros."""

    KEY = "macros"
    TITLE = "Macros"
    SUBTITLE = "Enchaînez lancement, attente, commandes adb et captures d'écran"
    RESETTABLE = False

    def build_top(self) -> None:
        """Cartes personnalisées placées avant les cartes déclaratives."""
        self._player: MacroPlayer | None = None
        self._running = False
        self._seeded = False

        macros = GlassCard("MACROS", "cube")
        self.macro_list = QListWidget()
        self.macro_list.setMinimumHeight(120)
        self.macro_list.currentRowChanged.connect(lambda _row: self._fill_steps())
        macros.add_widget(self.macro_list)
        macros.add_layout(self._buttons(("Nouvelle", "plus", self._new_macro), ("Dupliquer", "copy", self._duplicate_macro),
                                        ("Renommer", "edit", self._rename_macro), ("Supprimer", "trash", self._delete_macro)))
        self.column.addWidget(macros)

        steps = GlassCard("ÉTAPES", "list")
        self.step_list = QListWidget()
        self.step_list.setMinimumHeight(190)
        steps.add_widget(self.step_list)
        steps.add_layout(self._buttons(("Ajouter", "plus", self._add_step_menu), ("Modifier", "edit", self._edit_step),
                                       ("Monter", "chevron-up", lambda: self._move_step(-1)),
                                       ("Descendre", "chevron-down", lambda: self._move_step(1)),
                                       ("Retirer", "x", self._remove_step)))
        self.column.addWidget(steps)

        run = GlassCard("EXÉCUTION", "play")
        self.run_button = GlassButton("Exécuter", "play", "primary")
        self.run_button.clicked.connect(self._run)
        self.cancel_button = GlassButton("Annuler", "stop", "stop")
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.setEnabled(False)
        row = QHBoxLayout()
        row.addWidget(self.run_button)
        row.addWidget(self.cancel_button)
        row.addStretch(1)
        run.add_layout(row)
        self.log = QPlainTextEdit()
        self.log.setObjectName("Mono")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(150)
        run.add_widget(self.log)
        self.column.addWidget(run)

    @staticmethod
    def _buttons(*specs: tuple[str, str, Any]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for label, icon, handler in specs:
            button = GlassButton(label, icon)
            button.clicked.connect(lambda _c=False, h=handler: h())
            row.addWidget(button)
        row.addStretch(1)
        return row

    # ── données ──
    def _macros(self) -> list[Macro]:
        return [Macro.from_dict(d) for d in self.ctx.pref("macros_list")]

    def _save(self, macros: list[Macro], select: int | None = None) -> None:
        self.ctx.set_pref("macros_list", [m.to_dict() for m in macros])
        self._fill_macros(select if select is not None else self.macro_list.currentRow())

    def _current(self) -> tuple[list[Macro], int]:
        macros = self._macros()
        index = self.macro_list.currentRow()
        return macros, (index if 0 <= index < len(macros) else -1)

    def _fill_macros(self, select: int = 0) -> None:
        macros = self._macros()
        self.macro_list.blockSignals(True)
        self.macro_list.clear()
        for macro in macros:
            self.macro_list.addItem(f"{macro.name}  ·  {len(macro.steps)} étape(s)")
        self.macro_list.blockSignals(False)
        if macros:
            self.macro_list.setCurrentRow(max(0, min(select, len(macros) - 1)))
        self._fill_steps()

    def _fill_steps(self, select: int = -1) -> None:
        macros, index = self._current()
        self.step_list.clear()
        if index >= 0:
            for number, step in enumerate(macros[index].steps, start=1):
                self.step_list.addItem(f"{number}. {step.describe()}")
            if select >= 0 and self.step_list.count():
                self.step_list.setCurrentRow(min(select, self.step_list.count() - 1))
        self.run_button.setEnabled(index >= 0 and not self._running)

    # ── macros ──
    def _new_macro(self) -> None:
        name, ok = QInputDialog.getText(self, "Nouvelle macro", "Nom de la macro :")
        if ok and name.strip():
            macros = self._macros() + [Macro(name.strip())]
            self._save(macros, len(macros) - 1)

    def _duplicate_macro(self) -> None:
        macros, index = self._current()
        if index >= 0:
            macros.append(Macro(f"{macros[index].name} (copie)", [Step(s.type, s.value) for s in macros[index].steps]))
            self._save(macros, len(macros) - 1)

    def _rename_macro(self) -> None:
        macros, index = self._current()
        if index < 0:
            return
        name, ok = QInputDialog.getText(self, "Renommer", "Nouveau nom :", text=macros[index].name)
        if ok and name.strip():
            macros[index].name = name.strip()
            self._save(macros, index)

    def _delete_macro(self) -> None:
        macros, index = self._current()
        if index >= 0 and confirm(self, "Supprimer", f"Supprimer la macro « {macros[index].name} » ?"):
            del macros[index]
            self._save(macros, max(0, index - 1))

    # ── étapes ──
    def _prompt_step(self, kind: str, current: str = "") -> Step | None:
        if kind not in _NEEDS_VALUE:
            return Step(kind)
        title, label, default = _NEEDS_VALUE[kind]
        value, ok = QInputDialog.getText(self, title, label, text=current or default)
        return Step(kind, value.strip()) if ok else None

    def _add_step_menu(self) -> None:
        macros, index = self._current()
        if index < 0:
            return
        menu = QMenu(self)
        actions = {menu.addAction(label): kind for kind, label in STEP_TYPES.items()}
        chosen = menu.exec(QCursor.pos())
        if chosen in actions:
            step = self._prompt_step(actions[chosen])
            if step is not None:
                macros[index].steps.append(step)
                self._save(macros, index)
                self._fill_steps(len(macros[index].steps) - 1)

    def _edit_step(self) -> None:
        macros, index = self._current()
        row = self.step_list.currentRow()
        if index < 0 or row < 0:
            return
        old = macros[index].steps[row]
        step = self._prompt_step(old.type, old.value)
        if step is not None:
            macros[index].steps[row] = step
            self._save(macros, index)
            self._fill_steps(row)

    def _move_step(self, delta: int) -> None:
        macros, index = self._current()
        row = self.step_list.currentRow()
        target = row + delta
        if index >= 0 and row >= 0 and 0 <= target < len(macros[index].steps):
            steps = macros[index].steps
            steps[row], steps[target] = steps[target], steps[row]
            self._save(macros, index)
            self._fill_steps(target)

    def _remove_step(self) -> None:
        macros, index = self._current()
        row = self.step_list.currentRow()
        if index >= 0 and row >= 0:
            del macros[index].steps[row]
            self._save(macros, index)
            self._fill_steps(max(0, row - 1))

    # ── exécution ──
    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _run(self) -> None:
        macros, index = self._current()
        if index < 0 or self._running:
            return
        inst = self.ctx.inst
        folder = Path(self.ctx.prefs.records_dir) if self.ctx.prefs.records_dir else default_records_dir()
        post = self.ctx.dispatcher.post if self.ctx.dispatcher else (lambda fn, *a: fn(*a))
        player = MacroPlayer(
            launch=lambda: self.ctx.run_action("launch"), stop=lambda: self.ctx.run_action("stop"), adb=self.ctx.adb,
            serial=lambda: (inst.device.serial if inst.device else inst.effective().serial),
            captures_dir=folder / "captures", dispatcher=self.ctx.dispatcher,
            on_log=lambda text: post(self._append_log, text))
        self._player, self._running = player, True
        self.log.clear()
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        macro = macros[index]

        def done(value: Any, error: BaseException | None) -> None:
            self._running = False
            self.cancel_button.setEnabled(False)
            self.run_button.setEnabled(True)
            result: MacroResult | None = value
            if error is not None or result is None:
                self.ctx.notify("error", f"Macro interrompue : {error}")
            elif result.ok:
                self.ctx.notify("success", f"Macro « {macro.name} » terminée.")
            else:
                self.ctx.notify("error", result.error or "La macro a échoué.")

        run_async(lambda: player.run(macro), done, dispatcher=self.ctx.dispatcher, name="scrcpy-studio-macro")

    def _cancel(self) -> None:
        if self._player is not None:
            self._player.cancel()

    # ── cycle de vie ──
    def refresh_extra(self) -> None:
        """Met à jour les éléments personnalisés de la vue."""
        self._fill_macros(self.macro_list.currentRow() if self.macro_list.count() else 0)

    def on_enter(self) -> None:
        """Appelé à chaque affichage de la vue."""
        super().on_enter()
        if not self._seeded and not self.ctx.pref("macros_list"):
            self._seeded = True
            self.ctx.set_pref("macros_list", [example_macro().to_dict()])
        self._fill_macros(self.macro_list.currentRow() if self.macro_list.count() else 0)
