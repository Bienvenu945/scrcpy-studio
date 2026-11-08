@echo off
rem Construit l'executable Windows de Scrcpy Studio (a lancer sous Windows).
rem Prerequis : Python 3.11+ dans le PATH. Inno Setup 6 (optionnel) pour l'installeur.
setlocal
cd /d "%~dp0\.."

if not exist .build-venv (
    python -m venv .build-venv || goto :error
)
call .build-venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt pyinstaller || goto :error

pyinstaller --noconfirm --clean packaging\scrcpy_studio.spec || goto :error
echo.
echo Executable : dist\ScrcpyStudio\ScrcpyStudio.exe

set ISCC=
where iscc >nul 2>nul && set ISCC=iscc
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if defined ISCC (
    %ISCC% packaging\installer.iss || goto :error
    echo Installeur : dist\ScrcpyStudio-setup.exe
) else (
    echo Inno Setup introuvable : installeur non genere ^(l'executable portable est pret^).
)
echo.
echo Termine.
exit /b 0

:error
echo.
echo ERREUR : la construction a echoue.
exit /b 1
