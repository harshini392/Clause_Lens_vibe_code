"""ClauseLens Main Application Server.
Provides the REST API, security middleware, upload handling, and static file serving.
Local-only, privacy-first, zero cloud dependencies.
"""
import io
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from flask import Flask, request, jsonify, render_template, send_file, make_response, g
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

import config
import database
import services.document_reader as document_reader
import services.evidence_service as evidence_service
import services.clause_detector as clause_detector
import services.rule_engine as rule_engine
import services.report_service as report_service
import services.nemotron_service as nemotron_service
import services.default_policy_service as default_policy_service

# Logging setup: log system events only, NEVER document text
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("clauselens")

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH


# --- CSRF Protection Helper ---
CSRF_COOKIE_NAME = "clauselens_csrf"


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_hex(24)


def verify_csrf():
    """Verify CSRF token on mutating requests (POST, PUT, DELETE)."""
    if request.method in ("POST", "PUT", "DELETE"):
        # Check X-CSRF-Token header
        token_header = request.headers.get("X-CSRF-Token")
        token_cookie = request.cookies.get(CSRF_COOKIE_NAME)

        if not token_header or not token_cookie or not secrets.compare_digest(token_header, token_cookie):
            # Special case: allow if test client specifically bypasses or header matches
            return jsonify({
                "error": {
                    "code": "invalid_csrf_token",
                    "message": "Missing or invalid CSRF token. Request rejected."
                }
            }), 403
    return None


@app.before_request
def before_request_handler():
    """Run security checks before every request."""
    # CSRF verification
    csrf_err = verify_csrf()
    if csrf_err:
        return csrf_err


@app.after_request
def after_request_handler(response):
    """Enforce strict security and privacy headers on all responses."""
    # Content-Security-Policy: no inline scripts
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"

    # Disable caching for all API endpoints
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

    return response


# --- Error Handlers (Strict JSON Error Shapes) ---

@app.errorhandler(413)
def handle_413(e):
    return jsonify({
        "error": {
            "code": "file_too_large",
            "message": f"File size exceeds the maximum allowed upload limit of {config.MAX_UPLOAD_MB}MB."
        }
    }), 413


@app.errorhandler(404)
def handle_404(e):
    return jsonify({
        "error": {
            "code": "not_found",
            "message": "The requested resource was not found."
        }
    }), 404


@app.errorhandler(405)
def handle_405(e):
    return jsonify({
        "error": {
            "code": "method_not_allowed",
            "message": "The HTTP method is not allowed for this endpoint."
        }
    }), 405


@app.errorhandler(415)
def handle_415(e):
    return jsonify({
        "error": {
            "code": "unsupported_media_type",
            "message": "Unsupported file type. Only PDF and DOCX files are allowed."
        }
    }), 415


@app.errorhandler(Exception)
def handle_generic_exception(e):
    if isinstance(e, document_reader.DocumentReaderError):
        return jsonify({
            "error": {
                "code": e.code,
                "message": e.message
            }
        }), e.status_code

    if isinstance(e, HTTPException):
        return jsonify({
            "error": {
                "code": e.name.lower().replace(" ", "_"),
                "message": e.description
            }
        }), e.code

    logger.error("Unhandled server exception: %s", type(e).__name__)
    return jsonify({
        "error": {
            "code": "internal_server_error",
            "message": "An internal server error occurred while processing your request."
        }
    }), 500


# --- View Routes ---

@app.route("/")
def index():
    """Serve the single-page application and set CSRF cookie if absent."""
    resp = make_response(render_template("index.html"))
    if not request.cookies.get(CSRF_COOKIE_NAME):
        token = generate_csrf_token()
        resp.set_cookie(CSRF_COOKIE_NAME, token, httponly=False, samesite="Strict")
    return resp


# --- API Routes ---

@app.route("/api/health", methods=["GET"])
def health():
    """System health check and configuration overview."""
    nemotron_configured = nemotron_service.is_nemotron_configured()
    return jsonify({
        "status": "healthy",
        "version": config.APP_VERSION,
        "nemotron": {
            "configured": nemotron_configured,
            "enabled_by_default": config.NEMOTRON_ENABLED,
            "reachable": None
        },
        "retention_days": config.RETENTION_DAYS
    })


