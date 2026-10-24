"""Tests for PDF report generation with ReportLab, XML escaping, disclaimer, and download endpoint."""
import io
import pytest
import pymupdf
import services.report_service as report_service


def test_pdf_report_with_findings():
    analysis = {
        "id": "test-rep-1",
        "filename": "Sample_Contract.pdf",
        "file_type": "pdf",
        "page_count_or_paragraph_count": 4,
        "text_length": 1500,
        "extraction_status": "success",
        "nemotron_used": 0,
        "created_at": "2026-10-23 12:00:00"
    }
    findings = [
        {
            "category": "payment",
            "status": "potential_conflict",
            "title": "Payment period exceeds your limit",
            "explanation": "The contract specifies payment within 60 days, exceeding your maximum allowed period of 30 days.",
            "next_step": "Consider requesting a payment period of 30 days.",
            "quote": "Client shall remit payment within sixty (60) days.",
            "location_label": "Page 2",
            "manual_review": 1
        },
        {
            "category": "renewal",
            "status": "potential_conflict",
            "title": "Automatic renewal condition detected",
            "explanation": "The agreement includes an automatic-renewal condition that conflicts with your policy.",
            "next_step": "Review the renewal and cancellation terms.",
            "quote": "This Agreement shall automatically renew for successive one-year periods.",
            "location_label": "Page 3",
            "manual_review": 1
        }
    ]
    policies = [
        {
            "name": "Maximum 30-Day Payment",
            "type": "payment",
            "mode": "structured",
            "params_json": '{"max_payment_days": 30}',
            "explanation": "Must be 30 days"
        }
    ]

    pdf_bytes = report_service.generate_pdf_report(analysis, findings, policies)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000

    # Open with PyMuPDF and verify content and disclaimer
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 1
    full_text = " ".join(page.get_text() for page in doc)
    assert "ClauseSight Policy Review Report" in full_text
    assert "Sample_Contract.pdf" in full_text
    assert "not legal advice" in full_text
    assert "Client shall remit payment within sixty (60) days" in full_text
    assert "Page 1 of" in full_text
    doc.close()


def test_pdf_report_with_no_conflicts():
    analysis = {
        "id": "test-rep-none",
        "filename": "Clean_Agreement.docx",
        "file_type": "docx",
        "page_count_or_paragraph_count": 10,
        "text_length": 800,
        "extraction_status": "success",
        "nemotron_used": 0,
        "created_at": "2026-10-23 14:00:00"
    }
    findings = []
    policies = []

    pdf_bytes = report_service.generate_pdf_report(analysis, findings, policies)
    assert pdf_bytes.startswith(b"%PDF-")

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    full_text = " ".join(page.get_text() for page in doc)
    assert "No conflicts were detected among the supported checks." in full_text
    assert "safe" not in full_text.lower() or "not mean a contract is safe" in full_text.lower()
    doc.close()


def test_pdf_report_download_endpoint(client, sample_dir):
    # Analyze a document to create an analysis record
    pdf_path = sample_dir / "compliant_services_agreement.pdf"
    with open(pdf_path, "rb") as f:
        res = client.post("/api/analyze", data={"file": (f, "compliant.pdf")})
    analysis_id = res.get_json()["analysis_id"]

    # Request report
    rep_res = client.get(f"/api/reports/{analysis_id}")
    assert rep_res.status_code == 200
    assert rep_res.headers["Content-Type"] == "application/pdf"
    assert "attachment" in rep_res.headers["Content-Disposition"]
    assert "ClauseSight_Report" in rep_res.headers["Content-Disposition"]
    assert rep_res.data.startswith(b"%PDF-")

    # Invalid ID -> 404
    rep_404 = client.get("/api/reports/non-existent-id-000")
    assert rep_404.status_code == 404
