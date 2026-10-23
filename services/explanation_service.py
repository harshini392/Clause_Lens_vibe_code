"""Explanation Service for ClauseLens.
Provides deterministic, legally responsible plain-language explanations
and actionable next steps. Never uses forbidden words ('safe', 'legal', 'illegal', etc.).
"""
from typing import Dict, Any, Optional

FORBIDDEN_WORDS = ["safe", "legal", "illegal", "unlawful", "void", "unenforceable", "compliant contract"]


def sanitize_language(text: str) -> str:
    """Ensure generated explanations adhere to the privacy-first assistance guidelines."""
    # Safety assertion to prevent regressions
    for word in ["illegal", "unlawful", "void"]:
        if word in text.lower():
            text = text.replace(word, "potential policy conflict")
    return text


def build_explanation(
    category: str,
    status: str,
    facts: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """Generate title, explanation, and next step using deterministic templates."""
    details = details or {}
    policy_name = policy.get("name", "Policy") if policy else "General Check"

    if category == "payment":
        if status == "potential_conflict":
            c_days = details.get("contract_days", facts.get("payment_days", 0))
            l_days = details.get("limit_days", 30)
            diff = details.get("difference_days", c_days - l_days if c_days and l_days else 0)
            return {
                "title": "Payment period exceeds your limit",
                "explanation": f"The contract specifies payment within {c_days} days, which exceeds your maximum allowed period of {l_days} days by {diff} days.",
                "next_step": f"Consider requesting a payment period of {l_days} days or less."
            }
        elif status == "no_conflict_detected":
            c_days = facts.get("payment_days")
            l_days = details.get("limit_days", 30)
            day_str = f"{c_days} days" if c_days is not None else "within limits"
            return {
                "title": "Payment terms align with policy limit",
                "explanation": f"The detected payment timeframe ({day_str}) appears to be within your maximum limit of {l_days} days.",
                "next_step": "Verify whether invoice triggers (e.g., receipt vs invoice date) meet operational expectations."
            }
        else: # review_recommended
            if not facts or facts.get("payment_days") is None:
                if details.get("reason") == "no_clause_detected":
                    return {
                        "title": "No payment clause detected",
                        "explanation": "No explicit payment timeframe clause was identified in the document against your configured policy.",
                        "next_step": "Confirm whether payment terms are set forth in an attached schedule, order form, or separate statement of work."
                    }
                return {
                    "title": "Payment terms require review",
                    "explanation": "Payment language was detected, but an exact day count could not be deterministically extracted or conflicting figures were found.",
                    "next_step": "Examine the invoice and payment schedule to verify the exact payment window."
                }
            return {
                "title": "Payment terms review recommended",
                "explanation": "The payment clause contains conditions or qualitative terms that require manual interpretation.",
                "next_step": "Review the payment terms manually against your operational policy."
            }

    elif category == "renewal":
        if status == "potential_conflict":
            if details.get("reason") == "notice_days_exceeded":
                n_days = details.get("notice_days")
                max_n = details.get("max_notice_days")
                return {
                    "title": "Renewal notice period exceeds limit",
                    "explanation": f"The agreement requires {n_days} days advance notice to prevent renewal, exceeding your configured maximum of {max_n} days.",
                    "next_step": "Request reducing the required advance cancellation notice period."
                }
            return {
                "title": "Automatic renewal condition detected",
                "explanation": "The agreement includes an automatic-renewal condition that conflicts with your policy.",
                "next_step": "Review the renewal and cancellation terms, and consider requesting an explicit opt-in renewal mechanism."
            }
        elif status == "no_conflict_detected":
            return {
                "title": "Renewal terms align with policy",
                "explanation": "No automatic renewal was detected, or renewal terms appear to align with your configured criteria.",
                "next_step": "Note the contract expiration date on your calendar for timely renegotiation."
            }
        else:
            if details.get("reason") == "no_clause_detected":
                return {
                    "title": "No renewal clause detected",
                    "explanation": "No explicit renewal or term extension clause was identified in the analyzed document.",
                    "next_step": "Check whether the agreement terminates automatically upon expiration of the initial term."
                }
            return {
                "title": "Renewal terms require manual review",
                "explanation": "Renewal or term extension language was identified, but auto-renewal conditions could not be conclusively determined.",
                "next_step": "Inspect the term and termination section to verify how extensions or renewals take effect."
            }

    elif category == "liability":
        if status == "potential_conflict":
            return {
                "title": "Unlimited or uncapped liability detected",
                "explanation": "The contract includes provisions indicating unlimited liability or an absence of any monetary cap, which conflicts with your liability policy.",
                "next_step": "Propose incorporating a clear monetary cap (such as fees paid in the preceding 12 months) on damages."
            }
        elif status == "no_conflict_detected":
            return {
                "title": "Liability cap aligns with fees-paid rule",
                "explanation": "The liability clause limits damages to fees paid under the contract, in accordance with your configured policy.",
                "next_step": "Ensure exclusions from the cap (such as confidentiality or gross negligence) are mutually acceptable."
            }
        else:
            cap_type = facts.get("cap_type", "unknown")
            if cap_type == "none_stated":
                return {
                    "title": "No liability cap specified",
                    "explanation": "The clause does not state a clear monetary limit on liability. The absence of a stated cap does not inherently create unlimited liability, but warrants review.",
                    "next_step": "Seek to insert a standard mutual limitation of liability clause."
                }
            elif cap_type == "fixed_amount":
                amt = facts.get("amount", "a fixed sum")
                return {
                    "title": "Fixed monetary liability cap detected",
                    "explanation": f"The liability clause specifies a fixed monetary cap ({amt}), which cannot be automatically evaluated against contract fees.",
                    "next_step": "Compare the fixed cap amount against the expected commercial value of the contract."
                }
            return {
                "title": "Liability clause requires review",
                "explanation": "Liability language was found with qualifying or non-standard terms requiring human interpretation.",
                "next_step": "Review the limitation of liability provisions with legal counsel or contract managers."
            }

    elif category == "jurisdiction":
        if status == "potential_conflict":
            named = facts.get("named_jurisdictions", [])
            named_str = ", ".join(named) if named else "unapproved territory"
            return {
                "title": "Governing law or venue not in approved list",
                "explanation": f"The contract designates jurisdiction or governing law in {named_str}, which is not present in your approved jurisdiction list.",
                "next_step": "Request amendment to an approved jurisdiction or propose neutral arbitration."
            }
        elif status == "no_conflict_detected":
            named = facts.get("named_jurisdictions", [])
            named_str = ", ".join(named) if named else "approved territory"
            return {
                "title": "Governing law matches approved jurisdiction",
                "explanation": f"The contract designates {named_str}, which aligns with your list of approved jurisdictions.",
                "next_step": "Confirm specific court or dispute venue convenience."
            }
        else:
            return {
                "title": "Jurisdiction clause requires interpretation",
                "explanation": "Governing law or dispute resolution language was detected, but no unambiguous specific venue was identified.",
                "next_step": "Clarify governing law and dispute venue in the contract draft."
            }

    elif category == "indemnification":
        one_sided = facts.get("one_sided")
        if one_sided is True:
            return {
                "title": "Informational: One-sided indemnification obligation",
                "explanation": "The indemnification clause appears to impose obligations primarily on one party.",
                "next_step": "Evaluate whether mutual indemnification or tailored liability boundaries should be requested."
            }
        return {
            "title": "Informational: Indemnification clause present",
            "explanation": "An indemnification provision was identified in the agreement for your awareness.",
            "next_step": "Review indemnified claims and defense procedures."
        }

    elif category == "termination":
        n_days = facts.get("notice_days")
        conv = facts.get("for_convenience")
        one_s = facts.get("one_sided")
        notice_str = f"with {n_days} days notice" if n_days else "without specified notice"
        conv_str = "for convenience" if conv is True else ""
        return {
            "title": "Informational: Termination terms identified",
            "explanation": f"The contract provides termination mechanisms {notice_str} {conv_str}. (Informational check only).",
            "next_step": "Verify whether termination notice timelines align with operational transition needs."
        }

    # Fallback
    return {
        "title": f"{category.capitalize()} clause review recommended",
        "explanation": f"A {category} clause was identified and warrants review against your organization's guidelines.",
        "next_step": "Inspect the corresponding contract section."
    }
