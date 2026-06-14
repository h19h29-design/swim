from __future__ import annotations

from swimdash.parser import parse_swim_title
from swimdash.record_resolver import (
    BODY_SOURCE,
    CANDIDATE_CONFLICT,
    OCR_LOW_CONFIDENCE,
    OCR_SOURCE,
    OUT_OF_RANGE,
    resolve_record_candidates,
)


def test_resolver_accepts_title_when_candidates_agree():
    parsed = parse_swim_title("1500 / 42:30")

    result = resolve_record_candidates(
        title_parse=parsed,
        body_candidate={"distance_m": 1500, "duration_seconds": 2550, "total_time_text": "42:30", "confidence": 0.9},
        ocr_enabled=False,
    )

    assert result.include is True
    assert result.source == "title_format"
    assert result.resolved_source == "mixed"
    assert result.review_needed is False


def test_resolver_prefers_title_when_candidates_conflict():
    parsed = parse_swim_title("1500 / 42:30")

    result = resolve_record_candidates(
        title_parse=parsed,
        body_candidate={"distance_m": 1200, "duration_seconds": 2550, "total_time_text": "42:30", "confidence": 0.9},
        ocr_enabled=False,
    )

    assert result.include is True
    assert result.review_needed is False
    assert result.source == "title_format"
    assert result.resolved_source == "title"
    assert CANDIDATE_CONFLICT in result.warning_codes


def test_resolver_marks_agreement_as_mixed_even_with_other_conflict():
    parsed = parse_swim_title("1500 / 42:30")

    result = resolve_record_candidates(
        title_parse=parsed,
        body_candidate={"distance_m": 1500, "duration_seconds": 2550, "total_time_text": "42:30", "confidence": 0.9},
        ocr_candidate={"distance_m": 1200, "duration_seconds": 2550, "total_time_text": "42:30", "confidence": 0.95},
        ocr_enabled=True,
    )

    assert result.include is True
    assert result.source == "title_format"
    assert result.resolved_source == "mixed"
    assert CANDIDATE_CONFLICT in result.warning_codes


def test_resolver_uses_body_when_body_and_ocr_agree_without_title():
    parsed = parse_swim_title("오수완")

    result = resolve_record_candidates(
        title_parse=parsed,
        body_candidate={"distance_m": 1500, "duration_seconds": 2550, "total_time_text": "42:30", "confidence": 0.9},
        ocr_candidate={"distance_m": 1500, "duration_seconds": 2550, "total_time_text": "42:30", "confidence": 0.94},
        ocr_enabled=True,
    )

    assert result.include is True
    assert result.source == BODY_SOURCE
    assert result.resolved_source == "mixed"


def test_resolver_uses_body_when_title_is_missing():
    parsed = parse_swim_title("오수완")

    result = resolve_record_candidates(
        title_parse=parsed,
        body_candidate={"distance_m": 1500, "duration_seconds": 2550, "total_time_text": "42:30", "confidence": 0.9},
        ocr_enabled=False,
    )

    assert result.include is True
    assert result.source == BODY_SOURCE
    assert result.resolved_source == "body"
    assert result.distance_m == 1500


def test_resolver_uses_high_confidence_ocr_when_it_is_the_only_complete_candidate():
    parsed = parse_swim_title("오수완")

    result = resolve_record_candidates(
        title_parse=parsed,
        ocr_candidate={
            "distance_m": 1500,
            "duration_seconds": 2550,
            "total_time_text": "42:30",
            "confidence": 0.92,
            "model": "test-model",
            "cache_key": "abc",
        },
        ocr_enabled=True,
        ocr_min_confidence=0.85,
    )

    assert result.include is True
    assert result.source == OCR_SOURCE
    assert result.source_candidates["ocr"]["cache_key"] == "abc"


def test_resolver_rejects_low_confidence_ocr_only_candidate():
    parsed = parse_swim_title("오수완")

    result = resolve_record_candidates(
        title_parse=parsed,
        ocr_candidate={"distance_m": 1500, "duration_seconds": 2550, "confidence": 0.4},
        ocr_enabled=True,
        ocr_min_confidence=0.85,
    )

    assert result.include is False
    assert result.review_reason_code == OCR_LOW_CONFIDENCE


def test_resolver_sends_out_of_range_candidates_to_review():
    parsed = parse_swim_title("100 / 42:30")

    result = resolve_record_candidates(title_parse=parsed, ocr_enabled=False)

    assert result.include is False
    assert result.review_reason_code == OUT_OF_RANGE
