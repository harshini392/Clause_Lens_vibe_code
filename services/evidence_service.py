"""Evidence Service for ClauseLens.
Handles conservative sentence segmentation, deterministic evidence ID assignment
(ev_0001, ev_0002, ...), character offset tracking, and database persistence/lookup.
"""
import re
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
import database

# Regex for sentence splitting that respects legal abbreviations and decimal numbering
# Negative lookbehinds for common abbreviations
ABBR_PATTERN = r"(?<!\bSec)(?<!\bSecs)(?<!\bNo)(?<!\bNos)(?<!\bArt)(?<!\bPara)(?<!\bInc)(?<!\bCorp)(?<!\bLtd)(?<!\bCo)(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bal)(?<!\bet al)(?<!\bJan)(?<!\bFeb)(?<!\bMar)(?<!\bApr)(?<!\bAug)(?<!\bSep)(?<!\bSept)(?<!\bOct)(?<!\bNov)(?<!\bDec)(?<!\bMr)(?<!\bMs)(?<!\bMrs)(?<!\bDr)(?<!\b\d)"

# Sentence terminator: period, question mark, or exclamation point followed by whitespace and a capital/quote/number/bracket
SPLIT_REGEX = re.compile(
    rf"{ABBR_PATTERN}(?:[\.!\?]+)(?=(?:\s+[\"\'\(\[]*[A-Z0-9])|(?:\s*\n)|$)"
)


def split_text_into_sentences(text: str) -> List[Tuple[int, int, str]]:
    """Split text into sentences while tracking exact (char_start, char_end, sentence_str) in the original text.
    Handles headings, numbered lists, blank lines, and normal sentences.
    """
    if not text or not text.strip():
        return []

    results: List[Tuple[int, int, str]] = []

    # First, split by prominent block breaks (newlines / paragraphs) to avoid cross-block spans
    # But preserve exact indices
    block_pattern = re.compile(r"(\r?\n\s*\r?\n|\r?\n(?=\s*(?:[A-Z0-9\(\[\*•\-]+[\.\)]|\d+\.)))")
    
    last_end = 0
    blocks: List[Tuple[int, int, str]] = []
    for match in block_pattern.finditer(text):
        m_start = match.start()
        if m_start > last_end:
            blocks.append((last_end, m_start, text[last_end:m_start]))
        last_end = match.end()
    if last_end < len(text):
        blocks.append((last_end, len(text), text[last_end:]))

    for b_start, b_end, block in blocks:
        stripped_block = block.strip()
        if not stripped_block:
            continue

        # Find sentence matches within the block
        curr_pos = 0
        matches = list(SPLIT_REGEX.finditer(block))
        if not matches:
            rel_start = block.find(stripped_block)
            abs_start = b_start + rel_start
            abs_end = abs_start + len(stripped_block)
            results.append((abs_start, abs_end, stripped_block))
            continue

        for m in matches:
            sentence_raw = block[curr_pos:m.end()]
            s_clean = sentence_raw.strip()
            if s_clean:
                rel_start = block.find(s_clean, curr_pos)
                if rel_start != -1:
                    abs_start = b_start + rel_start
                    abs_end = abs_start + len(s_clean)
                    results.append((abs_start, abs_end, s_clean))
            curr_pos = m.end()

        # Remainder of the block
        if curr_pos < len(block):
            remainder_raw = block[curr_pos:]
            rem_clean = remainder_raw.strip()
            if rem_clean:
                rel_start = block.find(rem_clean, curr_pos)
                if rel_start != -1:
                    abs_start = b_start + rel_start
                    abs_end = abs_start + len(rem_clean)
                    results.append((abs_start, abs_end, rem_clean))

    return results


def build_segments(raw_units: List[Dict[str, Any]], analysis_id: str) -> List[Dict[str, Any]]:
    """Convert raw page or paragraph units into deterministic sequential evidence segments.
    Evidence IDs are ev_0001, ev_0002, ... assigned in document order.
    """
    segments: List[Dict[str, Any]] = []
    evidence_counter = 1

    for unit in raw_units:
        loc_type = unit.get("location_type", "page")
        page_num = unit.get("page_number")
        para_idx = unit.get("paragraph_index")
        text = unit.get("text", "")

        sentences = split_text_into_sentences(text)
        if not sentences:
            # If text was non-empty whitespace or empty
            stripped = text.strip()
            if stripped:
                evidence_id = f"ev_{evidence_counter:04d}"
                segments.append({
                    "analysis_id": analysis_id,
                    "evidence_id": evidence_id,
                    "location_type": loc_type,
                    "page_number": page_num,
                    "paragraph_index": para_idx,
                    "char_start": 0,
                    "char_end": len(stripped),
                    "text": stripped
                })
                evidence_counter += 1
            continue

        for char_start, char_end, sent_text in sentences:
            evidence_id = f"ev_{evidence_counter:04d}"
            segments.append({
                "analysis_id": analysis_id,
                "evidence_id": evidence_id,
                "location_type": loc_type,
                "page_number": page_num,
                "paragraph_index": para_idx,
                "char_start": char_start,
                "char_end": char_end,
                "text": sent_text
            })
            evidence_counter += 1

    return segments


def save_segments(segments: List[Dict[str, Any]], conn: sqlite3.Connection) -> None:
    """Batch insert segments into SQLite database."""
    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO segments (analysis_id, evidence_id, location_type, page_number, paragraph_index, char_start, char_end, text)
        VALUES (:analysis_id, :evidence_id, :location_type, :page_number, :paragraph_index, :char_start, :char_end, :text);
    """, segments)


def get_segment_by_evidence_id(analysis_id: str, evidence_id: str, conn_or_path=None) -> Optional[Dict[str, Any]]:
    """Retrieve segment by analysis_id and evidence_id."""
    should_close = False
    if isinstance(conn_or_path, sqlite3.Connection):
        conn = conn_or_path
    else:
        conn = database.get_db(conn_or_path)
        should_close = True

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT evidence_id, location_type, page_number, paragraph_index, char_start, char_end, text
            FROM segments
            WHERE analysis_id = ? AND evidence_id = ?;
        """, (analysis_id, evidence_id))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def get_all_segments(analysis_id: str, conn_or_path=None) -> List[Dict[str, Any]]:
    """Retrieve all segments for an analysis in document order."""
    should_close = False
    if isinstance(conn_or_path, sqlite3.Connection):
        conn = conn_or_path
    else:
        conn = database.get_db(conn_or_path)
        should_close = True

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT evidence_id, location_type, page_number, paragraph_index, char_start, char_end, text
            FROM segments
            WHERE analysis_id = ?
            ORDER BY id ASC;
        """, (analysis_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        if should_close:
            conn.close()
