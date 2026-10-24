"""Tkinter desktop UI used by the Windows executable.

Design notes
------------
* Double-clicking the executable starts this UI and auto-discovers one PDF in
  the executable's folder.
* Dropping a PDF onto the executable starts the same UI with that absolute
  path prefilled; the two page fields are still entered by hand.
* Processing runs in a worker thread so the window stays responsive.  A
  ``synchronous=True`` switch exists only for automated GUI tests.
"""

from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import threading
import tkinter as tk
import tkinter.font as tkfont
import traceback
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import (
    PdfInfo,
    ProcessResult,
    analyze_pdf,
    process_pdf,
    validate_layout,
)
from .discovery import app_directory, choose_startup_pdf
from .errors import PupdfError, UserInputError

WINDOW_TITLE = "Pupdf - PDF 逐页书签工具"
WINDOW_SIZE = "760x520"
MUTED = "#667085"
ERROR = "#b42318"
SUCCESS = "#067647"
TEXT = "#1d2939"


def _log_unexpected_error(exc: BaseException) -> Path:
    """Write a traceback for a windowed build where stderr is invisible."""

    path = Path(tempfile.gettempdir()) / "pupdf-error.log"
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n")
            handle.write(
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            )
    except OSError:
        pass
    return path


def _fatal_message(message: str) -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(0, message, WINDOW_TITLE, 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def _enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class PupdfApp:
    """The main window.  Kept as a class to make GUI headless-testable."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        initial_pdf: Path | None = None,
        base_dir: Path | None = None,
        startup_note: str | None = None,
        synchronous: bool = False,
    ) -> None:
        self.root = root
        self.base_dir = Path(base_dir) if base_dir is not None else app_directory()
        self.synchronous = synchronous
        self.info: PdfInfo | None = None
        self.busy = False

        self.pdf_var = tk.StringVar()
        self.toc_var = tk.StringVar()
        self.body_var = tk.StringVar()
        self.info_var = tk.StringVar(value="尚未选择 PDF")
        self.plan_var = tk.StringVar(value="选择 PDF 后输入两个页码。")
        self.status_var = tk.StringVar(value="就绪")

        self._configure_window()
        self._build_widgets()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if initial_pdf is not None:
            self.root.after(10, lambda: self.load_pdf(initial_pdf))
        elif startup_note:
            self.info_var.set("未自动选择 PDF")
            self.plan_var.set(startup_note)
            self.plan_label.configure(foreground="#b54708")
            self._set_status(startup_note, "warning")
        self.root.after(120, self._focus_toc)

    # ------------------------------------------------------------------ UI
    def _configure_window(self) -> None:
        self.root.title(WINDOW_TITLE)
        self.root.minsize(660, 470)
        self.root.geometry(WINDOW_SIZE)

        family = tkfont.nametofont("TkDefaultFont").actual("family")
        self._family = family
        style = ttk.Style(self.root)
        available = style.theme_names()
        if os.name == "nt" and "vista" in available:
            style.theme_use("vista")
        elif "clam" in available:
            style.theme_use("clam")

        style.configure("Title.TLabel", font=(family, 18, "bold"), foreground=TEXT)
        style.configure("Subtitle.TLabel", foreground=MUTED)
        style.configure("Hint.TLabel", foreground=MUTED)
        style.configure("Error.TLabel", foreground=ERROR)
        style.configure("Success.TLabel", foreground=SUCCESS)
        style.configure("Status.TLabel", foreground=MUTED)
        style.configure("Action.TButton", font=(family, 10, "bold"), padding=(14, 6))
        style.configure("TLabelframe.Label", font=(family, 10, "bold"))

        # Center the window on the screen.
        self.root.update_idletasks()
        width = 760
        height = 520
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 3)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_widgets(self) -> None:
        outer = ttk.Frame(self.root, padding=(22, 18, 22, 14))
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        ttk.Label(outer, text="PDF 逐页书签", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            outer,
            text="给目录页打标签，并从正文第 1 页开始为每一页生成书签，处理后覆盖原 PDF。",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 14))

        file_frame = ttk.LabelFrame(outer, text=" PDF 文件 ", padding=10)
        file_frame.grid(row=2, column=0, sticky="ew")
        file_frame.columnconfigure(0, weight=1)

        self.file_entry = ttk.Entry(
            file_frame, textvariable=self.pdf_var, state="readonly"
        )
        self.file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.choose_button = ttk.Button(
            file_frame, text="选择…", command=self._choose_pdf, width=9
        )
        self.choose_button.grid(row=0, column=1)

        self.info_label = ttk.Label(
            file_frame, textvariable=self.info_var, style="Hint.TLabel"
        )
        self.info_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))

        page_frame = ttk.LabelFrame(outer, text=" 页码（从 1 开始） ", padding=12)
        page_frame.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        page_frame.columnconfigure(0, weight=1)
        page_frame.columnconfigure(1, weight=1)

        ttk.Label(page_frame, text="目录页所在页码").grid(
            row=0, column=0, sticky="w", padx=(0, 16)
        )
        ttk.Label(page_frame, text="正文第 1 页所在页码").grid(
            row=0, column=1, sticky="w"
        )

        self.toc_spin = ttk.Spinbox(
            page_frame,
            from_=1,
            to=999999,
            textvariable=self.toc_var,
            width=12,
            justify="center",
        )
        self.toc_spin.grid(row=1, column=0, sticky="w", padx=(0, 16), pady=(5, 0))
        self.body_spin = ttk.Spinbox(
            page_frame,
            from_=1,
            to=999999,
            textvariable=self.body_var,
            width=12,
            justify="center",
        )
        self.body_spin.grid(row=1, column=1, sticky="w", pady=(5, 0))

        ttk.Label(
            page_frame,
            text="例如：目录在第 5 页，正文第 1 页在第 7 页",
            style="Hint.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(7, 0))

        self.toc_var.trace_add("write", self._refresh_preview)
        self.body_var.trace_add("write", self._refresh_preview)
        self.toc_spin.bind("<Return>", lambda _event: self.body_spin.focus_set())
        self.body_spin.bind("<Return>", lambda _event: self.start_processing())

        self.plan_label = ttk.Label(
            outer,
            textvariable=self.plan_var,
            style="Hint.TLabel",
            wraplength=700,
            justify="left",
        )
        self.plan_label.grid(row=4, column=0, sticky="w", pady=(14, 0))

        action = ttk.Frame(outer)
        action.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        action.columnconfigure(1, weight=1)

        self.action_button = ttk.Button(
            action,
            text="生成书签并覆盖 PDF",
            command=self.start_processing,
            style="Action.TButton",
        )
        self.action_button.grid(row=0, column=0, sticky="w")

        self.progress = ttk.Progressbar(action, mode="indeterminate", length=180)
        self.progress.grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.progress.grid_remove()

        self.status_label = ttk.Label(
            outer, textvariable=self.status_var, style="Status.TLabel", wraplength=700
        )
        self.status_label.grid(row=6, column=0, sticky="w", pady=(14, 0))

        ttk.Label(
            outer,
            text=(
                "提示：也可以把 PDF 文件拖到 Pupdf.exe 上启动。"
                "处理会直接覆盖原文件，请先关闭正在打开该 PDF 的阅读器。"
            ),
            style="Hint.TLabel",
            wraplength=700,
            justify="left",
        ).grid(row=7, column=0, sticky="w", pady=(6, 0))

        outer.rowconfigure(8, weight=1)

    # ------------------------------------------------------------- helpers
    def _set_status(self, text: str, kind: str = "normal") -> None:
        self.status_var.set(text)
        color = {"error": ERROR, "success": SUCCESS, "warning": "#b54708"}.get(
            kind, MUTED
        )
        self.status_label.configure(foreground=color)

    def _focus_toc(self) -> None:
        try:
            self.toc_spin.focus_set()
        except tk.TclError:
            pass

    def _choose_pdf(self) -> None:
        if self.busy:
            return
        current = self.pdf_var.get().strip()
        initial_dir = str(Path(current).parent) if current else str(self.base_dir)
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="选择 PDF 文件",
            initialdir=initial_dir,
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
        )
        if selected:
            self.load_pdf(Path(selected))

    def load_pdf(self, path: Path | str, *, show_error: bool = True) -> bool:
        if self.busy:
            return False
        candidate = Path(path)
        try:
            info = analyze_pdf(candidate)
        except PupdfError as exc:
            self.info = None
            self.pdf_var.set(str(candidate))
            self.info_var.set("无法读取此 PDF")
            self.toc_var.set("")
            self.body_var.set("")
            self.plan_var.set("请选择一个有效的 PDF 文件。")
            self.plan_label.configure(foreground=ERROR)
            self._set_status(str(exc), "error")
            if show_error:
                messagebox.showerror("无法打开 PDF", str(exc), parent=self.root)
            return False

        self.info = info
        self.pdf_var.set(str(info.path))
        details = [f"共 {info.total_pages} 页"]
        if info.title:
            details.append(f"标题：{info.title}")
        details.append("已有书签" if info.has_outline else "当前无书签")
        self.info_var.set(" · ".join(details))

        self.toc_spin.configure(to=info.total_pages)
        self.body_spin.configure(to=info.total_pages)
        self.toc_var.set("")
        self.body_var.set("")
        self.plan_var.set("请输入目录页和正文第 1 页的页码。")
        self.plan_label.configure(foreground=MUTED)
        self._set_status(f"已选择 {info.path.name}，请输入两个页码。")
        self._focus_toc()
        return True

    def _read_page(self, variable: tk.StringVar, label: str) -> int:
        raw = variable.get().strip()
        if not raw:
            raise UserInputError(f"请输入{label}。")
        if not raw.isascii() or not raw.isdigit():
            raise UserInputError(f"{label}必须是整数。")
        return int(raw)

    def _current_layout(self):
        if self.info is None:
            raise UserInputError("请先选择要处理的 PDF。")
        toc = self._read_page(self.toc_var, "目录页所在页码")
        body = self._read_page(self.body_var, "正文第 1 页所在页码")
        return validate_layout(toc, body, self.info.total_pages)

    def _refresh_preview(self, *_args: object) -> None:
        if self.info is None:
            self.plan_var.set("选择 PDF 后输入两个页码。")
            self.plan_label.configure(foreground=MUTED)
            return

        toc_raw = self.toc_var.get().strip()
        body_raw = self.body_var.get().strip()
        if not toc_raw or not body_raw:
            self.plan_var.set("请输入目录页和正文第 1 页的页码。")
            self.plan_label.configure(foreground=MUTED)
            if not self.busy:
                self._set_status("请输入两个页码。")
            return

        try:
            layout = self._current_layout()
        except UserInputError as exc:
            self.plan_var.set(str(exc))
            self.plan_label.configure(foreground=ERROR)
            if not self.busy:
                self._set_status(str(exc), "error")
            return

        bookmark_count = (
            2 + layout.body_pages + (layout.toc_pages if layout.toc_pages > 1 else 0)
        )
        self.plan_var.set(
            f"目录页：第 {layout.toc_page}-{layout.toc_end_page} 页（{layout.toc_pages} 页）"
            f"  ·  正文：第 {layout.body_page}-{layout.body_end_page} 页"
            f"（书签“第1页”…“第{layout.body_pages}页”）\n"
            f"将新增 {bookmark_count} 条书签，并写入页码标签。"
        )
        self.plan_label.configure(foreground=MUTED)
        if not self.busy:
            self._set_status("准备写入：点击下方按钮覆盖原 PDF。")

    # ------------------------------------------------------------ actions
    def start_processing(self) -> None:
        if self.busy:
            return
        try:
            layout = self._current_layout()
        except UserInputError as exc:
            self._set_status(str(exc), "error")
            messagebox.showerror("页码无效", str(exc), parent=self.root)
            return

        assert self.info is not None
        if self.info.has_outline:
            proceed = messagebox.askyesno(
                "替换原有书签？",
                "这个 PDF 已经有书签。继续操作会替换原有书签。\n\n是否继续？",
                parent=self.root,
            )
            if not proceed:
                return

        self._set_busy(True)
        self._set_status("正在写入，请稍候…")
        self.progress.start(12)

        if self.synchronous:
            self._run_worker(self.info.path, layout.toc_page, layout.body_page)
        else:
            thread = threading.Thread(
                target=self._run_worker,
                args=(self.info.path, layout.toc_page, layout.body_page),
                daemon=True,
                name="pupdf-worker",
            )
            thread.start()

    def _run_worker(self, path: Path, toc_page: int, body_page: int) -> None:
        try:
            result = process_pdf(
                path,
                toc_page,
                body_page,
                keep_outline=False,
                write_page_labels=True,
            )
        except BaseException as exc:  # worker must always report to the UI
            self._call_in_ui(self._finish_error, exc)
        else:
            self._call_in_ui(self._finish_success, result)

    def _call_in_ui(self, callback, *args: object) -> None:
        try:
            self.root.after(0, callback, *args)
        except tk.TclError:
            pass

    def _finish_error(self, exc: BaseException) -> None:
        self._set_busy(False)
        if isinstance(exc, PupdfError):
            message = str(exc)
        else:
            log_path = _log_unexpected_error(exc)
            message = f"发生未预期的错误：{exc}\n\n详细信息已写入：{log_path}"
        self._set_status("处理失败，原 PDF 未被修改。", "error")
        messagebox.showerror("处理失败", message, parent=self.root)

    def _finish_success(self, result: ProcessResult) -> None:
        self._set_busy(False)
        try:
            self.info = analyze_pdf(result.pdf_path)
            details = [f"共 {self.info.total_pages} 页"]
            if self.info.title:
                details.append(f"标题：{self.info.title}")
            details.append("书签已写入")
            self.info_var.set(" · ".join(details))
        except PupdfError:
            pass

        self.plan_var.set(
            f"完成：{result.pdf_path.name} 已写入 {result.generated_bookmarks} 条书签"
            + ("，并写入页码标签。" if result.page_labels_written else "。")
        )
        self.plan_label.configure(foreground=SUCCESS)
        self._set_status(f"已覆盖 {result.pdf_path}", "success")
        messagebox.showinfo(
            "完成",
            (
                f"已覆盖：\n{result.pdf_path}\n\n"
                f"目录页：第 {result.toc_page}-{result.body_page - 1} 页"
                f"（{result.toc_pages} 页）\n"
                f"正文页：第 {result.body_page}-{result.total_pages} 页"
                f"（书签第 1-{result.body_pages} 页）\n"
                f"新增书签：{result.generated_bookmarks} 条\n"
                + (
                    "页码标签：已写入"
                    if result.page_labels_written
                    else "页码标签：未写入"
                )
            ),
            parent=self.root,
        )

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.choose_button.configure(state=state)
        self.toc_spin.configure(state=state)
        self.body_spin.configure(state=state)
        self.action_button.configure(
            state=state,
            text="正在处理…" if busy else "生成书签并覆盖 PDF",
        )
        if busy:
            self.progress.grid()
            self.root.configure(cursor="watch")
        else:
            self.progress.stop()
            self.progress.grid_remove()
            self.root.configure(cursor="")

    def _on_close(self) -> None:
        if self.busy:
            messagebox.showinfo(
                "正在处理",
                "PDF 正在写入，请等待处理完成后再关闭窗口。",
                parent=self.root,
            )
            return
        self.root.destroy()


def main(argv: Sequence[str] | None = None, *, base_dir: Path | None = None) -> int:
    _enable_windows_dpi_awareness()
    args = list(sys.argv[1:] if argv is None else argv)
    base_dir = Path(base_dir) if base_dir is not None else app_directory()
    selection = choose_startup_pdf(args, base_dir)
    initial_pdf, startup_note = selection.pdf, selection.note

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        _fatal_message(
            "无法启动图形界面。\n"
            f"{exc}\n\n"
            "Linux 无桌面环境时请使用命令行版本：pupdf --help"
        )
        return 1

    try:
        PupdfApp(
            root,
            initial_pdf=initial_pdf,
            base_dir=base_dir,
            startup_note=startup_note,
        )
        root.mainloop()
    except Exception as exc:  # last-resort error for a windowed build
        log_path = _log_unexpected_error(exc)
        _fatal_message(f"Pupdf 发生未预期的错误：\n{exc}\n\n详细信息：{log_path}")
        try:
            root.destroy()
        except Exception:
            pass
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
