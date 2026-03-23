from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from swimdash.admin_config import load_admin_config_bundle
from swimdash.config import DASHBOARD_DATE_FLOOR

CATEGORY_KEYS = (
    "attendance",
    "distance",
    "time",
    "efficiency",
    "growth",
    "season",
    "gallery",
    "fun",
)
CORE_SOURCES = {
    "title_format",
    "manual_review",
    "manual_patch",
}
PRIMARY_TITLE_CATEGORY_PRIORITY = {
    "growth": 80,
    "distance": 75,
    "time": 70,
    "attendance": 65,
    "efficiency": 60,
    "fun": 45,
    "season": 40,
    "gallery": 10,
}
NEXT_BADGE_CATEGORY_PRIORITY = {
    "attendance": 90,
    "distance": 80,
    "time": 70,
    "fun": 60,
    "efficiency": 50,
    "growth": 40,
    "season": 30,
    "gallery": 10,
}
try:
    KST = ZoneInfo("Asia/Seoul")
except ZoneInfoNotFoundError:
    KST = timezone(timedelta(hours=9), name="KST")


def build_badge_context(
    records: list[dict],
    *,
    admin_bundle: dict | None = None,
    reference_date: date | None = None,
    floor_date: date | None = DASHBOARD_DATE_FLOOR,
) -> dict:
    bundle = admin_bundle or load_admin_config_bundle()
    visible_records = _filter_visible_records(records, floor_date=floor_date)
    reference = reference_date or _resolve_reference_date(visible_records, fallback=floor_date)
    core_records = [record for record in visible_records if _is_core_record(record)]
    badge_catalog = _catalog_badges(bundle)
    gallery_status = _build_gallery_status(core_records, badge_catalog, bundle, reference)
    authors = sorted({str(record.get("author")) for record in visible_records if record.get("author")})

    author_payloads: dict[str, dict] = {}
    recent_unlocks: list[dict] = list(gallery_status["recent_unlocks"])
    for author in authors:
        author_records = [record for record in core_records if str(record.get("author") or "") == author]
        payload = _build_author_badges(
            author=author,
            author_records=author_records,
            badge_catalog=badge_catalog,
            bundle=bundle,
            reference_date=reference,
            floor_date=floor_date,
        )
        author_payloads[author] = payload
        recent_unlocks.extend(payload["recent_unlocks"])

    recent_unlocks.sort(
        key=lambda item: (
            item.get("unlocked_at") or "",
            item.get("author") or "",
            item.get("badge_id") or "",
        ),
        reverse=True,
    )

    return {
        "generated_at": _utc_now(),
        "reference_date": _format_date(reference),
        "dashboard_date_floor": _format_date(floor_date) if floor_date is not None else None,
        "category_labels": dict(bundle["badge_catalog"].get("category_labels", {})),
        "badge_catalog": badge_catalog,
        "gallery": gallery_status,
        "authors": author_payloads,
        "recent_unlocks": recent_unlocks[:12],
    }


def build_badge_index_payload(
    badge_context: dict,
    *,
    admin_bundle: dict | None = None,
) -> dict:
    bundle = admin_bundle or load_admin_config_bundle()
    badge_catalog = badge_context["badge_catalog"]
    category_counts = Counter(str(badge.get("category") or "unknown") for badge in badge_catalog)
    hidden_count = sum(1 for badge in badge_catalog if _as_bool(badge.get("is_hidden")))
    primary_title_count = sum(1 for badge in badge_catalog if _as_bool(badge.get("is_primary_title_candidate")))
    gallery_rules = _gallery_rules(bundle)

    return {
        "generated_at": badge_context["generated_at"],
        "reference_date": badge_context["reference_date"],
        "product_mode": "core_only",
        "category_labels": badge_context["category_labels"],
        "badge_count": len(badge_catalog),
        "badge_count_by_category": {key: int(category_counts.get(key, 0)) for key in CATEGORY_KEYS},
        "hidden_badge_count": hidden_count,
        "primary_title_candidate_count": primary_title_count,
        "season_badges": bundle["season_badges"],
        "gallery_title_rules": bundle["gallery_title_rules"],
        "gallery_titles": [
            {
                "badge_id": str(rule.get("badge_id") or ""),
                "name_ko": rule.get("name_ko"),
                "description_ko": rule.get("description_ko"),
                "threshold_type": rule.get("threshold_type"),
                "threshold_value": rule.get("threshold_value"),
            }
            for rule in gallery_rules
        ],
        "badges": badge_catalog,
    }


