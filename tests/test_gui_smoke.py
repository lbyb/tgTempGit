from __future__ import annotations

import time

import pymupdf as fitz
import pytest

pytest.importorskip("tkinter")


def _make_root():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # no DISPLAY / no window server
        pytest.skip(f"no GUI display available: {exc}")
    root.withdraw()
    return root


def test_gui_processes_selected_pdf(pdf_factory, monkeypatch):
    from pupdf import gui_app

    pdf = pdf_factory(pages=9)
    root = _make_root()
    messages: list[tuple] = []
    monkeypatch.setattr(
        gui_app.messagebox, "showinfo", lambda *a, **k: messages.append(("info", a))
    )
    monkeypatch.setattr(
        gui_app.messagebox, "showerror", lambda *a, **k: messages.append(("error", a))
    )
    monkeypatch.setattr(gui_app.messagebox, "askyesno", lambda *a, **k: True)

    app = gui_app.PupdfApp(
        root,
        initial_pdf=pdf,
        base_dir=pdf.parent,
        synchronous=True,
    )
    root.update()
    time.sleep(0.03)
    root.update()

    assert app.info is not None
    assert app.info.total_pages == 9
    assert app.pdf_var.get() == str(pdf.resolve())

    app.toc_var.set("2")
    app.body_var.set("4")
    app._refresh_preview()
    assert "将新增" in app.plan_var.get()
    assert "正文：第 4-9 页" in app.plan_var.get()

    app.start_processing()
    for _ in range(5):
        root.update()
        time.sleep(0.02)

    assert app.busy is False
    assert messages and messages[-1][0] == "info", messages
    assert "已覆盖" in app.status_var.get()
    assert "完成：" in app.plan_var.get()
    with fitz.open(pdf) as doc:
        outline = doc.get_toc()
        assert outline[0] == [1, "目录", 2]
        assert [1, "正文", 4] in outline
        assert doc[3].get_label() == "1"

    root.destroy()


def test_gui_invalid_page_shows_error_without_writing(pdf_factory, monkeypatch):
    from pupdf import gui_app

    pdf = pdf_factory(pages=5)
    before = pdf.read_bytes()
    root = _make_root()
    errors: list[tuple] = []
    monkeypatch.setattr(
        gui_app.messagebox, "showerror", lambda *a, **k: errors.append(a)
    )
    monkeypatch.setattr(gui_app.messagebox, "showinfo", lambda *a, **k: None)

    app = gui_app.PupdfApp(root, initial_pdf=pdf, base_dir=pdf.parent, synchronous=True)
    root.update()
    time.sleep(0.03)
    root.update()

    app.toc_var.set("4")
    app.body_var.set("4")
    app.start_processing()
    root.update()

    assert errors
    assert "必须大于目录页" in str(errors[-1])
    assert pdf.read_bytes() == before
    assert app.busy is False
    root.destroy()


def test_gui_startup_note_for_empty_folder(tmp_path, monkeypatch):
    from pupdf import gui_app

    root = _make_root()
    app = gui_app.PupdfApp(
        root,
        initial_pdf=None,
        base_dir=tmp_path,
        startup_note="程序目录中没有 PDF",
        synchronous=True,
    )
    root.update()
    assert "没有 PDF" in app.status_var.get()
    assert app.info is None
    root.destroy()
