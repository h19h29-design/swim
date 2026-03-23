from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from swimdash.admin_config import admin_config_source_paths, load_admin_config_bundle
from swimdash.badges import (
    build_admin_preview_payload,
    build_badge_context,
    build_badge_index_payload,
)
from swimdash.config import DASHBOARD_DATE_FLOOR

MODE_CORE_ONLY = "core_only"
METRIC_BUCKET_CORE = "core"
SUPPORTED_MODES = (MODE_CORE_ONLY,)
CORE_SOURCES = {
    "title_format",
    "manual_review",
    "manual_patch",
}
LEADERBOARD_METRICS = (
    "swim_count",
    "distance_m",
    "total_seconds",
    "distance_per_hour_m",
)
GROWTH_METRICS = (
    "growth_swim_count",
    "growth_distance_m",
    "growth_total_seconds",
)
PUBLIC_SUPPORTED_MODES = (MODE_CORE_ONLY,)
try:
    KST = ZoneInfo("Asia/Seoul")
except ZoneInfoNotFoundError:
    KST = timezone(timedelta(hours=9), name="KST")


def to_float(value: float | int | None) -> float:
    return float(value) if value is not None else 0.0


def resolve_metric_bucket(record: dict) -> str | None:
    if not _is_included(record):
        return None

    source = str(record.get("source") or "none")
    if source in CORE_SOURCES:
        return METRIC_BUCKET_CORE
    if source == "none":
        return None
    return METRIC_BUCKET_CORE


def filter_dashboard_records(records: list[dict], floor_date: date | None = DASHBOARD_DATE_FLOOR) -> list[dict]:
    if floor_date is None:
        return list(records)

    filtered: list[dict] = []
    for row in records:
        item_date = _record_date(row)
        if item_date is None:
            continue
        if item_date >= floor_date:
            filtered.append(row)
    return filtered


