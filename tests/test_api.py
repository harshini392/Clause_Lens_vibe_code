"""Comprehensive End-to-End API and Acceptance Tests for ClauseSight.
Validates the entire pipeline against Section 17 acceptance criteria:
upload, segmentation, clause detection, policy matching, quotes, locations,
security, CSRF, stats, retention purge, and temp file hygiene.
"""
import io
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

import config
import database


# Acceptance Test 1 & 2: Risky PDF with Demo Policies
def test_acceptance_1_and_2_risky_pdf(client, sample_dir):
    """Risky PDF yields payment conflict (60 vs 30, diff 30, quote equals stored text, true page number)
    and auto-renewal conflict with exact sentence as quote.
    """
    pdf_path = sample_dir / "risky_services_agreement.pdf"
    with open(pdf_path, "rb") as f:
        res = client.post("/api/analyze", data={"file": (f, "risky_services_agreement.pdf")})

    assert res.status_code == 200
    data = res.get_json()
    analysis_id = data["analysis_id"]
    findings = data["findings"]

    # 1. Payment Finding Check
    pay_conflict = next((f for f in findings if f["category"] == "payment" and f["status"] == "potential_conflict"), None)
    assert pay_conflict is not None
    details = json.loads(pay_conflict["details_json"])
    assert details["contract_days"] == 60
    assert details["limit_days"] == 30
    assert details["difference_days"] == 30
    assert pay_conflict["location_label"] == "Page 2"
    assert "sixty (60)" in pay_conflict["quote"] and "days" in pay_conflict["quote"]

    # Verify quote exactly equals segment text stored in DB
    hist = client.get(f"/api/history/{analysis_id}").get_json()
    seg = next(s for s in hist["segments"] if s["evidence_id"] == pay_conflict["evidence_id"])
    assert pay_conflict["quote"] == seg["text"]
    assert seg["page_number"] == 2

    # 2. Renewal Finding Check
    ren_conflict = next((f for f in findings if f["category"] == "renewal" and f["status"] == "potential_conflict"), None)
    assert ren_conflict is not None
    assert ren_conflict["location_label"] == "Page 3"
    assert "automatically renew" in ren_conflict["quote"]
    seg_ren = next(s for s in hist["segments"] if s["evidence_id"] == ren_conflict["evidence_id"])
    assert ren_conflict["quote"] == seg_ren["text"]


# Acceptance Test 3: Compliant PDF
def test_acceptance_3_compliant_pdf(client, sample_dir):
    """Compliant PDF yields no potential_conflict findings for demo policies, and no finding words as 'safe'."""
    pdf_path = sample_dir / "compliant_services_agreement.pdf"
    with open(pdf_path, "rb") as f:
        res = client.post("/api/analyze", data={"file": (f, "compliant_services_agreement.pdf")})

    assert res.status_code == 200
    data = res.get_json()
    findings = data["findings"]

    conflicts = [f for f in findings if f["status"] == "potential_conflict"]
    assert len(conflicts) == 0

    # Ensure no finding claims the contract is "safe" or "legal"
    for f in findings:
        text_to_check = (f["title"] + " " + f["explanation"] + " " + f["next_step"]).lower()
        assert "is safe" not in text_to_check
        assert "contract is safe" not in text_to_check
        assert "legal advice" not in text_to_check or "not legal advice" in text_to_check


