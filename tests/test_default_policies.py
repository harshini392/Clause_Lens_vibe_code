"""Tests for Domain-Specific Default Policy Profiles feature in ClauseSight."""
import io
import json
import os
import sqlite3
import pytest
from pathlib import Path

import database
from services.default_policy_service import (
    get_supported_domains,
    is_valid_domain_and_doc_type,
    get_default_policies_for_profile,
    matches_jurisdiction_scope,
    merge_policies,
    DEFAULT_POLICY_CATALOG
)


def test_get_supported_domains():
    """Verify all 6 required domains and their expected document types exist."""
    domains = get_supported_domains()
    required_domains = [
        "Government Documents",
        "Government Tenders and Procurement",
        "Employment Documents",
        "Service and Freelancer Agreements",
        "Non-Disclosure Agreements (NDA)",
        "Lease and Rental Agreements"
    ]
    for d in required_domains:
        assert d in domains, f"Missing required domain: {d}"
        assert len(domains[d]) > 0, f"Domain {d} must have document types"

    # Verify specific types
    assert "Government Application Form" in domains["Government Documents"]
    assert "Tender / Request for Proposal" in domains["Government Tenders and Procurement"]
    assert "Employment Offer Letter" in domains["Employment Documents"]
    assert "Service Agreement" in domains["Service and Freelancer Agreements"]
    assert "Mutual NDA" in domains["Non-Disclosure Agreements (NDA)"]
    assert "Residential Rental Agreement" in domains["Lease and Rental Agreements"]


def test_domains_api_endpoint(client):
    """GET /api/domains should return the supported domains and document types."""
    res = client.get("/api/domains")
    assert res.status_code == 200
    data = res.get_json()
    assert "domains" in data
    domains = data["domains"]
    assert "Government Documents" in domains
    assert "Service and Freelancer Agreements" in domains


def test_is_valid_domain_and_doc_type():
    """Test validation of domain and document type pairs."""
    assert is_valid_domain_and_doc_type("Employment Documents", "Employment Offer Letter") is True
    assert is_valid_domain_and_doc_type("Employment Documents", "Residential Rental Agreement") is False
    assert is_valid_domain_and_doc_type("Invalid Domain", "Service Agreement") is False
    assert is_valid_domain_and_doc_type(None, None) is False


def test_jurisdiction_matching():
    """Test jurisdiction scoping logic."""
    # Wildcard jurisdiction matches anything
    assert matches_jurisdiction_scope("*", "India") is True
    assert matches_jurisdiction_scope("*", "United States") is True
    assert matches_jurisdiction_scope("any", "Germany") is True

    # India-specific rules match India and Indian states/cities
    assert matches_jurisdiction_scope("India", "India") is True
    assert matches_jurisdiction_scope("India", "Karnataka, India") is True
    assert matches_jurisdiction_scope("India", "Tamil Nadu") is True

    # India-specific rules should not match foreign jurisdictions
    assert matches_jurisdiction_scope("India", "United States") is False
    assert matches_jurisdiction_scope("India", "United Kingdom") is False


def test_get_default_policies_endpoint(client):
    """GET /api/default-policies returns filtered default policies with source metadata."""
    res = client.get("/api/default-policies?domain=Government%20Tenders%20and%20Procurement&document_type=Tender%20%2F%20Request%20for%20Proposal&jurisdiction=India")
    assert res.status_code == 200
    data = res.get_json()
    assert "policies" in data
    policies = data["policies"]
    assert len(policies) > 0

    # Verify policy structure and metadata fields
    for p in policies:
        assert "policy_key" in p
        assert "name" in p
        assert "requirement_level" in p
        assert p["requirement_level"] in ["mandatory", "recommended"]
        assert "domain" in p
        assert "document_type" in p
        assert p["source"] == "domain_default"
        # Mandatory policies must have verified source names
        if p["requirement_level"] == "mandatory":
            assert p.get("source_name"), f"Mandatory policy {p['policy_key']} must have source_name"


def test_default_policies_endpoint_unknown_rejected(client):
    """GET /api/default-policies for unknown domain returns 422 Unprocessable Entity."""
    res = client.get("/api/default-policies?domain=FakeDomain&document_type=FakeType")
    assert res.status_code == 422
    data = res.get_json()
    assert "Unsupported document domain" in data["error"]["message"]