def build_admin_preview_payload(
    badge_context: dict,
    *,
    admin_bundle: dict | None = None,
    source_paths: dict[str, str] | None = None,
) -> dict:
    bundle = admin_bundle or load_admin_config_bundle()
    source_paths = source_paths or {}
    author_rows = [
        {
            "author": author,
            "primary_title": payload["primary_title"],
            "unlocked_badge_count": len(payload["unlocked_badges"]),
            "badge_counts_by_category": payload["badge_counts_by_category"],
            "next_badge_progress": payload["next_badge_progress"],
        }
        for author, payload in badge_context["authors"].items()
    ]
    author_rows.sort(key=lambda row: (-int(row["unlocked_badge_count"]), row["author"]))

    return {
        "generated_at": badge_context["generated_at"],
        "reference_date": badge_context["reference_date"],
        "product_mode": "core_only",
        "source_paths": source_paths,
        "site_config": bundle["site_config"],
        "navigation_config": bundle["navigation_config"],
        "home_sections": bundle["home_sections"],
        "profile_layout_config": bundle["profile_layout_config"],
        "season_badges": bundle["season_badges"],
        "gallery_title_rules": bundle["gallery_title_rules"],
        "badge_catalog_summary": {
            "badge_count": len(badge_context["badge_catalog"]),
            "badge_count_by_category": build_badge_index_payload(
                badge_context,
                admin_bundle=bundle,
            )["badge_count_by_category"],
        },
        "gallery_preview": {
            "current_title": badge_context["gallery"]["current_title"],
            "next_title_target": badge_context["gallery"]["next_title_target"],
            "progress": badge_context["gallery"]["progress"],
        },
        "author_preview": author_rows[:8],
    }


def _build_gallery_status(core_records: list[dict], badge_catalog: list[dict], bundle: dict, reference_date: date) -> dict:
    badge_by_id = {str(badge.get("badge_id") or ""): badge for badge in badge_catalog}
    rules = _gallery_rules(bundle)
    fallback = dict(bundle["gallery_title_rules"].get("fallback_title", {}))
    sorted_records = sorted(core_records, key=_record_sort_key)

    unlocked_events: list[dict] = []
    unlocked_ids: set[str] = set()
    total_distance = 0.0
    for record in sorted_records:
        total_distance += _safe_float(record.get("distance_m"))
        unlocked_at = _record_timestamp_token(record)
        for rule in rules:
            badge_id = str(rule.get("badge_id") or "")
            if not badge_id or badge_id in unlocked_ids:
                continue
            if total_distance < _safe_float(rule.get("threshold_value")):
                continue
            unlocked_ids.add(badge_id)
            badge = badge_by_id.get(badge_id, {})
            unlocked_events.append(
                {
                    "scope": "gallery",
                    "badge_id": badge_id,
                    "category": "gallery",
                    "name_ko": badge.get("name_ko") or rule.get("name_ko"),
                    "short_label_ko": badge.get("short_label_ko") or rule.get("short_label_ko"),
                    "description_ko": badge.get("description_ko") or rule.get("description_ko"),
                    "icon_key": badge.get("icon_key") or rule.get("icon_key"),
                    "tier": badge.get("tier") or rule.get("tier"),
                    "unlocked_at": unlocked_at,
                }
            )

    current_rule = {}
    for rule in rules:
        badge_id = str(rule.get("badge_id") or "")
        if badge_id in unlocked_ids:
            current_rule = rule

    next_rule = next((rule for rule in rules if str(rule.get("badge_id") or "") not in unlocked_ids), None)
    current_title = _gallery_title_payload(
        rule=current_rule,
        badge_by_id=badge_by_id,
        fallback=fallback,
        unlocked_events=unlocked_events,
    )
    next_title_target = _gallery_next_payload(next_rule, badge_by_id, total_distance)

    progress = {
        "metric_key": str(bundle["gallery_title_rules"].get("metric_key") or "total_distance_m"),
        "current_value": round(total_distance, 2),
        "current_value_text_ko": _format_value_ko("gallery_total_distance_m", total_distance),
        "target_value": next_title_target.get("target_value"),
        "target_value_text_ko": next_title_target.get("target_value_text_ko"),
        "remaining_value": next_title_target.get("remaining_value"),
        "remaining_value_text_ko": next_title_target.get("remaining_value_text_ko"),
        "progress_ratio": next_title_target.get("progress_ratio", 1.0),
        "unlocked_badge_count": len(unlocked_ids),
    }

    return {
        "current_title": current_title,
        "next_title_target": next_title_target,
        "progress": progress,
        "unlocked_badges": unlocked_events,
        "recent_unlocks": unlocked_events[-6:][::-1],
        "metric_value": round(total_distance, 2),
        "metric_value_text_ko": _format_value_ko("gallery_total_distance_m", total_distance),
        "reference_date": _format_date(reference_date),
    }


