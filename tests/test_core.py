from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf as fitz
import pytest

import pupdf as core
from pupdf import (
    EncryptedPdfError,
    PdfInfo,
    PdfOperationError,
    UserInputError,
    analyze_pdf,
    build_plan,
    execute_plan,
    process_pdf,
    validate_layout,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def toc(doc) -> list[list]:
    return doc.get_toc(simple=True)


def test_analyze_pdf(pdf_factory):
    path = pdf_factory(pages=9, title="Demo", outline=[[1, "Old", 1]])
    info = analyze_pdf(path)
    assert isinstance(info, PdfInfo)
    assert info.path == path.resolve()
    assert info.total_pages == 9
    assert info.title == "Demo"
    assert info.has_outline is True


def test_process_creates_grouped_bookmarks_and_labels(pdf_factory):
    path = pdf_factory(pages=12)

    result = process_pdf(path, 3, 5)

    assert result.total_pages == 12
    assert result.toc_page == 3
    assert result.body_page == 5
    assert result.toc_pages == 2
    assert result.body_pages == 8
    assert result.generated_bookmarks == 12  # 1 toc + 2 toc children + 1 body + 8 pages
    assert result.total_bookmarks == 12
    assert result.page_labels_written is True
    assert result.dry_run is False
    assert result.backup_path is None

    with fitz.open(path) as doc:
        assert doc.page_count == 12
        expected = [[1, "目录", 3]]
        expected += [[2, "目录 1", 3], [2, "目录 2", 4]]
        expected += [[1, "正文", 5]]
        expected += [[2, f"第{i}页", 4 + i] for i in range(1, 9)]
        assert toc(doc) == expected

        labels = doc.get_page_labels()
        assert [item["startpage"] for item in labels] == [2, 4]
        assert labels[0]["style"] == "D"
        # /P must be a standards-compliant UTF-16BE text string with BOM.
        raw = doc.xref_get_key(doc.pdf_catalog(), "PageLabels")[1]
        assert "FEFF76EE5F550020" in raw  # "目录 " in UTF-16BE
        assert doc[4].get_label() == "1"
        assert doc[5].get_label() == "2"
        assert doc[11].get_label() == "8"

    assert not list(path.parent.glob(".pupdf-*"))


def test_single_toc_page_has_no_redundant_child(pdf_factory):
    path = pdf_factory(pages=5)
    process_pdf(path, 2, 3)
    with fitz.open(path) as doc:
        assert toc(doc)[:2] == [[1, "目录", 2], [1, "正文", 3]]
        assert toc(doc)[2:] == [
            [2, "第1页", 3],
            [2, "第2页", 4],
            [2, "第3页", 5],
        ]


def test_existing_outline_is_replaced_by_default(pdf_factory):
    path = pdf_factory(pages=8, outline=[[1, "Preface", 1], [2, "Chapter", 2]])
    process_pdf(path, 3, 4)
    with fitz.open(path) as doc:
        titles = [entry[1] for entry in toc(doc)]
    assert "Preface" not in titles
    assert titles[:2] == ["目录", "正文"]


def test_existing_outline_can_be_kept(pdf_factory):
    path = pdf_factory(pages=8, outline=[[1, "Preface", 1], [2, "Chapter", 2]])
    process_pdf(path, 3, 4, keep_outline=True)
    with fitz.open(path) as doc:
        entries = toc(doc)
    assert entries[:2] == [[1, "Preface", 1], [2, "Chapter", 2]]
    assert entries[2] == [1, "目录", 3]
    assert entries[3] == [1, "正文", 4]


def test_plan_exposes_final_outline_and_labels(pdf_factory):
    path = pdf_factory(pages=8, outline=[[1, "Old", 1]])
    plan = build_plan(path, 3, 4, keep_outline=True)
    assert plan.layout.toc_pages == 1
    assert plan.layout.body_pages == 5
    assert plan.final_outline[0].title == "Old"
    assert plan.generated_count == 7
    assert [rule["startpage"] for rule in plan.page_labels] == [2, 3]


def test_page_labels_can_be_disabled(pdf_factory):
    path = pdf_factory(pages=6)
    process_pdf(path, 2, 3, write_page_labels=False)
    with fitz.open(path) as doc:
        assert doc.get_page_labels() == []
        # No /PageLabels tree at all: viewers fall back to their normal
        # 1-based numbering (PyMuPDF's get_label helper is empty in this case).
        assert doc.xref_get_key(doc.pdf_catalog(), "PageLabels") == ("null", "null")


def test_dry_run_does_not_touch_file(pdf_factory):
    path = pdf_factory(pages=8)
    before = digest(path)
    result = process_pdf(path, 2, 3, dry_run=True)
    assert result.dry_run is True
    assert digest(path) == before
    assert not (path.parent / (path.name + ".bak")).exists()
    assert not list(path.parent.glob(".pupdf-*"))


def test_backup_contains_original_bytes(pdf_factory):
    path = pdf_factory(pages=8)
    original = path.read_bytes()
    result = process_pdf(path, 2, 3, backup=True)
    assert result.backup_path == path.with_name(path.name + ".bak")
    assert result.backup_path.read_bytes() == original
    assert digest(path) != hashlib.sha256(original).hexdigest()


def test_operation_is_idempotent_when_replacing_outline(pdf_factory):
    path = pdf_factory(pages=7)
    process_pdf(path, 2, 4)
    with fitz.open(path) as doc:
        first = toc(doc)
    process_pdf(path, 2, 4)
    with fitz.open(path) as doc:
        second = toc(doc)
    assert first == second


@pytest.mark.parametrize(
    ("toc_page", "body_page", "message"),
    [
        (0, 3, "目录页页码必须从 1 开始"),
        (2, 0, "正文第1页页码必须从 1 开始"),
        (9, 10, "目录页 9 超出"),
        (2, 9, "正文第1页 9 超出"),
        (4, 4, "必须大于目录页"),
        (5, 4, "必须大于目录页"),
    ],
)
def test_invalid_page_layout(pdf_factory, toc_page, body_page, message):
    path = pdf_factory(pages=8)
    with pytest.raises(UserInputError, match=message):
        build_plan(path, toc_page, body_page)


@pytest.mark.parametrize("value", [True, False, 2.5, "3", None])
def test_page_numbers_must_be_plain_integers(pdf_factory, value):
    path = pdf_factory(pages=8)
    with pytest.raises(UserInputError, match="必须是整数"):
        validate_layout(value, 4, 8)
    with pytest.raises(UserInputError, match="必须是整数"):
        build_plan(path, 2, value)


def test_password_protected_pdf_is_rejected(pdf_factory):
    path = pdf_factory(pages=5, user_password="secret")
    with pytest.raises(EncryptedPdfError):
        process_pdf(path, 2, 3)


def test_owner_only_encrypted_pdf_is_rejected(pdf_factory):
    path = pdf_factory(pages=5, owner_only_encryption=True)
    with pytest.raises(EncryptedPdfError):
        analyze_pdf(path)


def test_missing_and_wrong_extension_files(tmp_path):
    with pytest.raises(PdfOperationError, match="不存在"):
        analyze_pdf(tmp_path / "missing.pdf")

    wrong = tmp_path / "document.txt"
    wrong.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(PdfOperationError, match="扩展名"):
        analyze_pdf(wrong)


def test_corrupt_pdf_has_friendly_error(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"this is not a pdf")
    with pytest.raises(PdfOperationError, match="无法打开 PDF"):
        analyze_pdf(path)


def test_failed_replace_keeps_original_and_cleans_temp(pdf_factory, monkeypatch):
    path = pdf_factory(pages=6)
    original = path.read_bytes()

    def refuse_replace(*_args, **_kwargs):
        raise PermissionError("file is locked")

    monkeypatch.setattr(core.os, "replace", refuse_replace)
    with pytest.raises(PdfOperationError, match="无法覆盖原 PDF"):
        process_pdf(path, 2, 3)

    assert path.read_bytes() == original
    assert not list(path.parent.glob(".pupdf-*"))


def test_failed_save_keeps_original_and_cleans_temp(pdf_factory, monkeypatch):
    path = pdf_factory(pages=6)
    original = path.read_bytes()

    def broken_save(*_args, **_kwargs):
        raise RuntimeError("simulated disk error")

    monkeypatch.setattr(fitz.Document, "save", broken_save)
    with pytest.raises(PdfOperationError, match="写入临时 PDF 失败"):
        process_pdf(path, 2, 3)

    assert path.read_bytes() == original
    assert not list(path.parent.glob(".pupdf-*"))


def test_execute_plan_from_prebuilt_plan(pdf_factory):
    path = pdf_factory(pages=9)
    plan = build_plan(path, 4, 6)
    result = execute_plan(plan)
    assert result.body_pages == 4
    with fitz.open(path) as doc:
        assert doc[3].get_label()  # a label exists at the TOC start
        assert doc[5].get_label() == "1"


def test_saving_preserves_page_count_and_metadata(pdf_factory):
    path = pdf_factory(pages=4, title="Keep me")
    process_pdf(path, 2, 3)
    with fitz.open(path) as doc:
        assert doc.page_count == 4
        assert doc.metadata.get("title") == "Keep me"


def test_unwritable_temp_location_has_friendly_error(pdf_factory, monkeypatch):
    path = pdf_factory(pages=5)
    original = path.read_bytes()

    def refuse_mkstemp(*_args, **_kwargs):
        raise PermissionError("read-only folder")

    monkeypatch.setattr(core.tempfile, "mkstemp", refuse_mkstemp)
    with pytest.raises(PdfOperationError, match="无法在 PDF 所在目录创建临时文件"):
        process_pdf(path, 2, 3)

    assert path.read_bytes() == original
