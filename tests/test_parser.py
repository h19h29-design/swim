from __future__ import annotations

import pytest

from swimdash.parser import (
    TITLE_FORMAT_INVALID,
    TITLE_FORMAT_MISSING,
    parse_swim_text,
    parse_total_time_text_value,
)


@pytest.mark.parametrize(
    ("title", "distance_m", "total_time_text", "total_seconds"),
    [
        ("1500 / 42:30", 1500, "42:30", 2550),
        ("1500m / 42:30", 1500, "42:30", 2550),
        ("1500 / 42\ubd84 30\ucd08", 1500, "42\ubd84 30\ucd08", 2550),
        ("1500 / 1\uc2dc\uac04 05\ubd84", 1500, "1\uc2dc\uac04 05\ubd84", 3900),
        ("1500m / 55\ubd84", 1500, "55\ubd84", 3300),
        ("\ucd1d\uac70\ub9ac 1500 / \uc2dc\uac04 42\ubd84 30\ucd08", 1500, "42\ubd84 30\ucd08", 2550),
    ],
)
def test_title_format_accepts_official_compatible_formats(
    title: str,
    distance_m: int,
    total_time_text: str,
    total_seconds: int,
):
    result = parse_swim_text(title, "")

    assert result.include is True
    assert result.source == "title_format"
    assert result.distance_m == distance_m
    assert result.total_time_text == total_time_text
    assert result.total_seconds == total_seconds
    assert result.exclude_reason_code is None
    assert result.review_needed is False
    assert result.review_reason_code is None


def test_title_is_the_only_official_ingestion_input():
    result = parse_swim_text("\uc624\uc218\uc644", "1500 / 42:30")

    assert result.include is False
    assert result.source == "none"
    assert result.distance_m is None
    assert result.total_seconds is None
    assert result.exclude_reason_code == TITLE_FORMAT_MISSING
    assert result.review_needed is True
    assert result.review_reason_code == TITLE_FORMAT_MISSING


@pytest.mark.parametrize(
    "title",
    [
        "1500 / 2:05/100m",
        "1500 / 08:51-10:03",
        "1km / 42:30",
        "1500 / 42:30 / 2",
        "\uc624\uc218\uc644 1500 / 42:30",
    ],
)
def test_invalid_or_ambiguous_titles_go_to_review(title: str):
    result = parse_swim_text(title, "")

    assert result.include is False
    assert result.source == "none"
    assert result.distance_m is None
    assert result.total_seconds is None
    assert result.exclude_reason_code == TITLE_FORMAT_INVALID
    assert result.review_needed is True
    assert result.review_reason_code == TITLE_FORMAT_INVALID


@pytest.mark.parametrize("title", ["", "\uc624\uc218\uc644", "1500 42:30", "1500m"])
def test_missing_core_title_format_goes_to_review(title: str):
    result = parse_swim_text(title, "")

    assert result.include is False
    assert result.exclude_reason_code == TITLE_FORMAT_MISSING
    assert result.review_needed is True
    assert result.review_reason_code == TITLE_FORMAT_MISSING


def test_parse_total_time_text_value_rejects_pace_and_clock_ranges():
    assert parse_total_time_text_value("2:05/100m") is None
    assert parse_total_time_text_value("08:51-10:03") is None


def test_parse_total_time_text_value_supports_clock_and_korean_duration():
    assert parse_total_time_text_value("42:30") == ("42:30", 2550)
    assert parse_total_time_text_value("55\ubd84") == ("55\ubd84", 3300)
    assert parse_total_time_text_value("1\uc2dc\uac04 05\ubd84") == ("1\uc2dc\uac04 05\ubd84", 3900)
