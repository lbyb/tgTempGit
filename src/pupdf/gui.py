"""Lazy entry point for the Tkinter GUI.

Tkinter is part of the official Windows Python distribution but is a separate
package on many Linux distributions.  Importing it lazily keeps the CLI fully
usable on a headless Linux server without Tk installed.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path


def main(argv: Sequence[str] | None = None, *, base_dir: Path | None = None) -> int:
    try:
        from .gui_app import main as app_main
    except ImportError as exc:  # pragma: no cover - platform dependent
        message = (
            "无法启动图形界面：当前 Python 缺少 Tkinter。\n"
            "Linux 请安装 python3-tk；Windows 官方 Python 安装包默认包含 Tkinter。\n"
            f"（{exc}）"
        )
        print(message, file=sys.stderr)
        return 1
    return app_main(argv, base_dir=base_dir)


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
