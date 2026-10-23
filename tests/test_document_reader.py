"""Tests for document reading, validation, magic bytes, and location extraction."""
import pytest
from pathlib import Path
import services.document_reader as document_reader
import config


def test_validate_pdf_magic_bytes(sample_dir):
    pdf_bytes = (sample_dir / "compliant_services_agreement.pdf").read_bytes()
    file_type = document_reader.validate_file_bytes(pdf_bytes, "compliant_services_agreement.pdf")
    assert file_type == "pdf"


def test_validate_docx_package(sample_dir):
    docx_bytes = (sample_dir / "ambiguous_agreement.docx").read_bytes()
    file_type = document_reader.validate_file_bytes(docx_bytes, "ambiguous_agreement.docx")
    assert file_type == "docx"


def test_reject_empty_file():
    with pytest.raises(document_reader.EmptyFileError) as exc:
        document_reader.validate_file_bytes(b"", "empty.pdf")
    assert exc.value.status_code == 400


def test_reject_unsupported_extension():
    with pytest.raises(document_reader.UnsupportedTypeError) as exc:
        document_reader.validate_file_bytes(b"content", "file.xlsx")
    assert exc.value.status_code == 415


def test_reject_fake_pdf(sample_dir):
    fake_bytes = (sample_dir / "fake.pdf").read_bytes()
    with pytest.raises(document_reader.CorruptedFileError) as exc:
        document_reader.validate_file_bytes(fake_bytes, "fake.pdf")
    assert exc.value.status_code == 422


def test_reject_file_too_large():
    huge_bytes = b"%PDF-" + b"0" * (config.MAX_CONTENT_LENGTH + 10)
    with pytest.raises(document_reader.FileTooLargeError) as exc:
        document_reader.validate_file_bytes(huge_bytes, "huge.pdf")
    assert exc.value.status_code == 413


def test_pdf_multipage_extraction(sample_dir):
    path = str(sample_dir / "risky_services_agreement.pdf")
    units, status, page_count, text_len = document_reader.extract_pdf_units(path)
    assert status == "success"
    assert page_count >= 4
    assert text_len > 200
    assert len(units) == page_count
    assert units[0]["location_type"] == "page"
    assert units[0]["page_number"] == 1
    assert units[3]["page_number"] == 4


def test_scanned_pdf_detection(sample_dir):
    path = str(sample_dir / "scanned_like.pdf")
    units, status, page_count, text_len = document_reader.extract_pdf_units(path)
    assert status == "scanned_no_text"
    assert text_len < config.SCANNED_THRESHOLD


def test_password_protected_pdf(sample_dir):
    path = str(sample_dir / "password_protected.pdf")
    with pytest.raises(document_reader.PasswordProtectedError) as exc:
        document_reader.extract_pdf_units(path)
    assert exc.value.status_code == 422


def test_corrupted_pdf(sample_dir):
    path = str(sample_dir / "corrupted.pdf")
    with pytest.raises(document_reader.CorruptedFileError) as exc:
        document_reader.extract_pdf_units(path)
    assert exc.value.status_code == 422


def test_docx_paragraph_extraction(sample_dir):
    path = str(sample_dir / "risky_services_agreement.docx")
    units, status, count, text_len = document_reader.extract_docx_units(path)
    assert status == "success"
    assert count > 0
    assert text_len > 0
    assert units[0]["location_type"] == "paragraph"
    assert units[0]["paragraph_index"] == 1


def test_sanitize_filename():
    unsafe = '\x00<script>alert("xss")</script>.pdf\r\n'
    safe = document_reader.sanitize_filename(unsafe)
    assert "<script>" in safe
    assert "\x00" not in safe
    assert "\r" not in safe
    assert "\n" not in safe


def test_ocr_extension_stub():
    with pytest.raises(NotImplementedError) as exc:
        document_reader.ocr_extension_stub("dummy.pdf")
    assert "OCR is not enabled" in str(exc.value)
