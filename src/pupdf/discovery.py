"""Locate the PDF that the application should work on.

The normal workflow intentionally involves *one* PDF in the program's
directory.  For a frozen Windows build that directory is the folder that
contains ``Pupdf.exe`` (not PyInstaller's temporary ``_MEIPASS`` folder).
When running from source, the current working directory is used.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import DiscoveryError


def app_directory() -> Path:
    """Return the directory used for implicit PDF discovery.

    A frozen executable must use the folder containing the ``.exe``.  In a
    PyInstaller one-file build ``__file__`` and ``sys._MEIPASS`` point into a
    temporary extraction folder, so neither can be used here.
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def _is_temporary_pdf(path: Path) -> bool:
    """Hide our own interrupted save files from automatic discovery."""

    return path.name.startswith(".") and ".pupdf-" in path.name


def find_pdfs(directory: str | Path | None = None) -> list[Path]:
    """Return all regular PDF files directly inside *directory*.

    The search is deliberately non-recursive and case-insensitive with
    respect to the ``.pdf`` suffix.
    """

    folder = Path(directory).expanduser() if directory is not None else app_directory()
    try:
        folder = folder.resolve()
    except OSError as exc:
        raise DiscoveryError(f"无法解析目录路径：{folder}（{exc}）") from exc

    if not folder.exists():
        raise DiscoveryError(f"目录不存在：{folder}")
    if not folder.is_dir():
        raise DiscoveryError(f"不是目录：{folder}")

    try:
        pdfs = [
            item
            for item in folder.iterdir()
            if item.is_file()
            and item.suffix.lower() == ".pdf"
            and not _is_temporary_pdf(item)
        ]
    except PermissionError as exc:
        raise DiscoveryError(f"没有权限读取目录：{folder}") from exc
    except OSError as exc:
        raise DiscoveryError(f"读取目录失败：{folder}（{exc}）") from exc

    return sorted(pdfs, key=lambda item: item.name.casefold())


def find_single_pdf(directory: str | Path | None = None) -> Path:
    """Find exactly one PDF or raise a helpful :class:`DiscoveryError`."""

    folder = Path(directory).expanduser() if directory is not None else app_directory()
    pdfs = find_pdfs(folder)

    if not pdfs:
        raise DiscoveryError(
            f"目录中没有 PDF 文件：{folder}\n"
            "请把一个 PDF 放在该目录，或使用 --pdf 指定文件。"
        )

    if len(pdfs) > 1:
        names = "\n".join(f"  - {pdf.name}" for pdf in pdfs)
        raise DiscoveryError(
            f"目录中有多个 PDF 文件：{folder}\n{names}\n"
            "为避免处理错误的文件，请只保留一个 PDF，或使用 --pdf 指定文件。"
        )

    return pdfs[0]


def pdfs_from_launch_args(argv: Iterable[str]) -> list[Path]:
    """Extract PDF path arguments passed by Windows drag-and-drop.

    Dropping a file onto ``Pupdf.exe`` makes Explorer start the program with
    the file as an ordinary command-line argument, e.g. ``Pupdf.exe
    "D:\\books\\a.pdf"``.  We accept that form as well as an explicit
    ``--pdf PATH`` / ``--pdf=PATH`` form used by shortcuts and tests.
    """

    args = list(argv)
    result: list[Path] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--pdf":
            if index + 1 >= len(args):
                raise DiscoveryError("--pdf 后面缺少文件路径。")
            result.append(Path(args[index + 1]).expanduser())
            index += 2
            continue
        if arg.startswith("--pdf="):
            value = arg.partition("=")[2]
            if not value:
                raise DiscoveryError("--pdf= 后面缺少文件路径。")
            result.append(Path(value).expanduser())
        elif not arg.startswith("-"):
            result.append(Path(arg).expanduser())
        index += 1

    # De-duplicate while preserving order (Explorer can only pass one file in
    # practice, but shortcuts and tests may repeat a path).
    unique: list[Path] = []
    seen: set[str] = set()
    for path in result:
        key = str(path.absolute()).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


@dataclass(frozen=True)
class StartupSelection:
    """Initial PDF and optional user-facing note for the GUI."""

    pdf: Path | None
    note: str | None = None


def choose_startup_pdf(
    argv: Sequence[str], base_dir: str | Path | None = None
) -> StartupSelection:
    """Choose what a freshly started GUI should load.

    A dropped file always wins, even if it lives outside the program folder.
    With no dropped file, auto-discovery is limited to the program folder.
    """

    try:
        dropped = pdfs_from_launch_args(argv)
    except DiscoveryError as exc:
        return StartupSelection(None, str(exc))

    if len(dropped) > 1:
        return StartupSelection(
            None,
            "一次只能处理一个 PDF。请把单个 PDF 拖到程序上，或点击“选择…”。",
        )
    if len(dropped) == 1:
        return StartupSelection(dropped[0], None)

    folder = Path(base_dir) if base_dir is not None else app_directory()
    try:
        pdfs = find_pdfs(folder)
    except DiscoveryError as exc:
        return StartupSelection(None, str(exc))

    if len(pdfs) == 1:
        return StartupSelection(pdfs[0], None)
    if not pdfs:
        return StartupSelection(
            None,
            f"程序目录中没有 PDF：{folder}。请点击“选择…”选择文件。",
        )
    return StartupSelection(
        None,
        f"程序目录中有 {len(pdfs)} 个 PDF，为避免选错，请点击“选择…”指定文件。",
    )
