# Notes de conception — écarts par rapport à la roadmap v4.0

## État de vérification

* **Testé automatiquement (140+ tests)** : modèles, `build_args` (18 sections, corrections de la roadmap, couverture de toutes les options), validation, runner avec faux `scrcpy`, processus et orphelins, adb (parseurs + client), métriques, macros, instances/profils/persistance, thème (QSS généré valide, aucun jeton non résolu), contexte, palette de commandes, couverture de l'interface.
* **Non exécuté avec le vrai PySide6** : l'environnement de développement n'avait ni PySide6 ni accès réseau. L'interface a été vérifiée par un faux Qt (imports, construction, navigation, logique des signaux) et par analyse statique, pas visuellement. Premier lancement : `python main.py`, puis `python -m unittest discover -s tests -t .` (le test de fumée utilisera alors le vrai Qt en `offscreen`).

## Écarts assumés

| Sujet | Roadmap | Réalisé | Pourquoi |
|---|---|---|---|
| Champs | `Settings` ~100 champs incluant l'interface | `Settings` (113 champs, par instance) + `AppPrefs` (global, `settings.json`) | une instance ne doit pas dupliquer palette, mode, macros… |
| Champs sans équivalent scrcpy 4.1 | `camera_no_torch_on_exit`, `camera_start_torch`, `no_cleanup_signal`, `ip`, `tcpip_force`, `no_audio` | non créés ; `camera_torch`, `tcpip_force_reconnect` et `audio` (inversé) couvrent le besoin | n'existent pas dans l'aide 4.1 |
| `--resolution` (aperçu du mockup) | présent dans l'image | le sélecteur « Résolution » pilote `--max-size` | `--resolution` n'est pas une option scrcpy |
| `-K / -M / -G` | « traduits en `--keyboard=uhid` » | `--keyboard=uhid` (ou `aoa` si OTG) ; un mode explicite l'emporte | sémantique identique à `-K` |
| `--orientation` | émet les deux options | idem (`--display-orientation` + `--record-orientation`, miroir → affichage seul) | alias documenté par l'aide |
| `QProcess` | asynchrone via QProcess | `subprocess` + threads + file `Dispatcher` vidée par un `QTimer` | cœur testable sans Qt ; aucun appel bloquant dans le thread graphique |
| Parallélisme | « une seule instance à la fois » *et* « min. 3 simultanées » | `allow_parallel` activé par défaut ; un même appareil ne sert qu'une instance | les deux phrases sont contradictoires ; réglable dans Paramètres |
| Latence | « parsée depuis scrcpy » | valeur de scrcpy si elle l'affiche, sinon aller-retour `adb shell` | scrcpy n'imprime pas de latence par défaut |
| « USB 3.2 » | affiché dans le mockup | « USB » / « Wi-Fi » | la vitesse du bus n'est pas lisible via adb |
| Verre dépoli | `backdrop-filter` | cartes translucides à 85 % | Qt Widgets n'offre pas de flou d'arrière-plan |
| Redimensionnement | — | fenêtre sans cadre : déplacement par la barre, redimensionnement par la poignée en bas à droite | simplicité et portabilité |
| Modules ajoutés | — | `core/macros.py`, `ui/context.py`, `ui/rows.py`, `ui/views/__init__.py` (registre) | logique pure testable, vues déclaratives |

## Principes

* Les vues sont **déclaratives** (`CardSpec` / `Row`) : une ligne = un champ + l'option scrcpy qu'elle documente (`opt`). Le test de couverture échoue si un champ de `Settings` ou une option de `scrcpy_aide.txt` n'a aucune ligne ou bouton.
* `build_args` n'émet que les valeurs **différentes des défauts scrcpy** ; l'ordre suit les 18 sections de la roadmap.
* Un changement de palette reconstruit l'interface (icônes et QSS recolorés) ; QSS généré uniquement à ce moment.
