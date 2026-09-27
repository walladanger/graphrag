@echo off
rem =====================================================================
rem  GraphTerm - Windows wrapper shell for the GraphRAG CLI.
rem  Started by graphterm.pyw (the desktop-app launcher) or run directly.
rem =====================================================================
setlocal
title GraphTerm

set "WRAP_DIR=%~dp0"

rem Prefer an explicit interpreter handed over by the launcher, then a
rem managed venv, then whatever python is on PATH.
if defined GRAPHTERM_PYTHON goto :have_python
if exist "%LOCALAPPDATA%\GraphTerm\venv\Scripts\python.exe" (
    set "GRAPHTERM_PYTHON=%LOCALAPPDATA%\GraphTerm\venv\Scripts\python.exe"
    goto :have_python
)
where python >nul 2>nul || (
    echo [graphterm] ERROR: Python was not found on this system.
    echo             Install Python 3.10+ from https://www.python.org/downloads/
    echo             ^(check "Add python.exe to PATH" during install^).
    exit /b 9009
)
for /f "delims=" %%P in ('where python') do (
    if not defined GRAPHTERM_PYTHON set "GRAPHTERM_PYTHON=%%P"
)

:have_python
"%GRAPHTERM_PYTHON%" -m graphrag_wrapper %*
if errorlevel 1 (
    echo.
    echo [graphterm] Wrapper exited with code %ERRORLEVEL%.
)
endlocal
