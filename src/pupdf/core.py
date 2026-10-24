"""PDF bookmark and page-label engine.

Public entry points
-------------------
``analyze_pdf(path)``
    Read basic information without modifying anything.
``build_plan(path, toc_page, body_page, ...)``
    Validate page numbers and produce an immutable description of the work.
``process_pdf(path, toc_page, body_page, ...)``
    Build a plan and apply it in place (atomic replacement).
``execute_plan(plan, backup=False)``
    Apply a previously built plan, useful for preview/confirm workflows.

All page numbers accepted by this module are 1-based, exactly as shown in a
PDF viewer.  The resulting PDF gets:

* a grouped outline: ``目录`` -> ``目录 1 .. 目录 k`` and
  ``正文`` -> ``第1页 .. 第N页``;
* page labels: TOC pages are ``目录 1 .. 目录 k`` and body pages are
  ``1 .. N``.

The original file is never edited in place.  A hidden temporary file is
written next to it, reopened for verification, and only then atomically
replaces the original.  If anything fails, the original is untouched.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .errors import EncryptedPdfError, PdfOperationError, UserInputError

try:  # PyMuPDF >= 1.24 prefers the "pymupdf" import name.
    import pymupdf as fitz  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised only on older installs
    try:
        import fitz  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - dependency problem
        fitz = None  # type: ignore[assignment]


TOC_TITLE = "目录"
BODY_TITLE = "正文"
TOC_PREFIX = "目录 "


def _require_fitz():
    if fitz is None:
        raise PdfOperationError(
            "缺少 PDF 处理库 PyMuPDF。请先安装依赖：\n"
            "  python -m pip install -r requirements.txt"
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
    except Exception as exc:  # MuPDF raises several low-level exception types
        raise PdfOperationError(
            f"无法打开 PDF：{path}\n可能文件已损坏或不是有效的 PDF。（{exc}）"
        ) from exc

    if doc.needs_pass:
        doc.close()
        raise EncryptedPdfError(f"PDF 受密码保护，暂不支持处理：{path}")
    # MuPDF reports owner-password-only PDFs (empty user password) with
    # ``is_encrypted == False`` but still exposes an encryption description in
    # metadata.  Re-saving those would silently strip the original encryption
    # and permission settings, so reject them as well.
    metadata = doc.metadata or {}
    if getattr(doc, "is_encrypted", False) or metadata.get("encryption"):
        doc.close()
        raise EncryptedPdfError(f"PDF 已加密或带有权限密码，暂不支持处理：{path}")
    if doc.page_count < 1:
        doc.close()
        raise PdfOperationError(f"PDF 没有页面：{path}")
    return doc


@dataclass(frozen=True)
class PdfInfo:
    """Read-only information shown in the CLI summary and GUI."""

    path: Path
    total_pages: int
    title: str | None
    has_outline: bool


def analyze_pdf(pdf_path: str | Path) -> PdfInfo:
    """Open a PDF, validate that it can be processed, and read its metadata."""

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
    """Convenience wrapper used by the GUI before starting a worker."""

    return PageLayout(toc_page=toc_page, body_page=body_page, total_pages=total_pages)


@dataclass(frozen=True)
class BookmarkItem:
    """One PDF outline entry.  ``page`` is 1-based."""

    level: int
    title: str
    page: int

    def as_list(self) -> list:
        return [self.level, self.title, self.page]


def _pdf_text_string_escape(text: str) -> str:
    """Return a PDF literal-string body containing UTF-16BE with a BOM.

    ``Document.set_page_labels`` inserts its ``prefix`` argument unescaped
    into a PDF literal string.  PyMuPDF passes a plain Python string through
    as UTF-8 bytes, which is not a valid PDF *text string* for Chinese and is
    displayed incorrectly by many readers.  Octal escapes let us place a
    standards-compliant UTF-16BE string inside the same literal string.
    """

    payload = b"\xfe\xff" + text.encode("utf-16-be")
    return "".join(f"\\{byte:03o}" for byte in payload)


@dataclass(frozen=True)
class ProcessPlan:
    """Immutable description of a planned bookmark operation."""

    pdf_path: Path
    layout: PageLayout
    existing_outline: tuple[BookmarkItem, ...] = field(default_factory=tuple)
    keep_outline: bool = False
    write_page_labels: bool = True

    @property
    def generated_outline(self) -> tuple[BookmarkItem, ...]:
        """The outline entries created by this tool (excluding old ones)."""

        layout = self.layout
        items: list[BookmarkItem] = [
            BookmarkItem(1, TOC_TITLE, layout.toc_page),
        ]
        if layout.toc_pages > 1:
            for offset in range(layout.toc_pages):
                items.append(
                    BookmarkItem(
                        2, f"{TOC_TITLE} {offset + 1}", layout.toc_page + offset
                    )
                )

        items.append(BookmarkItem(1, BODY_TITLE, layout.body_page))
        for offset in range(layout.body_pages):
            items.append(
                BookmarkItem(2, f"第{offset + 1}页", layout.body_page + offset)
            )
        return tuple(items)

    @property
    def final_outline(self) -> tuple[BookmarkItem, ...]:
        if self.keep_outline:
            return self.existing_outline + self.generated_outline
        return self.generated_outline

    @property
    def page_labels(self) -> tuple[dict, ...]:
        """Page-label rules for ``Document.set_page_labels``."""

        return (
            {
                "startpage": self.layout.toc_page - 1,
                "prefix": _pdf_text_string_escape(TOC_PREFIX),
                "style": "D",
                "firstpagenum": 1,
            },
            {
                "startpage": self.layout.body_page - 1,
                "prefix": "",
                "style": "D",
                "firstpagenum": 1,
            },
        )

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
        # External-URL outline entries have no page destination.  A simple
        # set_toc() list cannot represent them, so preserving them is not
        # possible (the README documents this limitation).
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
        return ProcessPlan(
            pdf_path=path,
            layout=layout,
            existing_outline=existing,
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
        # A light structural check is enough to catch a failed outline write.
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
    """Apply *plan* to the PDF using a verified, atomic replacement."""

    path = _normalise_pdf_path(plan.pdf_path)
    doc = _open_document(path)
    if doc.page_count != plan.layout.total_pages:
        doc.close()
        raise PdfOperationError("PDF 在规划后发生了变化，请重新读取页码后再试。")

    # Re-read the old outline at execution time so a race with another editor
    # cannot silently drop entries when --keep-outline is requested.
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
                prefix=".pupdf-",
                suffix=".pdf",
                dir=str(path.parent),
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
            source_mode = stat.S_IMODE(path.stat().st_mode)
            os.chmod(temp_name, source_mode)
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

        temp_name = None  # successfully moved; do not delete it
        _fsync_directory(path.parent)
    finally:
        # Covers failures during set_toc/save/verification/replace.  The
        # original was never touched, and no hidden temporary file is left.
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
    """One-call API: validate, build a plan, and overwrite the PDF."""

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


__all__ = [
    "BookmarkItem",
    "PageLayout",
    "PdfInfo",
    "ProcessPlan",
    "ProcessResult",
    "analyze_pdf",
    "build_plan",
    "execute_plan",
    "process_pdf",
    "validate_layout",
]
