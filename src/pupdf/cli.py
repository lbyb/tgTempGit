"""Command-line interface, primarily intended for Linux.

Running ``pupdf`` with no options discovers the only PDF in the current
directory and asks for the two page numbers.  Passing ``--toc-page`` and
``--body-page`` makes it fully non-interactive, which is useful in scripts.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .core import (
    PdfInfo,
    ProcessPlan,
    analyze_pdf,
    build_plan,
    process_pdf,
)
from .discovery import find_single_pdf
from .errors import PupdfError, UserInputError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pupdf",
        description=(
            "为 PDF 创建逐页书签和页码标签，并直接覆盖原文件。\n"
            "不指定 --pdf 时，自动使用当前目录（或 --dir 指定目录）中唯一的 PDF。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  pupdf                          # 交互输入两个页码\n"
            "  pupdf --toc-page 5 --body-page 7\n"
            "  pupdf --pdf /path/book.pdf --toc-page 5 --body-page 7\n"
            "  pupdf --toc-page 5 --body-page 7 --dry-run\n"
            "  pupdf --gui                    # 启动图形界面（需要 Tk）\n"
        ),
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--pdf",
        type=Path,
        metavar="PATH",
        help="要处理的 PDF；不指定则自动查找唯一 PDF",
    )
    source.add_argument(
        "--dir",
        type=Path,
        metavar="DIR",
        help="自动查找 PDF 的目录（默认：当前目录）",
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
        help="保留 PDF 原有书签，并把新书签追加到末尾（默认替换原书签）",
    )
    parser.add_argument(
        "--no-page-labels",
        action="store_true",
        help="只写书签，不写 PDF 页码标签",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="覆盖前在 PDF 旁边创建 .bak 备份",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示将要执行的操作，不修改文件",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="启动图形界面（Windows 可执行程序默认使用图形界面）",
    )
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
    info: PdfInfo,
    toc_page: int | None,
    body_page: int | None,
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
        toc_page = _prompt_int(
            f"目录页所在页码（1-{total - 1}）：",
            1,
            total - 1,
        )
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
        f"（{layout.body_pages} 页，书签“第1页”…“第{layout.body_pages}页”）"
    )
    print(f"新增书签 ：{plan.generated_count} 条")
    if info.has_outline:
        if keep_outline:
            print(f"原有书签 ：保留（{len(plan.existing_outline)} 条，追加在末尾）")
        else:
            print("原有书签 ：将被替换")
    print(
        "页码标签 ：写入（目录 1…；正文 1…）"
        if plan.write_page_labels
        else "页码标签 ：不写入"
    )
    print()


def _run_gui(pdf: Path | None, directory: Path | None = None) -> int:
    try:
        from .gui import main as gui_main
    except ImportError as exc:
        print(
            "无法启动图形界面：当前 Python 缺少 Tkinter。\n"
            "Linux 请安装 python3-tk；Windows 官方 Python 安装包默认包含 Tkinter。\n"
            f"（{exc}）",
            file=sys.stderr,
        )
        return 1
    argv = ["--pdf", str(pdf)] if pdf is not None else []
    return gui_main(argv, base_dir=directory)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.gui:
        if args.toc_page is not None or args.body_page is not None:
            parser.error(
                "--gui 模式下请在图形界面中输入页码，不要同时使用 --toc-page/--body-page。"
            )
        return _run_gui(args.pdf, args.dir)

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
                print("已写入页码标签：目录页显示“目录 1…”；正文页显示 1…N。")
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
    except Exception as exc:  # last-resort safety net for a friendly CLI
        if args.debug:
            traceback.print_exc()
        else:
            print(
                f"发生未预期的错误：{exc}\n可使用 --debug 查看完整堆栈。",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
