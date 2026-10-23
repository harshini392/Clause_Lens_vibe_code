"""Clause Detection Service for ClauseLens.
Detects contract clauses across payment, renewal, liability, indemnification,
jurisdiction, and termination using regex and keyword patterns with confidence scoring.
"""
import re
from typing import List, Dict, Any, Optional, Tuple

# Word-to-number mapping for common contract timeframes
WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "twenty": 20, "twenty-five": 25, "twenty five": 25,
    "thirty": 30, "thirty-five": 35, "thirty five": 35,
    "forty": 40, "forty-five": 45, "forty five": 45,
    "fifty": 50, "sixty": 60, "sixty-five": 65, "sixty five": 65,
    "seventy": 70, "seventy-five": 75, "seventy five": 75,
    "eighty": 80, "eighty-five": 85, "eighty five": 85,
    "ninety": 90, "one hundred": 100, "one hundred twenty": 120,
    "one hundred and twenty": 120, "one hundred eighty": 180,
    "one hundred and eighty": 180
}


def parse_duration_in_days(text: str) -> Tuple[Optional[int], Optional[str]]:
    """Parse duration in days from text snippet.
    Handles: '30 days', 'thirty (30) days', 'net 45', 'within sixty days',
    '2 months' (converts to days using 30-day month convention), '12 months', 'one year'.
    Returns: (days: Optional[int], note: Optional[str])
    """
    clean = text.lower()

    # Pattern: Net 30, Net 45, Net 60
    net_match = re.search(r"\bnet\s+(\d+)\b", clean)
    if net_match:
        return int(net_match.group(1)), "Derived from Net term"

    # Pattern: thirty (30) days / 30 (thirty) days
    paren_match = re.search(r"(\w+)\s*\(\s*(\d+)\s*\)\s*(?:calendar\s+|business\s+)?days", clean)
    if paren_match:
        return int(paren_match.group(2)), None

    paren_rev = re.search(r"(\d+)\s*\(\s*(\w+)\s*\)\s*(?:calendar\s+|business\s+)?days", clean)
    if paren_rev:
        return int(paren_rev.group(1)), None

    # Pattern: \d+ days
    digits_days = re.search(r"\b(\d+)\s*(?:calendar\s+|business\s+)?days\b", clean)
    if digits_days:
        return int(digits_days.group(1)), None

    # Pattern: word days, e.g. "within thirty days", "sixty days"
    for word, val in WORD_NUMBERS.items():
        if re.search(rf"\b{re.escape(word)}\s*(?:calendar\s+|business\s+)?days\b", clean):
            return val, f"Converted from written words '{word}'"

    # Pattern: Months (converted to 30-day months)
    digit_months = re.search(r"\b(\d+)\s*months?\b", clean)
    if digit_months:
        months = int(digit_months.group(1))
        return months * 30, f"Converted from {months} month(s) based on 30-day month convention"

    for word, val in WORD_NUMBERS.items():
        if re.search(rf"\b{re.escape(word)}\s*months?\b", clean):
            return val * 30, f"Converted from written '{word}' month(s) based on 30-day month convention"

    # Pattern: Years (converted to 365 days)
    digit_years = re.search(r"\b(\d+)\s*years?\b", clean)
    if digit_years:
        years = int(digit_years.group(1))
        return years * 365, f"Converted from {years} year(s) based on 365-day year convention"

    if re.search(r"\b(one|a)\s+year\b", clean):
        return 365, "Converted from 1 year based on 365-day year convention"
    if re.search(r"\btwo\s+years\b", clean):
        return 730, "Converted from 2 years based on 365-day year convention"

    return None, None


# Known jurisdictions and aliases
JURISDICTION_ALIASES = [
    ("India", ["india", "indian", "republic of india", "chennai", "bengaluru", "bangalore", "delhi", "new delhi", "mumbai", "bombay", "madras", "karnataka", "tamil nadu"]),
    ("England and Wales", ["england and wales", "english law", "england", "wales", "london", "united kingdom", "uk"]),
    ("United States", ["united states", "usa", "delaware", "new york", "california", "texas"]),
    ("Singapore", ["singapore", "singapore law"]),
    ("European Union", ["european union", "eu", "france", "germany"])
]


