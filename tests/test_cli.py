from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "pupdf.py"


def run_cli(args: list[str], *, cwd: Path, stdin: str | None = None):
    env = os.environ.copy()
    # CI also runs on an English Windows runner (cp1252).  Force UTF-8 so the
    # Chinese CLI messages can be captured reliably on every platform.
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        check=False,
        input=stdin,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
        timeout=120,
    )


def test_version_and_help(tmp_path):
    version = run_cli(["--version"], cwd=tmp_path)
    assert version.returncode == 0
    assert "pupdf.py 0.3.0" in version.stdout

    help_result = run_cli(["--help"], cwd=tmp_path)
    assert help_result.returncode == 0
    assert "--toc-page" in help_result.stdout
    assert "--body-page" in help_result.stdout


def test_noninteractive_process_with_explicit_pdf(pdf_factory, tmp_path):
    pdf = pdf_factory(pages=10)
    result = run_cli(
        [
            "--pdf",
            str(pdf),
            "--toc-page",
            "3",
            "--body-page",
            "5",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "完成：已覆盖" in result.stdout
    assert "写入 7 条新书签" in result.stdout
    assert "页码标签" in result.stdout

    with fitz.open(pdf) as doc:
        assert doc.page_count == 10
        assert doc[4].get_label() == "1"
        assert [entry[1] for entry in doc.get_toc()] == [
            "目录",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
        ]


def test_discovers_single_pdf_in_working_directory(pdf_factory, tmp_path):
    pdf = pdf_factory(pages=7, name="唯一.pdf")
    result = run_cli(["--toc-page", "2", "--body-page", "4"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert str(pdf) in result.stdout
    with fitz.open(pdf) as doc:
        assert doc.get_toc()[0][1] == "目录"


def test_interactive_prompts_and_dry_run(pdf_factory, tmp_path):
    pdf = pdf_factory(pages=8)
    before = pdf.read_bytes()
    result = run_cli(
        ["--pdf", str(pdf), "--dry-run"],
        cwd=tmp_path,
        stdin="2\n4\n",
    )
    assert result.returncode == 0, result.stderr
    assert "预览完成" in result.stdout
    assert "目录页   ：第 2-3 页" in result.stdout
    assert pdf.read_bytes() == before


def test_multiple_pdfs_in_directory_is_refused(pdf_factory, tmp_path):
    pdf_factory(name="a.pdf")
    pdf_factory(name="b.pdf")
    result = run_cli(["--toc-page", "2", "--body-page", "3"], cwd=tmp_path)
    assert result.returncode == 1
    assert "多个 PDF" in result.stderr
    assert "--pdf" in result.stderr


def test_invalid_pages_return_usage_exit_code(pdf_factory, tmp_path):
    pdf = pdf_factory(pages=8)
    result = run_cli(
        ["--pdf", str(pdf), "--toc-page", "5", "--body-page", "5"],
        cwd=tmp_path,
    )
    assert result.returncode == 2
    assert "输入错误" in result.stderr
    assert "必须大于目录页" in result.stderr


def test_keep_outline_and_no_page_labels_flags(pdf_factory, tmp_path):
    pdf = pdf_factory(pages=8, outline=[[1, "Old", 1]])
    result = run_cli(
        [
            "--pdf",
            str(pdf),
            "--toc-page",
            "2",
            "--body-page",
            "4",
            "--keep-outline",
            "--no-page-labels",
            "--backup",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "原有书签 ：保留" in result.stdout
    assert "页码标签 ：不写入" in result.stdout
    assert (pdf.parent / (pdf.name + ".bak")).exists()
    with fitz.open(pdf) as doc:
        assert doc.get_toc()[0][1] == "Old"
        assert doc.get_page_labels() == []


def test_missing_pdf_file(pdf_factory, tmp_path):
    result = run_cli(
        ["--pdf", "missing.pdf", "--toc-page", "2", "--body-page", "3"],
        cwd=tmp_path,
    )
    assert result.returncode == 1
    assert "不存在" in result.stderr


def test_impossible_toc_page_fails_fast_instead_of_prompting(pdf_factory, tmp_path):
    pdf = pdf_factory(pages=8)
    result = run_cli(
        ["--pdf", str(pdf), "--toc-page", "8"],
        cwd=tmp_path,
        stdin="4\n",
    )
    assert result.returncode == 2
    assert "目录页 8 无效" in result.stderr
    assert "正文第1页" not in result.stdout


def test_single_page_pdf_has_clear_error(pdf_factory, tmp_path):
    pdf = pdf_factory(pages=1)
    result = run_cli(
        ["--pdf", str(pdf), "--toc-page", "1", "--body-page", "2"],
        cwd=tmp_path,
    )
    assert result.returncode == 2
    assert "至少需要 2 页" in result.stderr


def test_dir_option_finds_pdf(pdf_factory, tmp_path):
    books = tmp_path / "books"
    books.mkdir()
    pdf = pdf_factory(pages=6, name="in-dir.pdf")
    moved = books / pdf.name
    pdf.replace(moved)
    result = run_cli(
        ["--dir", str(books), "--toc-page", "2", "--body-page", "3"],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert str(moved) in result.stdout
    with fitz.open(moved) as doc:
        assert doc.get_toc()[0][1] == "目录"
