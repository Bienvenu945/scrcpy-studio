# Scrcpy Studio

**Lanceur graphique pour [scrcpy](https://github.com/Genymobile/scrcpy) 4.1** — Python 3.11+ / PySide6.
Direction artistique néon-bleu premium · modes **BASE** (6 vues) et **PRO** (toutes les options) · multi-instances, profils, préréglages, Command Palette.

> Conçu par **@Bienvenu K.K** — 2026

*Simple par défaut, complet sur demande.* Les 108 options longues de scrcpy 4.1 (plus `-G`, `-K`, `-M`) sont accessibles depuis l'interface en mode PRO ; le champ « Options libres » (vue Avancé) reste l'échappatoire.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt                        # PySide6 uniquement
python main.py
```

`scrcpy` et `adb` doivent être dans le `PATH` (ou renseignés dans **Paramètres › Exécution**). Activez le débogage USB sur l'appareil.

## Prise en main

| Zone | Rôle |
|---|---|
| **A** Barre supérieure | menu, logo, bascule **BASE / PRO**, recherche (Ctrl+K), état « Live », notifications, paramètres |
| **B** Navigation | sections repliables, onglets d'**instances** (un onglet = un appareil/une session) et de **profils** (clic droit : renommer, dupliquer, supprimer) |
| **C** Vue | une page par thème ; chaque réglage a une infobulle tirée de `scrcpy_aide.txt` |
| **D** Contexte | état de connexion, FPS / latence / batterie, aperçu de la commande, infos appareil |
| **E** Action dock | état ADB, commande générée, **Test** (3 s) et **LAUNCH SCRCPY** |

Capture de référence : `docs/mockup_reference.png`.

### Raccourcis

`Ctrl+Entrée` lancer · `Ctrl+.` arrêter · `Ctrl+K` palette · `Ctrl+B` barre latérale · `Ctrl+D` panneau contexte · `F11` mode focus · `Ctrl+1…9` vue n · `Ctrl+T` / `Ctrl+W` nouvelle / fermer l'instance · `Ctrl+Tab` instance suivante · `Ctrl+,` paramètres · `F1` chercher une option scrcpy · `Ctrl+Q` quitter.

### Profils et préréglages

* Un **profil** est un *delta* appliqué sur la base de l'instance (« Vue principale ») : modifier un réglage sous un profil ne touche pas la base.
* Les **préréglages** (Stream Ultra, Record 4K, LowLat + les vôtres, bouton ⚙ de la vue Device) appliquent un lot de réglages en un clic.

### Données

Configuration dans `~/.config/scrcpy-studio/` (Linux), `%APPDATA%\ScrcpyStudio` (Windows) ou `~/Library/Application Support/ScrcpyStudio` (macOS) ; variable `SCRCPY_STUDIO_HOME` pour la surcharger. `settings.json` : préférences et macros · `config.json` : instances et profils. Import/export JSON dans **Paramètres**.

## Paquets : `.deb` et `.exe`

| Cible | Commande | Résultat |
|---|---|---|
| Debian / Kali / Ubuntu (léger, PySide6 du système) | `packaging/build_deb.sh` | `dist/scrcpy-studio_4.0.0_all.deb` |
| Debian / Kali (autonome, sans PySide6 système) | `pip install PySide6 pyinstaller && packaging/build_deb.sh --bundled` | `dist/scrcpy-studio_4.0.0_<arch>.deb` |
| Windows | `packaging\build_exe.bat` | `dist\ScrcpyStudio\ScrcpyStudio.exe` (+ `dist\ScrcpyStudio-setup.exe` si Inno Setup est installé) |
| Les deux, dans le cloud | workflow GitHub Actions `.github/workflows/build.yml` (manuel ou tag `v*`) | artefacts `.exe`, `.zip` portable et `.deb` |

```bash
sudo apt install ./dist/scrcpy-studio_4.0.0_all.deb     # installe aussi les dépendances ; lanceur : « scrcpy-studio »
```

* Un `.exe` ne peut être construit que **sous Windows** (PyInstaller ne compile pas d'une plateforme à l'autre) : lancez `build_exe.bat` sur une machine Windows ou utilisez le workflow GitHub.
* Pour livrer scrcpy avec l'application, déposez l'archive scrcpy officielle dans `packaging/vendor/scrcpy/` avant le build (voir `packaging/vendor/README.txt`) : elle est utilisée automatiquement.
* Le journal d'erreurs de l'exécutable sans console est `scrcpy-studio.log`, dans le dossier de configuration.
* Changez `MAINTAINER` (variable d'environnement) pour renseigner votre adresse dans le paquet Debian.

## Tests

```bash
python -m unittest discover -s tests -t .     # ou : pytest
```

* `core/`, `config/` et la logique pure de `ui/` (thème, contexte, registre, palette) sont testés sans Qt.
* `tests/test_smoke.py` : avec PySide6 installé, il construit la vraie fenêtre (plateforme `offscreen`) ; sans PySide6 il utilise un faux Qt minimal (`tests/qt_stub.py`) qui vérifie imports, construction, navigation et **la couverture à 100 % des champs et des options scrcpy**.

## Structure

```
main.py · requirements.txt · pyproject.toml · scrcpy_aide.txt (référence, non modifié)
packaging/  build_deb.sh · build_exe.bat · scrcpy_studio.spec · installer.iss · scrcpy-studio.desktop · vendor/
config/   defaults · settings_store · profiles (préréglages)
core/     models · scrcpy (build_args, validate, runner) · adb · process · scrcpy_help · metrics · instances · macros
ui/       theme · context · rows · window · widgets/ · views/
resources/  fonts/ · icons/ · themes.json
docs/     roadmap_v4.0.txt · design_notes.md · mockup_reference.png
tests/
```

Écarts et choix de conception par rapport à la roadmap : [`docs/design_notes.md`](docs/design_notes.md).
