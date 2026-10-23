# ClauseLens — Privacy-First Contract Policy Verification

ClauseLens is a local, privacy-first web application that checks uploaded legal agreements (PDF or DOCX) against your **own** policies and produces evidence-backed, verifiable findings. It provides policy-based assistance and is **not legal advice**. It never declares a contract "safe", "legal", or "illegal".

---

## 1. Core Principles & Privacy Architecture
- **Zero Cloud by Default:** All document segmentation, clause detection, and policy evaluation run 100% locally on your machine.
- **Strict Evidence Integrity:** Quotes and page/paragraph locations are retrieved directly from stored server-side segments by sequential deterministic evidence IDs (`ev_0001`, `ev_0002`, ...). The client or AI models are never trusted to fabricate quotes.
- **Secure File Lifecycle:** Uploaded files are verified via magic bytes (`%PDF`, PK zip package), written to an isolated directory outside any served static path with UUID filenames, parsed, and deleted in a guaranteed `finally` block.
- **Configurable Retention:** Extracted text and findings are persisted in a local SQLite database with an automatic 30-day retention purge on startup, plus manual purge and "delete all" controls.
- **Deterministic Evaluation:** Rule engine uses an unambiguous decision table. Disabled policies are never evaluated. Old analyses remain snapshot-immutable even if policies are edited later.
- **XSS & Injection Protection:** The frontend avoids `innerHTML` for untrusted contract content and builds DOM nodes using `createElement` and `textContent`. ReportLab PDF output strictly escapes XML entities (`saxutils.escape`).

---

## 2. Canonical Demo Policy Set
For live demonstration and test verification, the canonical demo policy set contains:

1. **Maximum 30-Day Payment Term**
   - **Category:** `payment` | **Mode:** `structured`
   - **Parameters:** `{"max_payment_days": 30}`
   - **Standard:** Invoices must be payable within 30 days of receipt; longer terms trigger a Potential Policy Conflict.
2. **Prohibit Automatic Renewal**
   - **Category:** `renewal` | **Mode:** `structured`
   - **Parameters:** `{"auto_renewal_prohibited": true, "max_notice_days": 30}`
   - **Standard:** Evergreen or auto-renewal clauses trigger a Potential Policy Conflict unless explicitly mutual.
3. **Liability Capped at Fees Paid**
   - **Category:** `liability` | **Mode:** `structured`
   - **Parameters:** `{"rule": "cap_not_exceed_fees"}`
   - **Standard:** Prohibits unlimited liability; requires liability capped at contract fees.
4. **Approved Jurisdiction: India**
   - **Category:** `jurisdiction` | **Mode:** `structured`
   - **Parameters:** `{"approved": ["India", "Indian law", "Chennai", "Bengaluru", "Bangalore"]}`
   - **Standard:** Flags foreign, non-Indian governing laws or courts as Potential Policy Conflicts.

---

## 3. Assumptions Recorded
As required by the specification, the following design decisions were made for unspecified details:
1. **Timeframe Conversion Convention:** Durations stated in months (e.g., "2 months") are converted to days based on a standard 30-day month convention (e.g., 60 days) and explicitly noted in the finding details. "1 year" converts to 365 days.
2. **Table Text in DOCX:** Paragraphs inside table cells in Word documents are treated in document flow order and indexed continuously with body paragraphs, preserving exact paragraph numbering.
3. **Absence of a Stated Liability Cap:** If a contract mentions liability but does not specify a monetary cap (`none_stated`), this is classified as `review_recommended` ("Review recommended") rather than an automatic conflict, because the absence of a stated cap does not inherently make liability unlimited at law.
4. **Document-Wide Fallbacks:** If a required clause category (such as payment or renewal) is completely missing from an agreement, a `review_recommended` finding is generated with location `"Document-wide"` and quote note `"No explicit clause detected in document"`. It is never labeled "safe".
5. **CSRF Enforcement:** State-mutating HTTP methods (`POST`, `PUT`, `DELETE`) require the `X-CSRF-Token` header matching the cookie token. Read-only endpoints (`GET`) do not require CSRF tokens.

---

## 4. Setup and Run Instructions (Windows PowerShell)

### Prerequisites
- Python 3.11+ (tested on Python 3.13)
- Windows PowerShell (or macOS/Linux terminal)

### Setup & Installation
```powershell
# Navigate into the project folder
cd ClauseLens

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install pinned dependencies
pip install -r requirements.txt

# Generate realistic sample contracts and test edge cases
python sample_contracts\generate_samples.py
```

### Running the Application
```powershell
# Start the local server
python app.py
```
Open your browser and navigate to:
**`http://127.0.0.1:5000`**

