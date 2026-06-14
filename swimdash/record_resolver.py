from __future__ import annotations

import os
from dataclasses import dataclass

from swimdash.parser import TITLE_SOURCE, ParseResult

OCR_DISABLED = "OCR_DISABLED"
OCR_LOW_CONFIDENCE = "OCR_LOW_CONFIDENCE"
OCR_DISTANCE_ONLY = "OCR_DISTANCE_ONLY"
OCR_DURATION_ONLY = "OCR_DURATION_ONLY"
CANDIDATE_CONFLICT = "CANDIDATE_CONFLICT"
OUT_OF_RANGE = "OUT_OF_RANGE"

BODY_SOURCE = "body_text"
OCR_SOURCE = "gemini_ocr"

DEFAULT_MIN_DISTANCE_M = 200
DEFAULT_MAX_DISTANCE_M = 5000
DEFAULT_MIN_DURATION_SECONDS = 300
DEFAULT_MAX_DURATION_SECONDS = 14400
DEFAULT_OCR_MIN_CONFIDENCE = 0.85


@dataclass(slots=True)
class ResolvedRecord:
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
    source_candidates: dict
    resolved_source: str
    resolver_confidence: float
    review_reason: str | None


def resolve_record_candidates(
    *,
    title_parse: ParseResult,
    body_candidate: dict | None = None,
    ocr_candidate: dict | None = None,
    ocr_enabled: bool = False,
    ocr_min_confidence: float | None = None,
) -> ResolvedRecord:
    title = candidate_from_title_parse(title_parse)
    body = normalize_candidate(body_candidate, source="body")
    ocr = normalize_candidate(ocr_candidate, source="ocr")
    if not ocr_enabled and not ocr.get("reason"):
        ocr["reason"] = OCR_DISABLED

    candidates = {"title": title, "body": body, "ocr": ocr}
    complete = {
        key: item
        for key, item in candidates.items()
        if _is_complete(item) and not _candidate_disabled(key, item, ocr_enabled)
    }
    warnings = _collect_warnings(candidates)

    ocr_min = DEFAULT_OCR_MIN_CONFIDENCE if ocr_min_confidence is None else ocr_min_confidence
    conflict = _has_conflict(complete)
    if conflict:
        warnings = [*warnings, CANDIDATE_CONFLICT]

    agreement = _agreement_group(complete)
    if agreement is not None:
        key, candidate = agreement
        out_reason = _out_of_range_reason(candidate)
        if out_reason is not None:
            return _review_from_candidate(
                candidate,
                title_parse=title_parse,
                candidates=candidates,
                reason=out_reason,
                warnings=warnings,
            )
        return _accepted(
            candidate,
            source=_source_for_key(key),
            resolved_source="mixed",
            confidence=_confidence_for_key(key, candidate),
            candidates=candidates,
            warnings=warnings,
        )

    if _is_complete(title):
        out_reason = _out_of_range_reason(title)
        if out_reason is not None:
            return _review_from_candidate(
                title,
                title_parse=title_parse,
                candidates=candidates,
                reason=out_reason,
                warnings=warnings,
            )
        return _accepted(
            title,
            source=TITLE_SOURCE,
            resolved_source="title",
            confidence=1.0,
            candidates=candidates,
            warnings=warnings,
        )

    if _is_complete(body):
        out_reason = _out_of_range_reason(body)
        if out_reason is not None:
            return _review_from_candidate(
                body,
                title_parse=title_parse,
                candidates=candidates,
                reason=out_reason,
                warnings=warnings,
            )
        confidence = float(body.get("confidence") or 0.0)
        return _accepted(
            body,
            source=BODY_SOURCE,
            resolved_source="body",
            confidence=max(0.0, min(0.95, confidence)),
            candidates=candidates,
            warnings=warnings,
        )

    if _is_complete(ocr):
        out_reason = _out_of_range_reason(ocr)
        if out_reason is not None:
            return _review_from_candidate(
                ocr,
                title_parse=title_parse,
                candidates=candidates,
                reason=out_reason,
                warnings=warnings,
            )
        confidence = float(ocr.get("confidence") or 0.0)
        if confidence >= ocr_min:
            return _accepted(
                ocr,
                source=OCR_SOURCE,
                resolved_source="ocr",
                confidence=max(0.0, min(0.95, confidence)),
                candidates=candidates,
                warnings=warnings,
            )
        return _review_from_candidate(
            ocr,
            title_parse=title_parse,
            candidates=candidates,
            reason=OCR_LOW_CONFIDENCE,
            warnings=[*warnings, OCR_LOW_CONFIDENCE],
        )

    reason = _first_reason(title, body, ocr, ocr_enabled=ocr_enabled) or title_parse.review_reason_code
    return ResolvedRecord(
        distance_m=None,
        total_time_text=None,
        total_seconds=None,
        source="none",
        include=False,
        score=title_parse.score,
        exclude_reason_code=reason,
        warning_codes=warnings,
        evidence_text=title_parse.evidence_text,
        review_needed=True,
        review_reason_code=reason,
        source_candidates=candidates,
        resolved_source="none",
        resolver_confidence=0.0,
        review_reason=reason,
    )


