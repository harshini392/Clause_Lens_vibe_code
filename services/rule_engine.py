"""Rule Engine Service for ClauseLens.
Evaluates detected clauses against user policies deterministically.
Implements the decision table for payment, renewal, liability, and jurisdiction,
and informational evaluation for indemnification and termination.
"""
import json
from typing import List, Dict, Any, Optional
import services.explanation_service as explanation_service


def get_location_label(segment: Optional[Dict[str, Any]]) -> str:
    """Generate human-readable location label (e.g. 'Page 4' or 'Paragraph 12')."""
    if not segment:
        return "Document-wide"
    loc_type = segment.get("location_type")
    page_num = segment.get("page_number")
    para_idx = segment.get("paragraph_index")

    if loc_type == "page" and page_num is not None:
        return f"Page {page_num}"
    elif loc_type == "paragraph" and para_idx is not None:
        return f"Paragraph {para_idx}"
    elif page_num is not None:
        return f"Page {page_num}"
    elif para_idx is not None:
        return f"Paragraph {para_idx}"
    return "Document-wide"


def matches_jurisdiction(named_items: List[str], approved_items: List[str]) -> bool:
    """Determine if any named jurisdiction matches the user's approved list using alias-aware matching."""
    norm_approved = [a.strip().lower() for a in approved_items if a.strip()]
    if not norm_approved:
        return False

    for item in named_items:
        it = item.strip().lower()
        if it in norm_approved:
            return True
        for app in norm_approved:
            if it in app or app in it:
                return True
            # Canonical aliases
            if ("india" in app or "indian" in app) and ("india" in it or "indian" in it or "chennai" in it or "bengaluru" in it or "bangalore" in it):
                return True
            if ("england" in app or "english" in app) and ("england" in it or "english" in it or "wales" in it or "london" in it):
                return True
            if ("united states" in app or "usa" in app or "us" == app) and ("united states" in it or "delaware" in it or "new york" in it or "california" in it):
                return True
    return False


