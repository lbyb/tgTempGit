from __future__ import annotations

from pathlib import Path

import pytest

from pupdf import DiscoveryError, find_pdfs, find_single_pdf


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


def test_find_single_pdf_defaults_to_current_directory(tmp_path, monkeypatch):
    expected = touch(tmp_path / "当前目录.pdf")
    monkeypatch.chdir(tmp_path)
    assert find_single_pdf() == expected
