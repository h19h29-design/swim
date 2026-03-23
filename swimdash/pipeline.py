from __future__ import annotations

import csv
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from swimdash.admin_config import load_admin_config_bundle
from swimdash.aggregate import (
    build_admin_preview,
    MODE_CORE_ONLY,
    build_author_index,
    build_author_profiles,
    build_badge_index,
    build_dashboard_views,
    build_parse_status_payload,
    build_monthly,
    build_leaderboard_payload,
    build_summary_payload,
    filter_dashboard_records,
    resolve_metric_bucket,
)
from swimdash.admin_config import build_public_site_config_payload
from swimdash.config import (
    ADMIN_PREVIEW_FILE,
    AUTHOR_INDEX_FILE,
    AUTHOR_PROFILES_FILE,
    PUBLIC_BADGE_ART_CATALOG_FILE,
    PUBLIC_SITE_CONFIG_FILE,
    BADGE_INDEX_FILE,
    BADGE_ART_CATALOG_FILE,
    DASHBOARD_VIEWS_FILE,
    LEADERBOARD_FILE,
    MANUAL_REVIEW_OVERRIDE_FILE,
    MONTHLY_FILE,
    PARSE_STATUS_FILE,
    RECORDS_FILE,
    REVIEW_QUEUE_FILE,
    SUMMARY_FILE,
)
from swimdash.io_utils import read_json, write_json
from swimdash.models import CrawledPost, SwimRecord
from swimdash.parser import parse_swim_text, parse_total_time_text_value

LEGACY_SOURCE_MAP = {
    "text_strict_pair": "title_format",
    "text_structured_pair": "title_format",
    "text_structured": "title_format",
    "text_format": "title_format",
    "text_format_with_image_match": "title_format",
    "text_format_with_image_mismatch": "title_format",
}

LEGACY_EXCLUDE_REASON_MAP = {
    "missing_distance": "TEXT_DISTANCE_MISSING",
    "missing_duration": "TEXT_TIME_MISSING",
    "missing_both": "NO_DATA",
    "no_strict_pair_and_no_image_pair": "TEXT_PARSE_FAILED",
    "distance_le_500": "TEXT_PARSE_FAILED",
    "distance_ge_2000": "TEXT_PARSE_FAILED",
    "distance_le_500_weak_evidence": "TEXT_PARSE_FAILED",
    "distance_ge_2000_weak_evidence": "TEXT_PARSE_FAILED",
    "image_parse_failed_or_incomplete": "IMAGE_PARSE_FAILED",
    "image_missing_duration": "IMAGE_PARSE_FAILED",
}

AUTOMATIC_RECORD_FIELDS = (
    "distance_m",
    "total_time_text",
    "total_seconds",
    "source",
    "metric_bucket",
    "include",
    "score",
    "exclude_reason_code",
    "warning_codes",
    "evidence_text",
    "review_needed",
    "review_reason_code",
)

NORMALIZED_RECORD_FIELDS = (
    "post_id",
    "url",
    "title",
    "author",
    "post_datetime",
    "post_date",
    "distance_m",
    "total_time_text",
    "total_seconds",
    "source",
    "metric_bucket",
    "include",
    "score",
    "exclude_reason_code",
    "warning_codes",
    "evidence_text",
    "review_needed",
    "review_reason_code",
    "manual_override_decision",
    "manual_override_applied",
    "manual_override_note",
    "automatic_record",
)

MANUAL_OVERRIDE_DECISIONS = {"accept", "reject", "patch"}


def load_existing_records() -> list[dict]:
    payload = read_json(RECORDS_FILE, default=[])
    if not isinstance(payload, list):
        return []
    return [_normalize_record_schema(_rebuild_record_from_title(item)) for item in payload if isinstance(item, dict)]


def parse_posts_to_records(posts: list[CrawledPost]) -> list[SwimRecord]:
    records: list[SwimRecord] = []
    for post in posts:
        parsed = parse_swim_text(
            post.title,
            post.content_text,
        )
        post_date = post.post_datetime[:10] if post.post_datetime else ""
        metric_bucket = resolve_metric_bucket({"source": parsed.source, "include": parsed.include})
        records.append(
            SwimRecord(
                post_id=post.post_id,
                url=post.url,
                title=post.title,
                author=post.author,
                post_datetime=post.post_datetime,
                post_date=post_date,
                distance_m=parsed.distance_m,
                total_time_text=parsed.total_time_text,
                total_seconds=parsed.total_seconds,
                source=parsed.source,
                include=parsed.include,
                score=parsed.score,
                exclude_reason_code=parsed.exclude_reason_code,
                warning_codes=parsed.warning_codes,
                evidence_text=parsed.evidence_text,
                review_needed=parsed.review_needed,
                review_reason_code=parsed.review_reason_code,
                metric_bucket=metric_bucket,
            )
        )
    return records


