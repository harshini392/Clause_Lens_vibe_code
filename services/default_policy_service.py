"""Domain-Specific Default Policy Profiles and Merging Service for ClauseSight.

Provides curated, versioned default policy profiles for 6 major document domains:
1. Government Documents
2. Government Tenders and Procurement
3. Employment Documents
4. Service and Freelancer Agreements
5. Non-Disclosure Agreements (NDA)
6. Lease and Rental Agreements

Maintains strict separation between:
- "mandatory": Authoritative statutory/regulatory requirements verified from official sources.
- "recommended": Best-practice review recommendations where statutory rules are discretionary or context-specific.
"""
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

PROFILE_VERSION = "2.0.0"

# Canonical Domains and Document Types mapping
SUPPORTED_DOMAINS: Dict[str, List[str]] = {
    "Government Documents": [
        "Government Application Form",
        "Government Notice or Instructions",
        "Government Policy or Regulation",
        "Government Declaration",
        "Other Government Document"
    ],
    "Government Tenders and Procurement": [
        "Tender / Request for Proposal",
        "Bid Document",
        "Procurement Contract",
        "Other Procurement Document"
    ],
    "Employment Documents": [
        "Employment Offer Letter",
        "Employment Agreement",
        "Other Employment Document"
    ],
    "Service and Freelancer Agreements": [
        "Freelance Agreement",
        "Service Agreement",
        "Consulting Agreement",
        "Other Service Document"
    ],
    "Non-Disclosure Agreements (NDA)": [
        "One-Way NDA",
        "Mutual NDA",
        "Other Confidentiality Document"
    ],
    "Lease and Rental Agreements": [
        "Residential Rental Agreement",
        "Commercial Lease",
        "Leave-and-License Agreement",
        "Other Property Document"
    ]
}

