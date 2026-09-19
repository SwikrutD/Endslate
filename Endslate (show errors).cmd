@echo off
rem Same as Endslate.cmd, but keeps the window open and prints
rem everything. Use this when the normal launcher does nothing.
title Endslate - show errors
cd /d "%~dp0"

set "CONPY="
for %%C in (py.exe python.exe python3.exe) do (
    for /f "delims=" %%I in ('where %%C 2^>nul') do (
        if not defined CONPY (
            "%%I" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 set "CONPY=%%I"
        )
    )
)
if not defined CONPY (
    echo Python 3.10 or newer was not found on PATH.
    pause
    exit /b 1
)

echo Using: %CONPY%
"%CONPY%" -V
echo.
echo Checking dependencies...
"%CONPY%" -m pip install --disable-pip-version-check -r requirements.txt
echo.
echo Running the test suite...
"%CONPY%" -m pytest -q
echo.
echo Opening the window. Errors will appear below.
"%CONPY%" -m endslate gui
echo.
echo Endslate closed with exit code %errorlevel%.
pause
