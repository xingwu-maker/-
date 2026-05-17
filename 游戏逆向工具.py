"""游戏逆向工具 — 快速入口脚本

使用方法：
  python 游戏逆向工具.py analyze -f ce_export.xml
  python 游戏逆向工具.py analyze -p 12345 -a "game.exe+0x7FF8ABC"
  python 游戏逆向工具.py scan -p 12345 -m game.exe --pattern "48 8B ?? ?? ??"
  python 游戏逆向工具.py dump -p 12345 -a 0x7FF80000 -s 512
"""

import sys
from pathlib import Path

# 确保 game-reai 包在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent / "game-reai"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.cli.main import app  # noqa: E402

if __name__ == "__main__":
    app()