def _build_author_badges(
    *,
    author: str,
    author_records: list[dict],
    badge_catalog: list[dict],
    bundle: dict,
    reference_date: date,
    floor_date: date | None,
) -> dict:
    state = _build_author_state(author_records, reference_date, floor_date=floor_date)
    unlock_events = _author_unlock_events(
        author=author,
        author_records=author_records,
        badge_catalog=badge_catalog,
        floor_date=floor_date,
    )
    unlocked_at_by_badge = {event["badge_id"]: event["unlocked_at"] for event in unlock_events}
    category_order = list(bundle["profile_layout_config"].get("badge_category_order", CATEGORY_KEYS))

    unlocked_badges: list[dict] = []
    locked_badges: list[dict] = []
    for badge in badge_catalog:
        if str(badge.get("category") or "") == "gallery":
            continue
        progress = _evaluate_author_badge(badge, state)
        payload = _badge_payload(badge, progress)
        unlocked_at = unlocked_at_by_badge.get(payload["badge_id"])
        if progress["unlocked"]:
            payload["unlocked_at"] = unlocked_at or state["latest_post_date"] or _format_date(reference_date)
            unlocked_badges.append(payload)
        else:
            locked_badges.append(payload)

    unlocked_badges.sort(
        key=lambda badge: (
            _category_index(str(badge.get("category") or ""), category_order),
            -int(badge.get("tier") or 0),
            badge.get("name_ko") or "",
        )
    )

    category_counts = {key: 0 for key in CATEGORY_KEYS}
    for badge in unlocked_badges:
        category = str(badge.get("category") or "")
        if category in category_counts:
            category_counts[category] += 1

    recent_unlocks = [
        _recent_unlock_payload(author, event, unlocked_badges)
        for event in unlock_events
    ]
    recent_unlocks = [item for item in recent_unlocks if item is not None]
    recent_unlocks.sort(key=lambda item: (item["unlocked_at"], item["badge_id"]), reverse=True)

    return {
        "primary_title": _select_primary_title(unlocked_badges),
        "unlocked_badges": unlocked_badges,
        "next_badge_progress": _select_next_badge(locked_badges),
        "badge_counts_by_category": category_counts,
        "recent_unlocks": recent_unlocks[:6],
        "summary": {
            "core_swim_count": state["total_swim_count"],
            "core_total_distance_m": state["total_distance_m"],
            "core_total_seconds": state["total_seconds"],
            "distance_per_hour_m": state["distance_per_hour_m"],
        },
    }


