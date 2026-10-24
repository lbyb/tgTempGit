from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pupdf.discovery import (
    app_directory,
    choose_startup_pdf,
    find_pdfs,
    find_single_pdf,
    pdfs_from_launch_args,
)
from pupdf.errors import DiscoveryError


def touch(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.4\n")
    return path


def test_find_pdfs_is_case_insensitive_and_non_recursive(tmp_path):
    upper = touch(tmp_path / "A.PDF")
    lower = touch(tmp_path / "b.pdf")
    touch(tmp_path / "notes.txt")
    nested = tmp_path / "nested"
    nested.mkdir()
    touch(nested / "inside.pdf")

    assert find_pdfs(tmp_path) == [upper, lower]


def test_find_pdfs_ignores_our_temporary_files(tmp_path):
    real = touch(tmp_path / "book.pdf")
    touch(tmp_path / ".pupdf-abc123.pdf")
    touch(tmp_path / "book.pdf.bak")
    assert find_pdfs(tmp_path) == [real]


def test_find_single_pdf_errors(tmp_path):
    with pytest.raises(DiscoveryError, match="没有 PDF"):
        find_single_pdf(tmp_path)

    touch(tmp_path / "a.pdf")
    touch(tmp_path / "b.pdf")
    with pytest.raises(DiscoveryError, match="多个 PDF") as excinfo:
        find_single_pdf(tmp_path)
    assert "a.pdf" in str(excinfo.value)
    assert "b.pdf" in str(excinfo.value)

    with pytest.raises(DiscoveryError, match="不存在"):
        find_single_pdf(tmp_path / "nope")


def test_find_single_pdf_success(tmp_path):
    expected = touch(tmp_path / "只有一本.pdf")
    assert find_single_pdf(tmp_path) == expected


def test_app_directory_uses_cwd_when_running_from_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert app_directory() == tmp_path.resolve()


def test_app_directory_uses_executable_folder_when_frozen(tmp_path, monkeypatch):
    exe = tmp_path / "Pupdf.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert app_directory() == tmp_path.resolve()


def test_pdfs_from_launch_args_accepts_windows_drop_and_flags(tmp_path):
    one = tmp_path / "one.pdf"
    two = tmp_path / "two.pdf"
    assert pdfs_from_launch_args([str(one)]) == [one]
    assert pdfs_from_launch_args(["--pdf", str(one)]) == [one]
    assert pdfs_from_launch_args([f"--pdf={one}"]) == [one]
    assert pdfs_from_launch_args([str(one), str(one)]) == [one]
    assert pdfs_from_launch_args(["--unknown", str(two)]) == [two]


def test_pdfs_from_launch_args_errors_on_missing_value():
    with pytest.raises(DiscoveryError, match="缺少文件路径"):
        pdfs_from_launch_args(["--pdf"])
    with pytest.raises(DiscoveryError, match="缺少文件路径"):
        pdfs_from_launch_args(["--pdf="])


def test_choose_startup_pdf_prefers_dropped_file_outside_base(tmp_path):
    base = tmp_path / "app"
    base.mkdir()
    touch(base / "local.pdf")
    dropped = touch(tmp_path / "elsewhere.pdf")

    selection = choose_startup_pdf([str(dropped)], base)
    assert selection.pdf == dropped
    assert selection.note is None


def test_choose_startup_pdf_discovers_single_pdf_in_base(tmp_path):
    only = touch(tmp_path / "only.pdf")
    selection = choose_startup_pdf([], tmp_path)
    assert selection.pdf == only
    assert selection.note is None


def test_choose_startup_pdf_explains_ambiguous_or_empty_folder(tmp_path):
    selection = choose_startup_pdf([], tmp_path)
    assert selection.pdf is None
    assert "没有 PDF" in selection.note

    touch(tmp_path / "a.pdf")
    touch(tmp_path / "b.pdf")
    selection = choose_startup_pdf([], tmp_path)
    assert selection.pdf is None
    assert "2 个 PDF" in selection.note


def test_choose_startup_pdf_rejects_multiple_dropped_files(tmp_path):
    a = touch(tmp_path / "a.pdf")
    b = touch(tmp_path / "b.pdf")
    selection = choose_startup_pdf([str(a), str(b)], tmp_path)
    assert selection.pdf is None
    assert "一次只能处理一个" in selection.note
