# 摸鱼看书 🐟📖

轻量级 EPUB 阅读器，专为摸鱼设计。

## 特性

- **窗口随意缩放** — 最小 120×100，缩到任务栏旁边看
- **鼠标离开自动变淡** — 鼠标移出窗口后透明度降到 15%，就是个淡淡的影子
- **整章加载 + 平滑滚动** — 不分页，滚轮/方向键/空格逐行滚动
- **目录弹窗** — 菜单栏点「目录」弹出搜索+列表窗口，双击跳转
- **进度自动保存** — 关掉再打开接着上次的位置看
- **窗口置顶** — 视图菜单可切换
- **字体/背景色自定义** — Ctrl++ 放大，Ctrl+- 缩小
- **Escape 最小化** — 一键缩到任务栏

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+O | 打开 EPUB |
| Ctrl++ | 字体放大 |
| Ctrl+- | 字体缩小 |
| Ctrl+Q | 退出 |
| ← → | 上/下一章 |
| ↑ ↓ / 滚轮 | 平滑滚动 |
| PageUp/Down | 翻页 |
| 空格 | 下一页 |
| Escape | 最小化窗口 |

## 使用方法

1. 安装 Python 3.x
2. 双击 `启动摸鱼看书.bat`（自动安装依赖，无黑框）

或者命令行运行：
```bash
pip install ebooklib
python reader.py
```

## 截图

窗口很小，鼠标离开后自动变淡：

![screenshot](https://github.com/HAAAAe1/novel-reader/raw/master/screenshot.png)

## 依赖

- Python 3.x
- tkinter（内置）
- ebooklib
- lxml（ebooklib 依赖）