def _author_unlock_events(
    *,
    author: str,
    author_records: list[dict],
    badge_catalog: list[dict],
    floor_date: date | None,
) -> list[dict]:
    sorted_records = sorted(author_records, key=_record_sort_key)
    unlocked_ids: set[str] = set()
    events: list[dict] = []

    for index, record in enumerate(sorted_records):
        snapshot = sorted_records[: index + 1]
        reference = _record_date(record) or DASHBOARD_DATE_FLOOR or datetime.now(UTC).date()
        state = _build_author_state(snapshot, reference, floor_date=floor_date)
        unlocked_at = _record_timestamp_token(record)
        for badge in badge_catalog:
            category = str(badge.get("category") or "")
            badge_id = str(badge.get("badge_id") or "")
            if not badge_id or category == "gallery" or badge_id in unlocked_ids:
                continue
            progress = _evaluate_author_badge(badge, state)
            if not progress["unlocked"]:
                continue
            unlocked_ids.add(badge_id)
            events.append(
                {
                    "author": author,
                    "badge_id": badge_id,
                    "unlocked_at": unlocked_at,
                }
            )

    return events


def _build_author_state(
    author_records: list[dict],
    reference_date: date,
    *,
    floor_date: date | None,
) -> dict:
    total_distance = round(sum(_safe_float(record.get("distance_m")) for record in author_records), 2)
    total_seconds = sum(_safe_int(record.get("total_seconds")) for record in author_records)
    monthly_tags = {
        str(record.get("post_date") or "")[5:7]
        for record in author_records
        if str(record.get("post_date") or "")[:7]
    }
    max_single_distance = max((_safe_float(record.get("distance_m")) for record in author_records), default=0.0)
    max_single_seconds = max((_safe_int(record.get("total_seconds")) for record in author_records), default=0)
    weekend_count = 0
    early_bird_count = 0
    night_owl_count = 0

    for record in author_records:
        item_date = _record_date(record)
        item_dt = _record_datetime(record)
        if item_date is not None and item_date.weekday() >= 5:
            weekend_count += 1
        if item_dt is not None and item_dt.hour < 8:
            early_bird_count += 1
        if item_dt is not None and item_dt.hour >= 21:
            night_owl_count += 1

    growth = _build_growth_summary(author_records, reference_date, floor_date=floor_date)
    return {
        "total_swim_count": len(author_records),
        "total_distance_m": total_distance,
        "total_seconds": total_seconds,
        "distance_per_hour_m": _distance_per_hour(total_distance, total_seconds),
        "growth": growth,
        "months_with_activity": monthly_tags,
        "max_single_distance_m": round(max_single_distance, 2),
        "max_single_total_seconds": max_single_seconds,
        "weekend_swim_count": weekend_count,
        "early_bird_swim_count": early_bird_count,
        "night_owl_swim_count": night_owl_count,
        "latest_post_date": _latest_post_date(author_records),
    }


