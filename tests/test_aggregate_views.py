from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from uuid import uuid4

from swimdash import pipeline
from swimdash.aggregate import (
    MODE_CORE_ONLY,
    build_author_index,
    build_author_profiles,
    build_dashboard_views,
    build_leaderboard,
    build_monthly,
    build_parse_status_payload,
    build_summary,
    resolve_metric_bucket,
)


def test_metric_bucket_split_and_mode_summary():
    records = _sample_records()

    included_rows = [row for row in records if row["include"]]
    buckets = {row["post_id"]: resolve_metric_bucket(row) for row in included_rows}
    assert buckets == {
        1: "core",
        2: "core",
        3: "core",
        4: "core",
        5: "core",
        7: "core",
    }

    summary = build_summary(records, mode=MODE_CORE_ONLY, reference_date=date(2026, 3, 5))
    monthly = build_monthly(records, mode=MODE_CORE_ONLY)

    assert summary["swim_count"] == 3
    assert summary["total_record_count"] == 4
    assert summary["source_record_count"] == 7
    assert summary["dashboard_date_floor"] == "2026-03-01"
    assert summary["visible_date_range"] == {"start": "2026-03-02", "end": "2026-03-05"}
    assert summary["included_metric_bucket_counts"] == {"core": 3}
    assert summary["total_distance_m"] == 3000.0
    assert summary["total_seconds"] == 7800
    assert summary["distance_per_hour_m"] == 1384.62
    assert summary["growth"]["recent_window"]["start"] == "2026-03-01"
    assert summary["growth"]["recent_window"]["truncated_by_floor"] is True
    assert summary["growth"]["previous_window"]["start"] is None
    assert summary["growth"]["previous_window"]["truncated_by_floor"] is True

    assert len(monthly) == 1
    assert monthly[-1]["distance_per_hour_m"] == 1384.62
    assert monthly[-1]["metric_bucket_counts"] == {"core": 3}


def test_leaderboard_includes_efficiency_and_growth_metrics():
    records = _sample_records()
    leaderboard = build_leaderboard(records, mode=MODE_CORE_ONLY, reference_date=date(2026, 3, 5))

    alpha = next(row for row in leaderboard["authors"] if row["author"] == "Alpha")
    beta = next(row for row in leaderboard["authors"] if row["author"] == "Beta")

    assert leaderboard["dashboard_date_floor"] == "2026-03-01"
    assert leaderboard["total_record_count"] == 4
    assert leaderboard["source_record_count"] == 7
    assert alpha["distance_per_hour_m"] == 1320.0
    assert alpha["growth_swim_count"]["delta_value"] == 2.0
    assert alpha["growth_distance_m"]["pct_change"] is None
    assert alpha["growth_total_seconds"]["pct_change_status"] == "previous_zero_growth"

    assert beta["distance_per_hour_m"] == 1600.0
    assert beta["growth_swim_count"]["pct_change_status"] == "previous_zero_growth"

    assert leaderboard["by_distance_per_hour_m"][0]["author"] == "Beta"
    assert leaderboard["growth_by_swim_count"][0]["author"] == "Alpha"
    assert leaderboard["growth_by_distance_m"][0]["author"] == "Alpha"