@app.route("/api/csrf", methods=["GET"])
def get_csrf():
    """Return a CSRF token for the frontend and set cookie."""
    token = request.cookies.get(CSRF_COOKIE_NAME) or generate_csrf_token()
    resp = make_response(jsonify({"token": token}))
    resp.set_cookie(CSRF_COOKIE_NAME, token, httponly=False, samesite="Strict")
    return resp


# --- Policies API ---

def validate_policy_payload(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validate policy creation and update payloads."""
    name = str(data.get("name", "")).strip()
    if not name or len(name) > 120:
        return False, "Policy name must be between 1 and 120 characters.", {}

    p_type = str(data.get("type", "")).strip().lower()
    if p_type not in ("payment", "renewal", "liability", "jurisdiction"):
        return False, "Policy type must be one of: payment, renewal, liability, jurisdiction.", {}

    mode = str(data.get("mode", "structured")).strip().lower()
    if mode not in ("structured", "free_text"):
        return False, "Policy mode must be 'structured' or 'free_text'.", {}

    params = data.get("params", {})
    if not isinstance(params, dict):
        return False, "Policy params must be an object.", {}

    if mode == "structured":
        if p_type == "payment":
            max_days = params.get("max_payment_days")
            if not isinstance(max_days, int) or max_days < 1 or max_days > 3650:
                return False, "max_payment_days must be an integer between 1 and 3650.", {}
        elif p_type == "renewal":
            if "auto_renewal_prohibited" not in params or not isinstance(params["auto_renewal_prohibited"], bool):
                return False, "auto_renewal_prohibited must be a boolean.", {}
            max_notice = params.get("max_notice_days")
            if max_notice is not None and (not isinstance(max_notice, int) or max_notice < 1 or max_notice > 365):
                return False, "max_notice_days must be null or an integer between 1 and 365.", {}
        elif p_type == "liability":
            rule = params.get("rule")
            if rule not in ("cap_not_exceed_fees", "no_unlimited"):
                return False, "Liability rule must be 'cap_not_exceed_fees' or 'no_unlimited'.", {}
        elif p_type == "jurisdiction":
            approved = params.get("approved")
            if not isinstance(approved, list) or not approved or not all(isinstance(x, str) and x.strip() for x in approved):
                return False, "approved must be a non-empty list of non-empty strings.", {}

    explanation = str(data.get("explanation", "")).strip()
    enabled = 1 if bool(data.get("enabled", True)) else 0

    sanitized = {
        "name": name,
        "type": p_type,
        "category": p_type,
        "mode": mode,
        "params": params,
        "params_json": json.dumps(params),
        "explanation": explanation,
        "enabled": enabled
    }
    return True, None, sanitized


@app.route("/api/policies", methods=["GET"])
def list_policies():
    """List all stored user policies."""
    conn = database.get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM policies ORDER BY id ASC;")
        rows = cur.fetchall()
        policies = []
        for r in rows:
            p_dict = dict(r)
            try:
                p_dict["params"] = json.loads(p_dict.get("params_json", "{}"))
            except Exception:
                p_dict["params"] = {}
            policies.append(p_dict)
        return jsonify(policies)
    finally:
        conn.close()


@app.route("/api/policies", methods=["POST"])
def create_policy():
    """Create a new policy."""
    data = request.get_json(silent=True) or {}
    is_valid, err_msg, clean = validate_policy_payload(data)
    if not is_valid:
        return jsonify({"error": {"code": "invalid_parameters", "message": err_msg}}), 422

    now_iso = datetime.now(timezone.utc).isoformat()
    conn = database.get_db()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO policies (name, type, category, mode, params_json, explanation, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                clean["name"], clean["type"], clean["category"], clean["mode"],
                clean["params_json"], clean["explanation"], clean["enabled"],
                now_iso, now_iso
            ))
            new_id = cur.lastrowid
            cur.execute("SELECT * FROM policies WHERE id = ?;", (new_id,))
            created = dict(cur.fetchone())
            created["params"] = clean["params"]
        return jsonify(created), 201
    finally:
        conn.close()


@app.route("/api/policies/<int:policy_id>", methods=["PUT"])
def update_policy(policy_id: int):
    """Update an existing policy."""
    data = request.get_json(silent=True) or {}
    is_valid, err_msg, clean = validate_policy_payload(data)
    if not is_valid:
        return jsonify({"error": {"code": "invalid_parameters", "message": err_msg}}), 422

    now_iso = datetime.now(timezone.utc).isoformat()
    conn = database.get_db()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM policies WHERE id = ?;", (policy_id,))
            if not cur.fetchone():
                return jsonify({"error": {"code": "not_found", "message": f"Policy #{policy_id} not found."}}), 404

            cur.execute("""
                UPDATE policies
                SET name = ?, type = ?, category = ?, mode = ?, params_json = ?, explanation = ?, enabled = ?, updated_at = ?
                WHERE id = ?;
            """, (
                clean["name"], clean["type"], clean["category"], clean["mode"],
                clean["params_json"], clean["explanation"], clean["enabled"],
                now_iso, policy_id
            ))
            cur.execute("SELECT * FROM policies WHERE id = ?;", (policy_id,))
            updated = dict(cur.fetchone())
            updated["params"] = clean["params"]
        return jsonify(updated)
    finally:
        conn.close()


@app.route("/api/policies/<int:policy_id>", methods=["DELETE"])
def delete_policy(policy_id: int):
    """Delete a policy by ID."""
    conn = database.get_db()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM policies WHERE id = ?;", (policy_id,))
            if cur.rowcount == 0:
                return jsonify({"error": {"code": "not_found", "message": f"Policy #{policy_id} not found."}}), 404
        return jsonify({"deleted": True, "id": policy_id})
    finally:
        conn.close()


@app.route("/api/policies/seed_examples", methods=["POST"])
def seed_policies():
    """Reset / seed demo policies."""
    count = database.seed_demo_policies(overwrite=True)
    return jsonify({"seeded": True, "count": count})


# --- Domain and Profile Discovery APIs ---

@app.route("/api/domains", methods=["GET"])
def get_domains():
    """Return supported document domains and dependent document types."""
    return jsonify({
        "domains": default_policy_service.get_supported_domains(),
        "authority_domains": default_policy_service.AUTHORITY_DOMAINS
    })


@app.route("/api/default-policies", methods=["GET"])
def get_default_policies():
    """Return default policy profile checks for the specified domain and document type."""
    domain = request.args.get("domain", "").strip()
    document_type = request.args.get("document_type", "").strip()
    jurisdiction = request.args.get("jurisdiction", "India").strip() or "India"

    if not domain or not document_type:
        return jsonify({
            "error": {
                "code": "missing_parameters",
                "message": "Both 'domain' and 'document_type' query parameters are required."
            }
        }), 400

    if not default_policy_service.is_valid_domain_and_doc_type(domain, document_type):
        return jsonify({
            "error": {
                "code": "invalid_domain_configuration",
                "message": f"Unsupported document domain '{domain}' or document type '{document_type}'."
            }
        }), 422

    policies = default_policy_service.get_default_policies_for_profile(domain, document_type, jurisdiction)
    return jsonify({
        "domain": domain,
        "document_type": document_type,
        "jurisdiction": jurisdiction,
        "policies": policies
    })


# --- Contract Analysis Endpoint ---

@app.route("/api/analyze", methods=["POST"])
def analyze_contract():
    """Upload and analyze a contract file against default profile policies and user policies."""
    if "file" not in request.files:
        return jsonify({"error": {"code": "missing_file", "message": "No file part in upload request."}}), 400

    uploaded_file = request.files["file"]
    raw_filename = uploaded_file.filename or ""
    if not raw_filename:
        return jsonify({"error": {"code": "empty_filename", "message": "No file selected for upload."}}), 400

    file_bytes = uploaded_file.read()
    if not file_bytes or len(file_bytes) == 0:
        return jsonify({"error": {"code": "empty_file", "message": "Uploaded file is empty."}}), 400

    # Validate file format and magic bytes
    try:
        file_type = document_reader.validate_file_bytes(file_bytes, raw_filename)
    except document_reader.DocumentReaderError as de:
        return jsonify({"error": {"code": de.code, "message": de.message}}), de.status_code

    # Read and validate domain configuration
    raw_domain = request.form.get("domain", "").strip()
    raw_doc_type = request.form.get("document_type", "").strip()
    jurisdiction = request.form.get("jurisdiction", "India").strip() or "India"
    issuing_authority = request.form.get("issuing_authority", "").strip()
    deselected_keys_str = request.form.get("deselected_default_keys", "").strip()

    deselected_keys = []
    if deselected_keys_str:
        try:
            if deselected_keys_str.startswith("["):
                deselected_keys = json.loads(deselected_keys_str)
            else:
                deselected_keys = [k.strip() for k in deselected_keys_str.split(",") if k.strip()]
        except Exception:
            deselected_keys = [k.strip() for k in deselected_keys_str.split(",") if k.strip()]

    # If domain/document_type are provided, validate strictly; if omitted (legacy test calls), evaluate user policies only
    if raw_domain or raw_doc_type:
        if not default_policy_service.is_valid_domain_and_doc_type(raw_domain, raw_doc_type):
            return jsonify({
                "error": {
                    "code": "invalid_domain_configuration",
                    "message": f"Unsupported document domain '{raw_domain}' or document type '{raw_doc_type}'. Please select a valid profile."
                }
            }), 422
        domain = raw_domain
        document_type = raw_doc_type
        has_domain_profile = True
    else:
        domain = "General Contracts"
        document_type = "Custom Policy Evaluation"
        has_domain_profile = False

    # Validate requested policy IDs if provided
    selected_policy_ids_str = request.form.get("policy_ids")
    conn = database.get_db()
    try:
        cur = conn.cursor()
        if selected_policy_ids_str:
            try:
                selected_ids = [int(x.strip()) for x in selected_policy_ids_str.split(",") if x.strip()]
            except ValueError:
                return jsonify({"error": {"code": "invalid_policy_id", "message": "Policy IDs must be integers."}}), 422

            if not selected_ids:
                return jsonify({"error": {"code": "invalid_policy_id", "message": "No valid policy IDs provided."}}), 422

            # Query all selected policies
            placeholders = ",".join("?" for _ in selected_ids)
            cur.execute(f"SELECT * FROM policies WHERE id IN ({placeholders});", selected_ids)
            found_policies = [dict(r) for r in cur.fetchall()]
            found_id_map = {p["id"]: p for p in found_policies}

            # Must exist and be enabled
            for pid in selected_ids:
                if pid not in found_id_map:
                    return jsonify({"error": {"code": "invalid_policy_id", "message": f"Policy ID {pid} does not exist."}}), 422
                if not found_id_map[pid].get("enabled", 1):
                    return jsonify({"error": {"code": "invalid_policy_id", "message": f"Policy ID {pid} is disabled."}}), 422

            active_policies = found_policies
        else:
            # Default: all enabled policies
            cur.execute("SELECT * FROM policies WHERE enabled = 1;")
            active_policies = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    use_nemotron_opt_in = request.form.get("use_nemotron", "false").lower() in ("true", "1", "yes")

    # Merge default policies and user policies
    if has_domain_profile:
        merged_policies = default_policy_service.merge_policies(
            domain=domain,
            document_type=document_type,
            jurisdiction=jurisdiction,
            issuing_authority=issuing_authority,
            user_policies=active_policies,
            deselected_default_keys=deselected_keys
        )
    else:
        merged_policies = list(active_policies)

    # Secure temporary storage
    display_name = document_reader.sanitize_filename(raw_filename)
    temp_filename = f"{uuid.uuid4().hex}.{file_type}"
    temp_path = config.TEMP_UPLOAD_DIR / temp_filename

    analysis_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    expires_at_iso = (now + timedelta(days=config.RETENTION_DAYS)).isoformat()

    try:
        temp_path.write_bytes(file_bytes)

        # Extract text units
        if file_type == "pdf":
            raw_units, extraction_status, count, text_length = document_reader.extract_pdf_units(str(temp_path))
        else:
            raw_units, extraction_status, count, text_length = document_reader.extract_docx_units(str(temp_path))

        # Check for scanned PDF
        if extraction_status == "scanned_no_text":
            scanned_msg = "This PDF appears to be scanned images with no extractable text. OCR is required and is not enabled in this version."
            # Save analysis with scanned status and empty findings
            conn = database.get_db()
            try:
                with conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO analyses (
                            id, filename, file_type, page_count_or_paragraph_count, text_length,
                            extraction_status, nemotron_used, nemotron_note, policies_snapshot_json,
                            created_at, expires_at, domain, document_type, jurisdiction, issuing_authority
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        analysis_id, display_name, file_type, count, 0,
                        "scanned_no_text", 0, "OCR is required and not enabled.",
                        json.dumps({
                            "domain": domain,
                            "document_type": document_type,
                            "jurisdiction": jurisdiction,
                            "issuing_authority": issuing_authority,
                            "profile_version": default_policy_service.PROFILE_VERSION,
                            "policies": []
                        }),
                        now_iso, expires_at_iso,
                        domain, document_type, jurisdiction, issuing_authority
                    ))
            finally:
                conn.close()

            return jsonify({
                "analysis_id": analysis_id,
                "document": {
                    "filename": display_name,
                    "file_type": file_type,
                    "extraction_status": "scanned_no_text",
                    "message": scanned_msg,
                    "page_count_or_paragraph_count": count,
                    "text_length": 0
                },
                "profile": {
                    "domain": domain,
                    "document_type": document_type,
                    "jurisdiction": jurisdiction,
                    "issuing_authority": issuing_authority
                },
                "nemotron": {
                    "requested": use_nemotron_opt_in,
                    "used": False,
                    "note": "Document contained no extractable text layer."
                },
                "summary": {
                    "potential_conflicts": 0,
                    "review_recommended": 0,
                    "no_conflict_detected": 0
                },
                "findings": []
            })

        # Build evidence segments and assign deterministic ev_0001 IDs
        segments = evidence_service.build_segments(raw_units, analysis_id)
        segments_by_ev_id = {s["evidence_id"]: s for s in segments}

        # Detect clauses
        detected_clauses = clause_detector.detect_clauses_in_segments(segments, analysis_id)

        # Nemotron optional interpretation (P2)
        nemotron_used = False
        nemotron_note = "Advanced interpretation was not used. Results are rule-based."

        if use_nemotron_opt_in:
            if nemotron_service.is_nemotron_configured():
                # Identify ambiguous segments
                ambiguous_ev_ids = {cl["evidence_id"] for cl in detected_clauses if cl.get("confidence") != "high"}
                ambiguous_segs = [s for s in segments if s["evidence_id"] in ambiguous_ev_ids]
                high_conf_facts = {cl["category"]: cl["facts"] for cl in detected_clauses if cl.get("confidence") == "high"}

                success, refined, note = nemotron_service.call_nemotron_interpret(ambiguous_segs, high_conf_facts)
                nemotron_used = success
                nemotron_note = note
                if success and refined:
                    for ref_item in refined:
                        detected_clauses.append({
                            "analysis_id": analysis_id,
                            "evidence_id": ref_item["evidence_ids"][0],
                            "category": ref_item["clause_type"],
                            "facts": ref_item["facts"],
                            "confidence": "medium",
                            "source": "nemotron",
                            "review_status": "unreviewed"
                        })
            else:
                nemotron_note = "Nemotron service is not configured or disabled in environment."

        # Evaluate deterministic rules against merged policies
        findings = rule_engine.evaluate_rules(
            detected_clauses, merged_policies, segments_by_ev_id, analysis_id, segments=segments
        )

        # Persist everything atomically to SQLite
        policies_snapshot_payload = {
            "domain": domain,
            "document_type": document_type,
            "jurisdiction": jurisdiction,
            "issuing_authority": issuing_authority,
            "profile_version": default_policy_service.PROFILE_VERSION,
            "policies": merged_policies
        }
        policies_snapshot_json = json.dumps(policies_snapshot_payload)

        conn = database.get_db()
        try:
            with conn:
                cur = conn.cursor()
                # 1. Insert analysis
                cur.execute("""
                    INSERT INTO analyses (
                        id, filename, file_type, page_count_or_paragraph_count, text_length,
                        extraction_status, nemotron_used, nemotron_note, policies_snapshot_json,
                        created_at, expires_at, domain, document_type, jurisdiction, issuing_authority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    analysis_id, display_name, file_type, count, text_length,
                    extraction_status, 1 if nemotron_used else 0, nemotron_note,
                    policies_snapshot_json, now_iso, expires_at_iso,
                    domain, document_type, jurisdiction, issuing_authority
                ))

                # 2. Insert segments
                evidence_service.save_segments(segments, conn)

                # 3. Insert detected clauses
                cur.executemany("""
                    INSERT INTO clauses (analysis_id, evidence_id, category, facts_json, confidence, source, review_status)
                    VALUES (:analysis_id, :evidence_id, :category, :facts_json, :confidence, :source, :review_status);
                """, [
                    {
                        "analysis_id": cl["analysis_id"],
                        "evidence_id": cl["evidence_id"],
                        "category": cl["category"],
                        "facts_json": json.dumps(cl["facts"]),
                        "confidence": cl["confidence"],
                        "source": cl["source"],
                        "review_status": cl["review_status"]
                    }
                    for cl in detected_clauses
                ])

                # 4. Insert findings
                cur.executemany("""
                    INSERT INTO findings (
                        analysis_id, policy_id, policy_snapshot_json, category, status,
                        title, explanation, quote, evidence_id, location_label, next_step,
                        manual_review, details_json
                    ) VALUES (
                        :analysis_id, :policy_id, :policy_snapshot_json, :category, :status,
                        :title, :explanation, :quote, :evidence_id, :location_label, :next_step,
                        :manual_review, :details_json
                    );
                """, findings)
        finally:
            conn.close()

        # Build response summary
        conflicts = sum(1 for f in findings if f["status"] == "potential_conflict")
        reviews = sum(1 for f in findings if f["status"] == "review_recommended")
        no_conflicts = sum(1 for f in findings if f["status"] == "no_conflict_detected")

        logger.info("Analysis completed for %s [ID: %s, Domain: %s, DocType: %s]: %d conflicts, %d reviews, %d no conflicts.",
                    display_name, analysis_id, domain, document_type, conflicts, reviews, no_conflicts)

        return jsonify({
            "analysis_id": analysis_id,
            "document": {
                "filename": display_name,
                "file_type": file_type,
                "extraction_status": extraction_status,
                "page_count_or_paragraph_count": count,
                "text_length": text_length
            },
            "profile": {
                "domain": domain,
                "document_type": document_type,
                "jurisdiction": jurisdiction,
                "issuing_authority": issuing_authority
            },
            "nemotron": {
                "requested": use_nemotron_opt_in,
                "used": nemotron_used,
                "note": nemotron_note
            },
            "summary": {
                "potential_conflicts": conflicts,
                "review_recommended": reviews,
                "no_conflict_detected": no_conflicts
            },
            "findings": findings
        })

    finally:
        # Guarantee temp upload file is deleted in finally block
        if temp_path.exists():
            import gc
            import time
            gc.collect()
            for attempt in range(4):
                try:
                    temp_path.unlink()
                    break
                except Exception as e:
                    if attempt == 3:
                        logger.warning("Failed to remove temp file %s: %s", temp_path, e)
                    else:
                        time.sleep(0.05)
                        gc.collect()


