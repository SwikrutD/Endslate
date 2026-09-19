@echo off
rem ==============================================================
rem  Endslate. Double-click this file to open the window.
rem  No terminal, no commands. The console you may see for a
rem  moment is this script checking that Python has what it needs.
rem ==============================================================
title Endslate
cd /d "%~dp0"

set "CONPY="
set "GUIPY="
call :find_python
call :find_pythonw

if not exist "endslate\__init__.py" goto :wrong_folder
if not defined CONPY goto :wrong_folder
echo.
echo   This launcher has to sit in the Endslate folder, next to the
echo   "endslate" folder that holds the code.
echo.
echo   Current folder: %CD%
echo.
pause
exit /b 1

:no_python
if not defined GUIPY set "GUIPY=%CONPY%"

"%CONPY%" -c "import PySide6, requests" >nul 2>&1
if errorlevel 1 (
    call :install
    if errorlevel 1 exit /b 1
)

start "" "%GUIPY%" -m endslate gui
exit /b 0


:find_python
for %%C in (py.exe python.exe python3.exe) do (
    for /f "delims=" %%I in ('where %%C 2^>nul') do (
        if not defined CONPY (
            "%%I" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 set "CONPY=%%I"
        )
    )
)
exit /b 0

:find_pythonw
for %%C in (pythonw.exe pyw.exe) do (
    for /f "delims=" %%I in ('where %%C 2^>nul') do (
        if not defined GUIPY set "GUIPY=%%I"
    )
)
exit /b 0

:install
echo.
echo   First run. Installing what Endslate needs (PySide6 and requests).
echo   This takes a minute or two and only happens once.
echo.
"%CONPY%" -m pip install --disable-pip-version-check --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo   That install did not work.
    echo   Run "Endslate (show errors).cmd" to see the reason.
    echo.
    pause
    exit /b 1
)
echo   Done. Opening Endslate.
exit /b 0

:wrong_folder
echo.
echo   This launcher has to sit in the Endslate folder, next to the
echo   "endslate" folder that holds the code.
echo.
echo   Current folder: %CD%
echo.
pause
exit /b 1

:no_python
echo.
echo   Endslate needs Python 3.10 or newer, and I could not find it.
echo.
echo   1. Go to https://www.python.org/downloads/
echo   2. Download the latest Windows installer
echo   3. On the FIRST screen of the installer, tick
echo      "Add python.exe to PATH", then install
echo   4. Double-click this file again
echo.
pause
exit /b 1
