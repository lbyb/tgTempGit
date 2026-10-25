#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = [
#   "pymupdf==1.24.14",
# ]
# ///
"""Pupdf - create per-page bookmarks and page labels in a PDF.

Run directly with uv on Linux, macOS or Windows::

    uv run pupdf.py

Only two page numbers are required: the page where the table of contents
starts and the page where body page 1 starts.  The PDF is overwritten in
place after a verified, atomic temporary-file write.

The command-line layer and PDF engine deliberately live in this one file so
the tool can be copied anywhere and run with uv without installing a project
or polluting the system Python environment.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import sys
import tempfile
import traceback
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

__version__ = "0.3.0"

TOC_TITLE = "目录"

try:  # PyMuPDF >= 1.24 prefers the "pymupdf" import name.
    import pymupdf as fitz
except ImportError:  # pragma: no cover - older installations
    try:
        import fitz  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - dependency missing
        fitz = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# User-facing errors
# ---------------------------------------------------------------------------


class PupdfError(Exception):
    """Base class for expected, recoverable errors."""


class UserInputError(PupdfError):
    """A page number, path or option supplied by the user is not valid."""


class DiscoveryError(PupdfError):
    """The input PDF could not be determined."""


class PdfOperationError(PupdfError):
    """A PDF could not be opened, changed, or written safely."""


class EncryptedPdfError(PdfOperationError):
    """The PDF requires a password and cannot be processed."""


# ---------------------------------------------------------------------------
# PDF discovery
# ---------------------------------------------------------------------------


def _is_temporary_pdf(path: Path) -> bool:
    return path.name.startswith(".") and ".pupdf-" in path.name


def find_pdfs(directory: str | Path | None = None) -> list[Path]:
    """Return all PDFs directly inside *directory* (non-recursive)."""

    folder = Path(directory).expanduser() if directory is not None else Path.cwd()
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

    folder = Path(directory).expanduser() if directory is not None else Path.cwd()
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
            "为避免处理错误的文件，请只保留一个，或使用 --pdf 指定文件。"
        )
    return pdfs[0]


# ---------------------------------------------------------------------------
# PDF engine
# ---------------------------------------------------------------------------


def _require_fitz():
    if fitz is None:
        raise PdfOperationError(
            "缺少 PDF 处理库 PyMuPDF。\n"
            "推荐用 uv 运行，它会自动安装脚本声明的依赖：\n"
            "  uv run pupdf.py\n"
            "或者手动执行：python -m pip install -r requirements.txt"
        )
    return fitz


def _as_page_number(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UserInputError(f"{field_name}必须是整数页码。")
    return value


def _normalise_pdf_path(pdf_path: str | Path) -> Path:
    raw = Path(pdf_path).expanduser()
    try:
        path = raw.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PdfOperationError(f"PDF 文件不存在：{raw}") from exc
    except OSError as exc:
        raise PdfOperationError(f"无法解析 PDF 路径：{raw}（{exc}）") from exc

    if path.suffix.lower() != ".pdf":
        raise PdfOperationError(f"不是 PDF 文件（扩展名必须为 .pdf）：{path}")
    if not path.is_file():
        raise PdfOperationError(f"不是普通文件：{path}")
    return path


def _open_document(path: Path):
    fitz_module = _require_fitz()
    try:
        doc = fitz_module.open(str(path), filetype="pdf")
    except Exception as exc:
        raise PdfOperationError(
            f"无法打开 PDF：{path}\n可能文件已损坏或不是有效的 PDF。（{exc}）"
        ) from exc

    if doc.needs_pass:
        doc.close()
        raise EncryptedPdfError(f"PDF 受密码保护，暂不支持处理：{path}")
    metadata = doc.metadata or {}
    # Owner-password-only PDFs can report is_encrypted == False while still
    # carrying encryption metadata.  Re-saving them would silently remove
    # encryption/permissions, so reject them too.
    if getattr(doc, "is_encrypted", False) or metadata.get("encryption"):
        doc.close()
        raise EncryptedPdfError(f"PDF 已加密或带有权限密码，暂不支持处理：{path}")
    if doc.page_count < 1:
        doc.close()
        raise PdfOperationError(f"PDF 没有页面：{path}")
    return doc


@dataclass(frozen=True)
class PdfInfo:
    """Read-only information about one PDF."""

    path: Path
    total_pages: int
    title: str | None
    has_outline: bool


def analyze_pdf(pdf_path: str | Path) -> PdfInfo:
    """Open and validate a PDF without changing it."""

    path = _normalise_pdf_path(pdf_path)
    doc = _open_document(path)
    try:
        metadata = doc.metadata or {}
        title = (metadata.get("title") or "").strip() or None
        outline = doc.get_toc(simple=True) or []
        return PdfInfo(
            path=path,
            total_pages=doc.page_count,
            title=title,
            has_outline=bool(outline),
        )
    finally:
        doc.close()


@dataclass(frozen=True)
class PageLayout:
    """Validated 1-based page layout for one PDF."""

    toc_page: int
    body_page: int
    total_pages: int

    def __post_init__(self) -> None:
        toc = _as_page_number(self.toc_page, "目录页")
        body = _as_page_number(self.body_page, "正文第1页")
        total = _as_page_number(self.total_pages, "PDF总页数")

        if total < 1:
            raise UserInputError("PDF 必须至少有一页。")
        if toc < 1:
            raise UserInputError("目录页页码必须从 1 开始。")
        if body < 1:
            raise UserInputError("正文第1页页码必须从 1 开始。")
        if toc > total:
            raise UserInputError(f"目录页 {toc} 超出 PDF 范围（共 {total} 页）。")
        if body > total:
            raise UserInputError(f"正文第1页 {body} 超出 PDF 范围（共 {total} 页）。")
        if toc >= body:
            raise UserInputError(
                f"正文第1页（{body}）必须大于目录页（{toc}），"
                "两者之间至少要有 1 页目录。"
            )

    @property
    def toc_pages(self) -> int:
        return self.body_page - self.toc_page

    @property
    def body_pages(self) -> int:
        return self.total_pages - self.body_page + 1

    @property
    def toc_end_page(self) -> int:
        return self.body_page - 1

    @property
    def body_end_page(self) -> int:
        return self.total_pages


def validate_layout(toc_page: int, body_page: int, total_pages: int) -> PageLayout:
    """Validate and return a :class:`PageLayout`."""

    return PageLayout(toc_page=toc_page, body_page=body_page, total_pages=total_pages)


@dataclass(frozen=True)
class BookmarkItem:
    """One PDF outline entry. ``page`` is 1-based."""

    level: int
    title: str
    page: int

    def as_list(self) -> list:
        return [self.level, self.title, self.page]


_ROMAN_PATTERN = re.compile(
    r"m{0,4}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
)
_ROMAN_VALUES = (
    (1000, "m"),
    (900, "cm"),
    (500, "d"),
    (400, "cd"),
    (100, "c"),
    (90, "xc"),
    (50, "l"),
    (40, "xl"),
    (10, "x"),
    (9, "ix"),
    (5, "v"),
    (4, "iv"),
    (1, "i"),
)


def _to_roman(number: int) -> str:
    """Return a lowercase Roman numeral; 1 -> i, 4 -> iv, 9 -> ix."""

    if number < 1:
        return ""
    result = []
    remainder = number
    for value, symbol in _ROMAN_VALUES:
        while remainder >= value:
            result.append(symbol)
            remainder -= value
    return "".join(result)


def _to_letters(index: int) -> str:
    """Return A, B, … Z, AA, AB, … for a zero-based index."""

    result = []
    number = index + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        result.append(chr(ord("A") + remainder))
    return "".join(reversed(result))


def _is_roman_token(token: str) -> bool:
    return bool(token) and bool(_ROMAN_PATTERN.fullmatch(token.lower()))


def _classify_front_label(prefix: str, style: str) -> str:
    """Classify a front-matter page label as ``letter`` or ``roman``.

    The style field is the most reliable signal because it comes directly from
    the PDF page-label rule.  For tools that leave ``style`` empty and put the
    marker in ``prefix``, a leading ASCII token is inspected as a fallback.
    """

    clean = re.sub(r"\.pdg$", "", prefix or "", flags=re.IGNORECASE).strip()
    style = (style or "").strip()

    if style in {"r", "R"}:
        return "roman"
    if style in {"A", "a"}:
        return "letter"
    if clean.startswith("!"):
        return "roman"
    if re.match(r"^(?:cov|bok|leg|fow)", clean, flags=re.IGNORECASE):
        return "letter"

    token_match = re.match(r"^[A-Za-z]+", clean)
    if token_match:
        token = token_match.group(0)
        # Lowercase Roman, multi-letter Roman and I/V/X are unambiguous.
        # A single uppercase "A"/"B"/"C" is treated as a front-matter letter.
        if _is_roman_token(token) and (
            token.islower() or len(token) > 1 or token in {"I", "V", "X"}
        ):
            return "roman"
        return "letter"
    return "letter"


def _front_label_kinds(doc, count: int) -> tuple[str, ...]:
    """Inspect the existing labels for pages before the TOC."""

    if count <= 0:
        return ()
    try:
        rules = sorted(
            doc.get_page_labels() or [],
            key=lambda item: int(item.get("startpage", 0)),
        )
    except Exception:
        rules = []

    kinds: list[str] = []
    active: dict | None = None
    rule_index = 0
    for page_index in range(count):
        while (
            rule_index < len(rules)
            and int(rules[rule_index].get("startpage", 0)) <= page_index
        ):
            active = rules[rule_index]
            rule_index += 1
        if active is None:
            kinds.append("letter")
        else:
            kinds.append(
                _classify_front_label(
                    str(active.get("prefix", "")), str(active.get("style", ""))
                )
            )
    return tuple(kinds)


def _page_labels_for_layout(
    layout: PageLayout, front_label_kinds: tuple[str, ...]
) -> tuple[dict, ...]:
    """Build explicit per-page labels: A…, i…, 1….

    Every page gets an explicit prefix with an empty numbering style.  This
    keeps the resulting page labels exactly as normalized instead of allowing
    a continuing style to append hidden automatic numbers.
    """

    labels: list[dict] = []
    letter_number = 0
    roman_number = 0
    body_number = 1

    for page in range(1, layout.total_pages + 1):
        if page < layout.toc_page:
            index = page - 1
            kind = (
                front_label_kinds[index] if index < len(front_label_kinds) else "letter"
            )
            if kind == "roman":
                roman_number += 1
                prefix = _to_roman(roman_number)
            else:
                letter_number += 1
                prefix = _to_letters(letter_number - 1)
        elif page < layout.body_page:
            roman_number += 1
            prefix = _to_roman(roman_number)
        else:
            prefix = str(body_number)
            body_number += 1

        labels.append(
            {
                "startpage": page - 1,
                "prefix": prefix,
                "style": "",
                "firstpagenum": 1,
            }
        )
    return tuple(labels)


@dataclass(frozen=True)
class ProcessPlan:
    """Immutable description of one bookmark operation."""

    pdf_path: Path
    layout: PageLayout
    existing_outline: tuple[BookmarkItem, ...] = field(default_factory=tuple)
    front_label_kinds: tuple[str, ...] = field(default_factory=tuple)
    keep_outline: bool = False
    write_page_labels: bool = True

    @property
    def generated_outline(self) -> tuple[BookmarkItem, ...]:
        """A flat outline: one 目录 entry, then 1, 2, … for body pages."""

        layout = self.layout
        items: list[BookmarkItem] = [BookmarkItem(1, TOC_TITLE, layout.toc_page)]
        for offset in range(layout.body_pages):
            items.append(BookmarkItem(1, str(offset + 1), layout.body_page + offset))
        return tuple(items)

    @property
    def final_outline(self) -> tuple[BookmarkItem, ...]:
        if self.keep_outline:
            return self.existing_outline + self.generated_outline
        return self.generated_outline

    @property
    def page_labels(self) -> tuple[dict, ...]:
        return _page_labels_for_layout(self.layout, self.front_label_kinds)

    @property
    def generated_count(self) -> int:
        return len(self.generated_outline)


def _outline_from_doc(doc) -> tuple[BookmarkItem, ...]:
    try:
        raw = doc.get_toc(simple=True) or []
    except Exception as exc:
        raise PdfOperationError(f"读取原 PDF 书签失败：{exc}") from exc

    items = []
    for entry in raw:
        if len(entry) < 3:
            continue
        page = int(entry[2])
        # External-URL outline entries have no page destination and cannot be
        # represented by set_toc()'s simple list.
        if page < 1:
            continue
        items.append(BookmarkItem(int(entry[0]), str(entry[1]), page))
    return tuple(items)


def build_plan(
    pdf_path: str | Path,
    toc_page: int,
    body_page: int,
    *,
    keep_outline: bool = False,
    write_page_labels: bool = True,
) -> ProcessPlan:
    """Validate the PDF and page numbers without modifying the file."""

    path = _normalise_pdf_path(pdf_path)
    toc = _as_page_number(toc_page, "目录页")
    body = _as_page_number(body_page, "正文第1页")
    doc = _open_document(path)
    try:
        layout = PageLayout(toc_page=toc, body_page=body, total_pages=doc.page_count)
        existing = _outline_from_doc(doc) if keep_outline else ()
        front_kinds = _front_label_kinds(doc, layout.toc_page - 1)
        return ProcessPlan(
            pdf_path=path,
            layout=layout,
            existing_outline=existing,
            front_label_kinds=front_kinds,
            keep_outline=keep_outline,
            write_page_labels=write_page_labels,
        )
    finally:
        doc.close()


@dataclass(frozen=True)
class ProcessResult:
    """What was (or, for a dry run, would have been) written."""

    pdf_path: Path
    total_pages: int
    toc_page: int
    body_page: int
    toc_pages: int
    body_pages: int
    generated_bookmarks: int
    total_bookmarks: int
    page_labels_written: bool
    backup_path: Path | None = None
    dry_run: bool = False


def _result_for_plan(
    plan: ProcessPlan, *, backup_path: Path | None = None, dry_run: bool = False
) -> ProcessResult:
    return ProcessResult(
        pdf_path=plan.pdf_path,
        total_pages=plan.layout.total_pages,
        toc_page=plan.layout.toc_page,
        body_page=plan.layout.body_page,
        toc_pages=plan.layout.toc_pages,
        body_pages=plan.layout.body_pages,
        generated_bookmarks=plan.generated_count,
        total_bookmarks=len(plan.final_outline),
        page_labels_written=plan.write_page_labels,
        backup_path=backup_path,
        dry_run=dry_run,
    )


def _outline_as_lists(items: Iterable[BookmarkItem]) -> list[list]:
    return [item.as_list() for item in items]


def _verify_temporary_pdf(
    path: Path, layout: PageLayout, expected_outline: Sequence[BookmarkItem]
) -> None:
    fitz_module = _require_fitz()
    try:
        check = fitz_module.open(str(path), filetype="pdf")
    except Exception as exc:
        raise PdfOperationError(
            f"写入后的 PDF 无法重新打开，已取消覆盖：{exc}"
        ) from exc

    try:
        if check.page_count != layout.total_pages:
            raise PdfOperationError("写入后的 PDF 页数发生变化，已取消覆盖原始文件。")
        written = check.get_toc(simple=True) or []
        if expected_outline and len(written) < len(expected_outline):
            raise PdfOperationError("写入后的 PDF 书签数量不正确，已取消覆盖原始文件。")
    finally:
        check.close()


def _make_backup(source: Path) -> Path:
    backup = source.with_name(source.name + ".bak")
    try:
        shutil.copy2(source, backup)
    except OSError as exc:
        raise PdfOperationError(f"创建备份失败，已取消覆盖：{backup}（{exc}）") from exc
    return backup


def _fsync_directory(directory: Path) -> None:
    """Best-effort fsync of the containing directory (POSIX only)."""

    if os.name != "posix":
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def execute_plan(plan: ProcessPlan, *, backup: bool = False) -> ProcessResult:
    """Apply *plan* with a verified, atomic overwrite of the original PDF."""

    path = _normalise_pdf_path(plan.pdf_path)
    doc = _open_document(path)
    if doc.page_count != plan.layout.total_pages:
        doc.close()
        raise PdfOperationError("PDF 在规划后发生了变化，请重新读取页码后再试。")

    existing = _outline_from_doc(doc) if plan.keep_outline else ()
    generated = plan.generated_outline
    final_outline = existing + generated

    temp_name: str | None = None
    backup_path: Path | None = None
    try:
        try:
            doc.set_toc(_outline_as_lists(final_outline), collapse=0)
        except Exception as exc:
            raise PdfOperationError(f"写入 PDF 书签失败：{exc}") from exc

        if plan.write_page_labels:
            try:
                doc.set_page_labels(list(plan.page_labels))
            except Exception as exc:
                raise PdfOperationError(f"写入 PDF 页码标签失败：{exc}") from exc

        try:
            fd, temp_name = tempfile.mkstemp(
                prefix=".pupdf-", suffix=".pdf", dir=str(path.parent)
            )
            os.close(fd)
        except OSError as exc:
            raise PdfOperationError(
                f"无法在 PDF 所在目录创建临时文件：{path.parent}（{exc}）"
            ) from exc

        try:
            doc.save(temp_name, garbage=3, deflate=True)
        except Exception as exc:
            raise PdfOperationError(f"写入临时 PDF 失败：{exc}") from exc
        finally:
            doc.close()

        _verify_temporary_pdf(Path(temp_name), plan.layout, final_outline)

        try:
            mode = stat.S_IMODE(path.stat().st_mode)
            os.chmod(temp_name, mode)
        except OSError:
            pass

        if backup:
            backup_path = _make_backup(path)

        try:
            os.replace(temp_name, path)
        except PermissionError as exc:
            raise PdfOperationError(
                "无法覆盖原 PDF。请先关闭正在打开该文件的 PDF 阅读器，"
                f"并确认文件不是只读的。原文件未被修改。\n{exc}"
            ) from exc
        except OSError as exc:
            raise PdfOperationError(
                f"无法覆盖原 PDF，原文件未被修改。（{exc}）"
            ) from exc

        temp_name = None
        _fsync_directory(path.parent)
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass

    return _result_for_plan(plan, backup_path=backup_path)


def process_pdf(
    pdf_path: str | Path,
    toc_page: int,
    body_page: int,
    *,
    keep_outline: bool = False,
    write_page_labels: bool = True,
    backup: bool = False,
    dry_run: bool = False,
) -> ProcessResult:
    """One-call API: validate, plan, and overwrite the PDF."""

    plan = build_plan(
        pdf_path,
        toc_page,
        body_page,
        keep_outline=keep_outline,
        write_page_labels=write_page_labels,
    )
    if dry_run:
        return _result_for_plan(plan, dry_run=True)
    return execute_plan(plan, backup=backup)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------


def _configure_stdio() -> None:
    """Make redirected output UTF-8 on every platform, especially Windows."""

    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pupdf.py",
        description=(
            "为 PDF 创建逐页书签和页码标签，并直接覆盖原文件。\n"
            "不指定 --pdf 时，自动使用当前目录（或 --dir）中唯一的 PDF。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  uv run pupdf.py\n"
            "  uv run pupdf.py --toc-page 5 --body-page 7\n"
            "  uv run pupdf.py --pdf D:/books/demo.pdf --toc-page 5 --body-page 7\n"
            "  uv run pupdf.py --toc-page 5 --body-page 7 --dry-run\n"
        ),
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--pdf", type=Path, metavar="PATH", help="要处理的 PDF；默认自动查找唯一 PDF"
    )
    source.add_argument(
        "--dir", type=Path, metavar="DIR", help="自动查找 PDF 的目录（默认当前目录）"
    )
    parser.add_argument(
        "--toc-page", type=int, metavar="N", help="目录页所在页码（从 1 开始）"
    )
    parser.add_argument(
        "--body-page",
        type=int,
        metavar="N",
        help="正文第 1 页所在页码（从 1 开始，必须大于目录页）",
    )
    parser.add_argument(
        "--keep-outline",
        action="store_true",
        help="保留 PDF 原有书签，并把新书签追加到末尾（默认替换）",
    )
    parser.add_argument(
        "--no-page-labels",
        action="store_true",
        help="只写书签，不写 PDF 页码标签",
    )
    parser.add_argument("--backup", action="store_true", help="覆盖前创建 .bak 备份")
    parser.add_argument("--dry-run", action="store_true", help="只显示计划，不修改文件")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="发生未预期错误时显示完整 traceback",
    )
    return parser


def _prompt_int(prompt: str, minimum: int, maximum: int) -> int:
    while True:
        try:
            raw = input(prompt)
        except EOFError as exc:
            raise UserInputError(
                "无法读取交互输入。请在命令中同时提供 --toc-page 和 --body-page。"
            ) from exc
        text = raw.strip()
        if not text:
            print("请输入一个页码。")
            continue
        try:
            value = int(text)
        except ValueError:
            print("页码必须是整数。")
            continue
        if not minimum <= value <= maximum:
            print(f"页码必须在 {minimum} 到 {maximum} 之间。")
            continue
        return value


def _read_page_numbers(
    info: PdfInfo, toc_page: int | None, body_page: int | None
) -> tuple[int, int]:
    total = info.total_pages
    if total < 2:
        raise UserInputError("PDF 至少需要 2 页，才能区分目录页和正文第1页。")
    if toc_page is not None and not 1 <= toc_page < total:
        raise UserInputError(
            f"目录页 {toc_page} 无效；它必须在 1 到 {total - 1} 之间，"
            "且正文第1页要排在它后面。"
        )
    if body_page is not None and not 1 <= body_page <= total:
        raise UserInputError(
            f"正文第1页 {body_page} 无效；它必须在 1 到 {total} 之间。"
        )

    if toc_page is None:
        toc_page = _prompt_int(f"目录页所在页码（1-{total - 1}）：", 1, total - 1)
    if body_page is None:
        body_page = _prompt_int(
            f"正文第1页所在页码（{toc_page + 1}-{total}）：",
            toc_page + 1,
            total,
        )
    return toc_page, body_page


def _print_plan(info: PdfInfo, plan: ProcessPlan, *, keep_outline: bool) -> None:
    layout = plan.layout
    print(f"PDF      ：{info.path}")
    print(f"总页数   ：{info.total_pages}")
    print(
        f"目录页   ：第 {layout.toc_page}-{layout.toc_end_page} 页"
        f"（{layout.toc_pages} 页）"
    )
    print(
        f"正文     ：第 {layout.body_page}-{layout.body_end_page} 页"
        f"（{layout.body_pages} 页，书签“1”…“{layout.body_pages}”）"
    )
    print(
        f"新增书签 ：{plan.generated_count} 条"
        f"（1 条“目录” + {layout.body_pages} 条正文页码）"
    )
    if info.has_outline:
        if keep_outline:
            print(f"原有书签 ：保留（{len(plan.existing_outline)} 条，追加在末尾）")
        else:
            print("原有书签 ：将被替换")
    print(
        "页码标签 ：写入（前置 A…/i…；目录 i…；正文 1…）"
        if plan.write_page_labels
        else "页码标签 ：不写入"
    )
    print()


def main(argv: Sequence[str] | None = None) -> int:
    _configure_stdio()
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if args.pdf is not None:
            pdf_path = args.pdf
        else:
            pdf_path = find_single_pdf(args.dir)

        info = analyze_pdf(pdf_path)
        toc_page, body_page = _read_page_numbers(info, args.toc_page, args.body_page)
        plan = build_plan(
            pdf_path,
            toc_page,
            body_page,
            keep_outline=args.keep_outline,
            write_page_labels=not args.no_page_labels,
        )
        _print_plan(info, plan, keep_outline=args.keep_outline)

        result = process_pdf(
            pdf_path,
            toc_page,
            body_page,
            keep_outline=args.keep_outline,
            write_page_labels=not args.no_page_labels,
            backup=args.backup,
            dry_run=args.dry_run,
        )

        if result.dry_run:
            print("预览完成：未修改任何文件。")
        else:
            print(f"完成：已覆盖 {result.pdf_path}")
            print(
                f"写入 {result.generated_bookmarks} 条新书签，"
                f"当前共 {result.total_bookmarks} 条书签。"
            )
            if result.page_labels_written:
                print("已写入页码标签：前置页 A…/i…，目录页 i…，正文页 1…N。")
            if result.backup_path is not None:
                print(f"备份：{result.backup_path}")
        return 0
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except UserInputError as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2
    except PupdfError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(
                f"发生未预期的错误：{exc}\n可使用 --debug 查看完整堆栈。",
                file=sys.stderr,
            )
        return 1


__all__ = [
    "BookmarkItem",
    "DiscoveryError",
    "EncryptedPdfError",
    "PageLayout",
    "PdfInfo",
    "PdfOperationError",
    "ProcessPlan",
    "ProcessResult",
    "PupdfError",
    "UserInputError",
    "analyze_pdf",
    "build_plan",
    "execute_plan",
    "find_pdfs",
    "find_single_pdf",
    "process_pdf",
    "validate_layout",
]


if __name__ == "__main__":
    raise SystemExit(main())