def candidate_from_title_parse(parsed: ParseResult) -> dict:
    return {
        "distance_m": parsed.distance_m,
        "duration_seconds": parsed.total_seconds,
        "total_time_text": parsed.total_time_text,
        "confidence": 1.0 if parsed.include else 0.0,
        "reason": parsed.review_reason_code or parsed.exclude_reason_code,
        "evidence_text": parsed.evidence_text,
        "warnings": list(parsed.warning_codes),
    }


def normalize_candidate(candidate: dict | None, *, source: str) -> dict:
    raw = dict(candidate or {})
    duration = _coerce_int(raw.get("duration_seconds", raw.get("total_seconds", raw.get("possible_duration_seconds"))))
    distance = _coerce_int(raw.get("distance_m", raw.get("possible_distance_m")))
    result = {
        "distance_m": distance,
        "duration_seconds": duration,
        "total_time_text": raw.get("total_time_text") or raw.get("possible_duration_text"),
        "confidence": _coerce_float(raw.get("confidence"), 0.0),
        "reason": raw.get("reason"),
        "evidence_text": raw.get("evidence_text"),
        "warnings": [str(item) for item in (raw.get("warnings") or []) if item],
    }
    if source == "ocr":
        result.update(
            {
                "model": raw.get("model"),
                "cache_key": raw.get("cache_key"),
                "screen_type": raw.get("screen_type"),
                "raw_ocr_text": raw.get("raw_ocr_text"),
                "evidence_lines": list(raw.get("evidence_lines") or []),
                "notes": raw.get("notes"),
            }
        )
    return result


def ocr_enabled_from_env() -> bool:
    return str(os.getenv("SWIMDASH_ENABLE_GEMINI_OCR", "0")).strip().lower() in {"1", "true", "yes", "on"}


def ocr_min_confidence_from_env() -> float:
    try:
        return float(os.getenv("GEMINI_OCR_MIN_CONFIDENCE", str(DEFAULT_OCR_MIN_CONFIDENCE)))
    except ValueError:
        return DEFAULT_OCR_MIN_CONFIDENCE


def _accepted(
    candidate: dict,
    *,
    source: str,
    resolved_source: str,
    confidence: float,
    candidates: dict,
    warnings: list[str],
) -> ResolvedRecord:
    return ResolvedRecord(
        distance_m=_coerce_int(candidate.get("distance_m")),
        total_time_text=candidate.get("total_time_text"),
        total_seconds=_coerce_int(candidate.get("duration_seconds")),
        source=source,
        include=True,
        score=int(round(confidence * 100)),
        exclude_reason_code=None,
        warning_codes=warnings,
        evidence_text=str(candidate.get("evidence_text") or ""),
        review_needed=False,
        review_reason_code=None,
        source_candidates=candidates,
        resolved_source=resolved_source,
        resolver_confidence=round(confidence, 3),
        review_reason=None,
    )


