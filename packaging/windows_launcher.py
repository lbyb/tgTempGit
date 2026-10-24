"""PyInstaller entry point for the Windows GUI executable.

PyInstaller windowed builds have no console, so every startup failure must be
shown with a native message box.  Windows Explorer passes files dropped onto
the executable as normal command-line arguments; ``pupdf.gui_app`` handles
them, so this launcher only has to delegate ``sys.argv[1:]``.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import datetime


def _show_error(message: str) -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "Pupdf 启动失败", 0x10)
            return
        except Exception:
            pass
    stream = sys.stderr if sys.stderr is not None else sys.stdout
    if stream is not None:
        print(message, file=stream)


def _write_log(exc: BaseException) -> str:
    path = os.path.join(tempfile.gettempdir(), "pupdf-startup-error.log")
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n")
            handle.write(
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            )
    except OSError:
        pass
    return path


def main() -> int:
    try:
        from pupdf.gui_app import main as gui_main

        return gui_main(sys.argv[1:])
    except SystemExit:
        raise
    except BaseException as exc:  # startup errors are invisible in --windowed
        log_path = _write_log(exc)
        _show_error(
            "Pupdf 启动失败。\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            f"详细信息已写入：\n{log_path}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