def _rebuild_record_from_title(item: dict) -> dict:
    restored = _restore_automatic_record(item)
    parsed = parse_swim_text(str(restored.get("title") or ""), "")
    rebuilt = dict(restored)
    rebuilt.pop("automatic_record", None)
    rebuilt["distance_m"] = parsed.distance_m
    rebuilt["total_time_text"] = parsed.total_time_text
    rebuilt["total_seconds"] = parsed.total_seconds
    rebuilt["source"] = parsed.source
    rebuilt["include"] = parsed.include
    rebuilt["score"] = parsed.score
    rebuilt["exclude_reason_code"] = parsed.exclude_reason_code
    rebuilt["warning_codes"] = list(parsed.warning_codes)
    rebuilt["evidence_text"] = parsed.evidence_text
    rebuilt["review_needed"] = parsed.review_needed
    rebuilt["review_reason_code"] = parsed.review_reason_code

    if not rebuilt.get("post_date") and rebuilt.get("post_datetime"):
        rebuilt["post_date"] = str(rebuilt["post_datetime"])[:10]

    return rebuilt


def merge_records(existing: list[dict], new_records: list[SwimRecord], replace_all: bool) -> list[dict]:
    record_map: dict[int, dict] = {}

    if not replace_all:
        for item in existing:
            try:
                record_map[int(item["post_id"])] = _normalize_record_schema(_restore_automatic_record(item))
            except Exception:  # noqa: BLE001
                continue

    for rec in new_records:
        record_map[rec.post_id] = _normalize_record_schema(rec.to_dict())

    merged = list(record_map.values())

    def sort_key(row: dict):
        dt = row.get("post_datetime") or ""
        if not dt:
            return datetime.min
        try:
            return datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.min

    merged.sort(key=lambda x: (sort_key(x), int(x.get("post_id", 0))), reverse=True)
    return merged


