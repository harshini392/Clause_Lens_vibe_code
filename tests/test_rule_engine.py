"""Tests for deterministic rule evaluation, policy snapshotting, and status decision table."""
import json
import pytest
import services.rule_engine as rule_engine


def test_payment_rule_decision_table():
    policy = {
        "id": 1,
        "name": "Payment 30 Days",
        "type": "payment",
        "mode": "structured",
        "params_json": json.dumps({"max_payment_days": 30}),
        "explanation": "Must be 30 days or less",
        "enabled": 1
    }

    # 1. 60 days vs 30 days -> potential_conflict
    clause_60 = {
        "category": "payment",
        "evidence_id": "ev_0001",
        "facts": {"payment_days": 60, "trigger": "invoice date", "late_fee_present": True}
    }
    segments = {"ev_0001": {"text": "Pay within 60 days.", "location_type": "page", "page_number": 2}}

    findings = rule_engine.evaluate_rules([clause_60], [policy], segments, "a-1")
    assert len(findings) == 1
    f = findings[0]
    assert f["status"] == "potential_conflict"
    details = json.loads(f["details_json"])
    assert details["contract_days"] == 60
    assert details["limit_days"] == 30
    assert details["difference_days"] == 30
    assert "exceeds your maximum" in f["explanation"]

    # 2. 30 days vs 30 days -> no_conflict_detected
    clause_30 = {
        "category": "payment",
        "evidence_id": "ev_0002",
        "facts": {"payment_days": 30, "trigger": "receipt of invoice"}
    }
    segments["ev_0002"] = {"text": "Pay within 30 days.", "location_type": "page", "page_number": 1}

    findings_30 = rule_engine.evaluate_rules([clause_30], [policy], segments, "a-2")
    assert len(findings_30) == 1
    assert findings_30[0]["status"] == "no_conflict_detected"

    # 3. Days not extractable -> review_recommended
    clause_vague = {
        "category": "payment",
        "evidence_id": "ev_0003",
        "facts": {"payment_days": None, "trigger": "unspecified"}
    }
    segments["ev_0003"] = {"text": "Payment in reasonable time.", "location_type": "paragraph", "paragraph_index": 5}
    findings_vague = rule_engine.evaluate_rules([clause_vague], [policy], segments, "a-3")
    assert findings_vague[0]["status"] == "review_recommended"

    # 4. No payment clause found -> review_recommended with title "No payment clause detected"
    findings_none = rule_engine.evaluate_rules([], [policy], segments, "a-4")
    assert len(findings_none) == 1
    assert findings_none[0]["status"] == "review_recommended"
    assert "No payment clause detected" in findings_none[0]["title"]
    assert "safe" not in findings_none[0]["explanation"].lower()


def test_renewal_rule_decision_table():
    policy = {
        "id": 2,
        "name": "No Auto-Renewal",
        "type": "renewal",
        "mode": "structured",
        "params_json": json.dumps({"auto_renewal_prohibited": True, "max_notice_days": 30}),
        "explanation": "No auto-renewal allowed",
        "enabled": 1
    }

    # Auto renewal true -> potential_conflict
    clause_auto = {
        "category": "renewal",
        "evidence_id": "ev_0010",
        "facts": {"auto_renews": True, "notice_days": 60}
    }
    segments = {"ev_0010": {"text": "Shall automatically renew for successive terms.", "location_type": "page", "page_number": 3}}

    findings = rule_engine.evaluate_rules([clause_auto], [policy], segments, "a-ren-1")
    assert len(findings) == 1
    assert findings[0]["status"] == "potential_conflict"

    # Auto renewal false -> no_conflict_detected
    clause_no_auto = {
        "category": "renewal",
        "evidence_id": "ev_0011",
        "facts": {"auto_renews": False, "notice_days": None}
    }
    segments["ev_0011"] = {"text": "Shall not automatically renew.", "location_type": "page", "page_number": 2}
    findings_no = rule_engine.evaluate_rules([clause_no_auto], [policy], segments, "a-ren-2")
    assert findings_no[0]["status"] == "no_conflict_detected"


