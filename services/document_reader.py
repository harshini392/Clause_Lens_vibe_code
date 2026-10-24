"""Document Reader Service for ClauseSight.
Handles upload validation, magic byte verification, and text extraction
for PDF (via PyMuPDF) and DOCX (via python-docx) with location tracking.
"""
import io
import os
import re
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pymupdf
import docx
import config


class DocumentReaderError(Exception):
    """Base exception for document extraction errors."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class UnsupportedTypeError(DocumentReaderError):
    def __init__(self, message: str = "Unsupported file type. Only PDF and DOCX are allowed."):
        super().__init__("unsupported_file_type", message, 415)


class FileTooLargeError(DocumentReaderError):
    def __init__(self, message: str = "File exceeds the maximum allowed upload size."):
        super().__init__("file_too_large", message, 413)


class EmptyFileError(DocumentReaderError):
    def __init__(self, message: str = "Uploaded file is empty."):
        super().__init__("empty_file", message, 400)


class CorruptedFileError(DocumentReaderError):
    def __init__(self, message: str = "The document file is corrupted and cannot be read."):
        super().__init__("corrupted_file", message, 422)


class PasswordProtectedError(DocumentReaderError):
    def __init__(self, message: str = "The document is password-protected and cannot be analyzed."):
        super().__init__("password_protected", message, 422)


def ocr_extension_stub(file_path: str) -> str:
    """OCR Extension Point.
    ClauseSight does not perform Optical Character Recognition in this version.
    To enable OCR in future versions, hook an OCR pipeline (such as Tesseract,
    EasyOCR, or a secure local vision model) into this function.
    """
    raise NotImplementedError("OCR is not enabled in this version.")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for display: strip control characters and limit length (Section 14)."""
    if not filename:
        return "unnamed_document"
    # Strip null bytes and non-printable control chars
    cleaned = "".join(ch for ch in filename if ch.isprintable() and ch not in ("\x00", "\r", "\n"))
    # Normalize excessive whitespace
    cleaned = " ".join(cleaned.split())
    # Limit display length
    if len(cleaned) > 120:
        cleaned = cleaned[:116] + "..."
    return cleaned or "unnamed_document"


def validate_file_bytes(file_bytes: bytes, filename: str) -> str:
    """Validate file extension, size, and magic bytes. Returns detected file_type ('pdf' or 'docx')."""
    if not file_bytes or len(file_bytes) == 0:
        raise EmptyFileError()

    if len(file_bytes) > config.MAX_CONTENT_LENGTH:
        raise FileTooLargeError(f"File size exceeds maximum allowed limit of {config.MAX_UPLOAD_MB}MB.")

    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        # Check PDF magic bytes '%PDF'
        if not file_bytes.startswith(b"%PDF"):
            raise CorruptedFileError("File has .pdf extension but lacks valid PDF magic bytes.")
        return "pdf"
    elif lower_name.endswith(".docx"):
        # Check ZIP magic bytes PK\x03\x04
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise CorruptedFileError("File has .docx extension but is not a valid ZIP package.")
        # Check for word/document.xml inside ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                namelist = zf.namelist()
                if "word/document.xml" not in namelist:
                    raise CorruptedFileError("DOCX archive is missing required word/document.xml package component.")
        except zipfile.BadZipFile:
            raise CorruptedFileError("DOCX file is corrupted or not a valid archive package.")
        return "docx"
    else:
        raise UnsupportedTypeError()


def extract_pdf_units(file_path: str) -> Tuple[List[Dict[str, Any]], str, int, int]:
    """Extract page-by-page text from PDF.
    Returns: (raw_units, extraction_status, page_count, total_text_length)
    """
    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise CorruptedFileError(f"Failed to open PDF: {str(e)}")

    try:
        if doc.is_encrypted or doc.needs_pass:
            raise PasswordProtectedError("The PDF document is password-protected and cannot be analyzed.")

        page_count = len(doc)
        raw_units: List[Dict[str, Any]] = []
        total_text_length = 0
        non_empty_pages = 0

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = doc[page_idx]
            page_text = page.get_text("text") or ""
            stripped = page_text.strip()
            total_text_length += len(stripped)
            if len(stripped) > 0:
                non_empty_pages += 1

            raw_units.append({
                "location_type": "page",
                "page_number": page_num,
                "paragraph_index": None,
                "text": page_text
            })

        # Check for scanned PDF
        is_scanned = (
            total_text_length < config.SCANNED_THRESHOLD or
            (page_count > 1 and non_empty_pages <= (page_count / 3) and total_text_length < 200)
        )

        extraction_status = "scanned_no_text" if is_scanned else "success"
        return raw_units, extraction_status, page_count, total_text_length
    finally:
        doc.close()
        del doc


def extract_docx_units(file_path: str) -> Tuple[List[Dict[str, Any]], str, int, int]:
    """Extract paragraph-by-paragraph text from DOCX in document order, including table cell paragraphs.
    Returns: (raw_units, extraction_status, paragraph_count, total_text_length)
    """
    try:
        with open(file_path, "rb") as f:
            docx_data = io.BytesIO(f.read())
        doc = docx.Document(docx_data)
    except Exception as e:
        raise CorruptedFileError(f"Failed to parse DOCX document: {str(e)}")

    raw_units: List[Dict[str, Any]] = []
    paragraph_idx = 1
    total_text_length = 0

    # Extract body paragraphs and table paragraphs in document order
    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
        if tag == "p":
            para = docx.text.paragraph.Paragraph(element, doc)
            text = para.text or ""
            stripped = text.strip()
            total_text_length += len(stripped)
            raw_units.append({
                "location_type": "paragraph",
                "page_number": None,
                "paragraph_index": paragraph_idx,
                "text": text
            })
            paragraph_idx += 1
        elif tag == "tbl":
            table = docx.table.Table(element, doc)
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        text = para.text or ""
                        stripped = text.strip()
                        total_text_length += len(stripped)
                        raw_units.append({
                            "location_type": "paragraph",
                            "page_number": None,
                            "paragraph_index": paragraph_idx,
                            "text": text,
                            "is_table": True
                        })
                        paragraph_idx += 1

    count = paragraph_idx - 1
    extraction_status = "empty" if total_text_length == 0 else "success"
    return raw_units, extraction_status, count, total_text_length