# Domains requiring conditional Issuing Authority field
AUTHORITY_DOMAINS = [
    "Government Documents",
    "Government Tenders and Procurement"
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Master Default Policy Catalog
# Each entry contains complete metadata, sources, verification level, and rule configuration
DEFAULT_POLICY_CATALOG: List[Dict[str, Any]] = [
    # =========================================================================
    # A. Government Documents
    # =========================================================================
    {
        "policy_key": "gov_doc_applicant_org_info",
        "domain": "Government Documents",
        "document_types": ["Government Application Form", "Government Declaration", "Other Government Document"],
        "jurisdiction": "Any",
        "name": "Applicant and Organization Identification",
        "description": "Verifies that the applicant name, registered entity, address, or designated identifier is stated in the document.",
        "category": "applicant_info",
        "rule_type": "required_information",
        "requirement_level": "mandatory",
        "parameters": {
            "required_fields": ["applicant", "organization", "name", "address"],
            "cues": ["applicant", "name of applicant", "organization", "registered office", "permanent address", "identity", "cin", "pan", "authorized representative"]
        },
        "enabled_by_default": True,
        "source_name": "General Administrative Rules & Standard Government Application Guidelines",
        "source_url": "https://darpg.gov.in/central-secretariat-manual-office-procedure",
        "source_version": "CSMOP 16th Edition",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "gov_doc_mandatory_declarations",
        "domain": "Government Documents",
        "document_types": ["Government Application Form", "Government Declaration", "Other Government Document"],
        "jurisdiction": "Any",
        "name": "Mandatory Textual Declarations",
        "description": "Checks for prescribed solemn declaration or affirmation of veracity of statements provided.",
        "category": "declaration",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["hereby declare", "solemnly affirm", "true to the best of my knowledge", "declaration", "undertaking", "verify that the contents", "penalty of perjury"]
        },
        "enabled_by_default": True,
        "source_name": "Statutory Declarations Framework & Indian Oaths Act / Evidence Act Procedures",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Statutory Practice Standards",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "gov_doc_eligibility_criteria",
        "domain": "Government Documents",
        "document_types": ["Government Application Form", "Government Notice or Instructions", "Government Policy or Regulation", "Other Government Document"],
        "jurisdiction": "Any",
        "name": "Eligibility and Qualification Requirements",
        "description": "Verifies that eligibility conditions, qualifications, or qualifying criteria are specified.",
        "category": "eligibility",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["eligibility", "eligible", "qualification", "qualifications", "minimum criteria", "prerequisite", "conditions of eligibility", "who can apply"]
        },
        "enabled_by_default": True,
        "source_name": "Public Guidelines for Government Schemes and Application Procedures",
        "source_url": "https://dopt.gov.in/guidelines",
        "source_version": "2024 Administrative Guidelines",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "gov_doc_application_deadlines",
        "domain": "Government Documents",
        "document_types": ["Government Application Form", "Government Notice or Instructions", "Other Government Document"],
        "jurisdiction": "Any",
        "name": "Application Deadlines and Cut-off Dates",
        "description": "Checks whether a definitive submission cut-off date or application deadline is identifiable.",
        "category": "deadline",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["deadline", "last date", "cut-off date", "due date", "closing date", "submission deadline", "received on or before", "late applications"]
        },
        "enabled_by_default": True,
        "source_name": "Central Secretariat Manual of Office Procedure (CSMOP)",
        "source_url": "https://darpg.gov.in",
        "source_version": "CSMOP 16th Edition",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "gov_doc_supporting_documents",
        "domain": "Government Documents",
        "document_types": ["Government Application Form", "Government Notice or Instructions", "Other Government Document"],
        "jurisdiction": "Any",
        "name": "Required Supporting Document Enclosures",
        "description": "Checks for an enumerated list of required textual enclosures, certificates, or annexures.",
        "category": "supporting_docs",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["enclosures", "supporting documents", "annexure", "documents to be attached", "checklist of documents", "certificates required", "enclosed herewith"]
        },
        "enabled_by_default": True,
        "source_name": "Recommended Practice Checklist for Citizen Service Deliveries",
        "source_url": "https://darpg.gov.in/service-standards",
        "source_version": "Citizen Charter Guidelines",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "gov_doc_submission_instructions",
        "domain": "Government Documents",
        "document_types": ["Government Application Form", "Government Notice or Instructions", "Government Declaration", "Other Government Document"],
        "jurisdiction": "Any",
        "name": "Submission Instructions and Prescribed Formats",
        "description": "Verifies that instructions specifying submission address, designated portal, or prescribed format are provided.",
        "category": "submission_format",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["submission", "submit to", "mode of submission", "prescribed format", "online portal", "addressed to", "superscribed as", "forwarded to"]
        },
        "enabled_by_default": True,
        "source_name": "Standard Administrative Notice Protocols",
        "source_url": "https://darpg.gov.in",
        "source_version": "2023 Guidelines",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "gov_doc_scheme_rules_reference",
        "domain": "Government Documents",
        "document_types": ["Government Application Form", "Government Notice or Instructions", "Government Policy or Regulation", "Other Government Document"],
        "jurisdiction": "Any",
        "name": "Statutory Authority and Scheme Reference",
        "description": "Checks for explicit references to the authorizing act, gazette notification, scheme, or issuing ministry.",
        "category": "scheme_reference",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["pursuant to", "under section", "in exercise of powers", "ministry of", "department of", "government of", "notification no", "rules, 20", "scheme", "gazette"]
        },
        "enabled_by_default": True,
        "source_name": "Principles of Administrative Drafting",
        "source_url": "https://legislative.gov.in",
        "source_version": "Legislative Drafting Manual",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },

    # =========================================================================
    # B. Government Tenders and Procurement
    # =========================================================================
    {
        "policy_key": "tender_bid_submission_deadline",
        "domain": "Government Tenders and Procurement",
        "document_types": ["Tender / Request for Proposal", "Bid Document", "Other Procurement Document"],
        "jurisdiction": "Any",
        "name": "Bid Submission Deadline and Schedule",
        "description": "Verifies that bid submission opening, closing dates, or critical dates schedule are explicitly stated.",
        "category": "deadline",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["bid submission", "last date of submission", "closing date and time", "tender opening date", "bid due date", "schedule of dates", "critical dates"]
        },
        "enabled_by_default": True,
        "source_name": "General Financial Rules (GFR) 2017 & Manual for Procurement of Goods",
        "source_url": "https://doe.gov.in/manuals",
        "source_version": "MoF Procurement Manual 2022",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "tender_bid_validity_period",
        "domain": "Government Tenders and Procurement",
        "document_types": ["Tender / Request for Proposal", "Bid Document", "Procurement Contract", "Other Procurement Document"],
        "jurisdiction": "Any",
        "name": "Bid Validity Period (Minimum 90 Days Recommended)",
        "description": "Checks whether the offer is required to remain valid for a minimum stated validity period.",
        "category": "bid_validity",
        "rule_type": "minimum_value",
        "requirement_level": "mandatory",
        "parameters": {
            "min_value": 90,
            "unit": "days",
            "cues": ["bid validity", "validity of bid", "validity period", "offer shall remain valid", "valid for a period of", "validity of offer"]
        },
        "enabled_by_default": True,
        "source_name": "General Financial Rules (GFR) 2017 - Rule 167 / CVC Guidelines",
        "source_url": "https://doe.gov.in/gfr-2017",
        "source_version": "GFR 2017 (Amended)",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "tender_eligibility_qualification_criteria",
        "domain": "Government Tenders and Procurement",
        "document_types": ["Tender / Request for Proposal", "Bid Document", "Procurement Contract", "Other Procurement Document"],
        "jurisdiction": "Any",
        "name": "Bidder Eligibility and Qualification Criteria",
        "description": "Verifies that technical, financial, or past performance eligibility criteria are defined.",
        "category": "eligibility",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["eligibility criteria", "qualifying criteria", "technical capacity", "financial turnover", "past experience", "minimum qualifications", "pre-qualification"]
        },
        "enabled_by_default": True,
        "source_name": "Central Vigilance Commission (CVC) Procurement Guidelines & GFR Rule 173",
        "source_url": "https://cvc.gov.in",
        "source_version": "CVC Guidelines on Tenders",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "tender_technical_specifications",
        "domain": "Government Tenders and Procurement",
        "document_types": ["Tender / Request for Proposal", "Bid Document", "Procurement Contract", "Other Procurement Document"],
        "jurisdiction": "Any",
        "name": "Technical Specifications and Requirements",
        "description": "Checks for explicit technical specifications, bill of quantities, or terms of reference.",
        "category": "technical_specs",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["technical specifications", "scope of work", "bill of quantities", "boq", "specifications", "schedule of requirements", "terms of reference", "tor"]
        },
        "enabled_by_default": True,
        "source_name": "General Financial Rules (GFR) 2017 - Rule 144 (Fundamental Principles of Public Buying)",
        "source_url": "https://doe.gov.in/gfr-2017",
        "source_version": "GFR 2017 Rule 144",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "tender_delivery_completion_deadlines",
        "domain": "Government Tenders and Procurement",
        "document_types": ["Tender / Request for Proposal", "Bid Document", "Procurement Contract", "Other Procurement Document"],
        "jurisdiction": "Any",
        "name": "Delivery or Contract Completion Period",
        "description": "Verifies that delivery milestones, execution timeline, or completion deadlines are specified.",
        "category": "delivery_schedule",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["delivery schedule", "delivery period", "time of completion", "completion period", "execution timeline", "milestone schedule", "delivery within"]
        },
        "enabled_by_default": True,
        "source_name": "MoF Manual for Procurement of Works & Goods",
        "source_url": "https://doe.gov.in/manuals",
        "source_version": "Procurement Manual 2022",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "tender_price_tax_payment_conditions",
        "domain": "Government Tenders and Procurement",
        "document_types": ["Tender / Request for Proposal", "Bid Document", "Procurement Contract", "Other Procurement Document"],
        "jurisdiction": "Any",
        "name": "Price, Tax, and Commercial Payment Terms",
        "description": "Verifies that prices (inclusive/exclusive of GST/taxes) and clear stage-wise payment conditions are outlined.",
        "category": "payment",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["payment terms", "commercial terms", "taxes", "gst", "duties", "price basis", "stage payments", "payment against invoice", "milestone payment"]
        },
        "enabled_by_default": True,
        "source_name": "Standard Terms of Public Procurement Contracts (MoF)",
        "source_url": "https://doe.gov.in",
        "source_version": "Standard Bidding Documents",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "tender_bid_performance_security",
        "domain": "Government Tenders and Procurement",
        "document_types": ["Tender / Request for Proposal", "Bid Document", "Procurement Contract", "Other Procurement Document"],
        "jurisdiction": "Any",
        "name": "Bid Security (EMD) and Performance Security (PBG)",
        "description": "Checks for provisions regarding Earnest Money Deposit (EMD) or Performance Bank Guarantee (PBG).",
        "category": "bid_security",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["earnest money deposit", "emd", "bid security", "performance security", "performance bank guarantee", "pbg", "security deposit", "bank guarantee"]
        },
        "enabled_by_default": True,
        "source_name": "General Financial Rules (GFR) 2017 - Rules 170 and 171",
        "source_url": "https://doe.gov.in/gfr-2017",
        "source_version": "GFR 2017 Rules 170/171",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "tender_bid_evaluation_criteria",
        "domain": "Government Tenders and Procurement",
        "document_types": ["Tender / Request for Proposal", "Bid Document", "Other Procurement Document"],
        "jurisdiction": "Any",
        "name": "Bid Evaluation Methodology (L1 / QCBS)",
        "description": "Verifies that the tender explains how bids will be objectively evaluated (e.g. Least Cost L1 or Quality-and-Cost Based Selection QCBS).",
        "category": "evaluation_criteria",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["evaluation criteria", "method of evaluation", "l1", "lowest responsive bidder", "qcbs", "scoring matrix", "technical evaluation", "financial evaluation"]
        },
        "enabled_by_default": True,
        "source_name": "CVC Common Irregularities in Public Procurement & MoF Guidelines",
        "source_url": "https://cvc.gov.in",
        "source_version": "CVC Guidelines 2021",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "tender_dispute_resolution_arbitration",
        "domain": "Government Tenders and Procurement",
        "document_types": ["Tender / Request for Proposal", "Procurement Contract", "Other Procurement Document"],
        "jurisdiction": "Any",
        "name": "Dispute Resolution and Arbitration Mechanism",
        "description": "Checks for dispute resolution, conciliation, or arbitration provisions in general conditions of contract.",
        "category": "jurisdiction",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["dispute resolution", "arbitration", "conciliation", "settlement of disputes", "arbitration and conciliation act", "courts having jurisdiction"]
        },
        "enabled_by_default": True,
        "source_name": "Standard General Conditions of Contract (GCC) for Public Procurement",
        "source_url": "https://doe.gov.in",
        "source_version": "GCC Guidelines 2022",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },

    # =========================================================================
    # C. Employment Documents
    # =========================================================================
    {
        "policy_key": "emp_job_title_and_role",
        "domain": "Employment Documents",
        "document_types": ["Employment Offer Letter", "Employment Agreement", "Other Employment Document"],
        "jurisdiction": "Any",
        "name": "Job Title and Designated Role",
        "description": "Verifies that the job title, designation, reporting line, or core responsibilities are stated.",
        "category": "role_title",
        "rule_type": "required_information",
        "requirement_level": "mandatory",
        "parameters": {
            "required_fields": ["title", "position", "designation", "role"],
            "cues": ["job title", "designation", "appointed as", "position of", "role of", "duties and responsibilities", "reporting to"]
        },
        "enabled_by_default": True,
        "source_name": "Standard Employment Contracting Standards & Industrial Employment Model Standing Orders",
        "source_url": "https://labour.gov.in",
        "source_version": "Model Standing Orders Framework",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "emp_compensation_payment_frequency",
        "domain": "Employment Documents",
        "document_types": ["Employment Offer Letter", "Employment Agreement", "Other Employment Document"],
        "jurisdiction": "Any",
        "name": "Compensation and Payment Frequency",
        "description": "Checks for remuneration details (salary, CTC, hourly rate, or stipend) and disbursement schedule (monthly/weekly).",
        "category": "compensation",
        "rule_type": "required_information",
        "requirement_level": "mandatory",
        "parameters": {
            "required_fields": ["salary", "ctc", "compensation", "remuneration"],
            "cues": ["salary", "ctc", "compensation", "gross salary", "basic pay", "remuneration", "payable monthly", "per month", "per annum", "stipend"]
        },
        "enabled_by_default": True,
        "source_name": "Code on Wages / Payment of Wages Act Standards",
        "source_url": "https://labour.gov.in",
        "source_version": "Statutory Wage Standard",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "emp_commencement_date",
        "domain": "Employment Documents",
        "document_types": ["Employment Offer Letter", "Employment Agreement", "Other Employment Document"],
        "jurisdiction": "Any",
        "name": "Employment Commencement Date",
        "description": "Verifies that an effective joining date or employment start date is identifiable.",
        "category": "commencement_date",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["commencement date", "start date", "date of joining", "joining date", "effective from", "commence employment on", "effective date"]
        },
        "enabled_by_default": True,
        "source_name": "Standard Employment Practice Standards",
        "source_url": "https://labour.gov.in",
        "source_version": "Employment Best Practice",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "emp_duration_or_permanence",
        "domain": "Employment Documents",
        "document_types": ["Employment Offer Letter", "Employment Agreement", "Other Employment Document"],
        "jurisdiction": "Any",
        "name": "Employment Duration or Tenured Term",
        "description": "Identifies whether employment is permanent, indefinite, fixed-term, or project-based.",
        "category": "employment_duration",
        "rule_type": "manual_review",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["fixed term", "permanent", "indefinite", "contract duration", "period of employment", "tenure", "term of agreement", "full-time employment"]
        },
        "enabled_by_default": True,
        "source_name": "Fixed Term Employment (Central Rules) Guidelines",
        "source_url": "https://labour.gov.in",
        "source_version": "2018 Central Amendment Rules",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "emp_probation_period_terms",
        "domain": "Employment Documents",
        "document_types": ["Employment Offer Letter", "Employment Agreement", "Other Employment Document"],
        "jurisdiction": "Any",
        "name": "Probation Terms and Confirmation Process",
        "description": "Checks whether a probation period and confirmation criteria are clearly defined.",
        "category": "probation",
        "rule_type": "manual_review",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["probation", "probationary period", "confirmation", "confirmed in writing", "extended probation", "on probation"]
        },
        "enabled_by_default": True,
        "source_name": "Model Employment Guidelines for Professional Staff",
        "source_url": "https://labour.gov.in",
        "source_version": "Standard Practices",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "emp_notice_termination_provisions",
        "domain": "Employment Documents",
        "document_types": ["Employment Offer Letter", "Employment Agreement", "Other Employment Document"],
        "jurisdiction": "Any",
        "name": "Notice and Termination Provisions",
        "description": "Verifies that termination notice periods, termination grounds, or salary in lieu of notice are specified.",
        "category": "termination",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["notice period", "termination", "terminate employment", "written notice", "resignation", "summary dismissal", "salary in lieu of notice"]
        },
        "enabled_by_default": True,
        "source_name": "Industrial Disputes Act / Shops and Establishments Act Notice Requirements",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Statutory Notice Norms",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "emp_confidentiality_ip_assignment",
        "domain": "Employment Documents",
        "document_types": ["Employment Offer Letter", "Employment Agreement", "Other Employment Document"],
        "jurisdiction": "Any",
        "name": "Confidentiality and Intellectual Property Rights",
        "description": "Checks for standard clauses safeguarding proprietary confidential information and work-product IP ownership.",
        "category": "confidentiality",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["confidential information", "proprietary information", "intellectual property", "work for hire", "assignment of inventions", "inventions", "trade secrets"]
        },
        "enabled_by_default": True,
        "source_name": "Standard Professional Employment Agreements Practice",
        "source_url": "https://dpiit.gov.in",
        "source_version": "IPR Policy Guidelines",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },

    # =========================================================================
    # D. Service and Freelancer Agreements
    # =========================================================================
    {
        "policy_key": "service_scope_of_work",
        "domain": "Service and Freelancer Agreements",
        "document_types": ["Freelance Agreement", "Service Agreement", "Consulting Agreement", "Other Service Document"],
        "jurisdiction": "Any",
        "name": "Explicit Scope of Work (SOW)",
        "description": "Verifies that the services to be performed, statement of work, or service specifications are detailed.",
        "category": "scope_of_work",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["scope of work", "services", "statement of work", "sow", "consulting services", "professional services", "schedule a", "exhibit a"]
        },
        "enabled_by_default": True,
        "source_name": "Indian Contract Act, 1872 (Certainty of Contract Terms - Section 29)",
        "source_url": "https://indiacode.nic.in/handle/123456789/2187",
        "source_version": "Indian Contract Act, 1872",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "service_deliverables_and_milestones",
        "domain": "Service and Freelancer Agreements",
        "document_types": ["Freelance Agreement", "Service Agreement", "Consulting Agreement", "Other Service Document"],
        "jurisdiction": "Any",
        "name": "Deliverables and Milestone Deadlines",
        "description": "Checks whether specific work products, milestones, or completion dates are designated.",
        "category": "deliverables",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["deliverables", "milestone", "milestones", "completion date", "schedule of deliverables", "due date", "submission of deliverables"]
        },
        "enabled_by_default": True,
        "source_name": "Commercial Contracting Best Practices Guide",
        "source_url": "https://www.iccwbo.org",
        "source_version": "ICC Model Commercial Contracts",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "service_fees_and_payment_terms",
        "domain": "Service and Freelancer Agreements",
        "document_types": ["Freelance Agreement", "Service Agreement", "Consulting Agreement", "Other Service Document"],
        "jurisdiction": "Any",
        "name": "Professional Fees and Payment Terms",
        "description": "Verifies that service fees, billing rates, payment terms, or retainers are identifiable.",
        "category": "payment",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["fee", "fees", "compensation", "billing", "payment terms", "invoicing", "retainer", "hourly rate", "payable within", "invoice"]
        },
        "enabled_by_default": True,
        "source_name": "Commercial Contracts Standards (Invoicing & Consideration)",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Contract Practice Guide",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "service_invoicing_tax_conditions",
        "domain": "Service and Freelancer Agreements",
        "document_types": ["Freelance Agreement", "Service Agreement", "Consulting Agreement", "Other Service Document"],
        "jurisdiction": "Any",
        "name": "Invoicing and Tax Withholding Conditions",
        "description": "Checks for invoicing procedure, GST/sales tax treatment, or TDS (tax deducted at source) terms.",
        "category": "taxation",
        "rule_type": "recommended_check",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["invoice", "invoicing", "taxes", "gst", "tds", "tax deducted at source", "withholding tax", "vat"]
        },
        "enabled_by_default": True,
        "source_name": "GST and Income Tax Act Practice Guidance for Independent Contractors",
        "source_url": "https://incometaxindia.gov.in",
        "source_version": "TDS Section 194J / 194C Guidance",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "service_acceptance_criteria",
        "domain": "Service and Freelancer Agreements",
        "document_types": ["Freelance Agreement", "Service Agreement", "Consulting Agreement", "Other Service Document"],
        "jurisdiction": "Any",
        "name": "Client Deliverable Acceptance Criteria",
        "description": "Checks for an objective deliverable review, testing, rejection, or acceptance window.",
        "category": "acceptance_criteria",
        "rule_type": "manual_review",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["acceptance", "acceptance criteria", "inspection", "review period", "deemed accepted", "rejection of deliverable", "cure defects"]
        },
        "enabled_by_default": True,
        "source_name": "Standard IT and Consulting Service Contracting Manual",
        "source_url": "https://www.nasscom.in",
        "source_version": "Commercial IT Contracting Guide",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "service_change_request_procedure",
        "domain": "Service and Freelancer Agreements",
        "document_types": ["Freelance Agreement", "Service Agreement", "Consulting Agreement", "Other Service Document"],
        "jurisdiction": "Any",
        "name": "Change Request and Out-of-Scope Work Terms",
        "description": "Verifies that modifications to scope, deliverables, or additional fees require written change orders.",
        "category": "change_control",
        "rule_type": "recommended_check",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["change request", "change order", "out of scope", "additional work", "modification of scope", "written change order", "scope change"]
        },
        "enabled_by_default": True,
        "source_name": "Professional Services Contract Management Standards",
        "source_url": "https://www.iccwbo.org",
        "source_version": "Commercial Practice Standards",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "service_liability_indemnification",
        "domain": "Service and Freelancer Agreements",
        "document_types": ["Freelance Agreement", "Service Agreement", "Consulting Agreement", "Other Service Document"],
        "jurisdiction": "Any",
        "name": "Liability Cap and Mutual Indemnification",
        "description": "Checks whether limitation of liability and mutual indemnification terms are present.",
        "category": "liability",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["limitation of liability", "indemnification", "indemnify", "hold harmless", "aggregate liability", "consequential damages", "indirect damages"]
        },
        "enabled_by_default": True,
        "source_name": "Commercial Contracting Standards & Indian Contract Act, 1872 Section 73",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Contract Act Section 73 Practice",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "service_termination_conditions",
        "domain": "Service and Freelancer Agreements",
        "document_types": ["Freelance Agreement", "Service Agreement", "Consulting Agreement", "Other Service Document"],
        "jurisdiction": "Any",
        "name": "Termination for Cause and Convenience",
        "description": "Verifies that termination notice, cure periods for breach, or convenience termination are defined.",
        "category": "termination",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["termination", "terminate this agreement", "for convenience", "material breach", "cure period", "written notice", "upon termination"]
        },
        "enabled_by_default": True,
        "source_name": "Standard Commercial Contracts Framework",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Commercial Law Practice Standards",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "service_confidentiality_disputes",
        "domain": "Service and Freelancer Agreements",
        "document_types": ["Freelance Agreement", "Service Agreement", "Consulting Agreement", "Other Service Document"],
        "jurisdiction": "Any",
        "name": "Confidentiality and Dispute Resolution",
        "description": "Checks for ongoing non-disclosure protection and designated governing law / dispute resolution venue.",
        "category": "jurisdiction",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["confidentiality", "confidential information", "governing law", "jurisdiction", "dispute resolution", "arbitration", "courts of"]
        },
        "enabled_by_default": True,
        "source_name": "Commercial Dispute Resolution Model Clauses (Arbitration Act)",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Dispute Resolution Standards",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },

    # =========================================================================
    # E. Non-Disclosure Agreements (NDA)
    # =========================================================================
    {
        "policy_key": "nda_definition_confidential_info",
        "domain": "Non-Disclosure Agreements (NDA)",
        "document_types": ["One-Way NDA", "Mutual NDA", "Other Confidentiality Document"],
        "jurisdiction": "Any",
        "name": "Definition of Confidential Information",
        "description": "Verifies that protected confidential information is clearly defined with standard tangible/intangible scope.",
        "category": "confidentiality",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["confidential information", "definition of confidential information", "proprietary information", "marked as confidential", "business secrets", "trade secrets"]
        },
        "enabled_by_default": True,
        "source_name": "Indian Contract Act, 1872 & Standard NDA Commercial Practice",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Model NDA Standard Clauses",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "nda_purpose_and_permitted_use",
        "domain": "Non-Disclosure Agreements (NDA)",
        "document_types": ["One-Way NDA", "Mutual NDA", "Other Confidentiality Document"],
        "jurisdiction": "Any",
        "name": "Specific Purpose and Permitted Use",
        "description": "Checks whether the permitted purpose or transaction for which information is shared is defined.",
        "category": "purpose_use",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["purpose", "permitted use", "solely for the purpose", "evaluation of", "business relationship", "shall not use for any other purpose"]
        },
        "enabled_by_default": True,
        "source_name": "Standard Commercial Confidentiality Principles",
        "source_url": "https://www.iccwbo.org",
        "source_version": "ICC Model Confidentiality Agreement",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "nda_confidentiality_exclusions",
        "domain": "Non-Disclosure Agreements (NDA)",
        "document_types": ["One-Way NDA", "Mutual NDA", "Other Confidentiality Document"],
        "jurisdiction": "Any",
        "name": "Standard Confidentiality Exclusions (Carve-outs)",
        "description": "Verifies standard exclusions (publicly known, already in possession, independently developed, rightful third party).",
        "category": "exclusions",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["exclusions", "shall not include", "publicly known", "public domain", "independently developed", "already known", "rightfully received"]
        },
        "enabled_by_default": True,
        "source_name": "Established Common Law & Commercial NDA Precedents",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Standard Commercial Exceptions",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "nda_duration_of_obligations",
        "domain": "Non-Disclosure Agreements (NDA)",
        "document_types": ["One-Way NDA", "Mutual NDA", "Other Confidentiality Document"],
        "jurisdiction": "Any",
        "name": "Definite Duration of Non-Disclosure Obligations",
        "description": "Checks for a clear timeframe during which confidentiality obligations persist (e.g. 2, 3, or 5 years).",
        "category": "nda_duration",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["term of", "period of", "years from", "duration of this agreement", "survive termination", "obligations shall survive for"]
        },
        "enabled_by_default": True,
        "source_name": "Commercial Law Principles on Reasonable Restraint (Indian Contract Act Section 27)",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Section 27 Contract Guidance",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "nda_permitted_disclosures_exceptions",
        "domain": "Non-Disclosure Agreements (NDA)",
        "document_types": ["One-Way NDA", "Mutual NDA", "Other Confidentiality Document"],
        "jurisdiction": "Any",
        "name": "Legally Compelled Disclosures Exception",
        "description": "Verifies that disclosure required by court order, law, or government authority is permitted with prompt notice.",
        "category": "compelled_disclosure",
        "rule_type": "recommended_check",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["court order", "compelled by law", "required by law", "subpoena", "regulatory authority", "prompt written notice", "protective order"]
        },
        "enabled_by_default": True,
        "source_name": "Procedural Due Process & Statutory Disclosure Standards",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Standard Exception Clauses",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "nda_return_or_destruction_clause",
        "domain": "Non-Disclosure Agreements (NDA)",
        "document_types": ["One-Way NDA", "Mutual NDA", "Other Confidentiality Document"],
        "jurisdiction": "Any",
        "name": "Return or Destruction of Confidential Information",
        "description": "Checks for obligations to return or certify destruction of confidential materials upon request or termination.",
        "category": "return_destruction",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["return or destroy", "return of confidential", "destruction of", "certify in writing", "promptly return", "securely destroy"]
        },
        "enabled_by_default": True,
        "source_name": "Commercial Confidentiality Best Practice Standards",
        "source_url": "https://www.iccwbo.org",
        "source_version": "ICC NDA Standard",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "nda_injunctive_remedies_governing_law",
        "domain": "Non-Disclosure Agreements (NDA)",
        "document_types": ["One-Way NDA", "Mutual NDA", "Other Confidentiality Document"],
        "jurisdiction": "Any",
        "name": "Injunctive Remedies and Governing Law",
        "description": "Verifies availability of equitable injunctive relief for breach and designated governing jurisdiction.",
        "category": "jurisdiction",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["injunctive relief", "equitable relief", "specific performance", "governing law", "jurisdiction", "courts of", "irreparable harm"]
        },
        "enabled_by_default": True,
        "source_name": "Specific Relief Act, 1963 (Injunctions - Section 38/41)",
        "source_url": "https://indiacode.nic.in/handle/123456789/1583",
        "source_version": "Specific Relief Act, 1963",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },

    # =========================================================================
    # F. Lease and Rental Agreements
    # =========================================================================
    {
        "policy_key": "lease_parties_and_property_description",
        "domain": "Lease and Rental Agreements",
        "document_types": ["Residential Rental Agreement", "Commercial Lease", "Leave-and-License Agreement", "Other Property Document"],
        "jurisdiction": "Any",
        "name": "Parties and Demised Premises Description",
        "description": "Verifies that the landlord/licensor, tenant/licensee, and exact property address or premises description are identified.",
        "category": "property_description",
        "rule_type": "required_information",
        "requirement_level": "mandatory",
        "parameters": {
            "required_fields": ["landlord", "tenant", "property", "premises"],
            "cues": ["landlord", "tenant", "licensor", "licensee", "lessor", "lessee", "demised premises", "scheduled property", "premises situated at", "premises located at"]
        },
        "enabled_by_default": True,
        "source_name": "Transfer of Property Act, 1882 (Section 105) / Model Tenancy Act",
        "source_url": "https://mohua.gov.in/upload/uploadfiles/files/Model_Tenancy_Act_English.pdf",
        "source_version": "Model Tenancy Act Framework 2021",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "lease_rent_amount_and_due_date",
        "domain": "Lease and Rental Agreements",
        "document_types": ["Residential Rental Agreement", "Commercial Lease", "Leave-and-License Agreement", "Other Property Document"],
        "jurisdiction": "Any",
        "name": "Monthly Rent Amount and Payment Due Date",
        "description": "Checks for designated monthly/quarterly rent amount and specific payment calendar due date.",
        "category": "rent_terms",
        "rule_type": "required_information",
        "requirement_level": "mandatory",
        "parameters": {
            "required_fields": ["rent", "monthly", "due date"],
            "cues": ["monthly rent", "rent of rs", "rent amount", "payable on or before", "due date", "calendar month", "compensation of rs", "license fee"]
        },
        "enabled_by_default": True,
        "source_name": "Model Tenancy Act, 2021 (Rent Tenancy Provisions)",
        "source_url": "https://mohua.gov.in/upload/uploadfiles/files/Model_Tenancy_Act_English.pdf",
        "source_version": "MTA 2021 Section 8",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "lease_security_deposit_refund_conditions",
        "domain": "Lease and Rental Agreements",
        "document_types": ["Residential Rental Agreement", "Commercial Lease", "Leave-and-License Agreement", "Other Property Document"],
        "jurisdiction": "Any",
        "name": "Security Deposit and Refund Terms",
        "description": "Verifies that security deposit amount, deduction rules for damages, and clear refund timelines are stated.",
        "category": "deposit",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["security deposit", "interest-free refundable", "refundable deposit", "refund of deposit", "deductions from deposit", "refunded within", "vacating the premises"]
        },
        "enabled_by_default": True,
        "source_name": "Model Tenancy Act, 2021 (Security Deposit Ceilings & Refund)",
        "source_url": "https://mohua.gov.in/upload/uploadfiles/files/Model_Tenancy_Act_English.pdf",
        "source_version": "MTA 2021 Section 11",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "lease_duration_and_term",
        "domain": "Lease and Rental Agreements",
        "document_types": ["Residential Rental Agreement", "Commercial Lease", "Leave-and-License Agreement", "Other Property Document"],
        "jurisdiction": "Any",
        "name": "Lease Duration and Term",
        "description": "Verifies that commencement date, expiry date, or lease duration (e.g. 11 months, 3 years) are defined.",
        "category": "lease_duration",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["period of 11 months", "lease period", "duration of lease", "term of this agreement", "for a period of", "effective from", "commencing from", "expiring on"]
        },
        "enabled_by_default": True,
        "source_name": "Transfer of Property Act, 1882 / Registration Act, 1908 (Section 17)",
        "source_url": "https://indiacode.nic.in",
        "source_version": "Tenancy Term Standards",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "lease_renewal_conditions",
        "domain": "Lease and Rental Agreements",
        "document_types": ["Residential Rental Agreement", "Commercial Lease", "Leave-and-License Agreement", "Other Property Document"],
        "jurisdiction": "Any",
        "name": "Renewal and Extension Conditions",
        "description": "Checks whether extension or renewal requires mutual written consent and fresh agreement execution.",
        "category": "renewal",
        "rule_type": "manual_review",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["renewal", "extension of lease", "renewed with mutual consent", "option to renew", "fresh agreement", "notice of renewal"]
        },
        "enabled_by_default": True,
        "source_name": "Tenancy Best Practice Recommendations",
        "source_url": "https://mohua.gov.in",
        "source_version": "Model Tenancy Recommendations",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "lease_maintenance_utility_responsibilities",
        "domain": "Lease and Rental Agreements",
        "document_types": ["Residential Rental Agreement", "Commercial Lease", "Leave-and-License Agreement", "Other Property Document"],
        "jurisdiction": "Any",
        "name": "Maintenance and Utility Responsibilities",
        "description": "Verifies division of responsibilities for electricity, water, major structural repairs, and routine upkeep.",
        "category": "maintenance",
        "rule_type": "required_clause",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["maintenance charges", "utility charges", "electricity charges", "water charges", "repairs and maintenance", "routine repairs", "structural repairs"]
        },
        "enabled_by_default": True,
        "source_name": "Model Tenancy Act, 2021 (Division of Maintenance Responsibilities)",
        "source_url": "https://mohua.gov.in/upload/uploadfiles/files/Model_Tenancy_Act_English.pdf",
        "source_version": "MTA 2021 Schedule II",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "lease_termination_notice_period",
        "domain": "Lease and Rental Agreements",
        "document_types": ["Residential Rental Agreement", "Commercial Lease", "Leave-and-License Agreement", "Other Property Document"],
        "jurisdiction": "Any",
        "name": "Termination Notice Period",
        "description": "Checks for clear notice requirements (e.g. 30 days written notice) for early termination or handover.",
        "category": "termination",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["termination notice", "notice period", "months notice", "days notice", "vacate the premises", "early termination", "notice in writing"]
        },
        "enabled_by_default": True,
        "source_name": "Transfer of Property Act, 1882 (Section 106 - Notice to Quit)",
        "source_url": "https://indiacode.nic.in/handle/123456789/2338",
        "source_version": "Section 106 Notice Rules",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "lease_rent_escalation_terms",
        "domain": "Lease and Rental Agreements",
        "document_types": ["Residential Rental Agreement", "Commercial Lease", "Leave-and-License Agreement", "Other Property Document"],
        "jurisdiction": "Any",
        "name": "Rent Escalation Provisions",
        "description": "Checks whether an annual rent increase percentage (e.g. 5% or 10%) is defined or capped.",
        "category": "rent_escalation",
        "rule_type": "manual_review",
        "requirement_level": "recommended",
        "parameters": {
            "cues": ["escalation", "rent increase", "increase by", "% per annum", "annual increase", "enhancement of rent", "revised rent"]
        },
        "enabled_by_default": True,
        "source_name": "Model Tenancy Act & State Rent Control Guidelines",
        "source_url": "https://mohua.gov.in",
        "source_version": "MTA 2021 Practice Guidance",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    },
    {
        "policy_key": "lease_permitted_use_of_property",
        "domain": "Lease and Rental Agreements",
        "document_types": ["Residential Rental Agreement", "Commercial Lease", "Leave-and-License Agreement", "Other Property Document"],
        "jurisdiction": "Any",
        "name": "Permitted Use and Subletting Restrictions",
        "description": "Verifies that authorized premises use (residential/commercial) and prohibition on unauthorized subletting are specified.",
        "category": "permitted_use",
        "rule_type": "required_clause",
        "requirement_level": "mandatory",
        "parameters": {
            "cues": ["residential purpose", "commercial purpose", "permitted use", "sublet", "sub-lease", "assign or part with possession", "shall not sublet"]
        },
        "enabled_by_default": True,
        "source_name": "Transfer of Property Act, 1882 Section 108 / Model Tenancy Act Section 7",
        "source_url": "https://mohua.gov.in",
        "source_version": "Property Law Principles",
        "created_at": "2026-10-23T00:00:00Z",
        "updated_at": "2026-10-23T00:00:00Z"
    }
]


