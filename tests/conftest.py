from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pymupdf as fitz


@pytest.fixture
def pdf_factory(tmp_path: Path):
    """Create small, deliberately simple PDFs for tests."""

    counter = 0

    def make(
        *,
        name: str = "sample.pdf",
        pages: int = 12,
        outline: list[list] | None = None,
        title: str | None = None,
        user_password: str | None = None,
        owner_password: str | None = None,
        owner_only_encryption: bool = False,
    ) -> Path:
        nonlocal counter
        counter += 1
        path = tmp_path / name
        if path.exists():
            path = tmp_path / f"{path.stem}-{counter}{path.suffix}"

        doc = fitz.open()
        for index in range(pages):
            page = doc.new_page(width=420, height=600)
            page.insert_text((48, 80), f"TEST PAGE {index + 1}", fontsize=22)
            page.insert_text(
                (48, 115),
                "Table of contents" if index < 2 else "Body text",
                fontsize=12,
            )
        if title:
            doc.set_metadata({"title": title})
        if outline:
            doc.set_toc(outline)

        save_kwargs = {}
        if user_password is not None:
            save_kwargs.update(
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw=owner_password or "owner",
                user_pw=user_password,
            )
        elif owner_only_encryption:
            save_kwargs.update(
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw=owner_password or "owner",
                user_pw="",
            )

        doc.save(path, **save_kwargs)
        doc.close()
        return path

    return make