def test_dashboard_profile_and_author_index_schema_stable():
    records = _sample_records()

    dashboard_views = build_dashboard_views(records)
    author_index = build_author_index(records)
    author_profiles = build_author_profiles(records)

    assert dashboard_views["default_mode"] == MODE_CORE_ONLY
    assert dashboard_views["supported_modes"] == [MODE_CORE_ONLY]
    assert dashboard_views["dashboard_date_floor"] == "2026-03-01"
    assert dashboard_views["core_only_has_zero_visible_included_rows"] is False
    assert dashboard_views["summary"]["record_count"] == 3
    assert dashboard_views["gallery"]["current_title"]["badge_id"] == "gal_01"
    assert dashboard_views["gallery"]["next_title_target"]["badge_id"] == "gal_02"
    assert dashboard_views["gallery"]["progress"]["remaining_value"] == 3200
    assert "swim_count" in dashboard_views["rankings"]["metrics"]
    assert dashboard_views["rankings"]["metrics"]["swim_count"]["top3"][0]["author"] == "Alpha"
    assert dashboard_views["rankings"]["metrics"]["swim_count"]["ranks_4_to_20"] == []
    assert dashboard_views["recent_records"][0]["metric_bucket"] == "core"

    assert author_index["author_count"] == 3
    assert {row["author"] for row in author_index["authors"]} == {"Alpha", "Beta", "Gamma"}
    assert author_index["authors"][0]["search_key"] == "alpha"
    gamma_index = next(row for row in author_index["authors"] if row["author"] == "Gamma")
    assert gamma_index["total_record_count"] == 1
    assert gamma_index["included_record_count"] == 0
    assert gamma_index["next_badge_progress"]["badge_id"] == "att_01"

    assert author_profiles["default_mode"] == MODE_CORE_ONLY
    assert author_profiles["supported_modes"] == [MODE_CORE_ONLY]
    assert author_profiles["profile_count"] == 3
    alpha_profile = next(row for row in author_profiles["profiles"] if row["author"] == "Alpha")
    assert alpha_profile["total_record_count"] == 2
    assert alpha_profile["primary_title"]["badge_id"] == "eff_05"
    assert alpha_profile["badge_counts_by_category"]["attendance"] == 1
    assert alpha_profile["next_badge_progress"]["badge_id"] == "tim_01"
    assert alpha_profile["next_badge_progress"]["remaining_value"] == 1200
    assert len(alpha_profile["unlocked_badges"]) >= 10
    assert len(alpha_profile["recent_unlocks"]) >= 3
    assert "summary" in alpha_profile
    assert "recent_28d_vs_previous_28d" in alpha_profile
    assert "monthly_trend" in alpha_profile
    assert "recent_records" in alpha_profile
    assert "time_series" in alpha_profile
    assert "daily" in alpha_profile["time_series"]


def test_parse_status_payload_splits_parsed_and_unparsed_rows():
    records = _sample_records()

    payload = build_parse_status_payload(records)

    assert payload["parsed_count"] == 3
    assert payload["unparsed_count"] == 1
    assert payload["success_rate_pct"] == 75.0
    assert payload["failure_reason_counts"] == {"TITLE_FORMAT_MISSING": 1}
    assert payload["guidance"]["official_format"] == "1500 / 42:30"
    assert payload["parsed_rows"][0]["author"] == "Alpha"
    assert payload["parsed_rows"][0]["distance_m"] == 1200
    assert payload["unparsed_rows"][0]["author"] == "Gamma"
    assert payload["unparsed_rows"][0]["reason_code"] == "TITLE_FORMAT_MISSING"


