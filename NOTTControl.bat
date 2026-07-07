@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON="

if exist "%ROOT%.venv\Scripts\pythonw.exe" (
    set "PYTHON=%ROOT%.venv\Scripts\pythonw.exe"
) else if exist "%ROOT%venv\Scripts\pythonw.exe" (
    set "PYTHON=%ROOT%venv\Scripts\pythonw.exe"
) else (
    for %%P in (pythonw.exe python.exe) do (
        where %%P >nul 2>&1
        if not errorlevel 1 if not defined PYTHON set "PYTHON=%%P"
    )
)

if not defined PYTHON (
    echo Python was not found. Install Python 3 or activate the project virtual environment.
    pause
    exit /b 1
)

cd /d "%ROOT%"
start "" "%PYTHON%" -m nottcontrol.main %*