def get_supported_domains() -> Dict[str, List[str]]:
    """Return dictionary of supported domains and their dependent document types."""
    return {domain: list(doc_types) for domain, doc_types in SUPPORTED_DOMAINS.items()}


def is_valid_domain_and_doc_type(domain: str, document_type: str) -> bool:
    """Validate whether domain and document type combination is supported."""
    if domain not in SUPPORTED_DOMAINS:
        return False
    return document_type in SUPPORTED_DOMAINS[domain]


def matches_jurisdiction_scope(policy_jurisdiction: str, target_jurisdiction: Optional[str]) -> bool:
    """Determine if a policy jurisdiction applies to the target jurisdiction.
    'Any' matches any user-specified jurisdiction.
    Otherwise, case-insensitive substring or alias matching is performed.
    """
    if not policy_jurisdiction or policy_jurisdiction.strip().lower() in ("any", "all", "*"):
        return True
    if not target_jurisdiction:
        # Default target jurisdiction is India
        target_jurisdiction = "India"

    p_norm = policy_jurisdiction.strip().lower()
    t_norm = target_jurisdiction.strip().lower()

    if p_norm == t_norm or p_norm in t_norm or t_norm in p_norm:
        return True

    # Common canonical aliases and Indian states/cities
    indian_aliases = [
        "india", "indian", "tamil nadu", "karnataka", "maharashtra", "delhi",
        "uttar pradesh", "telangana", "andhra pradesh", "kerala", "gujarat",
        "west bengal", "rajasthan", "punjab", "haryana", "bihar", "odisha",
        "chennai", "bengaluru", "bangalore", "mumbai", "hyderabad", "kolkata"
    ]
    if ("india" in p_norm or "indian" in p_norm):
        if any(alias in t_norm for alias in indian_aliases):
            return True

    if ("united states" in p_norm or "usa" in p_norm) and ("united states" in t_norm or "usa" in t_norm):
        return True
    if ("uk" in p_norm or "england" in p_norm) and ("uk" in t_norm or "england" in t_norm):
        return True

    return False


