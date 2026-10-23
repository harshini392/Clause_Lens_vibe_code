"""Tests for clause detector pattern matching, number parsing, and fact extraction."""
import pytest
import services.clause_detector as clause_detector


def test_parse_duration_in_days_patterns():
    # 30 days
    days, note = clause_detector.parse_duration_in_days("Payment shall be made within 30 days of receipt.")
    assert days == 30

    # thirty (30) days
    days, note = clause_detector.parse_duration_in_days("Invoices are payable within thirty (30) days.")
    assert days == 30

    # net 45
    days, note = clause_detector.parse_duration_in_days("Terms: Net 45 from delivery.")
    assert days == 45
    assert "Net" in (note or "")

    # within sixty days
    days, note = clause_detector.parse_duration_in_days("Client shall pay within sixty days of invoice.")
    assert days == 60
    assert "sixty" in (note or "")

    # 2 months (converted to 60 days)
    days, note = clause_detector.parse_duration_in_days("Notice must be given at least 2 months prior.")
    assert days == 60
    assert "30-day month convention" in (note or "")

    # 12 months (converted to 360 days)
    days, note = clause_detector.parse_duration_in_days("Renewal term of 12 months.")
    assert days == 360

    # one year (converted to 365 days)
    days, note = clause_detector.parse_duration_in_days("Initial term of one year.")
    assert days == 365


def test_detect_payment_clause_facts():
    # Explicit 60 days, invoice date, late fee
    text = "Client shall remit payment within sixty (60) days of invoice date. Overdue amounts accrue 1.5% late fee per month."
    cl = clause_detector.detect_payment_clause(text)
    assert cl is not None
    assert cl["category"] == "payment"
    assert cl["facts"]["payment_days"] == 60
    assert cl["facts"]["trigger"] == "invoice date"
    assert cl["facts"]["late_fee_present"] is True
    assert cl["confidence"] == "high"

    # 30 days receipt of invoice
    text2 = "All payments are due within 30 days following receipt of invoice."
    cl2 = clause_detector.detect_payment_clause(text2)
    assert cl2["facts"]["payment_days"] == 30
    assert cl2["facts"]["trigger"] == "receipt of invoice"
    assert cl2["facts"]["late_fee_present"] is False

    # Ambiguous / vague payment
    text_vague = "Remuneration shall be payable within a reasonable time after milestone approval."
    cl_vague = clause_detector.detect_payment_clause(text_vague)
    assert cl_vague is not None
    assert cl_vague["facts"]["payment_days"] is None


def test_detect_renewal_clause_facts():
    # Auto renews 1-year with 60-day notice
    text = "This Agreement shall automatically renew for successive one-year periods unless either party provides at least sixty (60) days advance notice."
    cl = clause_detector.detect_renewal_clause(text)
    assert cl is not None
    assert cl["facts"]["auto_renews"] is True
    assert cl["facts"]["notice_days"] == 60
    assert cl["confidence"] == "high"

    # Explicit no auto-renewal
    text_no = "This agreement shall not automatically renew and shall expire upon conclusion of the initial term."
    cl_no = clause_detector.detect_renewal_clause(text_no)
    assert cl_no["facts"]["auto_renews"] is False

    # Ambiguous renewal
    text_amb = "The term may be extended upon mutual collaboration as appropriate."
    cl_amb = clause_detector.detect_renewal_clause(text_amb)
    assert cl_amb["facts"]["auto_renews"] == "unknown"


def test_detect_liability_clause_facts():
    # Unlimited liability
    text_unlimited = "Company's liability shall be unlimited and not subject to any monetary cap under this agreement."
    cl_unlimited = clause_detector.detect_liability_clause(text_unlimited)
    assert cl_unlimited["facts"]["cap_type"] == "unlimited"

    # Fees paid cap
    text_fees = "Neither party's aggregate liability shall exceed the total fees paid under this agreement in the preceding 12 months."
    cl_fees = clause_detector.detect_liability_clause(text_fees)
    assert cl_fees["facts"]["cap_type"] == "fees_paid"
    assert cl_fees["facts"]["mutual"] is True

    # Fixed amount cap
    text_fixed = "Liability shall not exceed $1,000,000 for any single occurrence."
    cl_fixed = clause_detector.detect_liability_clause(text_fixed)
    assert cl_fixed["facts"]["cap_type"] == "fixed_amount"
    assert "$1,000,000" in cl_fixed["facts"]["amount"]

    # None stated
    text_none = "Each party shall be responsible for damages caused by willful misconduct."
    cl_none = clause_detector.detect_liability_clause(text_none)
    assert cl_none["facts"]["cap_type"] == "none_stated"


def test_detect_jurisdiction_clause_facts():
    # India / Chennai
    text_india = "This agreement is governed by the laws of India, and courts in Chennai shall have exclusive jurisdiction."
    cl_india = clause_detector.detect_jurisdiction_clause(text_india)
    assert cl_india is not None
    assert "India" in cl_india["facts"]["named_jurisdictions"]
    assert cl_india["facts"]["ambiguous"] is False

    # New York
    text_ny = "Governed by the laws of the State of New York, and subject to exclusive venue in the courts of New York."
    cl_ny = clause_detector.detect_jurisdiction_clause(text_ny)
    assert "United States" in cl_ny["facts"]["named_jurisdictions"] or "New York" in str(cl_ny["facts"]["named_jurisdictions"])

    # Ambiguous jurisdiction
    text_amb = "Disputes shall be submitted to a competent court having jurisdiction over commercial matters."
    cl_amb = clause_detector.detect_jurisdiction_clause(text_amb)
    assert cl_amb["facts"]["ambiguous"] is True or len(cl_amb["facts"]["named_jurisdictions"]) == 0


def test_detect_indemnification_and_termination():
    text_indem = "Contractor shall indemnify, defend, and hold harmless Client against any third-party claims."
    cl_indem = clause_detector.detect_indemnification_clause(text_indem)
    assert cl_indem is not None
    assert cl_indem["facts"]["present"] is True
    assert cl_indem["facts"]["one_sided"] is True

    text_term = "Client may terminate this Agreement at any time for convenience upon 30 days written notice."
    cl_term = clause_detector.detect_termination_clause(text_term)
    assert cl_term is not None
    assert cl_term["facts"]["for_convenience"] is True
    assert cl_term["facts"]["notice_days"] == 30
    assert cl_term["facts"]["one_sided"] is True