def _evaluate_author_badge(badge: dict, state: dict) -> dict:
    threshold_type = str(badge.get("threshold_type") or "")
    threshold_value = badge.get("threshold_value")
    season_tag = badge.get("season_tag")

    current_value = 0.0
    if threshold_type == "author_total_swim_count":
        current_value = float(state["total_swim_count"])
    elif threshold_type == "author_total_distance_m":
        current_value = float(state["total_distance_m"])
    elif threshold_type == "author_total_seconds":
        current_value = float(state["total_seconds"])
    elif threshold_type == "author_distance_per_hour_m":
        current_value = float(state["distance_per_hour_m"] or 0.0)
    elif threshold_type == "author_recent_growth_swim_count":
        current_value = float(state["growth"]["metrics"]["swim_count"]["delta_value"])
    elif threshold_type == "author_recent_growth_distance_m":
        current_value = float(state["growth"]["metrics"]["distance_m"]["delta_value"])
    elif threshold_type == "author_recent_growth_total_seconds":
        current_value = float(state["growth"]["metrics"]["total_seconds"]["delta_value"])
    elif threshold_type == "season_month_participation":
        current_value = 1.0 if str(season_tag or "") in state["months_with_activity"] else 0.0
    elif threshold_type == "author_single_swim_distance_m":
        current_value = float(state["max_single_distance_m"])
    elif threshold_type == "author_single_swim_total_seconds":
        current_value = float(state["max_single_total_seconds"])
    elif threshold_type == "author_weekend_swim_count":
        current_value = float(state["weekend_swim_count"])
    elif threshold_type == "author_early_bird_swim_count":
        current_value = float(state["early_bird_swim_count"])
    elif threshold_type == "author_night_owl_swim_count":
        current_value = float(state["night_owl_swim_count"])

    target_value = max(_safe_float(threshold_value), 0.0)
    if target_value == 0:
        progress_ratio = 1.0
        remaining_value = 0.0
        unlocked = True
    else:
        progress_ratio = min(max(current_value / target_value, 0.0), 1.0)
        remaining_value = max(target_value - current_value, 0.0)
        unlocked = current_value >= target_value

    return {
        "threshold_type": threshold_type,
        "threshold_value": threshold_value,
        "current_value": _coerce_progress_value(current_value),
        "current_value_text_ko": _format_value_ko(threshold_type, current_value, season_tag=season_tag),
        "target_value": _coerce_progress_value(target_value),
        "target_value_text_ko": _format_value_ko(threshold_type, target_value, season_tag=season_tag),
        "remaining_value": _coerce_progress_value(remaining_value),
        "remaining_value_text_ko": _remaining_value_text_ko(
            threshold_type,
            remaining_value,
            season_tag=season_tag,
        ),
        "progress_ratio": round(progress_ratio, 4),
        "unlocked": unlocked,
    }


def _badge_payload(badge: dict, progress: dict) -> dict:
    return {
        "badge_id": str(badge.get("badge_id") or ""),
        "category": str(badge.get("category") or ""),
        "name_ko": badge.get("name_ko"),
        "short_label_ko": badge.get("short_label_ko"),
        "description_ko": badge.get("description_ko"),
        "threshold_type": progress["threshold_type"],
        "threshold_value": badge.get("threshold_value"),
        "icon_key": badge.get("icon_key"),
        "tier": badge.get("tier"),
        "is_primary_title_candidate": _as_bool(badge.get("is_primary_title_candidate")),
        "is_hidden": _as_bool(badge.get("is_hidden")),
        "season_tag": badge.get("season_tag"),
        "current_value": progress["current_value"],
        "current_value_text_ko": progress["current_value_text_ko"],
        "target_value": progress["target_value"],
        "target_value_text_ko": progress["target_value_text_ko"],
        "remaining_value": progress["remaining_value"],
        "remaining_value_text_ko": progress["remaining_value_text_ko"],
        "progress_ratio": progress["progress_ratio"],
    }


def _select_primary_title(unlocked_badges: list[dict]) -> dict | None:
    candidates = [badge for badge in unlocked_badges if not _as_bool(badge.get("is_hidden"))]
    if not candidates:
        candidates = list(unlocked_badges)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda badge: (
            int(badge.get("tier") or 0),
            int(_as_bool(badge.get("is_primary_title_candidate"))),
            PRIMARY_TITLE_CATEGORY_PRIORITY.get(str(badge.get("category") or ""), 0),
            _safe_float(badge.get("threshold_value")),
            badge.get("badge_id") or "",
        ),
    )