def detect_payment_clause(text: str) -> Optional[Dict[str, Any]]:
    """Detect payment clause and extract payment terms, trigger, and late fee cues."""
    lower = text.lower()
    
    # Must contain payment indicators
    payment_cues = ["payment", "invoice", "invoicing", "payable", "fee", "fees", "remittance", "net 30", "net 45", "net 60"]
    if not any(cue in lower for cue in payment_cues):
        return None

    # Check for context relevance (avoid false positives like 'payment of damages' in liability)
    if not re.search(r"\b(invoice|pay|payable|payment|due|net\s+\d+|remit)\b", lower):
        return None

    days, note = parse_duration_in_days(text)

    # Check multiple day figures in same text (e.g. "payment within 30 days or within 60 days")
    day_matches = re.findall(r"\b(\d+)\s*(?:calendar\s+|business\s+)?days\b", lower)
    conflicting_days = len(set(day_matches)) > 1 if day_matches else False

    # Trigger extraction
    trigger = "unspecified"
    if re.search(r"(receipt\s+of\s+(?:the\s+)?invoice|receiving\s+(?:the\s+)?invoice)", lower):
        trigger = "receipt of invoice"
    elif re.search(r"(invoice\s+date|date\s+of\s+(?:the\s+)?invoice)", lower):
        trigger = "invoice date"
    elif re.search(r"(delivery|completion|acceptance)", lower):
        trigger = "delivery"

    # Late fee / interest check
    late_fee = bool(re.search(r"\b(late\s+(?:fee|charge|penalty)|interest\s+at|interest\s+of|\d+(?:\.\d+)?%\s*(?:per\s+(?:month|annum|year)|interest))\b", lower))

    # Confidence calculation
    if days is not None and not conflicting_days:
        confidence = "high"
    elif days is not None or "net " in lower or "due within" in lower:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "category": "payment",
        "facts": {
            "payment_days": days,
            "trigger": trigger,
            "late_fee_present": late_fee,
            "conflicting_days": conflicting_days,
            "conversion_note": note
        },
        "confidence": confidence
    }


def detect_renewal_clause(text: str) -> Optional[Dict[str, Any]]:
    """Detect renewal clause and extract auto-renewal, renewal period, and notice period."""
    lower = text.lower()
    if not re.search(r"\b(renew|renewal|renewals|extend|extended|extension|extensions|auto-renew|automatically\s+renew|subsequent\s+term|successive\s+term)\b", lower):
        return None

    # Auto renew determination: evaluate negative expressions first
    auto_renews = "unknown"
    if re.search(r"\b(shall\s+not\s+(?:automatically\s+)?renew|will\s+not\s+renew|no\s+automatic\s+renewal|not\s+(?:automatically\s+)?renew|only\s+upon\s+mutual\s+written)\b", lower):
        auto_renews = False
    elif re.search(r"\b(automatic(?:ally)?\s+renew(?:s|ed)?|shall\s+(?:automatically\s+)?renew|renew\s+automatically|successive\s+(?:annual|one-year|one\s+year|monthly)\s+periods\s+unless)\b", lower):
        auto_renews = True

    # Notice period
    notice_days, note = parse_duration_in_days(text)

    # Renewal term
    renewal_period = None
    period_match = re.search(r"\b(successive|additional|subsequent)\s+(?:period\s+of\s+)?(\d+\s+(?:years?|months?)|one\s+year|two\s+years|twelve\s+months)\b", lower)
    if period_match:
        renewal_period = period_match.group(2)
    elif "one-year" in lower or "one year" in lower or "1 year" in lower:
        renewal_period = "1 year"
    elif "month-to-month" in lower or "monthly" in lower:
        renewal_period = "monthly"

    confidence = "high" if auto_renews is True and notice_days is not None else ("medium" if auto_renews != "unknown" or notice_days is not None else "low")

    return {
        "category": "renewal",
        "facts": {
            "auto_renews": auto_renews,
            "renewal_period": renewal_period,
            "notice_days": notice_days,
            "conversion_note": note
        },
        "confidence": confidence
    }


