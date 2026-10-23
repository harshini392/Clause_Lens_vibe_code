"""Tests for policy CRUD endpoints, parameter validation, and immutability of historical analyses."""
import json
import pytest


def test_list_and_seed_policies(client):
    res = client.get("/api/policies")
    assert res.status_code == 200
    policies = res.get_json()
    assert len(policies) >= 4  # Canonical demo policies seeded


def test_create_valid_policy(client):
    payload = {
        "name": "Custom 15 Day Payment",
        "type": "payment",
        "mode": "structured",
        "params": {"max_payment_days": 15},
        "explanation": "Strict vendor payment window.",
        "enabled": 1
    }
    res = client.post("/api/policies", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["name"] == payload["name"]
    assert data["params"]["max_payment_days"] == 15


def test_reject_invalid_policy_parameters(client):
    # 1. Negative payment days
    res1 = client.post("/api/policies", json={
        "name": "Invalid Payment",
        "type": "payment",
        "mode": "structured",
        "params": {"max_payment_days": -10}
    })
    assert res1.status_code == 422
    assert "between 1 and 3650" in res1.get_json()["error"]["message"]

    # 2. String instead of int
    res2 = client.post("/api/policies", json={
        "name": "Invalid Payment 2",
        "type": "payment",
        "mode": "structured",
        "params": {"max_payment_days": "thirty"}
    })
    assert res2.status_code == 422

    # 3. Invalid liability rule
    res3 = client.post("/api/policies", json={
        "name": "Invalid Liability",
        "type": "liability",
        "mode": "structured",
        "params": {"rule": "non_existent_rule"}
    })
    assert res3.status_code == 422

    # 4. Empty approved list for jurisdiction
    res4 = client.post("/api/policies", json={
        "name": "Invalid Jurisdiction",
        "type": "jurisdiction",
        "mode": "structured",
        "params": {"approved": []}
    })
    assert res4.status_code == 422


def test_update_and_delete_policy(client):
    # Create policy
    create_res = client.post("/api/policies", json={
        "name": "Policy to Edit",
        "type": "payment",
        "mode": "structured",
        "params": {"max_payment_days": 45}
    })
    pol_id = create_res.get_json()["id"]

    # Update
    update_res = client.put(f"/api/policies/{pol_id}", json={
        "name": "Updated Policy",
        "type": "payment",
        "mode": "structured",
        "params": {"max_payment_days": 20},
        "enabled": 0
    })
    assert update_res.status_code == 200
    assert update_res.get_json()["name"] == "Updated Policy"
    assert update_res.get_json()["enabled"] == 0

    # Delete
    del_res = client.delete(f"/api/policies/{pol_id}")
    assert del_res.status_code == 200

    # 404 on re-delete
    del_again = client.delete(f"/api/policies/{pol_id}")
    assert del_again.status_code == 404


def test_policy_snapshot_immutability(client, sample_dir):
    """Editing a policy after an analysis does NOT alter past analysis findings or reports."""
    # 1. Run analysis on risky PDF with default demo policies
    pdf_path = sample_dir / "risky_services_agreement.pdf"
    with open(pdf_path, "rb") as f:
        analyze_res = client.post("/api/analyze", data={"file": (f, "risky.pdf")})
    assert analyze_res.status_code == 200
    analysis_id = analyze_res.get_json()["analysis_id"]

    # Check original payment finding limit was 30
    hist_before = client.get(f"/api/history/{analysis_id}").get_json()
    pay_conflict_before = next(f for f in hist_before["findings"] if f["category"] == "payment" and f["status"] == "potential_conflict")
    assert "30 days" in pay_conflict_before["explanation"]
    assert "60 days" in pay_conflict_before["explanation"]

    # 2. Modify policy #1 to 90 days
    update_res = client.put("/api/policies/1", json={
        "name": "Relaxed 90 Days",
        "type": "payment",
        "mode": "structured",
        "params": {"max_payment_days": 90},
        "enabled": 1
    })
    assert update_res.status_code == 200

    # 3. Re-read past analysis: findings and snapshot MUST remain completely unchanged!
    hist_after = client.get(f"/api/history/{analysis_id}").get_json()
    pay_conflict_after = next(f for f in hist_after["findings"] if f["category"] == "payment" and f["status"] == "potential_conflict")
    assert "30 days" in pay_conflict_after["explanation"]
    assert "60 days" in pay_conflict_after["explanation"]
    assert pay_conflict_after["status"] == "potential_conflict"