def test_write_dashboard_data_writes_new_aggregate_files(monkeypatch):
    with _scratch_dir() as tmp_path:
        monkeypatch.setattr(pipeline, "RECORDS_FILE", tmp_path / "docs" / "data" / "records.json")
        monkeypatch.setattr(pipeline, "SUMMARY_FILE", tmp_path / "docs" / "data" / "summary.json")
        monkeypatch.setattr(pipeline, "MONTHLY_FILE", tmp_path / "docs" / "data" / "monthly.json")
        monkeypatch.setattr(pipeline, "LEADERBOARD_FILE", tmp_path / "docs" / "data" / "leaderboard.json")
        monkeypatch.setattr(pipeline, "REVIEW_QUEUE_FILE", tmp_path / "docs" / "data" / "review_queue.json")
        monkeypatch.setattr(pipeline, "PARSE_STATUS_FILE", tmp_path / "docs" / "data" / "parse_status.json")
        monkeypatch.setattr(pipeline, "AUTHOR_INDEX_FILE", tmp_path / "docs" / "data" / "author_index.json")
        monkeypatch.setattr(pipeline, "AUTHOR_PROFILES_FILE", tmp_path / "docs" / "data" / "author_profiles.json")
        monkeypatch.setattr(pipeline, "DASHBOARD_VIEWS_FILE", tmp_path / "docs" / "data" / "dashboard_views.json")
        monkeypatch.setattr(pipeline, "BADGE_INDEX_FILE", tmp_path / "docs" / "data" / "badge_index.json")
        monkeypatch.setattr(pipeline, "ADMIN_PREVIEW_FILE", tmp_path / "docs" / "data" / "admin_preview.json")
        monkeypatch.setattr(pipeline, "MANUAL_REVIEW_OVERRIDE_FILE", tmp_path / "data" / "manual_review_overrides.csv")

        pipeline.write_dashboard_data(_sample_records())

        expected = [
            tmp_path / "docs" / "data" / "records.json",
            tmp_path / "docs" / "data" / "summary.json",
            tmp_path / "docs" / "data" / "monthly.json",
            tmp_path / "docs" / "data" / "leaderboard.json",
            tmp_path / "docs" / "data" / "review_queue.json",
            tmp_path / "docs" / "data" / "parse_status.json",
            tmp_path / "docs" / "data" / "dashboard_views.json",
            tmp_path / "docs" / "data" / "author_index.json",
            tmp_path / "docs" / "data" / "author_profiles.json",
            tmp_path / "docs" / "data" / "badge_index.json",
            tmp_path / "docs" / "data" / "admin_preview.json",
        ]
        for path in expected:
            assert path.exists(), path

        records_payload = json.loads((tmp_path / "docs" / "data" / "records.json").read_text(encoding="utf-8"))
        assert {row["post_id"]: row["metric_bucket"] for row in records_payload if row["include"]} == {
            1: "core",
            2: "core",
            3: "core",
            4: "core",
            5: "core",
            7: "core",
        }

        summary_payload = json.loads((tmp_path / "docs" / "data" / "summary.json").read_text(encoding="utf-8"))
        assert summary_payload["default_mode"] == MODE_CORE_ONLY
        assert summary_payload["supported_modes"] == [MODE_CORE_ONLY]
        assert summary_payload["dashboard_date_floor"] == "2026-03-01"
        assert summary_payload["visible_record_count"] == 4
        assert summary_payload["summary"]["record_count"] == 3
        assert summary_payload["summary"]["source_record_count"] == 7
        assert summary_payload["gallery"]["current_title"]["badge_id"] == "gal_01"

        review_queue_payload = json.loads((tmp_path / "docs" / "data" / "review_queue.json").read_text(encoding="utf-8"))
        assert [row["post_id"] for row in review_queue_payload] == [6]

        parse_status_payload = json.loads((tmp_path / "docs" / "data" / "parse_status.json").read_text(encoding="utf-8"))
        assert parse_status_payload["parsed_count"] == 3
        assert parse_status_payload["unparsed_count"] == 1
        assert parse_status_payload["failure_reason_counts"] == {"TITLE_FORMAT_MISSING": 1}

        dashboard_payload = json.loads((tmp_path / "docs" / "data" / "dashboard_views.json").read_text(encoding="utf-8"))
        assert dashboard_payload["visible_record_count"] == 4
        assert dashboard_payload["rankings"]["metrics"]["swim_count"]["top3"][0]["author"] == "Alpha"
        assert dashboard_payload["gallery"]["next_title_target"]["badge_id"] == "gal_02"

        profiles_payload = json.loads((tmp_path / "docs" / "data" / "author_profiles.json").read_text(encoding="utf-8"))
        assert profiles_payload["profile_count"] == 3
        assert profiles_payload["profiles"][0]["primary_title"] is not None

        badge_index_payload = json.loads((tmp_path / "docs" / "data" / "badge_index.json").read_text(encoding="utf-8"))
        assert badge_index_payload["badge_count"] == 63
        assert badge_index_payload["badge_count_by_category"]["attendance"] == 8
        assert badge_index_payload["badge_count_by_category"]["gallery"] == 8

        admin_preview_payload = json.loads((tmp_path / "docs" / "data" / "admin_preview.json").read_text(encoding="utf-8"))
        assert "site_config" in admin_preview_payload
        assert admin_preview_payload["source_paths"]["site_config"].endswith("data/admin/site_config.json")