def detect_liability_clause(text: str) -> Optional[Dict[str, Any]]:
    """Detect limitation of liability clause, capping type, amount, and mutuality."""
    lower = text.lower()
    if not re.search(r"\b(liability|limitation\s+of\s+liability|aggregate\s+liability|maximum\s+liability|damages|consequential\s+damages)\b", lower):
        return None

    # Check capping type
    cap_type = "none_stated"
    amount = None

    if re.search(r"\b(total\s+fees\s+paid|fees\s+paid\s+(?:or\s+payable\s+)?(?:in|during|under)|amount\s+paid\s+under\s+this\s+agreement)\b", lower):
        cap_type = "fees_paid"
        amount = "fees paid"
    elif re.search(r"\b(unlimited\s+liability|liability\s+shall\s+be\s+unlimited|without\s+(?:any\s+)?limitation|not\s+subject\s+to\s+any\s+(?:monetary\s+)?cap|no\s+limitation\s+of\s+liability)\b", lower):
        cap_type = "unlimited"
    elif re.search(r"\b(capped\s+at|shall\s+not\s+exceed|maximum\s+of)\s+([\$€£₹]|usd|inr|eur|gbp)?\s*[\d,]+(?:\.\d+)?\b", lower):
        cap_type = "fixed_amount"
        amt_match = re.search(r"([\$€£₹]|usd|inr|eur|gbp)?\s*[\d,]+(?:\.\d+)?", lower)
        if amt_match:
            amount = amt_match.group(0).strip()
    elif "reasonable" in lower or "at law" in lower or "as permitted by applicable law" in lower:
        cap_type = "other"

    # Mutual check
    mutual = "unknown"
    if re.search(r"\b(neither\s+party|either\s+party|both\s+parties|each\s+party)\b", lower):
        mutual = True
    elif re.search(r"\b(vendor\'?s\s+liability|client\'?s\s+liability|contractor\'?s\s+liability|company\'?s\s+liability)\b", lower):
        mutual = False

    confidence = "high" if cap_type in ("fees_paid", "unlimited", "fixed_amount") else "medium"

    return {
        "category": "liability",
        "facts": {
            "cap_type": cap_type,
            "amount": amount,
            "mutual": mutual
        },
        "confidence": confidence
    }


def detect_jurisdiction_clause(text: str) -> Optional[Dict[str, Any]]:
    """Detect governing law, jurisdiction, venue, and arbitration clauses."""
    lower = text.lower()
    if not re.search(r"\b(governing\s+law|jurisdiction|venue|courts?\s+(?:of|in|at)|laws?\s+of|arbitration|dispute\s+resolution)\b", lower):
        return None

    clause_kind = "governing_law"
    if "arbitrat" in lower:
        clause_kind = "arbitration"
    elif "exclusive jurisdiction" in lower or "venue" in lower or "courts in" in lower or "courts of" in lower:
        clause_kind = "venue"

    # Search for named jurisdictions
    named: List[str] = []
    for canonical, aliases in JURISDICTION_ALIASES:
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", lower):
                if canonical not in named:
                    named.append(canonical)
                break

    # Look for US states or foreign cities explicitly named
    if "singapore" in lower and "Singapore" not in named:
        named.append("Singapore")
    if "dubai" in lower and "UAE" not in named:
        named.append("UAE")
    if "california" in lower and "United States" not in named:
        named.append("United States")
    if "new york" in lower and "United States" not in named:
        named.append("United States")
    if "delaware" in lower and "United States" not in named:
        named.append("United States")

    # Ambiguity check
    ambiguous = False
    if not named or re.search(r"\b(competent\s+jurisdiction|applicable\s+law|relevant\s+territory|as\s+agreed\s+by\s+the\s+parties)\b", lower):
        ambiguous = True

    confidence = "high" if (named and not ambiguous) else ("medium" if named or ambiguous else "low")

    return {
        "category": "jurisdiction",
        "facts": {
            "named_jurisdictions": named,
            "clause_kind": clause_kind,
            "ambiguous": ambiguous
        },
        "confidence": confidence
    }


