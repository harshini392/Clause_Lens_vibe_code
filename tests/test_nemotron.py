"""Tests for Nemotron service mock responses, strict schema validation, and fallback mechanisms."""
import json
import pytest
import requests
from unittest.mock import patch, MagicMock

import config
import services.nemotron_service as nemotron_service


def test_nemotron_validator_valid_payload():
    valid_data = {
        "clause_type": "payment",
        "evidence_ids": ["ev_0001"],
        "facts": {
            "payment_days": 45,
            "trigger": "invoice date",
            "late_fee_present": True
        },
        "uncertain": False,
        "uncertainty_reason": None
    }
    is_valid, err, sanitized = nemotron_service.validate_nemotron_output(valid_data, {"ev_0001"})
    assert is_valid is True
    assert err is None
    assert sanitized["facts"]["payment_days"] == 45


def test_nemotron_validator_rejects_quote_fields():
    """Model must NEVER provide quote-like fields; quotes must come strictly from server segments."""
    bad_data = {
        "clause_type": "payment",
        "evidence_ids": ["ev_0001"],
        "facts": {"payment_days": 45},
        "quote": "Payment shall be made within 45 days.",  # Forbidden field!
        "uncertain": False,
        "uncertainty_reason": None
    }
    is_valid, err, sanitized = nemotron_service.validate_nemotron_output(bad_data, {"ev_0001"})
    assert is_valid is False
    assert "forbidden quote-like field" in err


def test_nemotron_validator_rejects_unknown_evidence_id():
    bad_data = {
        "clause_type": "renewal",
        "evidence_ids": ["ev_9999"],  # Unknown ID
        "facts": {"auto_renews": True},
        "uncertain": False,
        "uncertainty_reason": None
    }
    is_valid, err, sanitized = nemotron_service.validate_nemotron_output(bad_data, {"ev_0001", "ev_0002"})
    assert is_valid is False
    assert "Unknown evidence_id" in err


def test_nemotron_validator_rejects_invalid_schema():
    bad_data = {
        "clause_type": "invalid_category",  # Not in allowed set
        "evidence_ids": ["ev_0001"],
        "facts": {},
        "uncertain": "not-a-bool"
    }
    is_valid, err, sanitized = nemotron_service.validate_nemotron_output(bad_data, {"ev_0001"})
    assert is_valid is False


def test_mock_nemotron_success(monkeypatch):
    monkeypatch.setattr(config, "NEMOTRON_ENABLED", True)
    monkeypatch.setattr(config, "NEMOTRON_BASE_URL", "http://mock-nemotron:8000/v1")
    monkeypatch.setattr(config, "NEMOTRON_MODEL", "nvidia/nemotron-4-340b-instruct")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "clauses": [{
                        "clause_type": "renewal",
                        "evidence_ids": ["ev_0001"],
                        "facts": {"auto_renews": True, "notice_days": 60},
                        "uncertain": False,
                        "uncertainty_reason": None
                    }]
                })
            }
        }]
    }

    with patch("requests.post", return_value=mock_resp):
        success, refined, note = nemotron_service.call_nemotron_interpret(
            [{"evidence_id": "ev_0001", "text": "Renewal text"}],
            {}
        )
        assert success is True
        assert len(refined) == 1
        assert refined[0]["facts"]["notice_days"] == 60


def test_mock_nemotron_http_500_fallback(monkeypatch):
    monkeypatch.setattr(config, "NEMOTRON_ENABLED", True)
    monkeypatch.setattr(config, "NEMOTRON_BASE_URL", "http://mock-nemotron:8000/v1")
    monkeypatch.setattr(config, "NEMOTRON_MODEL", "nvidia/nemotron-4-340b-instruct")

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("requests.post", return_value=mock_resp):
        success, refined, note = nemotron_service.call_nemotron_interpret(
            [{"evidence_id": "ev_0001", "text": "Some ambiguous text"}],
            {}
        )
        assert success is False
        assert refined is None
        assert "HTTP error 500" in note


def test_mock_nemotron_timeout_fallback(monkeypatch):
    monkeypatch.setattr(config, "NEMOTRON_ENABLED", True)
    monkeypatch.setattr(config, "NEMOTRON_BASE_URL", "http://mock-nemotron:8000/v1")
    monkeypatch.setattr(config, "NEMOTRON_MODEL", "nvidia/nemotron-4-340b-instruct")

    with patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
        success, refined, note = nemotron_service.call_nemotron_interpret(
            [{"evidence_id": "ev_0001", "text": "Ambiguous clause"}],
            {}
        )
        assert success is False
        assert refined is None
        assert "timed out" in note


def test_mock_nemotron_malformed_json_fallback(monkeypatch):
    monkeypatch.setattr(config, "NEMOTRON_ENABLED", True)
    monkeypatch.setattr(config, "NEMOTRON_BASE_URL", "http://mock-nemotron:8000/v1")
    monkeypatch.setattr(config, "NEMOTRON_MODEL", "nvidia/nemotron-4-340b-instruct")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "This is plain text, not valid JSON {{"}}]
    }

    with patch("requests.post", return_value=mock_resp):
        success, refined, note = nemotron_service.call_nemotron_interpret(
            [{"evidence_id": "ev_0001", "text": "Clause text"}],
            {}
        )
        assert success is False
        assert refined is None
        assert "invalid JSON" in note


def test_mock_nemotron_contradiction_rejected(monkeypatch):
    """If model output contradicts high confidence regex extraction, reject model facts."""
    monkeypatch.setattr(config, "NEMOTRON_ENABLED", True)
    monkeypatch.setattr(config, "NEMOTRON_BASE_URL", "http://mock-nemotron:8000/v1")
    monkeypatch.setattr(config, "NEMOTRON_MODEL", "nvidia/nemotron-4-340b-instruct")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "clauses": [{
                        "clause_type": "payment",
                        "evidence_ids": ["ev_0001"],
                        "facts": {"payment_days": 15},  # Model hallucinates 15
                        "uncertain": False,
                        "uncertainty_reason": None
                    }]
                })
            }
        }]
    }

    high_conf = {"payment": {"payment_days": 60}}  # Regex verified 60

    with patch("requests.post", return_value=mock_resp):
        success, refined, note = nemotron_service.call_nemotron_interpret(
            [{"evidence_id": "ev_0001", "text": "Payment text"}],
            high_conf
        )
        assert success is False
        assert "fact contradiction" in note
