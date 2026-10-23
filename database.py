"""SQLite persistence and schema management for ClauseLens."""
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import config

SCHEMA_VERSION = 2


def get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Obtain a SQLite connection with foreign keys enabled and Row factory."""
    path = db_path or config.DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Safely apply backward-compatible schema migrations."""
    cur = conn.cursor()

    # 1. Safely add domain-specific columns to analyses table if missing
    cur.execute("PRAGMA table_info(analyses);")
    existing_analyses_cols = {r["name"] for r in cur.fetchall()}
    analyses_new_cols = [
        ("domain", "TEXT"),
        ("document_type", "TEXT"),
        ("jurisdiction", "TEXT"),
        ("issuing_authority", "TEXT")
    ]
    for col_name, col_type in analyses_new_cols:
        if col_name not in existing_analyses_cols:
            conn.execute(f"ALTER TABLE analyses ADD COLUMN {col_name} {col_type};")

    # 2. Check clauses table constraint
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='clauses';")
    clause_row = cur.fetchone()
    if clause_row and "CHECK(category IN" in clause_row["sql"]:
        # Migrate clauses table to allow extensible domain categories
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute("ALTER TABLE clauses RENAME TO clauses_old;")
        conn.execute("""
            CREATE TABLE clauses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                evidence_id TEXT NOT NULL,
                category TEXT NOT NULL,
                facts_json TEXT NOT NULL,
                confidence TEXT NOT NULL CHECK(confidence IN ('high', 'medium', 'low')),
                source TEXT NOT NULL CHECK(source IN ('rule', 'nemotron')),
                review_status TEXT NOT NULL DEFAULT 'unreviewed'
            );
        """)
        conn.execute("""
            INSERT INTO clauses (id, analysis_id, evidence_id, category, facts_json, confidence, source, review_status)
            SELECT id, analysis_id, evidence_id, category, facts_json, confidence, source, review_status
            FROM clauses_old;
        """)
        conn.execute("DROP TABLE clauses_old;")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clauses_analysis ON clauses(analysis_id);")
        conn.execute("PRAGMA foreign_keys = ON;")

    # 3. Create default_policies table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS default_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_key TEXT UNIQUE NOT NULL,
            domain TEXT NOT NULL,
            document_type TEXT NOT NULL,
            jurisdiction TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            parameters_json TEXT NOT NULL DEFAULT '{}',
            enabled_by_default INTEGER NOT NULL DEFAULT 1,
            requirement_level TEXT NOT NULL CHECK(requirement_level IN ('mandatory', 'recommended')),
            source_name TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            source_version TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_default_policies_domain_type ON default_policies(domain, document_type);")

    # Update schema version record
    cur.execute("UPDATE schema_version SET version = ?;", (SCHEMA_VERSION,))


def sync_default_policies_table(conn: sqlite3.Connection) -> int:
    """Synchronize default policies table from the default policy service catalog."""
    import services.default_policy_service as dps
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM default_policies;")
    existing_cnt = cur.fetchone()["cnt"]

    if existing_cnt == 0:
        for p in dps.DEFAULT_POLICY_CATALOG:
            doc_types = p.get("document_types", ["*"])
            doc_type_str = ",".join(doc_types)
            cur.execute("""
                INSERT OR IGNORE INTO default_policies (
                    policy_key, domain, document_type, jurisdiction, name, description,
                    category, rule_type, parameters_json, enabled_by_default,
                    requirement_level, source_name, source_url, source_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                p["policy_key"],
                p["domain"],
                doc_type_str,
                p.get("jurisdiction", "Any"),
                p["name"],
                p["description"],
                p["category"],
                p["rule_type"],
                json.dumps(p.get("parameters", {})),
                1 if p.get("enabled_by_default", True) else 0,
                p.get("requirement_level", "recommended"),
                p.get("source_name", ""),
                p.get("source_url", ""),
                p.get("source_version", ""),
                p.get("created_at", datetime.now(timezone.utc).isoformat()),
                p.get("updated_at", datetime.now(timezone.utc).isoformat())
            ))
        return len(dps.DEFAULT_POLICY_CATALOG)
    return 0


def init_db(db_path: Optional[str] = None) -> None:
    """Create tables if they do not exist and ensure schema version."""
    conn = get_db(db_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );
            """)

            cur = conn.cursor()
            cur.execute("SELECT version FROM schema_version LIMIT 1;")
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO schema_version (version) VALUES (?);", (SCHEMA_VERSION,))

            conn.execute("""
                CREATE TABLE IF NOT EXISTS policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('payment', 'renewal', 'liability', 'jurisdiction')),
                    category TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK(mode IN ('structured', 'free_text')),
                    params_json TEXT NOT NULL DEFAULT '{}',
                    explanation TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL CHECK(file_type IN ('pdf', 'docx')),
                    page_count_or_paragraph_count INTEGER NOT NULL,
                    text_length INTEGER NOT NULL,
                    extraction_status TEXT NOT NULL,
                    nemotron_used INTEGER NOT NULL DEFAULT 0,
                    nemotron_note TEXT,
                    policies_snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    domain TEXT,
                    document_type TEXT,
                    jurisdiction TEXT,
                    issuing_authority TEXT
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                    evidence_id TEXT NOT NULL,
                    location_type TEXT NOT NULL CHECK(location_type IN ('page', 'paragraph')),
                    page_number INTEGER,
                    paragraph_index INTEGER,
                    char_start INTEGER NOT NULL,
                    char_end INTEGER NOT NULL,
                    text TEXT NOT NULL
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS clauses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                    evidence_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    facts_json TEXT NOT NULL,
                    confidence TEXT NOT NULL CHECK(confidence IN ('high', 'medium', 'low')),
                    source TEXT NOT NULL CHECK(source IN ('rule', 'nemotron')),
                    review_status TEXT NOT NULL DEFAULT 'unreviewed'
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                    policy_id INTEGER,
                    policy_snapshot_json TEXT,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('potential_conflict', 'review_recommended', 'no_conflict_detected')),
                    title TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    location_label TEXT NOT NULL,
                    next_step TEXT NOT NULL,
                    manual_review INTEGER NOT NULL DEFAULT 0,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );
            """)

            # Indexes for efficient lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_segments_analysis ON segments(analysis_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_segments_evidence ON segments(analysis_id, evidence_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_clauses_analysis ON clauses(analysis_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_analysis ON findings(analysis_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analyses_expires ON analyses(expires_at);")

            # Apply migrations to existing databases
            _migrate_schema(conn)

            # Sync default policy catalog table
            sync_default_policies_table(conn)

        # Auto-purge expired records on startup
        purge_expired_analyses(conn)
    finally:
        conn.close()


