Optionnel : placez ici le contenu d'une archive scrcpy officielle pour Windows
(scrcpy.exe, adb.exe, scrcpy-server, DLL…) dans un dossier nommé « scrcpy » :

    packaging/vendor/scrcpy/scrcpy.exe
    packaging/vendor/scrcpy/adb.exe
    ...

Le build PyInstaller l'embarque alors dans l'application (dossier « scrcpy »), et
Scrcpy Studio l'utilise automatiquement s'il n'est pas configuré autrement.
Respectez la licence de scrcpy en redistribuant ces fichiers (joignez son fichier LICENSE).