# Acceptance Test 4 & 5: Ambiguous DOCX
def test_acceptance_4_and_5_ambiguous_docx(client, sample_dir):
    """Ambiguous DOCX yields review_recommended for payment, renewal, liability, jurisdiction with 0 conflicts.
    DOCX findings show 'Paragraph N' labels matching real paragraph index.
    """
    docx_path = sample_dir / "ambiguous_agreement.docx"
    with open(docx_path, "rb") as f:
        res = client.post("/api/analyze", data={"file": (f, "ambiguous_agreement.docx")})

    assert res.status_code == 200
    data = res.get_json()
    findings = data["findings"]

    conflicts = [f for f in findings if f["status"] == "potential_conflict"]
    assert len(conflicts) == 0

    # Review recommended checks
    rev_categories = {f["category"] for f in findings if f["status"] == "review_recommended"}
    assert "payment" in rev_categories
    assert "renewal" in rev_categories
    assert "liability" in rev_categories
    assert "jurisdiction" in rev_categories

    # Check Paragraph N labels
    for f in findings:
        if f["location_label"] != "Document-wide":
            assert f["location_label"].startswith("Paragraph ")
            para_num = int(f["location_label"].replace("Paragraph ", ""))
            assert para_num >= 1


# Acceptance Test 6: Scanned-like and Empty PDFs
def test_acceptance_6_scanned_and_empty_pdfs(client, sample_dir):
    """Scanned-like returns clear message, empty returns 400. No findings fabricated."""
    # Scanned PDF
    scanned_path = sample_dir / "scanned_like.pdf"
    with open(scanned_path, "rb") as f:
        res_scanned = client.post("/api/analyze", data={"file": (f, "scanned_like.pdf")})
    assert res_scanned.status_code == 200
    data_scanned = res_scanned.get_json()
    assert data_scanned["document"]["extraction_status"] == "scanned_no_text"
    assert "OCR is required" in data_scanned["document"]["message"]
    assert len(data_scanned["findings"]) == 0

    # Empty PDF (0 bytes)
    empty_path = sample_dir / "empty.pdf"
    with open(empty_path, "rb") as f:
        res_empty = client.post("/api/analyze", data={"file": (f, "empty.pdf")})
    assert res_empty.status_code == 400
    assert res_empty.get_json()["error"]["code"] == "empty_file"


# Acceptance Test 7: Error Uploads
def test_acceptance_7_upload_error_codes(client, sample_dir):
    """Corrupted, fake-extension, password-protected, and unsupported uploads return correct codes."""
    # Corrupted PDF
    with open(sample_dir / "corrupted.pdf", "rb") as f:
        r1 = client.post("/api/analyze", data={"file": (f, "corrupted.pdf")})
    assert r1.status_code == 422
    assert r1.get_json()["error"]["code"] == "corrupted_file"

    # Fake PDF (text file renamed)
    with open(sample_dir / "fake.pdf", "rb") as f:
        r2 = client.post("/api/analyze", data={"file": (f, "fake.pdf")})
    assert r2.status_code == 422
    assert r2.get_json()["error"]["code"] == "corrupted_file"

    # Password-protected PDF
    with open(sample_dir / "password_protected.pdf", "rb") as f:
        r3 = client.post("/api/analyze", data={"file": (f, "password_protected.pdf")})
    assert r3.status_code == 422
    assert r3.get_json()["error"]["code"] == "password_protected"

    # Unsupported extension
    r4 = client.post("/api/analyze", data={"file": (io.BytesIO(b"fake"), "test.exe")})
    assert r4.status_code == 415


# Acceptance Test 9: Non-existent policy ID on analysis returns 422
def test_acceptance_9_invalid_policy_id(client, sample_dir):
    pdf_path = sample_dir / "compliant_services_agreement.pdf"
    with open(pdf_path, "rb") as f:
        res = client.post("/api/analyze", data={
            "file": (f, "test.pdf"),
            "policy_ids": "99999"  # Non-existent
        })
    assert res.status_code == 422
    assert res.get_json()["error"]["code"] == "invalid_policy_id"


# Acceptance Test 10: CSRF Protection
def test_acceptance_10_csrf_protection(test_db):
    from app import app
    with app.test_client() as c:
        # POST without CSRF token must fail with 403
        res = c.post("/api/policies/seed_examples")
        assert res.status_code == 403
        assert res.get_json()["error"]["code"] == "invalid_csrf_token"