### Running the Full Test Suite
```powershell
# Run all 56 automated tests with pytest
pytest -v
```

---

## 5. Enabling Nemotron (P2 Optional Integration)

ClauseLens operates 100% locally and does not require Nemotron for complete functionality. To connect Nemotron:

1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Configure your environment variables in `.env`:
   ```ini
   NEMOTRON_ENABLED=true
   NEMOTRON_BASE_URL=http://localhost:8000/v1
   NEMOTRON_API_KEY=your-api-key-here
   NEMOTRON_MODEL=nvidia/nemotron-4-340b-instruct
   NEMOTRON_TIMEOUT=20
   ```
3. Restart the server. In the UI, tick the checkbox **"Opt-in to Advanced AI Interpretation"** during upload. Only segments for ambiguous clauses are sent to the endpoint. If the endpoint is unreachable, timed out, or returns invalid schema, ClauseLens automatically falls back to rule-based evaluation without crashing.

---

## 6. 3-Minute Demo Script

Follow this sequence to showcase the full capabilities of ClauseLens:

### Minute 1: Dashboard & Risky Contract Verification
1. Open `http://127.0.0.1:5000` — see the **Contract Policy Dashboard** showing clean, live SQLite statistics and active policies.
2. Click **"Start New Analysis"**.
3. Under **Quick Demo Samples**, click **"Risky Agreement (PDF)"** (or drag & drop `sample_contracts/risky_services_agreement.pdf`).
4. Click **"Analyze Contract"**.
5. Within 1 second, the **Review Workspace** opens:
   - Notice the top summary: **5 Potential Conflicts**, **3 Reviews Recommended**, **0 No Conflict**.
   - Notice the banner: *"Advanced interpretation was not used. Results are rule-based."*
   - Click the first finding: **"Payment period exceeds your limit"**.
   - Observe how the left panel automatically scrolls and highlights Page 2: *"within sixty (60) days of invoice date"*.
   - Click the renewal finding: see Page 3 highlighted for automatic one-year renewal.
   - Click the liability finding: see Page 4 highlighted for unlimited liability.
   - Click the jurisdiction finding: see Page 4 highlighted for New York venue.

### Minute 2: PDF Audit Report & Compliant Agreement
1. In the Review Workspace, click **"Download PDF Report"**.
2. Open the downloaded PDF:
   - Notice the clean ReportLab styling, document metadata table, summary metrics, and policy snapshot.
   - Notice the mandatory legal disclaimer: *"ClauseLens provides policy-based assistance and is not legal advice..."*
   - See running footers with dynamic page numbering (*"Page 1 of 2"*).
3. Click **"New Analysis"** in the sidebar.
4. Click **"Compliant Agreement (PDF)"** and click **"Analyze Contract"**.
5. Observe the result: **0 Potential Conflicts**. Notice the finding titles state *"aligns with policy limit"*; none declare the contract "safe" or "legal".

### Minute 3: Ambiguous DOCX, Policy Customization & Data Retention
1. Click **"New Analysis"** -> click **"Ambiguous Agreement (DOCX)"** -> click **"Analyze Contract"**.
2. In the Review Workspace, see **4 Review Recommended** items with labels like *"Paragraph 2"*, *"Paragraph 3"*, and *"Needs interpretation"*.
3. Go to **"My Policies"** in the sidebar:
   - View your active policies.
   - Click **"Add New Policy"** or toggle one off to demonstrate real-time policy customization.
4. Go to **"Analysis History"**:
   - See all uploaded agreements stored locally in SQLite with their conflict counts.
   - Click **"Open"** to reload any past review instantly without re-uploading.
   - Click **"Purge Expired"** or **"Delete All"** to demonstrate local privacy control and zero leftover files.

---

## 7. Known Limitations
1. **No OCR:** Scanned image-only PDFs without an extractable text layer cannot be parsed in this version. The app detects scanned PDFs (< 100 characters) and displays an explicit notification recommending OCR. An extension point stub `ocr_extension_stub` is documented in `services/document_reader.py`.
2. **Nemotron Local Mock Testing:** As stated in the hackathon rules, live Nemotron endpoints cannot be reached from this environment. The Nemotron integration is fully tested against local mock servers and strictly falls back to rule-based evaluation.
3. **Single-User Architecture:** ClauseLens binds to `127.0.0.1:5000` for a single local user without authentication.
4. **Regex-Based Detection:** Highly unusual phrasing or non-standard contractual jargon may trigger `review_recommended` instead of an automatic extraction, which is by design to prioritize human review over false certainty.
