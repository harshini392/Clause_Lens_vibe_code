"""Tests for sentence segmentation, deterministic evidence ID assignment, and segment persistence."""
import pytest
import sqlite3
import services.evidence_service as evidence_service
import database


def test_sentence_splitting_abbreviations_and_decimals():
    text = (
        "Pursuant to Sec. 4.2 of the agreement, Acme Inc. shall pay No. 15 on invoice. "
        "The interest rate is 1.5% per month, e.g. for delayed remittance. "
        "This is the third sentence."
    )
    sentences = evidence_service.split_text_into_sentences(text)
    # Sec., Inc., No., 1.5%, e.g. must NOT cause sentence breaks!
    assert len(sentences) == 2 or len(sentences) == 3
    # Check that "Sec. 4.2" is kept intact inside the first sentence
    assert "Sec. 4.2 of the agreement" in sentences[0][2]
    # Check that "e.g." did not cause a split
    second_sent = sentences[1][2]
    assert "e.g." in second_sent or "1.5%" in second_sent


def test_build_segments_deterministic_ids():
    raw_units = [
        {
            "location_type": "page",
            "page_number": 1,
            "paragraph_index": None,
            "text": "First sentence of page one. Second sentence of page one."
        },
        {
            "location_type": "page",
            "page_number": 2,
            "paragraph_index": None,
            "text": "First sentence of page two. Second sentence of page two."
        }
    ]

    segments = evidence_service.build_segments(raw_units, "test-analysis-123")
    assert len(segments) == 4
    assert segments[0]["evidence_id"] == "ev_0001"
    assert segments[1]["evidence_id"] == "ev_0002"
    assert segments[2]["evidence_id"] == "ev_0003"
    assert segments[3]["evidence_id"] == "ev_0004"

    assert segments[0]["page_number"] == 1
    assert segments[2]["page_number"] == 2
    assert segments[0]["text"] == "First sentence of page one."


def test_segment_database_persistence_and_lookup(test_db):
    conn = database.get_db(test_db)
    analysis_id = "test-analysis-ev"

    # Insert parent analysis record
    with conn:
        conn.execute("""
            INSERT INTO analyses (id, filename, file_type, page_count_or_paragraph_count, text_length, extraction_status, policies_snapshot_json, created_at, expires_at)
            VALUES (?, 'test.pdf', 'pdf', 1, 100, 'success', '[]', '2026-01-01', '2026-02-01');
        """, (analysis_id,))

    raw_units = [{
        "location_type": "page",
        "page_number": 1,
        "paragraph_index": None,
        "text": "Payment within 30 days. Auto renewal is prohibited."
    }]
    segments = evidence_service.build_segments(raw_units, analysis_id)
    with conn:
        evidence_service.save_segments(segments, conn)

    # Lookup
    seg = evidence_service.get_segment_by_evidence_id(analysis_id, "ev_0001", conn)
    assert seg is not None
    assert seg["evidence_id"] == "ev_0001"
    assert "Payment within 30 days" in seg["text"]

    all_segs = evidence_service.get_all_segments(analysis_id, conn)
    assert len(all_segs) == 2
    conn.close()
