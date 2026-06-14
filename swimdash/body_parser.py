from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from swimdash.parser import parse_total_time_text_value

BODY_PARSE_FAILED = "BODY_PARSE_FAILED"
BODY_CANDIDATE_CONFLICT = "CANDIDATE_CONFLICT"
BODY_DISTANCE_ONLY = "OCR_DISTANCE_ONLY"
BODY_DURATION_ONLY = "OCR_DURATION_ONLY"
BODY_PACE_CONFUSION = "OCR_PACE_CONFUSION"

DISTANCE_LABEL_RE = re.compile(
    r"(?:총\s*)?(?:수영\s*)?(?:거리|운동거리|이동거리)\s*[:：=\-]?\s*"
    r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>km|KM|Km|m|M|미터)?"
)
DISTANCE_TOKEN_RE = re.compile(r"(?<![\d:])(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>km|KM|Km|m|M|미터)\b")
TIME_LABEL_RE = re.compile(
    r"(?:총\s*)?(?:운동|수영|기록)?\s*(?:시간|운동시간|수영시간|기록시간)\s*[:：=\-]?\s*"
    r"(?P<value>\d{1,2}:\d{2}(?::\d{2})?|\d+\s*시간\s*(?:\d+\s*분)?\s*(?:\d+\s*초)?|\d+\s*분\s*(?:\d+\s*초)?|\d+\s*초)"
)
TIME_TOKEN_RE = re.compile(
    r"(?P<value>\d{1,2}:\d{2}(?::\d{2})?|\d+\s*시간\s*(?:\d+\s*분)?\s*(?:\d+\s*초)?|\d+\s*분\s*(?:\d+\s*초)?|\d+\s*초)"
)
PACE_CONTEXT_RE = re.compile(r"(?i)(/\s*100\s*m|\bpace\b|페이스|평균\s*페이스)")
CLOCK_RANGE_RE = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?\s*[~\-]\s*\d{1,2}:\d{2}(?::\d{2})?")
SWIM_CONTEXT_RE = re.compile(r"(수영|오수완|자유형|배영|평영|접영|강습|킥판|풀부이|핀|레인|입수)")


@dataclass(slots=True)
class BodyParseResult:
    distance_m: int | None
    total_time_text: str | None
    total_seconds: int | None
    confidence: float
    reason: str | None
    evidence_text: str | None
    warning_codes: list[str]

    @property
    def complete(self) -> bool:
        return self.distance_m is not None and self.total_seconds is not None


def parse_swim_body(content: str) -> BodyParseResult:
    text = _normalize_text(content)
    if not text:
        return _empty(BODY_PARSE_FAILED)

    if PACE_CONTEXT_RE.search(text) and not _has_labeled_total_time(text):
        return _empty(BODY_PACE_CONFUSION)

    distances = _extract_distances(text)
    durations = _extract_durations(text)
    warnings: list[str] = []

    distance = _choose_single(distances)
    duration = _choose_single(durations)

    if distance is None and len({item[0] for item in distances}) > 1:
        warnings.append(BODY_CANDIDATE_CONFLICT)
    if duration is None and len({item[1] for item in durations}) > 1:
        warnings.append(BODY_CANDIDATE_CONFLICT)

    if distance is not None and duration is not None:
        confidence = 0.9 if distance[2] == "label" and duration[3] == "label" else 0.78
        if warnings:
            return _empty(BODY_CANDIDATE_CONFLICT, warnings=warnings, evidence=_evidence(text))
        return BodyParseResult(
            distance_m=distance[0],
            total_time_text=duration[0],
            total_seconds=duration[1],
            confidence=confidence,
            reason=None,
            evidence_text=_evidence(text),
            warning_codes=[],
        )

    if BODY_CANDIDATE_CONFLICT in warnings:
        return _empty(BODY_CANDIDATE_CONFLICT, warnings=warnings, evidence=_evidence(text))

    if distance is not None:
        return BodyParseResult(distance[0], None, None, 0.35, BODY_DISTANCE_ONLY, _evidence(text), warnings)
    if duration is not None:
        return BodyParseResult(None, duration[0], duration[1], 0.35, BODY_DURATION_ONLY, _evidence(text), warnings)
    return _empty(warnings[0] if warnings else BODY_PARSE_FAILED, warnings=warnings, evidence=_evidence(text))


def body_result_to_candidate(result: BodyParseResult) -> dict:
    return {
        "distance_m": result.distance_m,
        "duration_seconds": result.total_seconds,
        "total_time_text": result.total_time_text,
        "confidence": result.confidence,
        "reason": result.reason,
        "evidence_text": result.evidence_text,
        "warnings": list(result.warning_codes),
    }


def _extract_distances(text: str) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    for match in DISTANCE_LABEL_RE.finditer(text):
        value = _parse_distance(match.group("num"), match.group("unit") or "m")
        if value is not None:
            rows.append((value, match.group(0).strip(), "label"))

    if rows:
        return rows

    if not SWIM_CONTEXT_RE.search(text):
        return rows

    for match in DISTANCE_TOKEN_RE.finditer(text):
        value = _parse_distance(match.group("num"), match.group("unit"))
        if value is not None:
            rows.append((value, match.group(0).strip(), "token"))
    return rows


def _extract_durations(text: str) -> list[tuple[str, int, str, str]]:
    rows: list[tuple[str, int, str, str]] = []
    for match in TIME_LABEL_RE.finditer(text):
        if _is_pace_or_range_context(text, match.start(), match.end()):
            continue
        parsed = parse_total_time_text_value(match.group("value"))
        if parsed is not None:
            rows.append((parsed[0], parsed[1], match.group(0).strip(), "label"))

    if rows:
        return rows

    if not SWIM_CONTEXT_RE.search(text):
        return rows

    for match in TIME_TOKEN_RE.finditer(text):
        if _is_pace_or_range_context(text, match.start(), match.end()):
            continue
        parsed = parse_total_time_text_value(match.group("value"))
        if parsed is not None:
            rows.append((parsed[0], parsed[1], match.group(0).strip(), "token"))
    return rows


def _parse_distance(raw_num: str, raw_unit: str) -> int | None:
    token = raw_num
    if "," in token and "." not in token:
        head, tail = token.split(",", 1)
        token = f"{head}{tail}" if len(tail) == 3 else f"{head}.{tail}"
    token = token.replace(",", "")
    try:
        numeric = float(token)
    except ValueError:
        return None
    unit = (raw_unit or "m").lower()
    meters = numeric * 1000 if unit == "km" else numeric
    if meters <= 0:
        return None
    return int(round(meters))


def _choose_single(rows):
    if not rows:
        return None
    unique_values = {row[0] if isinstance(row[0], int) else row[1] for row in rows}
    if len(unique_values) != 1:
        return None
    return rows[0]


def _has_labeled_total_time(text: str) -> bool:
    return any(True for _ in TIME_LABEL_RE.finditer(text))


def _is_pace_or_range_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 24) : min(len(text), end + 24)]
    return bool(PACE_CONTEXT_RE.search(window) or CLOCK_RANGE_RE.search(window))


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t\u00A0]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _evidence(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:240]


def _empty(reason: str, *, warnings: list[str] | None = None, evidence: str | None = None) -> BodyParseResult:
    return BodyParseResult(
        distance_m=None,
        total_time_text=None,
        total_seconds=None,
        confidence=0.0,
        reason=reason,
        evidence_text=evidence,
        warning_codes=list(warnings or []),
    )
