from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

HOUR_UNIT = "\uc2dc\uac04"
MINUTE_UNIT = "\ubd84"
SECOND_UNIT = "\ucd08"

TITLE_SOURCE = "title_format"
TITLE_FORMAT_MISSING = "TITLE_FORMAT_MISSING"
TITLE_FORMAT_INVALID = "TITLE_FORMAT_INVALID"

DISTANCE_TOKEN_PATTERN = re.compile(r"^(?P<num>\d{1,3}(?:[ ,]\d{3})*|\d+)\s*(?P<unit>m|M)?$")
DISTANCE_LABEL_PATTERN = re.compile(r"^(?:총거리|거리)\s*", re.IGNORECASE)
TIME_LABEL_PATTERN = re.compile(r"^(?:총시간|운동시간|기록시간|시간)\s*", re.IGNORECASE)
KOREAN_DURATION_PATTERN = re.compile(
    rf"^\s*(?:(?P<h>\d+)\s*{HOUR_UNIT})?\s*(?:(?P<m>\d+)\s*{MINUTE_UNIT})?\s*(?:(?P<s>\d+)\s*{SECOND_UNIT})?\s*$"
)
CLOCK_DURATION_PATTERN = re.compile(r"^\s*(?P<clock>\d{1,2}:\d{2}(?::\d{2})?)\s*$")
CLOCK_RANGE_PATTERN = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?\s*[~\-]\s*\d{1,2}:\d{2}(?::\d{2})?")
PACE_CONTEXT_PATTERN = re.compile(r"(?i)(/\s*100\s*m|\bpace\b|\ud398\uc774\uc2a4)")
TIME_OF_DAY_CONTEXT_PATTERN = re.compile(r"(?i)(\uc624\uc804|\uc624\ud6c4|am|pm|gmt|kst)")


@dataclass(slots=True)
class ParseResult:
    distance_m: int | None
    total_time_text: str | None
    total_seconds: int | None
    source: str
    include: bool
    score: int | None
    exclude_reason_code: str | None
    warning_codes: list[str]
    evidence_text: str
    review_needed: bool
    review_reason_code: str | None


def parse_swim_text(
    title: str,
    content: str,
) -> ParseResult:
    del content

    return parse_swim_title(title)


def parse_swim_title(title: str) -> ParseResult:
    normalized_title = _normalize_text(title)
    parsed = _parse_title_core_format(normalized_title)
    evidence_text = _truncate_text(normalized_title, 240)

    if parsed is not None:
        distance_m, total_time_text, total_seconds = parsed
        return ParseResult(
            distance_m=distance_m,
            total_time_text=total_time_text,
            total_seconds=total_seconds,
            source=TITLE_SOURCE,
            include=True,
            score=100,
            exclude_reason_code=None,
            warning_codes=[],
            evidence_text=evidence_text,
            review_needed=False,
            review_reason_code=None,
        )

    reason_code = _classify_title_failure(normalized_title)
    return ParseResult(
        distance_m=None,
        total_time_text=None,
        total_seconds=None,
        source="none",
        include=False,
        score=_failure_score(reason_code),
        exclude_reason_code=reason_code,
        warning_codes=[],
        evidence_text=evidence_text,
        review_needed=True,
        review_reason_code=reason_code,
    )


def parse_total_time_text_value(raw: str) -> tuple[str, int] | None:
    return _parse_total_time_value(raw)


def _parse_title_core_format(title: str) -> tuple[int, str, int] | None:
    if not title:
        return None

    parts = [part.strip() for part in title.split("/")]
    if len(parts) != 2:
        return None

    distance_part, time_part = parts
    if not distance_part or not time_part:
        return None

    distance_m = _parse_distance_value(distance_part)
    parsed_time = _parse_total_time_value(time_part)
    if distance_m is None or parsed_time is None:
        return None

    total_time_text, total_seconds = parsed_time
    return distance_m, total_time_text, total_seconds


def _parse_distance_value(raw: str) -> int | None:
    normalized_raw = DISTANCE_LABEL_PATTERN.sub("", _normalize_space(raw))
    if not normalized_raw or "km" in normalized_raw.lower():
        return None

    match = DISTANCE_TOKEN_PATTERN.fullmatch(normalized_raw)
    if not match:
        return None

    cleaned = match.group("num").replace(" ", "").replace(",", "")
    try:
        meters = int(cleaned)
    except ValueError:
        return None

    if meters <= 0:
        return None
    return meters


def _parse_total_time_value(raw: str) -> tuple[str, int] | None:
    normalized_raw = TIME_LABEL_PATTERN.sub("", _normalize_space(raw))
    if not normalized_raw:
        return None
    if PACE_CONTEXT_PATTERN.search(normalized_raw):
        return None
    if CLOCK_RANGE_PATTERN.search(normalized_raw):
        return None
    if TIME_OF_DAY_CONTEXT_PATTERN.search(normalized_raw):
        return None

    clock_match = CLOCK_DURATION_PATTERN.fullmatch(normalized_raw)
    if clock_match:
        total_seconds = _clock_to_seconds(clock_match.group("clock"))
        if total_seconds is None:
            return None
        return normalized_raw, total_seconds

    duration_match = KOREAN_DURATION_PATTERN.fullmatch(normalized_raw)
    if duration_match is None:
        return None

    hours = int(duration_match.group("h") or 0)
    minutes = int(duration_match.group("m") or 0)
    seconds = int(duration_match.group("s") or 0)
    if hours == 0 and minutes == 0 and seconds == 0:
        return None

    total_seconds = hours * 3600 + minutes * 60 + seconds
    return normalized_raw, total_seconds


def _classify_title_failure(title: str) -> str:
    if not title:
        return TITLE_FORMAT_MISSING
    if "/" not in title:
        return TITLE_FORMAT_MISSING
    return TITLE_FORMAT_INVALID


def _failure_score(reason_code: str) -> int:
    if reason_code == TITLE_FORMAT_MISSING:
        return 10
    return 25


def _clock_to_seconds(token: str) -> int | None:
    parts = token.split(":")
    try:
        nums = [int(part) for part in parts]
    except ValueError:
        return None

    if len(nums) == 2:
        total_seconds = nums[0] * 60 + nums[1]
    elif len(nums) == 3:
        total_seconds = nums[0] * 3600 + nums[1] * 60 + nums[2]
    else:
        return None
    return total_seconds if total_seconds > 0 else None


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t\u00A0]+", " ", normalized)
    normalized = re.sub(r"\n{2,}", " ", normalized)
    return normalized.strip()


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate_text(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit]
