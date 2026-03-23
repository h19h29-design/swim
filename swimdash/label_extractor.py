from __future__ import annotations

import re
from dataclasses import dataclass
import math

APPROX_WORDS = ("약", "대략", "정도", "쯤", "남짓", "가량", "내외", "대충")

_LABEL_BOUNDARY = (
    r"(?:총거리|거리|distance|수영시간|운동시간|운동\s*시간|총시간|총\s*시간|활동시간|활동\s*시간|시간|time)\s*[:：]?"
)
DISTANCE_LABEL_PATTERN = re.compile(
    rf"(?P<label>총거리|거리|distance)\s*[:：]?\s*(?P<value>.*?)(?={_LABEL_BOUNDARY}|$)",
    flags=re.IGNORECASE,
)
DURATION_LABEL_PATTERN = re.compile(
    rf"(?P<label>수영시간|운동시간|운동\s*시간|총시간|총\s*시간|활동시간|활동\s*시간|시간|time)\s*[:：]?\s*(?P<value>.*?)(?={_LABEL_BOUNDARY}|$)",
    flags=re.IGNORECASE,
)

HOUR_MIN_PATTERN = re.compile(
    r"(?P<h>\d+(?:[.,]\d+)?)\s*(?:시간|h|hr|hour)s?(?:\s*(?P<m>\d+(?:[.,]\d+)?)\s*(?:분|min|minute)s?)?",
    flags=re.IGNORECASE,
)
MIN_PATTERN = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?(?:\s*(?:~|-|∼|～)\s*\d+(?:[.,]\d+)?)?)\s*(?:분|min|minute)s?",
    flags=re.IGNORECASE,
)
CLOCK_PATTERN = re.compile(r"(?<!\d)(?P<clock>\d{1,2}:\d{2}(?::\d{2})?)(?!\d)")
DIST_PATTERN = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?(?:\s*(?:~|-|∼|～)\s*\d+(?:[.,]\d+)?)?)\s*(?P<unit>km|키로미터|키로|m|미터)?",
    flags=re.IGNORECASE,
)


@dataclass(slots=True)
class LabeledValue:
    value: float
    approx: bool
    evidence: str
    line_index: int
    label: str


def extract_labeled_values(text: str) -> tuple[list[LabeledValue], list[LabeledValue]]:
    distance_values: list[LabeledValue] = []
    duration_values: list[LabeledValue] = []

    for idx, line in enumerate(text.splitlines()):
        compact = line.strip()
        if not compact:
            continue
        for match in DISTANCE_LABEL_PATTERN.finditer(compact):
            parsed = _parse_distance_value(match.group("value"))
            if parsed is None:
                continue
            value, approx = parsed
            distance_values.append(
                LabeledValue(
                    value=value,
                    approx=approx or _near_approx_word(compact, match.start(), match.end()),
                    evidence=match.group(0).strip(),
                    line_index=idx,
                    label=match.group("label").strip().lower(),
                )
            )
        for match in DURATION_LABEL_PATTERN.finditer(compact):
            parsed = _parse_duration_value(match.group("value"))
            if parsed is None:
                continue
            value, approx = parsed
            duration_values.append(
                LabeledValue(
                    value=value,
                    approx=approx or _near_approx_word(compact, match.start(), match.end()),
                    evidence=match.group(0).strip(),
                    line_index=idx,
                    label=match.group("label").strip().lower(),
                )
            )

    return distance_values, duration_values


def _parse_distance_value(raw: str) -> tuple[float, bool] | None:
    for match in DIST_PATTERN.finditer(raw):
        value = match.group("value")
        if not value:
            continue
        parsed, approx = _parse_numeric_or_range(value)
        if parsed is None:
            continue
        unit = (match.group("unit") or "m").lower()
        meters = parsed * 1000 if unit in ("km", "키로", "키로미터") else parsed
        if 20 <= meters <= 50000:
            return float(meters), approx
    return None


def _parse_duration_value(raw: str) -> tuple[float, bool] | None:
    clock = CLOCK_PATTERN.search(raw)
    if clock:
        minutes = _clock_to_minutes(clock.group("clock"))
        if minutes is not None and 5 <= minutes <= 600:
            return float(minutes), False

    for match in HOUR_MIN_PATTERN.finditer(raw):
        h = float(match.group("h").replace(",", "."))
        m = float(match.group("m").replace(",", ".")) if match.group("m") else 0.0
        minutes = h * 60 + m
        if 5 <= minutes <= 600:
            return float(minutes), False

    for match in MIN_PATTERN.finditer(raw):
        parsed, approx = _parse_numeric_or_range(match.group("value"))
        if parsed is None:
            continue
        if 5 <= parsed <= 600:
            return float(parsed), approx

    bare = re.search(r"(?<!\d)(\d+(?:[.,]\d+)?)(?!\d)", raw)
    if bare:
        minutes = float(bare.group(1).replace(",", "."))
        if 5 <= minutes <= 600:
            return minutes, False
    return None


def _clock_to_minutes(clock: str) -> int | None:
    parts = clock.split(":")
    try:
        nums = [int(x) for x in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        total_sec = nums[0] * 60 + nums[1]
    elif len(nums) == 3:
        total_sec = nums[0] * 3600 + nums[1] * 60 + nums[2]
    else:
        return None
    return int(math.ceil(total_sec / 60))


def _parse_numeric_or_range(value: str) -> tuple[float | None, bool]:
    cleaned = value.strip().replace(",", ".")
    range_match = re.search(r"(?P<a>\d+(?:\.\d+)?)\s*(?:~|-|∼|～)\s*(?P<b>\d+(?:\.\d+)?)", cleaned)
    if range_match:
        left = float(range_match.group("a"))
        right = float(range_match.group("b"))
        if left < 10 and right >= 100 and float(int(right)).is_integer() and len(range_match.group("a")) == 1:
            left = left * 100
        midpoint = (left + right) / 2
        return midpoint, True
    try:
        return float(cleaned), False
    except ValueError:
        return None, False


def _near_approx_word(text: str, start: int, end: int) -> bool:
    left = max(0, start - 12)
    right = min(len(text), end + 12)
    span = text[left:right]
    return any(word in span for word in APPROX_WORDS) or bool(re.search(r"\d\s*(?:~|-|∼|～)\s*\d", span))
