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


def test_process_creates_flat_bookmarks_and_normalized_labels(pdf_factory):
    path = pdf_factory(pages=12)

    result = process_pdf(path, 3, 5)

    assert result.total_pages == 12
    assert result.toc_page == 3
    assert result.body_page == 5
    assert result.toc_pages == 2
    assert result.body_pages == 8
    assert result.generated_bookmarks == 9  # one 目录 + 8 body pages
    assert result.total_bookmarks == 9
    assert result.page_labels_written is True
    assert result.dry_run is False
    assert result.backup_path is None

    with fitz.open(path) as doc:
        assert doc.page_count == 12
        expected = [[1, "目录", 3]]
        expected += [[1, str(i), 4 + i] for i in range(1, 9)]
        assert toc(doc) == expected

        labels = doc.get_page_labels()
        # A, B for front matter; i, ii for the TOC; 1..8 for the body.
        assert [item["startpage"] for item in labels] == list(range(12))
        assert [item["prefix"] for item in labels] == [
            "A",
            "B",
            "i",
            "ii",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
        ]
        assert all(item.get("style", "") == "" for item in labels)
        assert doc[0].get_label() == "A"
        assert doc[2].get_label() == "i"
        assert doc[4].get_label() == "1"
        assert doc[11].get_label() == "8"

    assert not list(path.parent.glob(".pupdf-*"))


def test_single_toc_page_has_one_toc_bookmark(pdf_factory):
    path = pdf_factory(pages=5)
    process_pdf(path, 2, 3)
    with fitz.open(path) as doc:
        assert toc(doc) == [
            [1, "目录", 2],
            [1, "1", 3],
            [1, "2", 4],
            [1, "3", 5],
        ]
        assert [label["prefix"] for label in doc.get_page_labels()] == [
            "A",
            "i",
            "1",
            "2",
            "3",
        ]


def test_existing_outline_is_replaced_by_default(pdf_factory):
    path = pdf_factory(pages=8, outline=[[1, "Preface", 1], [2, "Chapter", 2]])
    process_pdf(path, 3, 4)
    with fitz.open(path) as doc:
        titles = [entry[1] for entry in toc(doc)]
    assert "Preface" not in titles
    assert titles == ["目录", "1", "2", "3", "4", "5"]


def test_existing_outline_can_be_kept(pdf_factory):
    path = pdf_factory(pages=8, outline=[[1, "Preface", 1], [2, "Chapter", 2]])
    process_pdf(path, 3, 4, keep_outline=True)
    with fitz.open(path) as doc:
        entries = toc(doc)
    assert entries[:2] == [[1, "Preface", 1], [2, "Chapter", 2]]
    assert entries[2] == [1, "目录", 3]
    assert entries[3] == [1, "1", 4]
    assert entries[-1] == [1, "5", 8]


def test_plan_exposes_final_outline_and_labels(pdf_factory):
    path = pdf_factory(pages=8, outline=[[1, "Old", 1]])
    plan = build_plan(path, 3, 4, keep_outline=True)
    assert plan.layout.toc_pages == 1
    assert plan.layout.body_pages == 5
    assert plan.final_outline[0].title == "Old"
    assert plan.generated_count == 6  # 目录 + 5 body pages
    assert [rule["startpage"] for rule in plan.page_labels] == list(range(8))
    assert [rule["prefix"] for rule in plan.page_labels] == [
        "A",
        "B",
        "i",
        "1",
        "2",
        "3",
        "4",
        "5",
    ]


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
        first_labels = doc.get_page_labels()
    process_pdf(path, 2, 4)
    with fitz.open(path) as doc:
        second = toc(doc)
        second_labels = doc.get_page_labels()
    assert first == second
    assert first_labels == second_labels


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
        assert doc[3].get_label() == "i"
        assert doc[4].get_label() == "ii"
        assert doc[5].get_label() == "1"
        assert [entry[1] for entry in toc(doc)] == [
            "目录",
            "1",
            "2",
            "3",
            "4",
        ]


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


def test_front_matter_labels_are_normalized_by_existing_style(pdf_factory):
    path = pdf_factory(
        pages=12,
        page_labels=[
            {"startpage": 0, "prefix": "cov", "style": "", "firstpagenum": 1},
            {"startpage": 1, "prefix": "A", "style": "", "firstpagenum": 1},
            {"startpage": 2, "prefix": "", "style": "r", "firstpagenum": 1},
            {"startpage": 3, "prefix": "ii", "style": "", "firstpagenum": 1},
            {"startpage": 4, "prefix": "", "style": "r", "firstpagenum": 1},
            {"startpage": 6, "prefix": "001", "style": "", "firstpagenum": 1},
        ],
    )

    process_pdf(path, 5, 7)

    with fitz.open(path) as doc:
        assert [label["prefix"] for label in doc.get_page_labels()] == [
            "A",
            "B",
            "i",
            "ii",
            "i",
            "ii",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
        ]
        assert toc(doc) == [
            [1, "目录", 5],
            [1, "1", 7],
            [1, "2", 8],
            [1, "3", 9],
            [1, "4", 10],
            [1, "5", 11],
            [1, "6", 12],
        ]


def test_requested_bookmark_and_label_contract(pdf_factory):
    """The four explicit requirements: jump targets, names and prefixes."""

    path = pdf_factory(pages=12)
    process_pdf(path, 3, 7)

    with fitz.open(path) as doc:
        outline = toc(doc)

        # 1. Exactly one 目录 bookmark, pointing at the given TOC page.
        assert outline[0] == [1, "目录", 3]
        assert [entry[1] for entry in outline].count("目录") == 1

        # 2. Body bookmarks are 1..N, unique, no padding, no extra text.
        body_titles = [entry[1] for entry in outline[1:]]
        assert body_titles == [str(number) for number in range(1, 7)]
        assert len(body_titles) == len(set(body_titles))
        assert [entry[2] for entry in outline[1:]] == list(range(7, 13))

        labels = doc.get_page_labels()
        # 3. Every TOC page prefix is i, ii, iii, iv...
        assert [label["prefix"] for label in labels[2:6]] == [
            "i",
            "ii",
            "iii",
            "iv",
        ]
        # 4. Body prefixes are identical to the body bookmark titles.
        assert [label["prefix"] for label in labels[6:]] == body_titles


def test_letters_and_roman_helpers():
    assert core._to_letters(0) == "A"
    assert core._to_letters(25) == "Z"
    assert core._to_letters(26) == "AA"
    assert core._to_letters(27) == "AB"
    assert core._to_roman(1) == "i"
    assert core._to_roman(4) == "iv"
    assert core._to_roman(9) == "ix"
    assert core._to_roman(14) == "xiv"


@pytest.mark.parametrize(
    ("prefix", "style", "expected"),
    [
        ("A", "", "letter"),
        ("cov", "", "letter"),
        ("i", "", "roman"),
        ("iv", "", "roman"),
        ("II", "", "roman"),
        ("I", "", "roman"),
        ("!", "", "roman"),
        ("封面", "", "letter"),
        ("", "r", "roman"),
        ("", "A", "letter"),
    ],
)
def test_classify_front_label(prefix, style, expected):
    assert core._classify_front_label(prefix, style) == expected