def evaluate_rules(
    detected_clauses: List[Dict[str, Any]],
    active_policies: List[Dict[str, Any]],
    segments_by_ev_id: Dict[str, Dict[str, Any]],
    analysis_id: str
) -> List[Dict[str, Any]]:
    """Evaluate detected clauses against active policies according to deterministic rules.
    Disabled policies are never passed or evaluated.
    Returns list of findings.
    """
    findings: List[Dict[str, Any]] = []

    # Group detected clauses by category
    clauses_by_category: Dict[str, List[Dict[str, Any]]] = {}
    for cl in detected_clauses:
        cat = cl["category"]
        clauses_by_category.setdefault(cat, []).append(cl)

    # 1. Evaluate Active Policies
    for policy in active_policies:
        # Guarantee disabled policies are skipped
        if not policy.get("enabled", 1):
            continue

        p_id = policy.get("id")
        p_type = policy.get("type")
        p_mode = policy.get("mode", "structured")
        p_name = policy.get("name", "")
        raw_params = policy.get("params_json", "{}")
        params = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
        policy_snapshot = {
            "id": p_id,
            "name": p_name,
            "type": p_type,
            "mode": p_mode,
            "params": params,
            "explanation": policy.get("explanation", "")
        }
        policy_snapshot_json = json.dumps(policy_snapshot)

        matching_clauses = clauses_by_category.get(p_type, [])

        # FREE_TEXT MODE: Always yields review_recommended for matching clauses
        if p_mode == "free_text":
            if not matching_clauses:
                # No clause found for free-text policy
                exp_data = {
                    "title": f"No {p_type} clause detected for '{p_name}'",
                    "explanation": f"No matching {p_type} clause was identified in the contract for manual policy: {policy.get('explanation', '')}",
                    "next_step": "Check whether these terms are addressed in an exhibit or schedule."
                }
                findings.append({
                    "analysis_id": analysis_id,
                    "policy_id": p_id,
                    "policy_snapshot_json": policy_snapshot_json,
                    "category": p_type,
                    "status": "review_recommended",
                    "title": exp_data["title"],
                    "explanation": exp_data["explanation"],
                    "quote": "No matching clause detected in document.",
                    "evidence_id": "doc_wide",
                    "location_label": "Document-wide",
                    "next_step": exp_data["next_step"],
                    "manual_review": 1,
                    "details_json": json.dumps({"mode": "free_text", "note": "Needs interpretation", "reason": "no_clause_detected"})
                })
            else:
                for cl in matching_clauses:
                    ev_id = cl["evidence_id"]
                    seg = segments_by_ev_id.get(ev_id, {})
                    quote = seg.get("text", "")
                    loc_label = get_location_label(seg)
                    exp_data = {
                        "title": f"Review recommended: {p_name} (Needs interpretation)",
                        "explanation": f"A {p_type} clause was detected and requires human review against your policy: \"{policy.get('explanation', '')}\"",
                        "next_step": "Review the excerpt against your organization's guidelines."
                    }
                    findings.append({
                        "analysis_id": analysis_id,
                        "policy_id": p_id,
                        "policy_snapshot_json": policy_snapshot_json,
                        "category": p_type,
                        "status": "review_recommended",
                        "title": exp_data["title"],
                        "explanation": exp_data["explanation"],
                        "quote": quote,
                        "evidence_id": ev_id,
                        "location_label": loc_label,
                        "next_step": exp_data["next_step"],
                        "manual_review": 1,
                        "details_json": json.dumps({"mode": "free_text", "note": "Needs interpretation", "facts": cl.get("facts", {})})
                    })
            continue

        # STRUCTURED MODE
        if p_type == "payment":
            max_days = int(params.get("max_payment_days", 30))
            if not matching_clauses:
                exp = explanation_service.build_explanation(
                    "payment", "review_recommended", {}, policy, {"reason": "no_clause_detected", "limit_days": max_days}
                )
                findings.append({
                    "analysis_id": analysis_id,
                    "policy_id": p_id,
                    "policy_snapshot_json": policy_snapshot_json,
                    "category": "payment",
                    "status": "review_recommended",
                    "title": exp["title"],
                    "explanation": exp["explanation"],
                    "quote": "No explicit payment timeframe clause was identified in the document.",
                    "evidence_id": "doc_wide",
                    "location_label": "Document-wide",
                    "next_step": exp["next_step"],
                    "manual_review": 1,
                    "details_json": json.dumps({"reason": "no_clause_detected", "limit_days": max_days})
                })
            else:
                for cl in matching_clauses:
                    facts = cl.get("facts", {})
                    p_days = facts.get("payment_days")
                    ev_id = cl["evidence_id"]
                    seg = segments_by_ev_id.get(ev_id, {})
                    quote = seg.get("text", "")
                    loc_label = get_location_label(seg)

                    if p_days is None or facts.get("conflicting_days"):
                        status = "review_recommended"
                        manual_rev = 1
                        details = {"contract_days": p_days, "limit_days": max_days, "conflicting": facts.get("conflicting_days", False)}
                    elif p_days > max_days:
                        status = "potential_conflict"
                        manual_rev = 1
                        diff = p_days - max_days
                        details = {"contract_days": p_days, "limit_days": max_days, "difference_days": diff}
                    else: # p_days <= max_days
                        status = "no_conflict_detected"
                        manual_rev = 0
                        details = {"contract_days": p_days, "limit_days": max_days}

                    exp = explanation_service.build_explanation("payment", status, facts, policy, details)
                    findings.append({
                        "analysis_id": analysis_id,
                        "policy_id": p_id,
                        "policy_snapshot_json": policy_snapshot_json,
                        "category": "payment",
                        "status": status,
                        "title": exp["title"],
                        "explanation": exp["explanation"],
                        "quote": quote,
                        "evidence_id": ev_id,
                        "location_label": loc_label,
                        "next_step": exp["next_step"],
                        "manual_review": manual_rev,
                        "details_json": json.dumps(details)
                    })

        elif p_type == "renewal":
            prohibit_auto = bool(params.get("auto_renewal_prohibited", True))
            max_notice = params.get("max_notice_days")
            max_notice = int(max_notice) if max_notice is not None else None

            if not matching_clauses:
                exp = explanation_service.build_explanation("renewal", "review_recommended", {}, policy, {"reason": "no_clause_detected"})
                findings.append({
                    "analysis_id": analysis_id,
                    "policy_id": p_id,
                    "policy_snapshot_json": policy_snapshot_json,
                    "category": "renewal",
                    "status": "review_recommended",
                    "title": exp["title"],
                    "explanation": exp["explanation"],
                    "quote": "No explicit renewal or term extension clause was identified in the document.",
                    "evidence_id": "doc_wide",
                    "location_label": "Document-wide",
                    "next_step": exp["next_step"],
                    "manual_review": 1,
                    "details_json": json.dumps({"reason": "no_clause_detected"})
                })
            else:
                for cl in matching_clauses:
                    facts = cl.get("facts", {})
                    auto_r = facts.get("auto_renews")
                    n_days = facts.get("notice_days")
                    ev_id = cl["evidence_id"]
                    seg = segments_by_ev_id.get(ev_id, {})
                    quote = seg.get("text", "")
                    loc_label = get_location_label(seg)

                    if auto_r is True and prohibit_auto:
                        status = "potential_conflict"
                        manual_rev = 1
                        details = {"auto_renews": True, "prohibited": True}
                    elif auto_r is True and max_notice is not None and n_days is not None and n_days > max_notice:
                        status = "potential_conflict"
                        manual_rev = 1
                        details = {"reason": "notice_days_exceeded", "notice_days": n_days, "max_notice_days": max_notice}
                    elif auto_r == "unknown":
                        status = "review_recommended"
                        manual_rev = 1
                        details = {"auto_renews": "unknown", "notice_days": n_days}
                    elif auto_r is False:
                        status = "no_conflict_detected"
                        manual_rev = 0
                        details = {"auto_renews": False, "notice_days": n_days}
                    else:
                        status = "no_conflict_detected" if not prohibit_auto else "review_recommended"
                        manual_rev = 1 if status == "review_recommended" else 0
                        details = {"auto_renews": auto_r, "notice_days": n_days}

                    exp = explanation_service.build_explanation("renewal", status, facts, policy, details)
                    findings.append({
                        "analysis_id": analysis_id,
                        "policy_id": p_id,
                        "policy_snapshot_json": policy_snapshot_json,
                        "category": "renewal",
                        "status": status,
                        "title": exp["title"],
                        "explanation": exp["explanation"],
                        "quote": quote,
                        "evidence_id": ev_id,
                        "location_label": loc_label,
                        "next_step": exp["next_step"],
                        "manual_review": manual_rev,
                        "details_json": json.dumps(details)
                    })

        elif p_type == "liability":
            rule_variant = params.get("rule", "cap_not_exceed_fees")

            if not matching_clauses:
                exp = explanation_service.build_explanation("liability", "review_recommended", {}, policy, {"reason": "no_clause_detected"})
                findings.append({
                    "analysis_id": analysis_id,
                    "policy_id": p_id,
                    "policy_snapshot_json": policy_snapshot_json,
                    "category": "liability",
                    "status": "review_recommended",
                    "title": exp["title"],
                    "explanation": exp["explanation"],
                    "quote": "No explicit limitation of liability clause was identified in the document.",
                    "evidence_id": "doc_wide",
                    "location_label": "Document-wide",
                    "next_step": exp["next_step"],
                    "manual_review": 1,
                    "details_json": json.dumps({"reason": "no_clause_detected", "rule": rule_variant})
                })
            else:
                for cl in matching_clauses:
                    facts = cl.get("facts", {})
                    cap_type = facts.get("cap_type", "none_stated")
                    ev_id = cl["evidence_id"]
                    seg = segments_by_ev_id.get(ev_id, {})
                    quote = seg.get("text", "")
                    loc_label = get_location_label(seg)

                    if rule_variant == "no_unlimited":
                        if cap_type == "unlimited":
                            status = "potential_conflict"
                            manual_rev = 1
                            details = {"cap_type": "unlimited", "rule": "no_unlimited"}
                        elif cap_type == "none_stated":
                            status = "review_recommended"
                            manual_rev = 1
                            details = {"cap_type": "none_stated", "rule": "no_unlimited"}
                        elif cap_type == "fees_paid":
                            status = "no_conflict_detected"
                            manual_rev = 0
                            details = {"cap_type": "fees_paid", "rule": "no_unlimited"}
                        else: # fixed_amount, other
                            status = "review_recommended"
                            manual_rev = 1
                            details = {"cap_type": cap_type, "rule": "no_unlimited"}
                    else: # cap_not_exceed_fees
                        if cap_type == "fees_paid":
                            status = "no_conflict_detected"
                            manual_rev = 0
                            details = {"cap_type": "fees_paid", "rule": "cap_not_exceed_fees"}
                        elif cap_type == "unlimited":
                            status = "potential_conflict"
                            manual_rev = 1
                            details = {"cap_type": "unlimited", "rule": "cap_not_exceed_fees"}
                        elif cap_type == "none_stated":
                            status = "review_recommended"
                            manual_rev = 1
                            details = {"cap_type": "none_stated", "rule": "cap_not_exceed_fees"}
                        else: # fixed_amount, other
                            status = "review_recommended"
                            manual_rev = 1
                            details = {"cap_type": cap_type, "rule": "cap_not_exceed_fees"}

                    exp = explanation_service.build_explanation("liability", status, facts, policy, details)
                    findings.append({
                        "analysis_id": analysis_id,
                        "policy_id": p_id,
                        "policy_snapshot_json": policy_snapshot_json,
                        "category": "liability",
                        "status": status,
                        "title": exp["title"],
                        "explanation": exp["explanation"],
                        "quote": quote,
                        "evidence_id": ev_id,
                        "location_label": loc_label,
                        "next_step": exp["next_step"],
                        "manual_review": manual_rev,
                        "details_json": json.dumps(details)
                    })

        elif p_type == "jurisdiction":
            approved_list = params.get("approved", [])

            if not matching_clauses:
                exp = explanation_service.build_explanation("jurisdiction", "review_recommended", {}, policy, {"reason": "no_clause_detected"})
                findings.append({
                    "analysis_id": analysis_id,
                    "policy_id": p_id,
                    "policy_snapshot_json": policy_snapshot_json,
                    "category": "jurisdiction",
                    "status": "review_recommended",
                    "title": exp["title"],
                    "explanation": exp["explanation"],
                    "quote": "No explicit governing law or dispute venue clause was identified in the document.",
                    "evidence_id": "doc_wide",
                    "location_label": "Document-wide",
                    "next_step": exp["next_step"],
                    "manual_review": 1,
                    "details_json": json.dumps({"reason": "no_clause_detected"})
                })
            else:
                for cl in matching_clauses:
                    facts = cl.get("facts", {})
                    named = facts.get("named_jurisdictions", [])
                    ambiguous = facts.get("ambiguous", False)
                    ev_id = cl["evidence_id"]
                    seg = segments_by_ev_id.get(ev_id, {})
                    quote = seg.get("text", "")
                    loc_label = get_location_label(seg)

                    if not named or ambiguous:
                        status = "review_recommended"
                        manual_rev = 1
                        details = {"named": named, "ambiguous": ambiguous}
                    elif matches_jurisdiction(named, approved_list):
                        status = "no_conflict_detected"
                        manual_rev = 0
                        details = {"named": named, "approved_match": True}
                    else:
                        status = "potential_conflict"
                        manual_rev = 1
                        details = {"named": named, "approved_match": False}

                    exp = explanation_service.build_explanation("jurisdiction", status, facts, policy, details)
                    findings.append({
                        "analysis_id": analysis_id,
                        "policy_id": p_id,
                        "policy_snapshot_json": policy_snapshot_json,
                        "category": "jurisdiction",
                        "status": status,
                        "title": exp["title"],
                        "explanation": exp["explanation"],
                        "quote": quote,
                        "evidence_id": ev_id,
                        "location_label": loc_label,
                        "next_step": exp["next_step"],
                        "manual_review": manual_rev,
                        "details_json": json.dumps(details)
                    })

    # 2. Informational checks (indemnification and termination - no user policy exists)
    for cat in ["indemnification", "termination"]:
        info_clauses = clauses_by_category.get(cat, [])
        for cl in info_clauses:
            facts = cl.get("facts", {})
            ev_id = cl["evidence_id"]
            seg = segments_by_ev_id.get(ev_id, {})
            quote = seg.get("text", "")
            loc_label = get_location_label(seg)
            exp = explanation_service.build_explanation(cat, "review_recommended", facts, None, {})

            findings.append({
                "analysis_id": analysis_id,
                "policy_id": None,
                "policy_snapshot_json": None,
                "category": cat,
                "status": "review_recommended",
                "title": exp["title"],
                "explanation": exp["explanation"],
                "quote": quote,
                "evidence_id": ev_id,
                "location_label": loc_label,
                "next_step": exp["next_step"],
                "manual_review": 1,
                "details_json": json.dumps({"informational": True, "facts": facts})
            })

    return findings
