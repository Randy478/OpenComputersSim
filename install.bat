@echo off
REM ===================================================================
REM  OpenComputersSim installer for Windows (run from Command Prompt or
REM  by double-clicking this file).
REM
REM  Creates a local Python virtual environment in .venv and installs
REM  the dependencies (lupa + pygame-ce). Run run.bat afterwards to start.
REM ===================================================================
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo === OpenComputersSim installer ===
echo.

REM --- Find a Python launcher -----------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python was not found on your PATH.
    echo         Install Python 3.9 or newer from https://www.python.org/downloads/
    echo         and tick "Add Python to PATH" during setup, then run this again.
    echo.
    pause
    exit /b 1
)

echo Using Python: %PY%
%PY% --version

REM --- Create the virtual environment ---------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Creating virtual environment in .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists, reusing it.
)

set "VPY=.venv\Scripts\python.exe"

REM --- Install dependencies ------------------------------------------
REM Install packages one at a time so a problem with the optional GUI
REM library can't stop the required Lua runtime from installing.
REM --prefer-binary avoids slow/failing source builds on the newest
REM Python versions (it grabs a prebuilt wheel instead).
echo.
echo Upgrading pip ...
"%VPY%" -m pip install --upgrade pip setuptools wheel

echo.
echo Installing lupa (the Lua runtime - required) ...
"%VPY%" -m pip install --prefer-binary "lupa>=2.0"
if errorlevel 1 (
    echo.
    echo [ERROR] Could not install lupa. The simulator cannot run without it.
    echo         Please copy the messages above when asking for help.
    pause
    exit /b 1
)

echo.
echo Installing pygame-ce (the display window - optional) ...
"%VPY%" -m pip install --prefer-binary "pygame-ce>=2.4"
if errorlevel 1 (
    echo.
    echo [WARN] Could not install pygame-ce, so the graphical window is
    echo        unavailable. Everything still works in headless mode:
    echo            run.bat --headless "lshw; df"
    echo        You can try installing the window later with:
    echo            .venv\Scripts\python -m pip install --prefer-binary pygame-ce
    echo.
)

echo.
echo === Installation complete! ===
echo.
echo Start the simulator with:
echo     run.bat
echo.
echo Other commands:
echo     run.bat --spec            ^(show the machine specification^)
echo     run.bat --print-config    ^(show the config file^)
echo     run.bat --headless "lshw" ^(boot without a window^)
echo.
pause
endlocal