def test_liability_rule_decision_table():
    policy_fees = {
        "id": 3,
        "name": "Fees-Paid Cap",
        "type": "liability",
        "mode": "structured",
        "params_json": json.dumps({"rule": "cap_not_exceed_fees"}),
        "explanation": "Must not exceed fees",
        "enabled": 1
    }

    # Unlimited liability -> potential_conflict
    clause_unlimited = {
        "category": "liability",
        "evidence_id": "ev_0020",
        "facts": {"cap_type": "unlimited"}
    }
    segments = {"ev_0020": {"text": "Liability shall be unlimited.", "location_type": "page", "page_number": 4}}
    findings_unl = rule_engine.evaluate_rules([clause_unlimited], [policy_fees], segments, "a-lia-1")
    assert findings_unl[0]["status"] == "potential_conflict"

    # Fees paid -> no_conflict_detected
    clause_fees = {
        "category": "liability",
        "evidence_id": "ev_0021",
        "facts": {"cap_type": "fees_paid"}
    }
    segments["ev_0021"] = {"text": "Aggregate liability shall not exceed fees paid.", "location_type": "page", "page_number": 4}
    findings_fees = rule_engine.evaluate_rules([clause_fees], [policy_fees], segments, "a-lia-2")
    assert findings_fees[0]["status"] == "no_conflict_detected"

    # None stated -> review_recommended
    clause_none = {
        "category": "liability",
        "evidence_id": "ev_0022",
        "facts": {"cap_type": "none_stated"}
    }
    segments["ev_0022"] = {"text": "Parties are responsible for damages.", "location_type": "page", "page_number": 4}
    findings_none = rule_engine.evaluate_rules([clause_none], [policy_fees], segments, "a-lia-3")
    assert findings_none[0]["status"] == "review_recommended"


def test_jurisdiction_rule_decision_table():
    policy_jur = {
        "id": 4,
        "name": "Approved India Courts",
        "type": "jurisdiction",
        "mode": "structured",
        "params_json": json.dumps({"approved": ["India", "Chennai", "Bengaluru"]}),
        "explanation": "India jurisdiction only",
        "enabled": 1
    }

    # Chennai match -> no_conflict_detected
    clause_chennai = {
        "category": "jurisdiction",
        "evidence_id": "ev_0030",
        "facts": {"named_jurisdictions": ["India", "Chennai"], "ambiguous": False}
    }
    segments = {"ev_0030": {"text": "Governed by Indian law, courts in Chennai.", "location_type": "page", "page_number": 5}}
    findings_ch = rule_engine.evaluate_rules([clause_chennai], [policy_jur], segments, "a-jur-1")
    assert findings_ch[0]["status"] == "no_conflict_detected"

    # New York -> potential_conflict
    clause_ny = {
        "category": "jurisdiction",
        "evidence_id": "ev_0031",
        "facts": {"named_jurisdictions": ["United States", "New York"], "ambiguous": False}
    }
    segments["ev_0031"] = {"text": "Governed by laws of New York.", "location_type": "page", "page_number": 5}
    findings_ny = rule_engine.evaluate_rules([clause_ny], [policy_jur], segments, "a-jur-2")
    assert findings_ny[0]["status"] == "potential_conflict"


def test_disabled_policies_never_evaluated():
    disabled_policy = {
        "id": 99,
        "name": "Disabled Payment Policy",
        "type": "payment",
        "mode": "structured",
        "params_json": json.dumps({"max_payment_days": 10}),
        "explanation": "Test",
        "enabled": 0 # Disabled
    }
    clause_60 = {
        "category": "payment",
        "evidence_id": "ev_0001",
        "facts": {"payment_days": 60}
    }
    segments = {"ev_0001": {"text": "Payment within 60 days."}}
    findings = rule_engine.evaluate_rules([clause_60], [disabled_policy], segments, "a-dis")
    # Must yield 0 findings because the policy is disabled
    assert len(findings) == 0


def test_free_text_mode_policy():
    free_policy = {
        "id": 50,
        "name": "Custom Liability Guideline",
        "type": "liability",
        "mode": "free_text",
        "params_json": json.dumps({}),
        "explanation": "Liability must align with standard vendor commercial insurance levels.",
        "enabled": 1
    }
    clause = {
        "category": "liability",
        "evidence_id": "ev_0040",
        "facts": {"cap_type": "fees_paid"}
    }
    segments = {"ev_0040": {"text": "Liability capped at fees paid."}}
    findings = rule_engine.evaluate_rules([clause], [free_policy], segments, "a-free")
    assert len(findings) == 1
    assert findings[0]["status"] == "review_recommended"
    assert "Needs interpretation" in findings[0]["title"]
    assert findings[0]["manual_review"] == 1