def _sample_records() -> list[dict]:
    return [
        {
            "post_id": 1,
            "author": "Alpha",
            "post_date": "2026-03-05",
            "post_datetime": "2026-03-05 07:00:00",
            "distance_m": 1200,
            "total_seconds": 3600,
            "total_time_text": "1:00:00",
            "source": "text_format",
            "include": True,
            "score": 100,
            "exclude_reason_code": None,
            "review_needed": False,
            "review_reason_code": None,
            "warning_codes": [],
            "manual_override_decision": None,
            "manual_override_applied": False,
            "url": "https://example.com/1",
        },
        {
            "post_id": 2,
            "author": "Alpha",
            "post_date": "2026-03-04",
            "post_datetime": "2026-03-04 07:00:00",
            "distance_m": 1000,
            "total_seconds": 2400,
            "total_time_text": "40:00",
            "source": "manual_patch",
            "include": True,
            "score": 100,
            "exclude_reason_code": None,
            "review_needed": False,
            "review_reason_code": None,
            "warning_codes": [],
            "manual_override_decision": "patch",
            "manual_override_applied": True,
            "url": "https://example.com/2",
        },
        {
            "post_id": 3,
            "author": "Beta",
            "post_date": "2026-03-03",
            "post_datetime": "2026-03-03 07:00:00",
            "distance_m": 800,
            "total_seconds": 1800,
            "total_time_text": "30:00",
            "source": "title_format",
            "include": True,
            "score": 98,
            "exclude_reason_code": None,
            "review_needed": False,
            "review_reason_code": None,
            "warning_codes": [],
            "manual_override_decision": None,
            "manual_override_applied": False,
            "url": "https://example.com/3",
        },
        {
            "post_id": 4,
            "author": "Alpha",
            "post_date": "2026-02-05",
            "post_datetime": "2026-02-05 07:00:00",
            "distance_m": 900,
            "total_seconds": 2700,
            "total_time_text": "45:00",
            "source": "title_format",
            "include": True,
            "score": 92,
            "exclude_reason_code": None,
            "review_needed": True,
            "review_reason_code": "TITLE_FORMAT_INVALID",
            "warning_codes": [],
            "manual_override_decision": None,
            "manual_override_applied": False,
            "url": "https://example.com/4",
        },
        {
            "post_id": 5,
            "author": "Gamma",
            "post_date": "2026-01-20",
            "post_datetime": "2026-01-20 07:00:00",
            "distance_m": 1250,
            "total_seconds": 4500,
            "total_time_text": "1:15:00",
            "source": "manual_review",
            "include": True,
            "score": 100,
            "exclude_reason_code": None,
            "review_needed": False,
            "review_reason_code": None,
            "warning_codes": [],
            "manual_override_decision": "accept",
            "manual_override_applied": True,
            "url": "https://example.com/5",
        },
        {
            "post_id": 6,
            "author": "Gamma",
            "post_date": "2026-03-02",
            "post_datetime": "2026-03-02 07:00:00",
            "distance_m": 700,
            "total_seconds": None,
            "total_time_text": None,
            "source": "none",
            "include": False,
            "score": 25,
            "exclude_reason_code": "TITLE_FORMAT_MISSING",
            "review_needed": True,
            "review_reason_code": "TITLE_FORMAT_MISSING",
            "warning_codes": [],
            "manual_override_decision": None,
            "manual_override_applied": False,
            "url": "https://example.com/6",
        },
        {
            "post_id": 7,
            "author": "Delta",
            "post_date": "2026-02-12",
            "post_datetime": "2026-02-12 07:00:00",
            "distance_m": 1500,
            "total_seconds": 3600,
            "total_time_text": "1:00:00",
            "source": "text_format",
            "include": True,
            "score": 100,
            "exclude_reason_code": None,
            "review_needed": False,
            "review_reason_code": None,
            "warning_codes": [],
            "manual_override_decision": None,
            "manual_override_applied": False,
            "url": "https://example.com/7",
        },
    ]


@contextmanager
def _scratch_dir():
    base = Path(__file__).resolve().parents[1] / ".pytest_tmp_aggregate_views" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)
