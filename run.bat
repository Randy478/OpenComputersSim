@echo off
REM ===================================================================
REM  Launch OpenComputersSim on Windows.
REM
REM  Uses the virtual environment created by install.bat. Any arguments
REM  you pass are forwarded to the simulator, e.g.:
REM      run.bat
REM      run.bat --spec
REM      run.bat --headless "lshw; df"
REM      run.bat --scale 2
REM ===================================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "VPY=.venv\Scripts\python.exe"

if not exist "%VPY%" (
    echo [ERROR] The virtual environment was not found.
    echo         Run install.bat first.
    echo.
    pause
    exit /b 1
)

echo Starting OpenComputersSim...
"%VPY%" run.py %*
set "RC=%ERRORLEVEL%"

REM Keep the window open after a crash or when double-clicked, so the
REM error message stays readable.
if not "%RC%"=="0" (
    echo.
    echo OpenComputersSim exited with code %RC%.
    pause
)

endlocal
