[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
# build_exe.ps1 — 构建免 Python 独立版 → dist\摸鱼看书.exe
# 运行：node ..\scripts\ps-run.cjs build_exe.ps1
# 依赖：Python（含 tkinter/ebooklib/lxml）+ PyInstaller
# 注意：不要用 param() —— ps-run 注入的输出编码行在前面会让 param 失效
$Python = "C:\Users\H\AppData\Local\Programs\Python\Python312\python.exe"

Set-Location $PSScriptRoot
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name "摸鱼看书" `
    --distpath dist --workpath build `
    reader.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Get-ChildItem dist | Format-Table Name, Length