# --- History & Review APIs ---

@app.route("/api/history", methods=["GET"])
def get_history():
    """Retrieve analysis history."""
    conn = database.get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.*,
                   SUM(CASE WHEN f.status = 'potential_conflict' THEN 1 ELSE 0 END) as conflicts_count,
                   SUM(CASE WHEN f.status = 'review_recommended' THEN 1 ELSE 0 END) as reviews_count,
                   SUM(CASE WHEN f.status = 'no_conflict_detected' THEN 1 ELSE 0 END) as no_conflicts_count
            FROM analyses a
            LEFT JOIN findings f ON a.id = f.analysis_id
            GROUP BY a.id
            ORDER BY a.created_at DESC;
        """)
        rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "filename": r["filename"],
                "file_type": r["file_type"],
                "domain": r["domain"],
                "document_type": r["document_type"],
                "jurisdiction": r["jurisdiction"],
                "issuing_authority": r["issuing_authority"],
                "page_count_or_paragraph_count": r["page_count_or_paragraph_count"],
                "text_length": r["text_length"],
                "extraction_status": r["extraction_status"],
                "nemotron_used": bool(r["nemotron_used"]),
                "created_at": r["created_at"],
                "expires_at": r["expires_at"],
                "summary": {
                    "potential_conflicts": r["conflicts_count"] or 0,
                    "review_recommended": r["reviews_count"] or 0,
                    "no_conflict_detected": r["no_conflicts_count"] or 0
                }
            })
        return jsonify(items)
    finally:
        conn.close()


@app.route("/api/history/<analysis_id>", methods=["GET"])
def get_analysis_details(analysis_id: str):
    """Retrieve full analysis payload including all stored segments and findings."""
    conn = database.get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM analyses WHERE id = ?;", (analysis_id,))
        analysis_row = cur.fetchone()
        if not analysis_row:
            return jsonify({"error": {"code": "not_found", "message": f"Analysis '{analysis_id}' not found."}}), 404

        analysis = dict(analysis_row)
        try:
            raw_snap = json.loads(analysis.get("policies_snapshot_json", "[]"))
            if isinstance(raw_snap, dict) and "policies" in raw_snap:
                analysis["policies_snapshot"] = raw_snap["policies"]
                analysis["domain"] = analysis.get("domain") or raw_snap.get("domain")
                analysis["document_type"] = analysis.get("document_type") or raw_snap.get("document_type")
                analysis["jurisdiction"] = analysis.get("jurisdiction") or raw_snap.get("jurisdiction")
                analysis["issuing_authority"] = analysis.get("issuing_authority") or raw_snap.get("issuing_authority")
            else:
                analysis["policies_snapshot"] = raw_snap
        except Exception:
            analysis["policies_snapshot"] = []

        # Segments in document order
        cur.execute("SELECT evidence_id, location_type, page_number, paragraph_index, char_start, char_end, text FROM segments WHERE analysis_id = ? ORDER BY id ASC;", (analysis_id,))
        segments = [dict(r) for r in cur.fetchall()]

        # Findings
        cur.execute("SELECT * FROM findings WHERE analysis_id = ? ORDER BY id ASC;", (analysis_id,))
        findings = []
        for r in cur.fetchall():
            f_dict = dict(r)
            try:
                f_dict["details"] = json.loads(f_dict.get("details_json", "{}"))
            except Exception:
                f_dict["details"] = {}
            findings.append(f_dict)

        summary = {
            "potential_conflicts": sum(1 for f in findings if f["status"] == "potential_conflict"),
            "review_recommended": sum(1 for f in findings if f["status"] == "review_recommended"),
            "no_conflict_detected": sum(1 for f in findings if f["status"] == "no_conflict_detected")
        }

        return jsonify({
            "analysis": analysis,
            "segments": segments,
            "findings": findings,
            "summary": summary
        })
    finally:
        conn.close()


@app.route("/api/history/<analysis_id>", methods=["DELETE"])
def delete_single_history(analysis_id: str):
    """Delete an analysis and cascade delete its segments, clauses, and findings."""
    success = database.delete_analysis(analysis_id)
    if not success:
        return jsonify({"error": {"code": "not_found", "message": f"Analysis '{analysis_id}' not found."}}), 404
    return jsonify({"deleted": True, "analysis_id": analysis_id})


@app.route("/api/history", methods=["DELETE"])
def delete_all_history():
    """Delete all analyses from history."""
    deleted_count = database.delete_all_analyses()
    return jsonify({"deleted_all": True, "count": deleted_count})


@app.route("/api/retention/purge", methods=["POST"])
def manual_retention_purge():
    """Manually purge records older than RETENTION_DAYS."""
    count = database.purge_expired_analyses()
    return jsonify({"purged": True, "count": count})


# --- Dashboard Stats API ---

@app.route("/api/stats", methods=["GET"])
def get_dashboard_stats():
    """Retrieve dashboard stats computed directly from database records."""
    conn = database.get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total_docs FROM analyses;")
        total_docs = cur.fetchone()["total_docs"]

        cur.execute("SELECT COUNT(*) as total_conflicts FROM findings WHERE status = 'potential_conflict';")
        total_conflicts = cur.fetchone()["total_conflicts"]

        cur.execute("SELECT COUNT(*) as total_manual FROM findings WHERE manual_review = 1;")
        total_manual = cur.fetchone()["total_manual"]

        cur.execute("""
            SELECT a.id, a.filename, a.file_type, a.created_at,
                   SUM(CASE WHEN f.status = 'potential_conflict' THEN 1 ELSE 0 END) as conflicts_count,
                   SUM(CASE WHEN f.status = 'review_recommended' THEN 1 ELSE 0 END) as reviews_count
            FROM analyses a
            LEFT JOIN findings f ON a.id = f.analysis_id
            GROUP BY a.id
            ORDER BY a.created_at DESC
            LIMIT 5;
        """)
        recent_rows = cur.fetchall()
        recent = []
        for r in recent_rows:
            recent.append({
                "id": r["id"],
                "filename": r["filename"],
                "file_type": r["file_type"],
                "created_at": r["created_at"],
                "conflicts": r["conflicts_count"] or 0,
                "reviews": r["reviews_count"] or 0
            })

        return jsonify({
            "documents_analyzed": total_docs,
            "policy_conflicts": total_conflicts,
            "manual_reviews": total_manual,
            "recent": recent
        })
    finally:
        conn.close()


# --- PDF Report Download API ---

@app.route("/api/reports/<analysis_id>", methods=["GET"])
def download_pdf_report(analysis_id: str):
    """Generate and return a PDF report from stored database records without re-uploading."""
    conn = database.get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM analyses WHERE id = ?;", (analysis_id,))
        analysis_row = cur.fetchone()
        if not analysis_row:
            return jsonify({"error": {"code": "not_found", "message": f"Analysis '{analysis_id}' not found."}}), 404

        analysis = dict(analysis_row)
        try:
            raw_snap = json.loads(analysis.get("policies_snapshot_json", "[]"))
            if isinstance(raw_snap, dict) and "policies" in raw_snap:
                policies = raw_snap["policies"]
                analysis["domain"] = analysis.get("domain") or raw_snap.get("domain")
                analysis["document_type"] = analysis.get("document_type") or raw_snap.get("document_type")
                analysis["jurisdiction"] = analysis.get("jurisdiction") or raw_snap.get("jurisdiction")
                analysis["issuing_authority"] = analysis.get("issuing_authority") or raw_snap.get("issuing_authority")
            else:
                policies = raw_snap
        except Exception:
            policies = []

        cur.execute("SELECT * FROM findings WHERE analysis_id = ? ORDER BY id ASC;", (analysis_id,))
        findings = [dict(r) for r in cur.fetchall()]

        pdf_bytes = report_service.generate_pdf_report(analysis, findings, policies)

        # Sanitize filename for download header
        safe_base = secure_filename(analysis.get("filename", "contract")).replace(".", "_")
        pdf_filename = f"ClauseLens_Report_{safe_base}.pdf"

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=pdf_filename
        )
    finally:
        conn.close()


# --- Sample Contracts Serving for Quick Demo ---

@app.route("/sample_contracts/<path:filename>", methods=["GET"])
def get_sample_contract_file(filename: str):
    """Serve sample contracts for quick demo loading."""
    safe_name = os.path.basename(filename)
    sample_path = Path(__file__).parent / "sample_contracts" / safe_name
    if not sample_path.exists() or not sample_path.is_file():
        return jsonify({"error": {"code": "not_found", "message": "Sample contract not found."}}), 404
    return send_file(sample_path)


# --- Application Startup Hook ---

def create_app():
    """Application factory for development and testing."""
    database.init_db()
    # Check if policies table is empty, seed demo set
    database.seed_demo_policies()
    return app


if __name__ == "__main__":
    database.init_db()
    database.seed_demo_policies()
    print(f"ClauseLens starting on http://{config.HOST}:{config.PORT} (Debug: {config.DEBUG})")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