def test_merge_policies_combines_default_and_user_policies():
    """Test policy merging rules: combines defaults and user enabled policies, preserving categories."""
    user_policies = [
        {
            "id": 1,
            "name": "Payment Within 30 Days",
            "category": "payment",
            "type": "payment",
            "mode": "structured",
            "params": {"max_payment_days": 30},
            "enabled": 1
        },
        {
            "id": 2,
            "name": "Disabled Renewal Policy",
            "category": "renewal",
            "type": "renewal",
            "mode": "structured",
            "params": {"auto_renewal_prohibited": True},
            "enabled": 0  # Disabled!
        }
    ]

    merged = merge_policies(
        domain="Service and Freelancer Agreements",
        document_type="Service Agreement",
        jurisdiction="India",
        issuing_authority=None,
        user_policies=user_policies
    )

    # Must contain domain defaults + 1 enabled user policy (disabled user policy excluded)
    assert len(merged) > 1

    # Check source tag preservation
    sources = {p["source"] for p in merged}
    assert "domain_default" in sources
    assert "user" in sources

    # Both payment default check and user payment check must be preserved in the merged set
    payment_policies = [p for p in merged if p["category"] == "payment"]
    assert len(payment_policies) >= 2
    payment_sources = [p["source"] for p in payment_policies]
    assert "domain_default" in payment_sources
    assert "user" in payment_sources


def test_deselection_of_default_policy():
    """Deselecting a default policy by key removes it from the merged set."""
    merged_full = merge_policies(
        domain="Service and Freelancer Agreements",
        document_type="Service Agreement",
        jurisdiction="India",
        issuing_authority=None,
        user_policies=[]
    )
    assert len(merged_full) > 0
    target_key = merged_full[0]["policy_key"]

    merged_filtered = merge_policies(
        domain="Service and Freelancer Agreements",
        document_type="Service Agreement",
        jurisdiction="India",
        issuing_authority=None,
        user_policies=[],
        deselected_default_keys=[target_key]
    )
    assert len(merged_filtered) == len(merged_full) - 1
    assert all(p["policy_key"] != target_key for p in merged_filtered)


def test_analyze_with_invalid_domain_rejected(client, sample_dir):
    """Uploading a document with unsupported domain or document type returns HTTP 422."""
    pdf_path = sample_dir / "compliant_services_agreement.pdf"
    with open(pdf_path, "rb") as f:
        data = {
            "file": (f, "contract.pdf"),
            "domain": "NonExistentDomain",
            "document_type": "InvalidType"
        }
        res = client.post("/api/analyze", data=data, content_type="multipart/form-data")
        assert res.status_code == 422
        json_data = res.get_json()
        assert "Unsupported document domain" in json_data["error"]["message"]


def test_analyze_with_domain_profile_success(client, sample_dir):
    """Analyze contract with full domain classification, verify snapshot and findings."""
    pdf_path = sample_dir / "compliant_services_agreement.pdf"
    with open(pdf_path, "rb") as f:
        data = {
            "file": (f, "compliant_services_agreement.pdf"),
            "domain": "Service and Freelancer Agreements",
            "document_type": "Service Agreement",
            "jurisdiction": "India",
            "issuing_authority": "Ministry of Electronics"
        }
        res = client.post("/api/analyze", data=data, content_type="multipart/form-data")
        assert res.status_code == 200
        result = res.get_json()
        assert "analysis_id" in result
        analysis_id = result["analysis_id"]

    # Fetch history detail
    res_hist = client.get(f"/api/history/{analysis_id}")
    assert res_hist.status_code == 200
    hist = res_hist.get_json()

    analysis = hist["analysis"]
    assert analysis["domain"] == "Service and Freelancer Agreements"
    assert analysis["document_type"] == "Service Agreement"
    assert analysis["jurisdiction"] == "India"
    assert analysis["issuing_authority"] == "Ministry of Electronics"

    # Verify snapshot integrity
    snapshot = analysis.get("policies_snapshot", [])
    assert len(snapshot) > 0
    # Must have both domain_default and user policies
    default_snaps = [p for p in snapshot if p.get("source") == "domain_default"]
    assert len(default_snaps) > 0
    for p in default_snaps:
        assert p.get("domain") == "Service and Freelancer Agreements"
        assert p.get("requirement_level") in ["mandatory", "recommended"]

    # Verify findings are linked to exact evidence quotations
    findings = hist["findings"]
    for finding in findings:
        if finding["evidence_id"] != "doc_wide":
            assert finding["quote"] is not None
            assert len(finding["quote"]) > 0
            # Confirm segment contains quote
            matching_segs = [s for s in hist["segments"] if s["evidence_id"] == finding["evidence_id"]]
            assert len(matching_segs) > 0, f"Finding evidence {finding['evidence_id']} not found in segments"
            assert finding["quote"] in matching_segs[0]["text"]