def detect_indemnification_clause(text: str) -> Optional[Dict[str, Any]]:
    """Detect indemnification clause and one-sidedness cues."""
    lower = text.lower()
    if not re.search(r"\b(indemnif|hold\s+harmless|defend\s+and\s+hold\s+harmless)\b", lower):
        return None

    one_sided = "unknown"
    if re.search(r"\b(each\s+party\s+shall\s+indemnify|mutual\s+indemnification|both\s+parties\s+agree\s+to\s+indemnify)\b", lower):
        one_sided = False
    elif re.search(r"\b(contractor\s+shall\s+indemnify|vendor\s+shall\s+indemnify|consultant\s+shall\s+indemnify|client\s+shall\s+indemnify)\b", lower):
        one_sided = True

    return {
        "category": "indemnification",
        "facts": {
            "present": True,
            "one_sided": one_sided
        },
        "confidence": "high" if one_sided != "unknown" else "medium"
    }


def detect_termination_clause(text: str) -> Optional[Dict[str, Any]]:
    """Detect termination clause, notice period, and termination for convenience."""
    lower = text.lower()
    if not re.search(r"\b(terminat|cancellation\s+of\s+agreement|terminate\s+this\s+agreement|right\s+to\s+terminate)\b", lower):
        return None

    notice_days, note = parse_duration_in_days(text)

    for_convenience = "unknown"
    if re.search(r"\b(for\s+convenience|without\s+cause|at\s+any\s+time\s+for\s+any\s+reason|without\s+assigning\s+any\s+reason)\b", lower):
        for_convenience = True
    elif re.search(r"\b(only\s+for\s+cause|material\s+breach\s+only|solely\s+in\s+case\s+of\s+breach)\b", lower):
        for_convenience = False

    one_sided = "unknown"
    if re.search(r"\b(either\s+party\s+may\s+terminate|each\s+party\s+has\s+the\s+right\s+to\s+terminate)\b", lower):
        one_sided = False
    elif re.search(r"\b(client\s+may\s+terminate|company\s+may\s+terminate|solely\s+the\s+client)\b", lower):
        one_sided = True

    confidence = "high" if notice_days is not None or for_convenience is True else "medium"

    return {
        "category": "termination",
        "facts": {
            "notice_days": notice_days,
            "for_convenience": for_convenience,
            "one_sided": one_sided,
            "conversion_note": note
        },
        "confidence": confidence
    }


def detect_clauses_in_segments(segments: List[Dict[str, Any]], analysis_id: str) -> List[Dict[str, Any]]:
    """Scan all segments and detect clauses across categories.
    Returns list of detected clause records ready for database persistence.
    """
    detected_clauses: List[Dict[str, Any]] = []

    detectors = [
        detect_payment_clause,
        detect_renewal_clause,
        detect_liability_clause,
        detect_jurisdiction_clause,
        detect_indemnification_clause,
        detect_termination_clause
    ]

    for seg in segments:
        text = seg.get("text", "")
        ev_id = seg.get("evidence_id")

        for detector in detectors:
            res = detector(text)
            if res:
                detected_clauses.append({
                    "analysis_id": analysis_id,
                    "evidence_id": ev_id,
                    "category": res["category"],
                    "facts": res["facts"],
                    "confidence": res["confidence"],
                    "source": "rule",
                    "review_status": "unreviewed"
                })

    return detected_clauses