def _select_next_badge(locked_badges: list[dict]) -> dict | None:
    candidates = [
        badge
        for badge in locked_badges
        if not _as_bool(badge.get("is_hidden")) and str(badge.get("category") or "") not in {"gallery", "season"}
    ]
    if not candidates:
        candidates = [
            badge
            for badge in locked_badges
            if not _as_bool(badge.get("is_hidden")) and str(badge.get("category") or "") != "gallery"
        ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda badge: (
            float(badge.get("progress_ratio") or 0.0),
            NEXT_BADGE_CATEGORY_PRIORITY.get(str(badge.get("category") or ""), 0),
            -_safe_float(badge.get("remaining_value")),
            -_safe_float(badge.get("threshold_value")),
            badge.get("badge_id") or "",
        ),
    )


def _recent_unlock_payload(author: str, event: dict, unlocked_badges: list[dict]) -> dict | None:
    badge_id = str(event.get("badge_id") or "")
    badge = next((item for item in unlocked_badges if str(item.get("badge_id") or "") == badge_id), None)
    if badge is None:
        return None
    return {
        "scope": "author",
        "author": author,
        "badge_id": badge_id,
        "category": badge.get("category"),
        "name_ko": badge.get("name_ko"),
        "short_label_ko": badge.get("short_label_ko"),
        "icon_key": badge.get("icon_key"),
        "unlocked_at": event.get("unlocked_at"),
    }


def _gallery_title_payload(rule: dict, badge_by_id: dict[str, dict], fallback: dict, unlocked_events: list[dict]) -> dict:
    badge_id = str(rule.get("badge_id") or "")
    if not badge_id:
        return {
            "badge_id": str(fallback.get("badge_id") or "gal_00"),
            "name_ko": fallback.get("name_ko"),
            "short_label_ko": fallback.get("short_label_ko"),
            "description_ko": fallback.get("description_ko"),
            "icon_key": fallback.get("icon_key"),
            "tier": fallback.get("tier"),
            "unlocked_at": None,
        }

    badge = badge_by_id.get(badge_id, {})
    unlocked_at = None
    for event in unlocked_events:
        if str(event.get("badge_id") or "") == badge_id:
            unlocked_at = event.get("unlocked_at")
    return {
        "badge_id": badge_id,
        "name_ko": badge.get("name_ko") or rule.get("name_ko"),
        "short_label_ko": badge.get("short_label_ko") or rule.get("short_label_ko"),
        "description_ko": badge.get("description_ko") or rule.get("description_ko"),
        "icon_key": badge.get("icon_key") or rule.get("icon_key"),
        "tier": badge.get("tier") or rule.get("tier"),
        "unlocked_at": unlocked_at,
    }


def _gallery_next_payload(rule: dict | None, badge_by_id: dict[str, dict], current_distance: float) -> dict:
    if rule is None:
        return {
            "badge_id": None,
            "name_ko": None,
            "short_label_ko": None,
            "description_ko": None,
            "icon_key": None,
            "tier": None,
            "target_value": None,
            "target_value_text_ko": None,
            "remaining_value": 0,
            "remaining_value_text_ko": "모든 갤 칭호 해금 완료",
            "progress_ratio": 1.0,
        }

    badge_id = str(rule.get("badge_id") or "")
    badge = badge_by_id.get(badge_id, {})
    target_value = _safe_float(rule.get("threshold_value"))
    remaining_value = max(target_value - current_distance, 0.0)
    progress_ratio = 1.0 if target_value <= 0 else min(max(current_distance / target_value, 0.0), 1.0)
    return {
        "badge_id": badge_id,
        "name_ko": badge.get("name_ko") or rule.get("name_ko"),
        "short_label_ko": badge.get("short_label_ko") or rule.get("short_label_ko"),
        "description_ko": badge.get("description_ko") or rule.get("description_ko"),
        "icon_key": badge.get("icon_key") or rule.get("icon_key"),
        "tier": badge.get("tier") or rule.get("tier"),
        "target_value": _coerce_progress_value(target_value),
        "target_value_text_ko": _format_value_ko("gallery_total_distance_m", target_value),
        "remaining_value": _coerce_progress_value(remaining_value),
        "remaining_value_text_ko": _remaining_value_text_ko("gallery_total_distance_m", remaining_value),
        "progress_ratio": round(progress_ratio, 4),
    }