def test_deselected_default_key_in_analyze(client, sample_dir):
    """User can deselect a specific default policy during analysis."""
    pdf_path = sample_dir / "compliant_services_agreement.pdf"
    with open(pdf_path, "rb") as f:
        data = {
            "file": (f, "compliant_services_agreement.pdf"),
            "domain": "Service and Freelancer Agreements",
            "document_type": "Service Agreement",
            "deselected_default_keys": "service_subcontracting"
        }
        res = client.post("/api/analyze", data=data, content_type="multipart/form-data")
        assert res.status_code == 200
        analysis_id = res.get_json()["analysis_id"]

    res_hist = client.get(f"/api/history/{analysis_id}")
    snapshot = res_hist.get_json()["analysis"]["policies_snapshot"]
    deselected_keys = [p.get("policy_key") for p in snapshot]
    assert "service_subcontracting" not in deselected_keys


def test_backward_compatibility_with_legacy_records(test_db, client):
    """Ensure older records with NULL domain/doc_type and plain list snapshot are handled cleanly."""
    conn = database.get_db(test_db)
    legacy_id = "00000000-0000-0000-0000-000000000001"
    legacy_snapshot = json.dumps([
        {"id": 1, "name": "Legacy Payment Policy", "category": "payment", "source": "user"}
    ])
    with conn:
        conn.execute(
            """INSERT INTO analyses (
                id, filename, file_type, page_count_or_paragraph_count, text_length,
                extraction_status, policies_snapshot_json, nemotron_used,
                created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                legacy_id, "legacy_contract.pdf", "pdf", 1, 100,
                "complete", legacy_snapshot, 0,
                "2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z"
            )
        )

    # Fetch history list
    res = client.get("/api/history")
    assert res.status_code == 200
    items = res.get_json()
    legacy_item = next((i for i in items if i["id"] == legacy_id), None)
    assert legacy_item is not None
    assert legacy_item["domain"] is None
    assert legacy_item["document_type"] is None

    # Fetch history detail
    res_detail = client.get(f"/api/history/{legacy_id}")
    assert res_detail.status_code == 200
    detail = res_detail.get_json()
    assert detail["analysis"]["id"] == legacy_id
    assert len(detail["analysis"]["policies_snapshot"]) == 1
    assert detail["analysis"]["policies_snapshot"][0]["name"] == "Legacy Payment Policy"


def test_other_document_type_applies_only_domain_level_checks():
    """Verify that 'Other' document types apply only generic domain-level checks."""
    general_checks = get_default_policies_for_profile("Government Documents", "Other Government Document", "India")
    for check in general_checks:
        doc_types = check.get("document_types", [])
        assert "Other Government Document" in doc_types or "*" in doc_types


def test_no_visual_or_ocr_dependencies():
    """Ensure no OCR, image processing, or face detection libraries are imported in the codebase."""
    forbidden = ["pytesseract", "tesseract", "cv2", "face_recognition", "easyocr", "PIL.ImageDraw"]
    for path in Path("services").glob("*.py"):
        content = path.read_text(encoding="utf-8")
        for f in forbidden:
            assert f"import {f}" not in content, f"Forbidden visual library '{f}' found in {path}"
            assert f"from {f}" not in content, f"Forbidden visual library '{f}' found in {path}"
