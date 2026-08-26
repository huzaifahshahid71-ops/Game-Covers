@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo                 Game Covers - Windows Builder
echo ============================================================
echo.

where py >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo Make sure "Add Python to PATH" is enabled during setup.
    pause
    exit /b 1
)

echo [1/4] Updating pip...
py -m pip install --upgrade pip
if errorlevel 1 goto :failed

echo.
echo [2/4] Installing build dependencies...
py -m pip install -r requirements-dev.txt
if errorlevel 1 goto :failed

echo.
echo [3/4] Cleaning previous build output...
if exist build rmdir /s /q build
if exist "Game Covers.spec" del /q "Game Covers.spec"


echo.
echo [4/4] Building Game Covers.exe...
py -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "Game Covers" ^
  --icon "assets\game_covers.ico" ^
  --add-data "assets;assets" ^
  --collect-all customtkinter ^
  Game_Covers.py
if errorlevel 1 goto :failed

echo.
echo ============================================================
echo BUILD COMPLETE
echo Output: "%cd%\dist\Game Covers.exe"
echo ============================================================
if /I not "%~1"=="/ci" pause
exit /b 0

:failed
echo.
echo ============================================================
echo BUILD FAILED - review the errors above.
echo ============================================================
if /I not "%~1"=="/ci" pause
exit /b 1