def _build_growth_summary(records: list[dict], reference_date: date, *, floor_date: date | None) -> dict:
    recent_records, previous_records = _split_growth_windows(records, reference_date, floor_date=floor_date)
    return {
        "metrics": {
            "swim_count": _growth_metric_payload(len(recent_records), len(previous_records)),
            "distance_m": _growth_metric_payload(
                round(sum(_safe_float(record.get("distance_m")) for record in recent_records), 2),
                round(sum(_safe_float(record.get("distance_m")) for record in previous_records), 2),
            ),
            "total_seconds": _growth_metric_payload(
                sum(_safe_int(record.get("total_seconds")) for record in recent_records),
                sum(_safe_int(record.get("total_seconds")) for record in previous_records),
            ),
        }
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
    *,
    floor_date: date | None,
) -> tuple[list[dict], list[dict]]:
    recent_start = reference_date - timedelta(days=27)
    previous_end = recent_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=27)

    if floor_date is not None and recent_start < floor_date:
        recent_start = floor_date

    if floor_date is not None and previous_end < floor_date:
        previous_start = None
        previous_end = None
    elif floor_date is not None and previous_start < floor_date:
        previous_start = floor_date

    recent_records: list[dict] = []
    previous_records: list[dict] = []
    for record in records:
        item_date = _record_date(record)
        if item_date is None:
            continue
        if recent_start <= item_date <= reference_date:
            recent_records.append(record)
        elif previous_start is not None and previous_end is not None and previous_start <= item_date <= previous_end:
            previous_records.append(record)
    return recent_records, previous_records


def _catalog_badges(bundle: dict) -> list[dict]:
    payload = bundle["badge_catalog"]
    badges = payload.get("badges", []) if isinstance(payload, dict) else payload
    return [dict(item) for item in badges if isinstance(item, dict)]


def _gallery_rules(bundle: dict) -> list[dict]:
    payload = bundle["gallery_title_rules"]
    rules = payload.get("rules", []) if isinstance(payload, dict) else []
    return sorted(
        [dict(item) for item in rules if isinstance(item, dict)],
        key=lambda item: _safe_float(item.get("threshold_value")),
    )


def _filter_visible_records(records: list[dict], *, floor_date: date | None) -> list[dict]:
    if floor_date is None:
        return list(records)
    visible: list[dict] = []
    for record in records:
        item_date = _record_date(record)
        if item_date is None:
            continue
        if item_date >= floor_date:
            visible.append(record)
    return visible


def _is_core_record(record: dict) -> bool:
    if not _is_included(record):
        return False
    metric_bucket = str(record.get("metric_bucket") or "")
    if metric_bucket:
        return metric_bucket == "core"
    return str(record.get("source") or "none") in CORE_SOURCES


def _is_included(record: dict) -> bool:
    if "include" in record:
        return _as_bool(record.get("include"))
    return not _as_bool(record.get("is_excluded"))


def _record_sort_key(record: dict) -> tuple[str, int]:
    return (_record_timestamp_token(record), _safe_int(record.get("post_id")))


def _record_timestamp_token(record: dict) -> str:
    return str(record.get("post_datetime") or record.get("post_date") or "")


