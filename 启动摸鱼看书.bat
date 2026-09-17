@echo off
chcp 65001 >nul 2>&1
pythonw.exe -c "import ebooklib" >nul 2>&1 || python.exe -m pip install ebooklib --quiet
start "" pythonw.exe "%~dp0reader.py"