def _review_from_candidate(
    candidate: dict,
    *,
    title_parse: ParseResult,
    candidates: dict,
    reason: str,
    warnings: list[str],
) -> ResolvedRecord:
    return ResolvedRecord(
        distance_m=_coerce_int(candidate.get("distance_m")),
        total_time_text=candidate.get("total_time_text"),
        total_seconds=_coerce_int(candidate.get("duration_seconds")),
        source="none",
        include=False,
        score=50,
        exclude_reason_code=reason,
        warning_codes=[*dict.fromkeys(warnings)],
        evidence_text=str(candidate.get("evidence_text") or title_parse.evidence_text or ""),
        review_needed=True,
        review_reason_code=reason,
        source_candidates=candidates,
        resolved_source="none",
        resolver_confidence=0.0,
        review_reason=reason,
    )


def _has_conflict(candidates: dict[str, dict]) -> bool:
    values = {_candidate_pair(item) for item in candidates.values() if _is_complete(item)}
    return len(values) > 1


def _agreement_group(candidates: dict[str, dict]) -> tuple[str, dict] | None:
    pairs: dict[tuple[int | None, int | None], list[str]] = {}
    for key, candidate in candidates.items():
        if not _is_complete(candidate):
            continue
        pairs.setdefault(_candidate_pair(candidate), []).append(key)
    agreed = [keys for keys in pairs.values() if len(keys) >= 2]
    if not agreed:
        return None
    best_keys = max(agreed, key=lambda keys: (len(keys), _priority_score(keys)))
    for key in ("title", "body", "ocr"):
        if key in best_keys:
            return key, candidates[key]
    return None


def _priority_score(keys: list[str]) -> int:
    for index, key in enumerate(("title", "body", "ocr")):
        if key in keys:
            return 3 - index
    return 0


def _out_of_range_reason(candidate: dict) -> str | None:
    distance = _coerce_int(candidate.get("distance_m"))
    duration = _coerce_int(candidate.get("duration_seconds"))
    if distance is None or duration is None:
        return None
    if distance < DEFAULT_MIN_DISTANCE_M or distance > DEFAULT_MAX_DISTANCE_M:
        return OUT_OF_RANGE
    if duration < DEFAULT_MIN_DURATION_SECONDS or duration > DEFAULT_MAX_DURATION_SECONDS:
        return OUT_OF_RANGE
    return None


def _source_for_key(key: str) -> str:
    if key == "body":
        return BODY_SOURCE
    if key == "ocr":
        return OCR_SOURCE
    return TITLE_SOURCE


def _confidence_for_key(key: str, candidate: dict) -> float:
    if key == "title":
        return 1.0
    return max(0.0, min(0.95, float(candidate.get("confidence") or 0.0)))


def _first_reason(title: dict, body: dict, ocr: dict, *, ocr_enabled: bool) -> str | None:
    for item in (body, ocr if ocr_enabled else {}, title):
        reason = item.get("reason") if item else None
        if reason and reason != OCR_DISABLED:
            return str(reason)
    return title.get("reason")


def _collect_warnings(candidates: dict[str, dict]) -> list[str]:
    warnings: list[str] = []
    for item in candidates.values():
        warnings.extend(str(code) for code in (item.get("warnings") or []) if code)
    return [*dict.fromkeys(warnings)]


def _candidate_disabled(key: str, candidate: dict, ocr_enabled: bool) -> bool:
    return key == "ocr" and (not ocr_enabled or candidate.get("reason") == OCR_DISABLED)


def _is_complete(candidate: dict) -> bool:
    return candidate.get("distance_m") is not None and candidate.get("duration_seconds") is not None


def _candidate_pair(candidate: dict) -> tuple[int | None, int | None]:
    return _coerce_int(candidate.get("distance_m")), _coerce_int(candidate.get("duration_seconds"))


def _coerce_int(value) -> int | None:  # noqa: ANN001
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except Exception:  # noqa: BLE001
        return None


def _coerce_float(value, default: float) -> float:  # noqa: ANN001
    if value in (None, ""):
        return default
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default