def _record_date(record: dict) -> date | None:
    raw = str(record.get("post_date") or record.get("post_datetime") or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _record_datetime(record: dict) -> datetime | None:
    raw = str(record.get("post_datetime") or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _resolve_reference_date(records: list[dict], *, fallback: date | None) -> date:
    valid = [item for item in (_record_date(record) for record in records) if item is not None]
    if valid:
        return max(valid)
    if fallback is not None:
        return fallback
    return datetime.now(UTC).date()


def _latest_post_date(records: list[dict]) -> str | None:
    values = [str(record.get("post_date") or "") for record in records if record.get("post_date")]
    if not values:
        return None
    return max(values)


def _distance_per_hour(distance_m: float, total_seconds: int) -> float | None:
    if distance_m <= 0 or total_seconds <= 0:
        return None
    return round((distance_m * 3600.0) / float(total_seconds), 2)


def _category_index(category: str, category_order: list[str]) -> int:
    try:
        return category_order.index(category)
    except ValueError:
        return len(category_order) + 1


def _format_value_ko(threshold_type: str, value: float, *, season_tag: str | None = None) -> str:
    if threshold_type in {
        "author_total_swim_count",
        "author_recent_growth_swim_count",
        "author_weekend_swim_count",
        "author_early_bird_swim_count",
        "author_night_owl_swim_count",
    }:
        return f"{int(round(value))}회"
    if threshold_type in {
        "author_total_distance_m",
        "author_recent_growth_distance_m",
        "author_single_swim_distance_m",
        "gallery_total_distance_m",
    }:
        return _format_distance_ko(value)
    if threshold_type in {
        "author_total_seconds",
        "author_recent_growth_total_seconds",
        "author_single_swim_total_seconds",
    }:
        return _format_duration_ko(int(round(value)))
    if threshold_type == "author_distance_per_hour_m":
        return f"{int(round(value))}m/h"
    if threshold_type == "season_month_participation":
        month = str(season_tag or "").zfill(2)
        return f"{int(month)}월 완료" if value >= 1 else f"{int(month)}월 대기"
    return str(value)


def _remaining_value_text_ko(threshold_type: str, value: float, *, season_tag: str | None = None) -> str:
    if threshold_type == "season_month_participation":
        month = str(season_tag or "").zfill(2)
        return "해금 완료" if value <= 0 else f"{int(month)}월 core 기록 1건 필요"
    if value <= 0:
        return "해금 완료"
    if threshold_type in {
        "author_total_swim_count",
        "author_recent_growth_swim_count",
        "author_weekend_swim_count",
        "author_early_bird_swim_count",
        "author_night_owl_swim_count",
    }:
        return f"{int(round(value))}회 남음"
    if threshold_type in {
        "author_total_distance_m",
        "author_recent_growth_distance_m",
        "author_single_swim_distance_m",
        "gallery_total_distance_m",
    }:
        return f"{_format_distance_ko(value)} 남음"
    if threshold_type in {
        "author_total_seconds",
        "author_recent_growth_total_seconds",
        "author_single_swim_total_seconds",
    }:
        return f"{_format_duration_ko(int(round(value)))} 남음"
    if threshold_type == "author_distance_per_hour_m":
        return f"{int(round(value))}m/h 남음"
    return str(value)


def _format_distance_ko(value: float) -> str:
    if value >= 1000:
        km_value = value / 1000.0
        if abs(km_value - round(km_value)) < 0.0001:
            return f"{int(round(km_value))}km"
        return f"{km_value:.1f}km"
    return f"{int(round(value))}m"


def _format_duration_ko(total_seconds: int) -> str:
    if total_seconds <= 0:
        return "0분"
    hours, remainder = divmod(int(total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours and seconds:
        return f"{hours}시간 {minutes}분 {seconds}초"
    if hours:
        return f"{hours}시간 {minutes}분"
    if seconds and minutes == 0:
        return f"{seconds}초"
    if seconds:
        return f"{minutes}분 {seconds}초"
    return f"{minutes}분"

def _coerce_progress_value(value: float) -> int | float:
    if abs(value - round(value)) < 0.0001:
        return int(round(value))
    return round(value, 2)


def _safe_float(value) -> float:  # noqa: ANN001
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return 0.0


def _safe_int(value) -> int:  # noqa: ANN001
    if value in (None, ""):
        return 0
    try:
        return int(round(float(value)))
    except Exception:  # noqa: BLE001
        return 0


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


def _format_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _utc_now() -> str:
    return datetime.now(UTC).astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")