def purge_expired_analyses(conn_or_path=None) -> int:
    """Purge analyses whose expires_at is past now. Returns number of purged analyses."""
    should_close = False
    if isinstance(conn_or_path, sqlite3.Connection):
        conn = conn_or_path
    else:
        conn = get_db(conn_or_path)
        should_close = True

    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM analyses WHERE expires_at < ?;", (now_iso,))
            rows = cur.fetchall()
            count = len(rows)
            if count > 0:
                cur.execute("DELETE FROM analyses WHERE expires_at < ?;", (now_iso,))
        return count
    finally:
        if should_close:
            conn.close()


def delete_analysis(analysis_id: str, db_path: Optional[str] = None) -> bool:
    """Delete a single analysis by ID, cascading to segments, clauses, and findings."""
    conn = get_db(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM analyses WHERE id = ?;", (analysis_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def delete_all_analyses(db_path: Optional[str] = None) -> int:
    """Delete all analyses from the database."""
    conn = get_db(db_path)
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM analyses;")
            return cur.rowcount
    finally:
        conn.close()


def get_demo_policies() -> List[Dict[str, Any]]:
    """Return the canonical demo policy set."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "name": "Maximum 30-Day Payment Term",
            "type": "payment",
            "category": "payment",
            "mode": "structured",
            "params_json": json.dumps({"max_payment_days": 30}),
            "explanation": "Invoices must be payable within a maximum of 30 days from receipt.",
            "enabled": 1,
            "created_at": now,
            "updated_at": now
        },
        {
            "name": "Prohibit Automatic Renewal",
            "type": "renewal",
            "category": "renewal",
            "mode": "structured",
            "params_json": json.dumps({"auto_renewal_prohibited": True, "max_notice_days": 30}),
            "explanation": "Contracts must not renew automatically without explicit written mutual agreement.",
            "enabled": 1,
            "created_at": now,
            "updated_at": now
        },
        {
            "name": "Liability Capped at Fees Paid",
            "type": "liability",
            "category": "liability",
            "mode": "structured",
            "params_json": json.dumps({"rule": "cap_not_exceed_fees"}),
            "explanation": "Total liability must be capped at fees paid under the agreement; unlimited liability is prohibited.",
            "enabled": 1,
            "created_at": now,
            "updated_at": now
        },
        {
            "name": "Approved Jurisdiction: India",
            "type": "jurisdiction",
            "category": "jurisdiction",
            "mode": "structured",
            "params_json": json.dumps({"approved": ["India", "Indian law", "Chennai", "Bengaluru", "Bangalore"]}),
            "explanation": "Governing law and jurisdiction must be within approved Indian courts or laws.",
            "enabled": 1,
            "created_at": now,
            "updated_at": now
        }
    ]


def seed_demo_policies(db_path: Optional[str] = None, overwrite: bool = False) -> int:
    """Seed demo policies if table is empty or overwrite is requested."""
    conn = get_db(db_path)
    try:
        with conn:
            cur = conn.cursor()
            if overwrite:
                cur.execute("DELETE FROM policies;")
            else:
                cur.execute("SELECT COUNT(*) as cnt FROM policies;")
                if cur.fetchone()["cnt"] > 0:
                    return 0

            demo_policies = get_demo_policies()
            for p in demo_policies:
                cur.execute("""
                    INSERT INTO policies (name, type, category, mode, params_json, explanation, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    p["name"], p["type"], p["category"], p["mode"],
                    p["params_json"], p["explanation"], p["enabled"],
                    p["created_at"], p["updated_at"]
                ))
            return len(demo_policies)
    finally:
        conn.close()