def write_dashboard_data(records: list[dict]) -> None:
    final_records = apply_manual_review_overrides(records)
    visible_records = filter_dashboard_records(final_records)
    admin_bundle = load_admin_config_bundle()
    public_site_config = build_public_site_config_payload(
        bundle=admin_bundle,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    write_json(RECORDS_FILE, final_records)
    write_json(SUMMARY_FILE, build_summary_payload(final_records, admin_bundle=admin_bundle))
    write_json(MONTHLY_FILE, build_monthly(final_records, mode=MODE_CORE_ONLY))
    write_json(LEADERBOARD_FILE, build_leaderboard_payload(final_records, admin_bundle=admin_bundle))
    write_json(DASHBOARD_VIEWS_FILE, build_dashboard_views(final_records, admin_bundle=admin_bundle))
    write_json(PARSE_STATUS_FILE, build_parse_status_payload(final_records, admin_bundle=admin_bundle))
    write_json(AUTHOR_INDEX_FILE, build_author_index(final_records, admin_bundle=admin_bundle))
    write_json(AUTHOR_PROFILES_FILE, build_author_profiles(final_records, admin_bundle=admin_bundle))
    write_json(BADGE_INDEX_FILE, build_badge_index(final_records, admin_bundle=admin_bundle))
    write_json(ADMIN_PREVIEW_FILE, build_admin_preview(final_records, admin_bundle=admin_bundle))
    write_json(PUBLIC_SITE_CONFIG_FILE, public_site_config)
    badge_art_catalog = read_json(BADGE_ART_CATALOG_FILE, default=None)
    if badge_art_catalog is not None:
        write_json(PUBLIC_BADGE_ART_CATALOG_FILE, badge_art_catalog)
    write_json(REVIEW_QUEUE_FILE, [row for row in visible_records if _resolve_review_needed(row)])


def apply_manual_review_overrides(records: list[dict], override_path: Path | None = None) -> list[dict]:
    overrides = load_manual_review_overrides(override_path)
    normalized = [_normalize_record_schema(_restore_automatic_record(item)) for item in records]
    final_records: list[dict] = []
    for row in normalized:
        snapshotted = _attach_automatic_record(row)
        post_id = _coerce_int_or_none(snapshotted.get("post_id"))
        override = overrides.get(post_id) if post_id is not None else None
        final_records.append(_apply_manual_override(snapshotted, override))
    return final_records


def ensure_manual_review_override_file_exists(path: Path | None = None) -> Path:
    target = path or MANUAL_REVIEW_OVERRIDE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target

    with target.open("w", encoding="utf-8", newline="") as handle:
        handle.write("post_id,decision,distance_m,total_time_text,note\n")
        handle.write("# 17288,patch,1100,47:54,recovered from review\n")
        handle.write("# 17139,accept,,,verified manually\n")
        handle.write("# 17197,reject,,,rejected after review\n")
    return target


def load_manual_review_overrides(path: Path | None = None) -> dict[int, dict]:
    target = ensure_manual_review_override_file_exists(path)
    overrides: dict[int, dict] = {}

    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw_row in reader:
            post_token = str(raw_row.get("post_id", "")).strip()
            if not post_token or post_token.startswith("#"):
                continue

            post_id = _coerce_int_or_none(post_token)
            decision = _clean_string(raw_row.get("decision"))
            if post_id is None or decision is None:
                continue

            decision = decision.lower()
            if decision not in MANUAL_OVERRIDE_DECISIONS:
                continue

            overrides[post_id] = {
                "decision": decision,
                "distance_m": _coerce_int_or_none(raw_row.get("distance_m")),
                "total_time_text": _clean_string(raw_row.get("total_time_text")),
                "note": _clean_string(raw_row.get("note")),
            }

    return overrides


def _apply_manual_override(row: dict, override: dict | None) -> dict:
    final = dict(row)
    final["automatic_record"] = deepcopy(row.get("automatic_record"))
    final["manual_override_decision"] = None
    final["manual_override_applied"] = False
    final["manual_override_note"] = None
    final["metric_bucket"] = resolve_metric_bucket(final)

    if override is None:
        return final

    decision = override["decision"]
    note = override.get("note")
    final["manual_override_decision"] = decision
    final["manual_override_note"] = note

    if decision == "accept":
        final["include"] = True
        final["source"] = "manual_review"
        final["score"] = 100
        final["exclude_reason_code"] = None
        final["warning_codes"] = []
        final["review_needed"] = False
        final["review_reason_code"] = None
        final["manual_override_applied"] = True
        final["metric_bucket"] = resolve_metric_bucket(final)
        return final

    if decision == "reject":
        final["include"] = False
        final["score"] = 100
        final["exclude_reason_code"] = "MANUAL_REJECTED"
        final["warning_codes"] = []
        final["review_needed"] = False
        final["review_reason_code"] = None
        final["manual_override_applied"] = True
        final["metric_bucket"] = resolve_metric_bucket(final)
        return final

    if decision == "patch":
        distance_m = override.get("distance_m")
        if distance_m is None:
            distance_m = final.get("distance_m")

        total_time_text = override.get("total_time_text")
        total_seconds = None

        if total_time_text is not None:
            parsed_time = parse_total_time_text_value(total_time_text)
            if parsed_time is None:
                return final
            total_time_text, total_seconds = parsed_time
        else:
            total_time_text = final.get("total_time_text")
            total_seconds = _coerce_int_or_none(final.get("total_seconds"))
            if total_time_text is not None and total_seconds is None:
                parsed_time = parse_total_time_text_value(total_time_text)
                if parsed_time is not None:
                    total_time_text, total_seconds = parsed_time

        if distance_m is None or total_time_text is None or total_seconds is None:
            return final

        final["distance_m"] = int(distance_m)
        final["total_time_text"] = total_time_text
        final["total_seconds"] = int(total_seconds)
        final["include"] = True
        final["source"] = "manual_patch"
        final["score"] = 100
        final["exclude_reason_code"] = None
        final["warning_codes"] = []
        final["review_needed"] = False
        final["review_reason_code"] = None
        final["manual_override_applied"] = True
        final["metric_bucket"] = resolve_metric_bucket(final)
        return final

    final["metric_bucket"] = resolve_metric_bucket(final)
    return final


def _attach_automatic_record(row: dict) -> dict:
    final = dict(row)
    final["automatic_record"] = {field: deepcopy(row.get(field)) for field in AUTOMATIC_RECORD_FIELDS}
    final["manual_override_decision"] = None
    final["manual_override_applied"] = False
    final["manual_override_note"] = None
    return final


def _restore_automatic_record(item: dict) -> dict:
    row = dict(item)
    automatic = row.get("automatic_record")
    if not isinstance(automatic, dict):
        return row

    restored = dict(row)
    for field in AUTOMATIC_RECORD_FIELDS:
        if field in automatic:
            restored[field] = deepcopy(automatic.get(field))

    restored.pop("manual_override_decision", None)
    restored.pop("manual_override_applied", None)
    restored.pop("manual_override_note", None)
    return restored


def _normalize_record_schema(item: dict) -> dict:
    row = dict(item)
    row["distance_m"] = _coerce_int_or_none(row.get("distance_m"))
    row["total_seconds"] = _resolve_total_seconds(row)
    row["total_time_text"] = _resolve_total_time_text(row)
    row["source"] = _resolve_source(row)
    row["include"] = _resolve_include(row)
    row["metric_bucket"] = _clean_string(row.get("metric_bucket"))
    row["score"] = _coerce_int_or_none(row.get("score", row.get("confidence_score")))
    row["exclude_reason_code"] = _resolve_exclude_reason_code(row)
    row["warning_codes"] = _normalize_warning_codes(row.get("warning_codes"))
    row["evidence_text"] = _clean_string(row.get("evidence_text"))
    row["review_needed"] = _resolve_review_needed(row)
    row["review_reason_code"] = _resolve_review_reason_code(row)
    row["manual_override_decision"] = _resolve_manual_override_decision(row)
    row["manual_override_applied"] = _resolve_manual_override_applied(row)
    row["manual_override_note"] = _clean_string(row.get("manual_override_note"))

    if row["include"]:
        row["exclude_reason_code"] = None
    elif row["exclude_reason_code"] is None:
        row["exclude_reason_code"] = "NO_DATA"

    row["source"] = row["source"] or ("none" if not row["include"] else "title_format")
    row["score"] = row["score"] if row["score"] is not None else (100 if row["include"] else 0)
    row["metric_bucket"] = resolve_metric_bucket(row)
    return {field: deepcopy(row.get(field)) for field in NORMALIZED_RECORD_FIELDS if field in row}


def _resolve_total_seconds(row: dict) -> int | None:
    direct = _coerce_int_or_none(row.get("total_seconds"))
    if direct is not None:
        return direct

    total_time_text = _clean_string(row.get("total_time_text"))
    if total_time_text:
        parsed = parse_total_time_text_value(total_time_text)
        if parsed is not None:
            return parsed[1]

    duration_min = row.get("duration_min")
    if duration_min in (None, ""):
        return None
    try:
        return int(round(float(duration_min) * 60.0))
    except Exception:  # noqa: BLE001
        return None


def _resolve_total_time_text(row: dict) -> str | None:
    value = _clean_string(row.get("total_time_text"))
    if value:
        return value

    total_seconds = _resolve_total_seconds(row)
    if total_seconds is None:
        return None
    return _format_clock(total_seconds)


def _resolve_source(row: dict) -> str:
    direct = _clean_string(row.get("source"))
    if direct:
        return LEGACY_SOURCE_MAP.get(direct, direct)
    legacy = _clean_string(row.get("source_type"))
    return LEGACY_SOURCE_MAP.get(legacy, "none" if not _resolve_include(row) else "title_format")


def _resolve_include(row: dict) -> bool:
    if "include" in row:
        return _coerce_bool(row.get("include"))
    if "is_excluded" in row:
        return not _coerce_bool(row.get("is_excluded"))
    return False


def _resolve_exclude_reason_code(row: dict) -> str | None:
    direct = _clean_string(row.get("exclude_reason_code"))
    if direct:
        return direct
    legacy = _clean_string(row.get("exclude_reason"))
    return LEGACY_EXCLUDE_REASON_MAP.get(legacy) if legacy else None


def _resolve_review_needed(row: dict) -> bool:
    if "review_needed" in row:
        return _coerce_bool(row.get("review_needed"))
    if "needs_review" in row:
        return _coerce_bool(row.get("needs_review"))
    return False


def _resolve_review_reason_code(row: dict) -> str | None:
    direct = _clean_string(row.get("review_reason_code"))
    if direct:
        return direct
    legacy = _clean_string(row.get("review_reason"))
    return legacy if legacy else None


def _resolve_manual_override_decision(row: dict) -> str | None:
    decision = _clean_string(row.get("manual_override_decision"))
    if not decision:
        return None
    normalized = decision.lower()
    return normalized if normalized in MANUAL_OVERRIDE_DECISIONS else None


def _resolve_manual_override_applied(row: dict) -> bool:
    return _coerce_bool(row.get("manual_override_applied", False))


def _normalize_warning_codes(value) -> list[str]:  # noqa: ANN001
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def _coerce_bool(value) -> bool:  # noqa: ANN001
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return bool(value)


def _coerce_int_or_none(value) -> int | None:  # noqa: ANN001
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except Exception:  # noqa: BLE001
        return None


def _clean_string(value) -> str | None:  # noqa: ANN001
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _format_clock(total_seconds: int) -> str:
    hours, remainder = divmod(int(total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"
