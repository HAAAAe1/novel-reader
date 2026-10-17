@echo off
setlocal EnableExtensions
rem Launch reader.py with the first Python interpreter that has tkinter.
rem IMPORTANT: keep this file pure ASCII. cmd re-reads the file byte-by-byte;
rem after "chcp" any non-ASCII byte shifts later line parsing. Chinese only in the FILENAME.

set "PY="

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import tkinter" >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3.12 -c "import tkinter" >nul 2>nul
        if not errorlevel 1 set "PY=py -3.12"
    )
)
if not defined PY (
    python -c "import tkinter" >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    python3 -c "import tkinter" >nul 2>nul
    if not errorlevel 1 set "PY=python3"
)

if not defined PY goto no_python

for /f "delims=" %%I in ('%PY% -c "import sys; print(sys.executable)"') do set "PYEXE=%%I"
if not defined PYEXE goto no_python
for %%I in ("%PYEXE%") do set "PYDIR=%%~dpI"
set "PYW=%PYDIR%pythonw.exe"
if not exist "%PYW%" set "PYW=%PYEXE%"

rem EPUB support: install ebooklib into THIS interpreter if missing (TXT works without it)
"%PYEXE%" -c "import ebooklib" >nul 2>nul
if errorlevel 1 "%PYEXE%" -m pip install ebooklib --quiet --disable-pip-version-check

rem Windowed launch; %* forwards files dropped onto this bat
start "" "%PYW%" "%~dp0reader.py" %*
exit /b 0

:no_python
echo No Python with tkinter was found on this machine.
echo Install Python 3 from https://www.python.org/downloads/
echo and keep the "tcl/tk and IDLE" option checked, then run this again.
pause
exit /b 1
