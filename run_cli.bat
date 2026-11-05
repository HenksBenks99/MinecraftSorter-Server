@echo off
chcp 65001 >nul
title ForgeModSearch CLI

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo DEBUG: SCRIPT_DIR=%SCRIPT_DIR%

python --version >nul 2>&1
if errorlevel 1 (
    echo Python non trovato in PATH
    echo Usa ForgeModSearch_GUI.exe (non richiede Python)
    pause
    exit /b 1
)

echo DEBUG: Python found

if not exist "%SCRIPT_DIR%\separate_mods.py" (
    echo separate_mods.py non trovato in %SCRIPT_DIR%
    pause
    exit /b 1
)

echo DEBUG: separate_mods.py found
echo DEBUG: Args=%*

if "%~1"=="" (
    echo ForgeModSearch v4.1.0 - Modalita interattiva
    echo.
    set /p INPUT="Cartella modpack sorgente: "
    if "%INPUT%"=="" exit /b 0
    set /p OUTPUT="Cartella output [./mods/Server_Ready]: "
    if "%OUTPUT%"=="" set OUTPUT=./mods/Server_Ready
    set /p DRY="Solo dry-run? [s/N]: "

    if /i "%DRY:~0,1%"=="s" (
        echo DEBUG: Running with --dry-run
        python "%SCRIPT_DIR%\separate_mods.py" -i "%INPUT%" -o "%OUTPUT%" --dry-run
    ) else (
        echo DEBUG: Running without --dry-run
        python "%SCRIPT_DIR%\separate_mods.py" -i "%INPUT%" -o "%OUTPUT%"
    )
) else (
    echo DEBUG: Running with args
    python "%SCRIPT_DIR%\separate_mods.py" %*
)
pause
