@echo off
rem Run this once. It installs what Endslate needs and puts a
rem shortcut with a proper icon on your Desktop and Start Menu.
title Endslate setup
cd /d "%~dp0"

set "CONPY="
set "GUIPY="
for %%C in (py.exe python.exe python3.exe) do (
    for /f "delims=" %%I in ('where %%C 2^>nul') do (
        if not defined CONPY (
            "%%I" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 set "CONPY=%%I"
        )
    )
)
for %%C in (pythonw.exe pyw.exe) do (
    for /f "delims=" %%I in ('where %%C 2^>nul') do (
        if not defined GUIPY set "GUIPY=%%I"
    )
)

if not defined CONPY (
    echo.
    echo   Endslate needs Python 3.10 or newer, and I could not find it.
    echo   Install it from https://www.python.org/downloads/ and tick
    echo   "Add python.exe to PATH" on the first installer screen.
    echo.
    pause
    exit /b 1
)
if not defined GUIPY set "GUIPY=%CONPY%"

echo Installing PySide6 and requests...
"%CONPY%" -m pip install --disable-pip-version-check --quiet -r requirements.txt
if errorlevel 1 (
    echo The install failed. Nothing was changed.
    pause
    exit /b 1
)

echo Creating shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = '%CD%';" ^
  "$icon = Join-Path $root 'assets\endslate.ico';" ^
  "$shell = New-Object -ComObject WScript.Shell;" ^
  "foreach ($dir in @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'))) {" ^
  "  $link = $shell.CreateShortcut((Join-Path $dir 'Endslate.lnk'));" ^
  "  $link.TargetPath = '%GUIPY%';" ^
  "  $link.Arguments = '-m endslate gui';" ^
  "  $link.WorkingDirectory = $root;" ^
  "  $link.IconLocation = $icon;" ^
  "  $link.Description = 'Rename and reorganize the media library';" ^
  "  $link.Save();" ^
  "}"
if errorlevel 1 (
    echo Could not create the shortcuts. You can still use Endslate.cmd.
    pause
    exit /b 1
)

echo.
echo   Done.
echo   There is now an Endslate icon on your Desktop and in the Start Menu.
echo   Clicking it opens the window straight away, with no console at all.
echo.
pause
