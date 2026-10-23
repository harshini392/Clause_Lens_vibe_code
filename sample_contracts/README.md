# ClauseLens Sample Contracts and Test Fixtures

This directory contains fictional, programmatically generated test contracts and edge cases designed to validate ClauseLens against policy evaluation rules, boundary conditions, and file validation handlers.

## Canonical Demo Policy Set
For demonstration and evaluation, the recommended demo policies are:
1. **Maximum 30-Day Payment Term**
   - Type: `payment` | Mode: `structured`
   - Parameters: `{"max_payment_days": 30}`
   - Standard: Invoices payable within 30 days of receipt; longer payment cycles trigger potential conflict.
2. **Prohibit Automatic Renewal**
   - Type: `renewal` | Mode: `structured`
   - Parameters: `{"auto_renewal_prohibited": true, "max_notice_days": 30}`
   - Standard: Disallows evergreen/automatic renewal without affirmative mutual agreement.
3. **Liability Capped at Fees Paid**
   - Type: `liability` | Mode: `structured`
   - Parameters: `{"rule": "cap_not_exceed_fees"}`
   - Standard: Prohibits unlimited liability; requires damages to be limited to fees paid.
4. **Approved Jurisdiction: India**
   - Type: `jurisdiction` | Mode: `structured`
   - Parameters: `{"approved": ["India", "Indian law", "Chennai", "Bengaluru", "Bangalore"]}`
   - Standard: Flags foreign or unapproved jurisdictions as potential conflicts.

---

## Contract Inventory

### 1. `risky_services_agreement.pdf` and `risky_services_agreement.docx`
- **Description:** A 4-page commercial professional services agreement with multiple high-risk terms.
- **Key Clauses:**
  - Page 2 / Paragraph 3: 60-day payment term (`net 60` / `sixty (60) days of invoice date`).
  - Page 3 / Paragraph 4: Automatic one-year renewal requiring 60 days advance written notice.
  - Page 3 / Paragraph 5: One-sided termination for convenience (Client only).
  - Page 4 / Paragraph 6: Unlimited liability with no monetary cap.
  - Page 4 / Paragraph 7: Exclusive governing law and venue in New York (unapproved foreign jurisdiction).
- **Expected Result:** Potential policy conflicts on Payment (60 vs 30 days), Renewal (auto-renewal prohibited), Liability (unlimited), and Jurisdiction (New York vs India).

### 2. `compliant_services_agreement.pdf`
- **Description:** A standard service agreement compliant with the demo policy set.
- **Key Clauses:**
  - 30-day payment terms following receipt of invoice.
  - Explicit expiration at end of term without automatic renewal.
  - Total liability capped at fees paid in preceding 12 months.
  - Governed by Indian law with exclusive jurisdiction in Chennai.
- **Expected Result:** Zero potential conflicts. All checked categories report "No conflict detected for this rule". Note: Never reports the contract as "safe" or "legal".

### 3. `ambiguous_agreement.docx`
- **Description:** A collaboration framework agreement containing vague, subjective phrasing.
- **Key Clauses:**
  - Payment: "payable within a reasonable time after submission of milestones".
  - Renewal: "term may be continued from time to time as the parties may deem appropriate".
  - Liability: "Liability shall be determined in accordance with applicable general law principles".
  - Jurisdiction: "competent court having jurisdiction over commercial matters in the relevant territory".
- **Expected Result:** Yields `review_recommended` ("Needs interpretation") for payment, renewal, liability, and jurisdiction, with zero automatic conflicts.

### 4. `india_freelance_agreement.pdf`
- **Description:** A freelance consulting agreement based in India.
- **Key Clauses:**
  - 45-day payment term.
  - Auto-renewal for 6 months with 30-day notice.
  - Indian law and Chennai jurisdiction.
- **Expected Result:** Conflict on payment (45 vs 30) and renewal; no conflict on jurisdiction.

---

## Edge Case Test Fixtures

1. `empty.pdf` (0 bytes): Validates rejection of empty uploads (HTTP 400).
2. `scanned_like.pdf` (Image-only vector canvas with 0 extractable characters): Triggers scanned PDF detection and returns `extraction_status: "scanned_no_text"` with the required OCR guidance message.
3. `corrupted.pdf`: Incomplete, damaged byte stream returning HTTP 422.
4. `fake.pdf`: Plain text file renamed to `.pdf` without `%PDF` magic bytes (HTTP 422).
5. `password_protected.pdf`: AES-256 encrypted PDF returning HTTP 422.
6. `xss_contract.pdf`: Contract text containing `<script>alert('contract_xss')</script>` to verify HTML-safe text rendering in the UI and PDF report escaping.