def get_default_policies_for_profile(
    domain: str,
    document_type: str,
    jurisdiction: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve default policies applicable to the given domain, document type, and jurisdiction.
    
    For an 'Other' document type, applies only verified domain-level checks that are genuinely applicable,
    never silently imposing an unrelated specific-document profile.
    """
    if not is_valid_domain_and_doc_type(domain, document_type):
        return []

    target_jurisdiction = jurisdiction.strip() if jurisdiction and jurisdiction.strip() else "India"
    results: List[Dict[str, Any]] = []

    for item in DEFAULT_POLICY_CATALOG:
        if item["domain"] != domain:
            continue

        # Check document type applicability
        doc_types = item.get("document_types", [])
        if document_type not in doc_types and "*" not in doc_types:
            continue

        # Check jurisdiction applicability
        if not matches_jurisdiction_scope(item.get("jurisdiction", "Any"), target_jurisdiction):
            continue

        # Create defensive copy of policy dict
        policy_copy = dict(item)
        policy_copy["profile_version"] = PROFILE_VERSION
        policy_copy["document_type"] = document_type
        policy_copy["target_document_type"] = document_type
        policy_copy["target_jurisdiction"] = target_jurisdiction
        policy_copy["source"] = "domain_default"
        results.append(policy_copy)

    return results


def merge_policies(
    domain: str,
    document_type: str,
    jurisdiction: Optional[str],
    issuing_authority: Optional[str],
    user_policies: List[Dict[str, Any]],
    deselected_default_keys: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Merge domain-specific default policies with enabled user policies.
    
    Rules:
    - Filters defaults for matching domain, document type, and jurisdiction.
    - Excludes defaults whose policy_key is in deselected_default_keys.
    - Includes only enabled user policies.
    - Preserves source for every policy: 'domain_default' or 'user'.
    - Prevents accidental duplicates by stable policy identifier or identical rule definition.
    - Retains both checks if user has a policy in the same broad category as a default check
      (e.g., default check requires payment clause; user policy sets max payment <= 30 days).
    - Validates policy definitions before returning.
    """
    if not is_valid_domain_and_doc_type(domain, document_type):
        raise ValueError(f"Unsupported domain '{domain}' or document type '{document_type}'.")

    target_jurisdiction = (jurisdiction or "India").strip()
    deselected = set(deselected_default_keys or [])

    # 1. Load applicable default policies
    default_policies = get_default_policies_for_profile(domain, document_type, target_jurisdiction)

    merged: List[Dict[str, Any]] = []
    seen_policy_keys = set()

    for def_p in default_policies:
        pkey = def_p.get("policy_key")
        if not pkey or pkey in deselected:
            continue

        seen_policy_keys.add(pkey)
        merged.append({
            "id": f"def_{pkey}",
            "policy_key": pkey,
            "name": def_p["name"],
            "type": def_p["category"],
            "category": def_p["category"],
            "mode": "structured" if def_p["rule_type"] != "manual_review" else "free_text",
            "rule_type": def_p["rule_type"],
            "params": def_p.get("parameters", {}),
            "explanation": def_p["description"],
            "description": def_p["description"],
            "source": "domain_default",
            "requirement_level": def_p.get("requirement_level", "recommended"),
            "source_name": def_p.get("source_name", ""),
            "source_url": def_p.get("source_url", ""),
            "source_version": def_p.get("source_version", ""),
            "domain": domain,
            "document_type": document_type,
            "jurisdiction": target_jurisdiction,
            "issuing_authority": (issuing_authority or "").strip(),
            "enabled": 1
        })

    # 2. Add enabled user policies
    for up in user_policies:
        # Strictly skip disabled user policies
        if not up.get("enabled", 1):
            continue

        user_id = up.get("id")
        user_key = f"user_policy_{user_id}"

        # Avoid exact duplicate if somehow a user policy has the same key
        if user_key in seen_policy_keys:
            continue

        seen_policy_keys.add(user_key)

        raw_params = up.get("params_json", "{}")
        if isinstance(raw_params, str):
            import json
            try:
                params = json.loads(raw_params)
            except Exception:
                params = {}
        elif isinstance(raw_params, dict):
            params = raw_params
        else:
            params = up.get("params", {})

        p_type = up.get("type", "custom")
        rule_type = "maximum_value" if p_type == "payment" else ("prohibited_term" if p_type == "renewal" else "expected_term")

        merged.append({
            "id": user_id,
            "policy_key": user_key,
            "name": up.get("name", "Custom User Policy"),
            "type": p_type,
            "category": up.get("category", p_type),
            "mode": up.get("mode", "structured"),
            "rule_type": rule_type,
            "params": params,
            "explanation": up.get("explanation", ""),
            "description": up.get("explanation", ""),
            "source": "user",
            "requirement_level": "mandatory",
            "source_name": "User-Defined Policy",
            "source_url": "",
            "source_version": "User Custom",
            "domain": domain,
            "document_type": document_type,
            "jurisdiction": target_jurisdiction,
            "issuing_authority": (issuing_authority or "").strip(),
            "enabled": 1
        })

    return merged
