from __future__ import annotations

from swimdash.body_parser import (
    BODY_CANDIDATE_CONFLICT,
    BODY_PARSE_FAILED,
    BODY_PACE_CONFUSION,
    parse_swim_body,
)


def test_body_parser_extracts_labeled_meter_and_korean_duration():
    result = parse_swim_body("오늘 수영\n총거리 1,500m\n수영시간 42분 30초")

    assert result.complete is True
    assert result.distance_m == 1500
    assert result.total_time_text == "42분 30초"
    assert result.total_seconds == 2550
    assert result.confidence >= 0.9


def test_body_parser_extracts_km_and_clock_duration():
    result = parse_swim_body("오수완 거리 1.5km / 운동시간 42:30")

    assert result.complete is True
    assert result.distance_m == 1500
    assert result.total_seconds == 2550


def test_body_parser_uses_unlabeled_tokens_only_with_swim_context():
    result = parse_swim_body("오수완 자유형 1500m 42:30")

    assert result.complete is True
    assert result.distance_m == 1500
    assert result.total_seconds == 2550
    assert result.confidence < 0.9


def test_body_parser_rejects_pace_as_total_duration():
    result = parse_swim_body("수영 1500m 평균 페이스 2:05/100m")

    assert result.complete is False
    assert result.reason == BODY_PACE_CONFUSION


def test_body_parser_reports_conflicting_candidates():
    result = parse_swim_body("총거리 1000m\n거리 1500m\n운동시간 42:30")

    assert result.complete is False
    assert result.reason == BODY_CANDIDATE_CONFLICT


def test_body_parser_ignores_non_swim_unlabeled_numbers():
    result = parse_swim_body("점심 1500원 12:30")

    assert result.complete is False
    assert result.reason == BODY_PARSE_FAILED
