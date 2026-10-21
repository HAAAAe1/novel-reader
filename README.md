# 摸鱼看书 🐟📖

轻量级 EPUB/TXT 阅读器，专为摸鱼设计。

## 特性

- **免 Python 独立版** — Releases 提供单文件 exe，双击即用
- **EPUB + TXT 双格式** — TXT 自动识别编码（UTF-8/GB18030/UTF-16），按「第X章/回/节」自动切章；拖文件到快捷方式可直接打开
- **窗口随意缩放** — 最小 120×100，缩到任务栏旁边看
- **鼠标离开自动变淡** — 鼠标移出窗口后透明度降到 15%，就是个淡淡的影子
- **透明度可调** — 视图菜单「透明度...」里两个滑条：窗口透明度（30%~100%）和移开后透明度（5%~60%），拖动即生效、自动记住；默认 95% / 15% 不变
- **整章加载 + 平滑滚动** — 不分页，滚轮/方向键/空格逐行滚动
- **目录弹窗** — 菜单栏点「目录」弹出搜索+列表窗口，双击跳转
- **状态栏实时剩余字数** — 显示「本章剩 N 字 · 全书剩 M 字」（不含空白），随滚动刷新，滚到底归 0；字数条在菜单栏下方一行，窗口缩多小都可见
- **最近打开书架** — 文件菜单「最近打开」列最近 10 本，点击直接回到上次读到的章节和位置；文件被删/移走会置灰提示
- **进度自动保存** — 关掉再打开接着上次的位置和滚动位置接着看
- **窗口置顶** — 视图菜单可切换
- **字体/背景色自定义** — Ctrl++ 放大，Ctrl+- 缩小
- **Escape 最小化** — 一键缩到任务栏

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+O | 打开书籍（EPUB/TXT） |
| Ctrl++ | 字体放大 |
| Ctrl+- | 字体缩小 |
| Ctrl+Q | 退出 |
| ← → | 上/下一章 |
| ↑ ↓ / 滚轮 | 平滑滚动 |
| PageUp/Down | 翻页 |
| 空格 | 下一页 |
| Escape | 最小化窗口 |

## 使用方法

### 免 Python 独立版（推荐）

到 [Releases](https://github.com/HAAAAe1/novel-reader/releases) 下载 `novel-reader-vX.Y.Z.exe`，
双击即用，无需安装任何东西。

### 源码运行

1. 安装 Python 3.x
2. 双击 `启动摸鱼看书.bat`（自动安装依赖，无黑框）

或者命令行运行：
```bash
pip install ebooklib
python reader.py
```

### 构建独立版

需要 Python（含 tkinter/ebooklib/lxml）+ PyInstaller：

```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
# 产出 dist\摸鱼看书.exe
```

## 截图

窗口很小，鼠标离开后自动变淡：

![screenshot](https://github.com/HAAAAe1/novel-reader/raw/master/screenshot.png)

## 依赖

独立版（exe）：无

源码运行：

- Python 3.x
- tkinter（内置）
- ebooklib（仅 EPUB 需要，只读 TXT 可不装）
- lxml（ebooklib 依赖）