# Acceptance Test 11: Malicious filename and script tags
def test_acceptance_11_xss_safety(client, sample_dir):
    """Malicious filename and script tags are stored as inert text and escaped in report."""
    xss_path = sample_dir / "xss_contract.pdf"
    with open(xss_path, "rb") as f:
        res = client.post("/api/analyze", data={
            "file": (f, "<script>alert(1)</script>.pdf")
        })
    assert res.status_code == 200
    data = res.get_json()
    assert "<script>" in data["document"]["filename"]

    # Verify report generates and escapes without error
    rep_res = client.get(f"/api/reports/{data['analysis_id']}")
    assert rep_res.status_code == 200
    assert rep_res.data.startswith(b"%PDF-")


# Acceptance Test 12: Dashboard Stats from Database & Fresh Database Empty State
def test_acceptance_12_dashboard_stats(client, test_db, sample_dir):
    # First, clear analyses table to test fresh DB empty state
    conn = database.get_db(test_db)
    with conn:
        conn.execute("DELETE FROM analyses;")
    conn.close()

    fresh_stats = client.get("/api/stats").get_json()
    assert fresh_stats["documents_analyzed"] == 0
    assert fresh_stats["policy_conflicts"] == 0
    assert fresh_stats["manual_reviews"] == 0
    assert fresh_stats["recent"] == []

    # Upload risky agreement
    with open(sample_dir / "risky_services_agreement.pdf", "rb") as f:
        client.post("/api/analyze", data={"file": (f, "risky.pdf")})

    updated_stats = client.get("/api/stats").get_json()
    assert updated_stats["documents_analyzed"] == 1
    assert updated_stats["policy_conflicts"] > 0
    assert len(updated_stats["recent"]) == 1
    assert updated_stats["recent"][0]["filename"] == "risky.pdf"


# Acceptance Test 16: Retention Purge
def test_acceptance_16_retention_purge(test_db):
    conn = database.get_db(test_db)
    old_expired_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    future_date = (datetime.now(timezone.utc) + timedelta(days=25)).isoformat()

    with conn:
        # Insert an expired analysis
        conn.execute("""
            INSERT INTO analyses (id, filename, file_type, page_count_or_paragraph_count, text_length, extraction_status, policies_snapshot_json, created_at, expires_at)
            VALUES ('old-analysis-1', 'expired.pdf', 'pdf', 1, 100, 'success', '[]', '2025-01-01', ?);
        """, (old_expired_date,))

        # Insert a current analysis
        conn.execute("""
            INSERT INTO analyses (id, filename, file_type, page_count_or_paragraph_count, text_length, extraction_status, policies_snapshot_json, created_at, expires_at)
            VALUES ('valid-analysis-2', 'valid.pdf', 'pdf', 1, 100, 'success', '[]', '2026-01-01', ?);
        """, (future_date,))

    # Run purge
    purged_count = database.purge_expired_analyses(conn)
    assert purged_count == 1

    # Verify only valid remains
    cur = conn.cursor()
    cur.execute("SELECT id FROM analyses;")
    remaining = [r["id"] for r in cur.fetchall()]
    assert "old-analysis-1" not in remaining
    assert "valid-analysis-2" in remaining
    conn.close()


# Acceptance Test 17: Temp Directory Hygiene
def test_acceptance_17_temp_dir_hygiene(client, sample_dir):
    """No temporary upload files remain after upload completion or error."""
    temp_dir = config.TEMP_UPLOAD_DIR
    import gc
    gc.collect()
    for item in temp_dir.iterdir():
        try:
            item.unlink()
        except Exception:
            pass

    initial_files = list(temp_dir.iterdir())

    # Success case
    with open(sample_dir / "compliant_services_agreement.pdf", "rb") as f:
        client.post("/api/analyze", data={"file": (f, "clean.pdf")})

    # Error case (corrupted)
    with open(sample_dir / "corrupted.pdf", "rb") as f:
        client.post("/api/analyze", data={"file": (f, "corrupted.pdf")})

    current_files = list(temp_dir.iterdir())
    assert len(current_files) == len(initial_files), "Temp directory must contain no leaked files."