def build_summary(
    records: list[dict],
    mode: str = MODE_CORE_ONLY,
    reference_date: date | None = None,
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
) -> dict:
    _validate_mode(mode)
    visible_records = filter_dashboard_records(records, floor_date=floor_date)
    included = _included_records(visible_records, mode)
    excluded = [r for r in visible_records if not _is_included(r)]
    review_queue = [r for r in visible_records if _is_review_needed(r)]
    reference = reference_date or _resolve_reference_date(visible_records, fallback=floor_date)

    reason_counts: Counter[str] = Counter()
    for item in excluded:
        reason = item.get("exclude_reason_code") or item.get("exclude_reason") or "unknown"
        reason_counts[str(reason)] += 1

    review_reason_counts: Counter[str] = Counter()
    for item in review_queue:
        reason = item.get("review_reason_code") or "unknown"
        review_reason_counts[str(reason)] += 1

    warning_counts: Counter[str] = Counter()
    for item in visible_records:
        warning_counts.update(str(w) for w in (item.get("warning_codes") or []) if w)

    source_counts: Counter[str] = Counter(str(item.get("source") or "none") for item in visible_records)
    manual_override_counts: Counter[str] = Counter()
    for item in visible_records:
        if not _as_bool(item.get("manual_override_applied", False)):
            continue
        decision = item.get("manual_override_decision") or "unknown"
        manual_override_counts[str(decision)] += 1

    total_distance_m = round(sum(to_float(r.get("distance_m")) for r in included), 2)
    total_seconds = sum(_total_seconds(r) for r in included)
    total_duration_min = round(float(total_seconds) / 60.0, 2)
    distance_per_hour_m = _distance_per_hour(total_distance_m, total_seconds)
    bucket_counts = _metric_bucket_counts(included)
    included_source_counts = dict(sorted(Counter(str(r.get("source") or "none") for r in included).items()))

    summary = {
        "mode": mode,
        "record_count": len(included),
        "total_record_count": len(visible_records),
        "source_record_count": len(records),
        "dashboard_date_floor": _format_date(floor_date) if floor_date is not None else None,
        "dashboard_window": _dashboard_window(reference, floor_date),
        "visible_date_range": _date_range_payload(visible_records),
        "excluded_record_count": len(excluded),
        "excluded_reason_counts": dict(sorted(reason_counts.items())),
        "review_queue_count": len(review_queue),
        "review_reason_counts": dict(sorted(review_reason_counts.items())),
        "warning_code_counts": dict(sorted(warning_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "manual_override_counts": dict(sorted(manual_override_counts.items())),
        "swim_count": len(included),
        "total_distance_m": total_distance_m,
        "total_seconds": total_seconds,
        "total_duration_min": total_duration_min,
        "distance_per_hour_m": distance_per_hour_m,
        "active_authors": len({r.get("author", "") for r in included if r.get("author")}),
        "included_metric_bucket_counts": bucket_counts,
        "included_source_counts": included_source_counts,
        "has_zero_visible_included_rows": len(included) == 0,
        "reference_date": _format_date(reference),
        "growth": _build_growth_summary(included, reference, floor_date=floor_date),
        "generated_at": _utc_now(),
        "date_range": _date_range_payload(included),
    }

    return summary


def build_monthly(
    records: list[dict],
    mode: str = MODE_CORE_ONLY,
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
) -> list[dict]:
    _validate_mode(mode)
    bucket: dict[str, dict] = defaultdict(
        lambda: {
            "month": "",
            "swim_count": 0,
            "total_distance_m": 0.0,
            "total_seconds": 0,
            "active_authors": set(),
            "metric_bucket_counts": Counter(),
        }
    )

    for rec in _included_records(filter_dashboard_records(records, floor_date=floor_date), mode):
        month = str(rec.get("post_date") or "")[:7]
        if not month:
            continue
        entry = bucket[month]
        entry["month"] = month
        entry["swim_count"] += 1
        entry["total_distance_m"] += to_float(rec.get("distance_m"))
        entry["total_seconds"] += _total_seconds(rec)
        bucket_name = resolve_metric_bucket(rec)
        if bucket_name:
            entry["metric_bucket_counts"][bucket_name] += 1
        author = rec.get("author")
        if author:
            entry["active_authors"].add(author)

    rows: list[dict] = []
    for month in sorted(bucket):
        entry = bucket[month]
        rows.append(
            {
                "month": month,
                "swim_count": entry["swim_count"],
                "total_distance_m": round(entry["total_distance_m"], 2),
                "total_seconds": entry["total_seconds"],
                "total_duration_min": round(float(entry["total_seconds"]) / 60.0, 2),
                "distance_per_hour_m": _distance_per_hour(entry["total_distance_m"], entry["total_seconds"]),
                "active_authors": len(entry["active_authors"]),
                "metric_bucket_counts": dict(sorted(entry["metric_bucket_counts"].items())),
            }
        )
    return rows


def build_leaderboard(
    records: list[dict],
    mode: str = MODE_CORE_ONLY,
    reference_date: date | None = None,
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
) -> dict:
    _validate_mode(mode)
    visible_records = filter_dashboard_records(records, floor_date=floor_date)
    included_records = _included_records(visible_records, mode)
    reference = reference_date or _resolve_reference_date(visible_records, fallback=floor_date)
    author_rows = _author_aggregate_rows(included_records, reference, floor_date=floor_date)

    return {
        "mode": mode,
        "record_count": len(included_records),
        "total_record_count": len(visible_records),
        "source_record_count": len(records),
        "dashboard_date_floor": _format_date(floor_date) if floor_date is not None else None,
        "dashboard_window": _dashboard_window(reference, floor_date),
        "visible_date_range": _date_range_payload(visible_records),
        "date_range": _date_range_payload(included_records),
        "metric_bucket_counts": _metric_bucket_counts(included_records),
        "has_zero_visible_included_rows": len(included_records) == 0,
        "reference_date": _format_date(reference),
        "generated_at": _utc_now(),
        "leaderboard_metrics": list(LEADERBOARD_METRICS),
        "growth_metrics": list(GROWTH_METRICS),
        "authors": author_rows,
        "by_distance": _sort_author_rows(author_rows, "total_distance_m", "swim_count"),
        "by_swim_count": _sort_author_rows(author_rows, "swim_count", "total_distance_m"),
        "by_duration": _sort_author_rows(author_rows, "total_duration_min", "swim_count"),
        "by_total_seconds": _sort_author_rows(author_rows, "total_seconds", "swim_count"),
        "by_distance_per_hour_m": _sort_author_rows(author_rows, "distance_per_hour_m", "swim_count"),
        "growth_by_swim_count": _growth_rows(author_rows, "swim_count"),
        "growth_by_distance_m": _growth_rows(author_rows, "distance_m"),
        "growth_by_total_seconds": _growth_rows(author_rows, "total_seconds"),
    }


def build_summary_payload(
    records: list[dict],
    *,
    admin_bundle: dict | None = None,
    badge_context: dict | None = None,
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
) -> dict:
    admin_bundle, badge_context, visible_records, reference = _resolve_public_context(
        records,
        admin_bundle=admin_bundle,
        badge_context=badge_context,
        floor_date=floor_date,
    )
    summary = build_summary(records, mode=MODE_CORE_ONLY, reference_date=reference, floor_date=floor_date)
    return {
        "generated_at": summary["generated_at"],
        "reference_date": summary["reference_date"],
        "dashboard_date_floor": summary["dashboard_date_floor"],
        "dashboard_window": summary["dashboard_window"],
        "visible_date_range": summary["visible_date_range"],
        "product_mode": MODE_CORE_ONLY,
        "default_mode": MODE_CORE_ONLY,
        "supported_modes": list(PUBLIC_SUPPORTED_MODES),
        "source_record_count": len(records),
        "visible_record_count": len(visible_records),
        "summary": summary,
        "gallery": badge_context["gallery"],
        "recent_unlocks": badge_context["recent_unlocks"],
        "ops": _ops_snapshot(summary),
        "site_config": admin_bundle["site_config"],
    }


def build_leaderboard_payload(
    records: list[dict],
    *,
    admin_bundle: dict | None = None,
    badge_context: dict | None = None,
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
) -> dict:
    admin_bundle, badge_context, visible_records, reference = _resolve_public_context(
        records,
        admin_bundle=admin_bundle,
        badge_context=badge_context,
        floor_date=floor_date,
    )
    leaderboard = build_leaderboard(records, mode=MODE_CORE_ONLY, reference_date=reference, floor_date=floor_date)
    author_rows = _enrich_author_rows(leaderboard["authors"], badge_context)
    rankings = _build_ranking_sections(author_rows, admin_bundle["home_sections"])
    return {
        "generated_at": leaderboard["generated_at"],
        "reference_date": leaderboard["reference_date"],
        "dashboard_date_floor": leaderboard["dashboard_date_floor"],
        "dashboard_window": leaderboard["dashboard_window"],
        "visible_date_range": leaderboard["visible_date_range"],
        "product_mode": MODE_CORE_ONLY,
        "default_mode": MODE_CORE_ONLY,
        "supported_modes": list(PUBLIC_SUPPORTED_MODES),
        "source_record_count": len(records),
        "visible_record_count": len(visible_records),
        "authors": author_rows,
        "rankings": rankings,
        "gallery_current_title": badge_context["gallery"]["current_title"],
    }


def build_dashboard_views(
    records: list[dict],
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
    *,
    admin_bundle: dict | None = None,
    badge_context: dict | None = None,
) -> dict:
    admin_bundle, badge_context, visible_records, reference = _resolve_public_context(
        records,
        admin_bundle=admin_bundle,
        badge_context=badge_context,
        floor_date=floor_date,
    )
    summary = build_summary(records, mode=MODE_CORE_ONLY, reference_date=reference, floor_date=floor_date)
    monthly = build_monthly(records, mode=MODE_CORE_ONLY, floor_date=floor_date)
    leaderboard = build_leaderboard(records, mode=MODE_CORE_ONLY, reference_date=reference, floor_date=floor_date)
    author_rows = _enrich_author_rows(leaderboard["authors"], badge_context)

    return {
        "generated_at": summary["generated_at"],
        "reference_date": summary["reference_date"],
        "dashboard_date_floor": summary["dashboard_date_floor"],
        "dashboard_window": summary["dashboard_window"],
        "visible_date_range": summary["visible_date_range"],
        "product_mode": MODE_CORE_ONLY,
        "default_mode": MODE_CORE_ONLY,
        "supported_modes": list(PUBLIC_SUPPORTED_MODES),
        "source_record_count": len(records),
        "visible_record_count": len(visible_records),
        "core_only_has_zero_visible_included_rows": summary["has_zero_visible_included_rows"],
        "growth_windows": _growth_window_metadata(reference, floor_date),
        "site_config": admin_bundle["site_config"],
        "navigation_config": admin_bundle["navigation_config"],
        "home_sections": admin_bundle["home_sections"],
        "summary": summary,
        "monthly": monthly,
        "gallery": badge_context["gallery"],
        "rankings": _build_ranking_sections(author_rows, admin_bundle["home_sections"]),
        "authors": author_rows,
        "recent_records": _recent_record_previews(records, MODE_CORE_ONLY, 20),
        "recent_unlocks": badge_context["recent_unlocks"],
        "ops": _ops_snapshot(summary),
    }


def build_parse_status_payload(
    records: list[dict],
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
    *,
    admin_bundle: dict | None = None,
    badge_context: dict | None = None,
) -> dict:
    admin_bundle, _badge_context, visible_records, reference = _resolve_public_context(
        records,
        admin_bundle=admin_bundle,
        badge_context=badge_context,
        floor_date=floor_date,
    )
    parsed_rows = _parse_status_rows(visible_records, parsed=True)
    unparsed_rows = _parse_status_rows(visible_records, parsed=False)
    total_rows = len(parsed_rows) + len(unparsed_rows)
    success_rate = round((len(parsed_rows) / total_rows) * 100.0, 2) if total_rows else 0.0
    failure_reason_counts: Counter[str] = Counter()
    for row in unparsed_rows:
        failure_reason_counts[str(row.get("reason_code") or "UNKNOWN")] += 1

    return {
        "generated_at": _utc_now(),
        "reference_date": _format_date(reference),
        "dashboard_date_floor": _format_date(floor_date) if floor_date is not None else None,
        "dashboard_window": _dashboard_window(reference, floor_date),
        "visible_date_range": _date_range_payload(visible_records),
        "product_mode": MODE_CORE_ONLY,
        "default_mode": MODE_CORE_ONLY,
        "supported_modes": list(PUBLIC_SUPPORTED_MODES),
        "source_record_count": len(records),
        "visible_record_count": len(visible_records),
        "parsed_count": len(parsed_rows),
        "unparsed_count": len(unparsed_rows),
        "success_rate_pct": success_rate,
        "failure_reason_counts": dict(sorted(failure_reason_counts.items())),
        "site_config": admin_bundle["site_config"],
        "guidance": {
            "official_format": "1500 / 42:30",
            "accepted_examples": [
                "1500 / 42:30",
                "1500m / 42:30",
                "1500 / 42분 30초",
                "1500 / 1시간 05분",
                "1500m / 55분",
                "총거리 1000 / 시간 49분17초",
            ],
            "rules_ko": [
                "게시글 제목만 공식 파싱 대상입니다.",
                "앞 숫자는 거리, 뒤 숫자는 시간으로 해석합니다.",
                "거리는 항상 m 기준입니다.",
                "날짜, 오수완, 메모 같은 문구는 제목이 아니라 본문에 적어 주세요.",
            ],
        },
        "parsed_rows": parsed_rows,
        "unparsed_rows": unparsed_rows,
    }


def build_author_index(
    records: list[dict],
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
    *,
    admin_bundle: dict | None = None,
    badge_context: dict | None = None,
) -> dict:
    admin_bundle, badge_context, visible_records, reference = _resolve_public_context(
        records,
        admin_bundle=admin_bundle,
        badge_context=badge_context,
        floor_date=floor_date,
    )
    grouped = _records_by_author(visible_records)
    rows: list[dict] = []
    for author in sorted(grouped):
        author_records = grouped[author]
        badge_payload = badge_context["authors"].get(author, _empty_badge_payload())
        rows.append(
            {
                "author": author,
                "search_key": _author_search_key(author),
                "latest_post_date": _latest_post_date(author_records),
                "total_record_count": len(author_records),
                "included_record_count": len(_included_records(author_records, MODE_CORE_ONLY)),
                "review_queue_count": sum(1 for row in author_records if _is_review_needed(row)),
                "primary_title": badge_payload["primary_title"],
                "unlocked_badge_count": len(badge_payload["unlocked_badges"]),
                "badge_counts_by_category": badge_payload["badge_counts_by_category"],
                "next_badge_progress": badge_payload["next_badge_progress"],
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row["included_record_count"]),
            -int(row["unlocked_badge_count"]),
            row["author"],
        )
    )
    return {
        "generated_at": _utc_now(),
        "reference_date": _format_date(reference),
        "dashboard_date_floor": _format_date(floor_date) if floor_date is not None else None,
        "dashboard_window": _dashboard_window(reference, floor_date),
        "visible_date_range": _date_range_payload(visible_records),
        "product_mode": MODE_CORE_ONLY,
        "default_mode": MODE_CORE_ONLY,
        "supported_modes": list(PUBLIC_SUPPORTED_MODES),
        "source_record_count": len(records),
        "visible_record_count": len(visible_records),
        "author_count": len(rows),
        "authors": rows,
        "profile_layout_config": admin_bundle["profile_layout_config"],
    }


def build_author_profiles(
    records: list[dict],
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
    *,
    admin_bundle: dict | None = None,
    badge_context: dict | None = None,
) -> dict:
    admin_bundle, badge_context, visible_records, reference = _resolve_public_context(
        records,
        admin_bundle=admin_bundle,
        badge_context=badge_context,
        floor_date=floor_date,
    )
    grouped = _records_by_author(visible_records)
    profiles: list[dict] = []

    for author in sorted(grouped):
        author_records = grouped[author]
        badge_payload = badge_context["authors"].get(author, _empty_badge_payload())
        summary = build_summary(author_records, mode=MODE_CORE_ONLY, reference_date=reference, floor_date=floor_date)
        profiles.append(
            {
                "author": author,
                "search_key": _author_search_key(author),
                "latest_post_date": _latest_post_date(author_records),
                "total_record_count": len(author_records),
                "included_record_count": summary["record_count"],
                "review_queue_count": sum(1 for row in author_records if _is_review_needed(row)),
                "summary": summary,
                "recent_28d_vs_previous_28d": summary["growth"],
                "monthly_trend": build_monthly(author_records, mode=MODE_CORE_ONLY, floor_date=floor_date),
                "recent_records": _recent_record_previews(author_records, MODE_CORE_ONLY, 20),
                "time_series": {
                    "daily": _daily_time_series(author_records, MODE_CORE_ONLY),
                },
                "primary_title": badge_payload["primary_title"],
                "unlocked_badges": badge_payload["unlocked_badges"],
                "next_badge_progress": badge_payload["next_badge_progress"],
                "badge_counts_by_category": badge_payload["badge_counts_by_category"],
                "recent_unlocks": badge_payload["recent_unlocks"],
            }
        )

    return {
        "generated_at": _utc_now(),
        "reference_date": _format_date(reference),
        "dashboard_date_floor": _format_date(floor_date) if floor_date is not None else None,
        "dashboard_window": _dashboard_window(reference, floor_date),
        "visible_date_range": _date_range_payload(visible_records),
        "product_mode": MODE_CORE_ONLY,
        "default_mode": MODE_CORE_ONLY,
        "supported_modes": list(PUBLIC_SUPPORTED_MODES),
        "source_record_count": len(records),
        "visible_record_count": len(visible_records),
        "profile_count": len(profiles),
        "profiles": profiles,
        "profile_layout_config": admin_bundle["profile_layout_config"],
    }


def build_badge_index(
    records: list[dict],
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
    *,
    admin_bundle: dict | None = None,
    badge_context: dict | None = None,
) -> dict:
    admin_bundle, badge_context, _, _ = _resolve_public_context(
        records,
        admin_bundle=admin_bundle,
        badge_context=badge_context,
        floor_date=floor_date,
    )
    return build_badge_index_payload(badge_context, admin_bundle=admin_bundle)


def build_admin_preview(
    records: list[dict],
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
    *,
    admin_bundle: dict | None = None,
    badge_context: dict | None = None,
) -> dict:
    admin_bundle, badge_context, _, _ = _resolve_public_context(
        records,
        admin_bundle=admin_bundle,
        badge_context=badge_context,
        floor_date=floor_date,
    )
    return build_admin_preview_payload(
        badge_context,
        admin_bundle=admin_bundle,
        source_paths=admin_config_source_paths(),
    )


def _resolve_public_context(
    records: list[dict],
    *,
    admin_bundle: dict | None,
    badge_context: dict | None,
    floor_date: date | None,
) -> tuple[dict, dict, list[dict], date]:
    visible_records = filter_dashboard_records(records, floor_date=floor_date)
    reference = _resolve_reference_date(visible_records, fallback=floor_date)
    resolved_admin_bundle = admin_bundle or load_admin_config_bundle()
    resolved_badge_context = badge_context or build_badge_context(
        records,
        admin_bundle=resolved_admin_bundle,
        reference_date=reference,
        floor_date=floor_date,
    )
    return resolved_admin_bundle, resolved_badge_context, visible_records, reference


def _ops_snapshot(summary: dict) -> dict:
    return {
        "review_queue_count": summary["review_queue_count"],
        "review_reason_counts": summary["review_reason_counts"],
        "excluded_record_count": summary["excluded_record_count"],
        "excluded_reason_counts": summary["excluded_reason_counts"],
        "warning_code_counts": summary["warning_code_counts"],
        "source_counts": summary["source_counts"],
        "manual_override_counts": summary["manual_override_counts"],
    }


def _parse_status_rows(records: list[dict], *, parsed: bool) -> list[dict]:
    rows: list[dict] = []
    selected = [
        row for row in records
        if (_is_included(row) if parsed else not _is_included(row))
    ]
    selected.sort(
        key=lambda row: (row.get("post_datetime") or "", int(row.get("post_id") or 0)),
        reverse=True,
    )
    for row in selected:
        payload = {
            "post_id": row.get("post_id"),
            "post_date": row.get("post_date"),
            "post_datetime": row.get("post_datetime"),
            "author": row.get("author"),
            "title": row.get("title"),
            "url": row.get("url"),
            "source": row.get("source") or "none",
            "score": row.get("score"),
        }
        if parsed:
            payload.update(
                {
                    "distance_m": row.get("distance_m"),
                    "total_time_text": row.get("total_time_text"),
                    "total_seconds": _total_seconds(row),
                    "metric_bucket": resolve_metric_bucket(row),
                    "manual_override_decision": row.get("manual_override_decision"),
                }
            )
        else:
            payload.update(
                {
                    "reason_code": (
                        row.get("review_reason_code")
                        or row.get("exclude_reason_code")
                        or "UNKNOWN"
                    ),
                    "evidence_text": row.get("evidence_text") or "",
                    "review_needed": _is_review_needed(row),
                    "manual_override_decision": row.get("manual_override_decision"),
                }
            )
        rows.append(payload)
    return rows


def _empty_badge_payload() -> dict:
    return {
        "primary_title": None,
        "unlocked_badges": [],
        "next_badge_progress": None,
        "badge_counts_by_category": {
            "attendance": 0,
            "distance": 0,
            "time": 0,
            "efficiency": 0,
            "growth": 0,
            "season": 0,
            "gallery": 0,
            "fun": 0,
        },
        "recent_unlocks": [],
    }


def _enrich_author_rows(author_rows: list[dict], badge_context: dict) -> list[dict]:
    enriched: list[dict] = []
    for row in author_rows:
        badge_payload = badge_context["authors"].get(row["author"], _empty_badge_payload())
        enriched.append(
            {
                **row,
                "primary_title": badge_payload["primary_title"],
                "unlocked_badges": badge_payload["unlocked_badges"],
                "unlocked_badge_count": len(badge_payload["unlocked_badges"]),
                "badge_counts_by_category": badge_payload["badge_counts_by_category"],
                "next_badge_progress": badge_payload["next_badge_progress"],
                "recent_unlocks": badge_payload["recent_unlocks"],
            }
        )
    return enriched


def _build_ranking_sections(author_rows: list[dict], home_sections: dict) -> dict:
    ranking_specs = list(home_sections.get("ranking_sections", []))
    metrics: dict[str, dict] = {}
    for spec in ranking_specs:
        metric_key = str(spec.get("metric_key") or "")
        if not metric_key:
            continue
        rows = _ranking_rows_for_metric(author_rows, spec)
        metrics[metric_key] = {
            "metric_key": metric_key,
            "label_ko": spec.get("label_ko"),
            "description_ko": spec.get("description_ko"),
            "top3": rows[:3],
            "ranks_4_to_20": rows[3:20],
            "rows": rows[:20],
            "total_ranked_rows": len(rows),
        }
    return {
        "default_metric": home_sections.get("default_ranking_metric", "swim_count"),
        "metrics": metrics,
    }


def _ranking_rows_for_metric(author_rows: list[dict], spec: dict) -> list[dict]:
    metric_key = str(spec.get("metric_key") or "")
    rows = []
    for author_row in author_rows:
        metric_value = _author_metric_value(author_row, metric_key)
        rows.append(
            {
                "author": author_row["author"],
                "search_key": author_row["search_key"],
                "latest_post_date": author_row["latest_post_date"],
                "metric_key": metric_key,
                "metric_value": metric_value,
                "metric_value_text_ko": _format_ranking_metric(metric_key, metric_value),
                "secondary_text_ko": _ranking_secondary_text(author_row, metric_key),
                "primary_title": author_row.get("primary_title"),
                "unlocked_badge_count": author_row.get("unlocked_badge_count", 0),
                "badge_counts_by_category": author_row.get("badge_counts_by_category", {}),
                "badge_preview": [
                    badge.get("short_label_ko")
                    for badge in author_row.get("unlocked_badges", [])[:3]
                    if badge.get("short_label_ko")
                ],
            }
        )
    rows.sort(
        key=lambda row: (
            -_ranking_sort_value(row["metric_value"]),
            row["author"],
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def _author_metric_value(author_row: dict, metric_key: str) -> float | int | None:
    if metric_key == "swim_count":
        return author_row.get("swim_count")
    if metric_key == "total_distance_m":
        return author_row.get("total_distance_m")
    if metric_key == "total_seconds":
        return author_row.get("total_seconds")
    if metric_key == "distance_per_hour_m":
        return author_row.get("distance_per_hour_m")
    if metric_key == "growth_swim_count":
        return author_row.get("growth_swim_count", {}).get("delta_value")
    if metric_key == "growth_distance_m":
        return author_row.get("growth_distance_m", {}).get("delta_value")
    if metric_key == "growth_total_seconds":
        return author_row.get("growth_total_seconds", {}).get("delta_value")
    return 0


def _ranking_secondary_text(author_row: dict, metric_key: str) -> str:
    if metric_key.startswith("growth_"):
        return (
            f"누적 {_format_ranking_metric('total_distance_m', author_row.get('total_distance_m'))}"
            f" · {_format_ranking_metric('total_seconds', author_row.get('total_seconds'))}"
        )
    return (
        f"{_format_ranking_metric('swim_count', author_row.get('swim_count'))}"
        f" · {_format_ranking_metric('total_distance_m', author_row.get('total_distance_m'))}"
    )


def _format_ranking_metric(metric_key: str, value) -> str:  # noqa: ANN001
    if metric_key in {"swim_count", "growth_swim_count"}:
        prefix = "+" if metric_key.startswith("growth_") and float(value or 0) > 0 else ""
        return f"{prefix}{int(round(float(value or 0)))}회"
    if metric_key in {"total_distance_m", "growth_distance_m"}:
        prefix = "+" if metric_key.startswith("growth_") and float(value or 0) > 0 else ""
        return f"{prefix}{_format_distance_metric(float(value or 0))}"
    if metric_key in {"total_seconds", "growth_total_seconds"}:
        prefix = "+" if metric_key.startswith("growth_") and float(value or 0) > 0 else ""
        return f"{prefix}{_format_duration_metric(int(round(float(value or 0))))}"
    if metric_key == "distance_per_hour_m":
        return f"{int(round(float(value or 0)))}m/h"
    return str(value)


def _format_distance_metric(value: float) -> str:
    if value >= 1000:
        km_value = value / 1000.0
        if abs(km_value - round(km_value)) < 0.0001:
            return f"{int(round(km_value))}km"
        return f"{km_value:.1f}km"
    return f"{int(round(value))}m"


def _format_duration_metric(total_seconds: int) -> str:
    hours, remainder = divmod(max(total_seconds, 0), 3600)
    minutes, _seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}시간 {minutes}분"
    return f"{minutes}분"

def _ranking_sort_value(value) -> float:  # noqa: ANN001
    if value is None:
        return -1.0
    return float(value)


def _build_dashboard_mode_view(
    records: list[dict],
    mode: str,
    reference_date: date,
    *,
    floor_date: date | None,
    recent_limit: int,
    leaderboard_limit: int,
    monthly_limit: int | None,
) -> dict:
    summary = build_summary(records, mode=mode, reference_date=reference_date, floor_date=floor_date)
    monthly = build_monthly(records, mode=mode, floor_date=floor_date)
    leaderboard = build_leaderboard(records, mode=mode, reference_date=reference_date, floor_date=floor_date)

    if monthly_limit is not None:
        monthly = monthly[-monthly_limit:]

    return {
        "summary": summary,
        "monthly": monthly,
        "leaderboard": _slice_leaderboard(leaderboard, leaderboard_limit),
        "growth_leaderboard": {
            "by_swim_count": leaderboard["growth_by_swim_count"][:leaderboard_limit],
            "by_distance_m": leaderboard["growth_by_distance_m"][:leaderboard_limit],
            "by_total_seconds": leaderboard["growth_by_total_seconds"][:leaderboard_limit],
        },
        "recent_records": _recent_record_previews(records, mode, recent_limit),
    }


def _build_author_mode_profile(author_records: list[dict], mode: str, reference_date: date) -> dict:
    summary = build_summary(author_records, mode=mode, reference_date=reference_date)
    return {
        "summary": summary,
        "recent_28d_vs_previous_28d": summary["growth"],
        "monthly_trend": build_monthly(author_records, mode=mode),
        "recent_records": _recent_record_previews(author_records, mode, 20),
        "time_series": {
            "daily": _daily_time_series(author_records, mode),
        },
    }


def _author_aggregate_rows(records: list[dict], reference_date: date, floor_date: date | None = DASHBOARD_DATE_FLOOR) -> list[dict]:
    per_author: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        author = rec.get("author")
        if not author:
            continue
        per_author[str(author)].append(rec)

    rows: list[dict] = []
    for author in sorted(per_author):
        author_records = per_author[author]
        total_distance_m = round(sum(to_float(rec.get("distance_m")) for rec in author_records), 2)
        total_seconds = sum(_total_seconds(rec) for rec in author_records)
        total_duration_min = round(float(total_seconds) / 60.0, 2)
        growth = _build_growth_summary(author_records, reference_date, floor_date=floor_date)
        rows.append(
            {
                "author": author,
                "search_key": _author_search_key(author),
                "swim_count": len(author_records),
                "total_distance_m": total_distance_m,
                "total_seconds": total_seconds,
                "total_duration_min": total_duration_min,
                "distance_per_hour_m": _distance_per_hour(total_distance_m, total_seconds),
                "post_count": len(author_records),
                "latest_post_date": _latest_post_date(author_records),
                "metric_bucket_counts": _metric_bucket_counts(author_records),
                "growth": growth,
                "growth_swim_count": growth["metrics"]["swim_count"],
                "growth_distance_m": growth["metrics"]["distance_m"],
                "growth_total_seconds": growth["metrics"]["total_seconds"],
            }
        )
    return rows


def _growth_rows(author_rows: list[dict], metric_name: str) -> list[dict]:
    key_name = f"growth_{metric_name}"
    rows = [
        {
            "author": row["author"],
            "search_key": row["search_key"],
            "latest_post_date": row["latest_post_date"],
            "swim_count": row["swim_count"],
            "total_distance_m": row["total_distance_m"],
            "total_seconds": row["total_seconds"],
            "distance_per_hour_m": row["distance_per_hour_m"],
            "growth": row[key_name],
        }
        for row in author_rows
    ]
    rows.sort(
        key=lambda item: (
            -float(item["growth"]["delta_value"]),
            -float(item["growth"]["recent_value"]),
            item["author"],
        )
    )
    return rows


def _slice_leaderboard(leaderboard: dict, limit: int) -> dict:
    return {
        "mode": leaderboard["mode"],
        "reference_date": leaderboard["reference_date"],
        "generated_at": leaderboard["generated_at"],
        "leaderboard_metrics": list(leaderboard["leaderboard_metrics"]),
        "growth_metrics": list(leaderboard["growth_metrics"]),
        "authors": leaderboard["authors"][:limit],
        "by_distance": leaderboard["by_distance"][:limit],
        "by_swim_count": leaderboard["by_swim_count"][:limit],
        "by_duration": leaderboard["by_duration"][:limit],
        "by_total_seconds": leaderboard["by_total_seconds"][:limit],
        "by_distance_per_hour_m": leaderboard["by_distance_per_hour_m"][:limit],
        "growth_by_swim_count": leaderboard["growth_by_swim_count"][:limit],
        "growth_by_distance_m": leaderboard["growth_by_distance_m"][:limit],
        "growth_by_total_seconds": leaderboard["growth_by_total_seconds"][:limit],
    }


def _recent_record_previews(records: list[dict], mode: str, limit: int) -> list[dict]:
    selected = _included_records(records, mode)
    selected.sort(key=lambda row: (row.get("post_datetime") or "", int(row.get("post_id") or 0)), reverse=True)
    previews: list[dict] = []
    for rec in selected[:limit]:
        previews.append(
            {
                "post_id": rec.get("post_id"),
                "post_date": rec.get("post_date"),
                "post_datetime": rec.get("post_datetime"),
                "author": rec.get("author"),
                "distance_m": rec.get("distance_m"),
                "total_time_text": rec.get("total_time_text"),
                "total_seconds": _total_seconds(rec),
                "source": rec.get("source") or "none",
                "metric_bucket": resolve_metric_bucket(rec),
                "score": rec.get("score"),
                "warning_codes": [str(code) for code in (rec.get("warning_codes") or []) if code],
                "url": rec.get("url"),
            }
        )
    return previews


def _daily_time_series(records: list[dict], mode: str) -> list[dict]:
    bucket: dict[str, dict] = defaultdict(
        lambda: {
            "date": "",
            "swim_count": 0,
            "total_distance_m": 0.0,
            "total_seconds": 0,
        }
    )
    for rec in _included_records(records, mode):
        item_date = str(rec.get("post_date") or "")[:10]
        if not item_date:
            continue
        entry = bucket[item_date]
        entry["date"] = item_date
        entry["swim_count"] += 1
        entry["total_distance_m"] += to_float(rec.get("distance_m"))
        entry["total_seconds"] += _total_seconds(rec)

    rows: list[dict] = []
    for item_date in sorted(bucket):
        entry = bucket[item_date]
        rows.append(
            {
                "date": item_date,
                "swim_count": entry["swim_count"],
                "total_distance_m": round(entry["total_distance_m"], 2),
                "total_seconds": entry["total_seconds"],
                "total_duration_min": round(float(entry["total_seconds"]) / 60.0, 2),
                "distance_per_hour_m": _distance_per_hour(entry["total_distance_m"], entry["total_seconds"]),
            }
        )
    return rows


def _build_growth_summary(
    records: list[dict],
    reference_date: date,
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
) -> dict:
    recent_records, previous_records, recent_window, previous_window = _split_growth_windows(
        records,
        reference_date,
        floor_date=floor_date,
    )
    recent_distance = round(sum(to_float(row.get("distance_m")) for row in recent_records), 2)
    previous_distance = round(sum(to_float(row.get("distance_m")) for row in previous_records), 2)
    recent_seconds = sum(_total_seconds(row) for row in recent_records)
    previous_seconds = sum(_total_seconds(row) for row in previous_records)
    return {
        "reference_date": _format_date(reference_date),
        "window_days": 28,
        "dashboard_date_floor": _format_date(floor_date) if floor_date is not None else None,
        "recent_window": recent_window,
        "previous_window": previous_window,
        "metrics": {
            "swim_count": _growth_metric_payload(len(recent_records), len(previous_records)),
            "distance_m": _growth_metric_payload(recent_distance, previous_distance),
            "total_seconds": _growth_metric_payload(recent_seconds, previous_seconds),
        },
    }


def _growth_metric_payload(recent_value: float | int, previous_value: float | int) -> dict:
    delta_value = round(float(recent_value) - float(previous_value), 2)
    if float(previous_value) > 0:
        pct_change = round((delta_value / float(previous_value)) * 100.0, 2)
        pct_status = "standard"
    elif float(recent_value) == 0:
        pct_change = 0.0
        pct_status = "previous_zero_no_change"
    else:
        pct_change = None
        pct_status = "previous_zero_growth"
    return {
        "recent_value": recent_value,
        "previous_value": previous_value,
        "delta_value": delta_value,
        "pct_change": pct_change,
        "pct_change_status": pct_status,
    }


def _split_growth_windows(
    records: list[dict],
    reference_date: date,
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
) -> tuple[list[dict], list[dict], dict, dict]:
    recent_start_nominal = reference_date - timedelta(days=27)
    previous_end_nominal = recent_start_nominal - timedelta(days=1)
    previous_start_nominal = previous_end_nominal - timedelta(days=27)

    recent_start = recent_start_nominal
    previous_start: date | None = previous_start_nominal
    previous_end: date | None = previous_end_nominal
    recent_truncated = False
    previous_truncated = False

    if floor_date is not None and recent_start < floor_date:
        recent_start = floor_date
        recent_truncated = True

    if floor_date is not None:
        if previous_end_nominal < floor_date:
            previous_start = None
            previous_end = None
            previous_truncated = True
        elif previous_start_nominal < floor_date:
            previous_start = floor_date
            previous_end = previous_end_nominal
            previous_truncated = True

    recent_records: list[dict] = []
    previous_records: list[dict] = []
    for row in records:
        item_date = _record_date(row)
        if item_date is None:
            continue
        if recent_start <= item_date <= reference_date:
            recent_records.append(row)
        elif previous_start is not None and previous_end is not None and previous_start <= item_date <= previous_end:
            previous_records.append(row)

    return (
        recent_records,
        previous_records,
        _window_payload(
            start=recent_start,
            end=reference_date,
            nominal_start=recent_start_nominal,
            nominal_end=reference_date,
            truncated_by_floor=recent_truncated,
        ),
        _window_payload(
            start=previous_start,
            end=previous_end,
            nominal_start=previous_start_nominal,
            nominal_end=previous_end_nominal,
            truncated_by_floor=previous_truncated,
        ),
    )


def _included_records(records: list[dict], mode: str = MODE_CORE_ONLY) -> list[dict]:
    _validate_mode(mode)
    return [r for r in records if _is_included(r) and resolve_metric_bucket(r) == METRIC_BUCKET_CORE]


def _metric_bucket_counts(records: list[dict]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for record in records:
        bucket = resolve_metric_bucket(record)
        if bucket:
            counter[bucket] += 1
    return dict(sorted(counter.items()))


def _records_by_author(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        author = row.get("author")
        if not author:
            continue
        grouped[str(author)].append(row)
    return grouped


def _latest_post_date(records: list[dict]) -> str | None:
    dates = [row.get("post_date") for row in records if row.get("post_date")]
    if not dates:
        return None
    return max(str(value) for value in dates)


def _record_date(record: dict) -> date | None:
    raw = str(record.get("post_date") or record.get("post_datetime") or "").strip()
    if not raw:
        return None
    token = raw[:10]
    try:
        return datetime.strptime(token, "%Y-%m-%d").date()
    except ValueError:
        return None


def _resolve_reference_date(records: list[dict], fallback: date | None = None) -> date:
    dates = [_record_date(record) for record in records]
    valid = [item for item in dates if item is not None]
    if valid:
        return max(valid)
    if fallback is not None:
        return fallback
    return datetime.now(UTC).date()


def _distance_per_hour(distance_m: float | int, total_seconds: float | int) -> float | None:
    if float(distance_m) <= 0 or float(total_seconds) <= 0:
        return None
    return round((float(distance_m) * 3600.0) / float(total_seconds), 2)


def _duration_minutes(record: dict) -> float:
    return round(float(_total_seconds(record)) / 60.0, 2)


def _total_seconds(record: dict) -> int:
    value = record.get("total_seconds")
    if value in (None, ""):
        return 0
    try:
        return int(round(float(value)))
    except Exception:  # noqa: BLE001
        return 0


def _sort_author_rows(rows: list[dict], primary_key: str, secondary_key: str) -> list[dict]:
    def _sortable(value):  # noqa: ANN001
        if value is None:
            return -1.0
        if isinstance(value, (int, float)):
            return float(value)
        return value

    return sorted(
        rows,
        key=lambda row: (
            -_sortable(row.get(primary_key)),
            -_sortable(row.get(secondary_key)),
            row.get("author") or "",
        ),
    )


def _author_search_key(author: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(author or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def _validate_mode(mode: str) -> None:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported metric mode: {mode}")


def _is_included(record: dict) -> bool:
    if "include" in record:
        return _as_bool(record.get("include"))
    return not _as_bool(record.get("is_excluded", False))


def _is_review_needed(record: dict) -> bool:
    return _as_bool(record.get("review_needed", False))


def _format_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _utc_now() -> str:
    return datetime.now(UTC).astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def _as_bool(value) -> bool:  # noqa: ANN001
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


def _dashboard_window(reference_date: date, floor_date: date | None) -> dict:
    return {
        "start": _format_date(floor_date) if floor_date is not None else None,
        "end": _format_date(reference_date),
    }


def _date_range_payload(records: list[dict]) -> dict:
    dates = [_record_date(record) for record in records]
    valid = [item for item in dates if item is not None]
    if not valid:
        return {"start": None, "end": None}
    return {"start": _format_date(min(valid)), "end": _format_date(max(valid))}


def _mode_record_counts(records: list[dict]) -> dict[str, int]:
    return {mode: len(_included_records(records, mode)) for mode in SUPPORTED_MODES}


def _mode_metric_bucket_counts(records: list[dict]) -> dict[str, dict[str, int]]:
    return {mode: _metric_bucket_counts(_included_records(records, mode)) for mode in SUPPORTED_MODES}


def _growth_window_metadata(reference_date: date, floor_date: date | None) -> dict:
    recent_window, previous_window = _window_bounds(reference_date, floor_date)
    return {
        "window_days": 28,
        "dashboard_date_floor": _format_date(floor_date) if floor_date is not None else None,
        "recent_window": recent_window,
        "previous_window": previous_window,
    }


def _window_bounds(reference_date: date, floor_date: date | None) -> tuple[dict, dict]:
    recent_start_nominal = reference_date - timedelta(days=27)
    previous_end_nominal = recent_start_nominal - timedelta(days=1)
    previous_start_nominal = previous_end_nominal - timedelta(days=27)

    recent_start = max(recent_start_nominal, floor_date) if floor_date is not None else recent_start_nominal
    recent_truncated = floor_date is not None and recent_start_nominal < floor_date

    previous_start: date | None = previous_start_nominal
    previous_end: date | None = previous_end_nominal
    previous_truncated = False
    if floor_date is not None:
        if previous_end_nominal < floor_date:
            previous_start = None
            previous_end = None
            previous_truncated = True
        elif previous_start_nominal < floor_date:
            previous_start = floor_date
            previous_end = previous_end_nominal
            previous_truncated = True

    return (
        _window_payload(
            start=recent_start,
            end=reference_date,
            nominal_start=recent_start_nominal,
            nominal_end=reference_date,
            truncated_by_floor=recent_truncated,
        ),
        _window_payload(
            start=previous_start,
            end=previous_end,
            nominal_start=previous_start_nominal,
            nominal_end=previous_end_nominal,
            truncated_by_floor=previous_truncated,
        ),
    )


def _window_payload(
    *,
    start: date | None,
    end: date | None,
    nominal_start: date,
    nominal_end: date,
    truncated_by_floor: bool,
) -> dict:
    visible_day_count = 0
    if start is not None and end is not None and start <= end:
        visible_day_count = (end - start).days + 1
    return {
        "start": _format_date(start) if start is not None else None,
        "end": _format_date(end) if end is not None else None,
        "nominal_start": _format_date(nominal_start),
        "nominal_end": _format_date(nominal_end),
        "nominal_day_count": 28,
        "visible_day_count": visible_day_count,
        "truncated_by_floor": truncated_by_floor,
    }
