from __future__ import annotations

import csv
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from swimdash.aggregate import build_leaderboard, build_monthly, build_summary
from swimdash.models import CrawledPost
from swimdash.pipeline import apply_manual_review_overrides, merge_records, parse_posts_to_records
from swimdash.parser import TITLE_FORMAT_MISSING


def test_pipeline_uses_title_format_only():
    post = CrawledPost(
        post_id=1,
        url="https://example.com/post/1",
        title="800 / 50\ubd84",
        author="\uc791\uc131\uc790",
        post_datetime="2026-03-05 07:00:00",
        content_text="\ucd1d\uac70\ub9ac 1500\n\uc2dc\uac04 90\ubd84",
        image_urls=["https://example.com/image.jpg"],
    )

    records = parse_posts_to_records([post])

    assert len(records) == 1
    row = records[0].to_dict()
    assert row["distance_m"] == 800
    assert row["total_seconds"] == 3000
    assert row["include"] is True
    assert row["review_needed"] is False
    assert row["source"] == "title_format"
    assert row["evidence_text"] == "800 / 50\ubd84"


def test_aggregate_uses_backend_include_boolean_and_review_queue():
    records = [
        {
            "post_id": 1,
            "author": "A",
            "post_date": "2026-03-01",
            "distance_m": 800,
            "total_seconds": 3000,
            "source": "title_format",
            "include": True,
            "exclude_reason_code": "",
            "review_needed": False,
            "review_reason_code": "",
            "warning_codes": [],
            "manual_override_decision": None,
            "manual_override_applied": False,
        },
        {
            "post_id": 2,
            "author": "B",
            "post_date": "2026-03-01",
            "distance_m": None,
            "total_seconds": None,
            "source": "none",
            "include": False,
            "exclude_reason_code": TITLE_FORMAT_MISSING,
            "review_needed": True,
            "review_reason_code": TITLE_FORMAT_MISSING,
            "warning_codes": [],
            "manual_override_decision": None,
            "manual_override_applied": False,
        },
        {
            "post_id": 3,
            "author": "C",
            "post_date": "2026-03-01",
            "distance_m": 400,
            "total_seconds": 2400,
            "source": "manual_patch",
            "include": True,
            "exclude_reason_code": "",
            "review_needed": False,
            "review_reason_code": "",
            "warning_codes": [],
            "manual_override_decision": "patch",
            "manual_override_applied": True,
        },
    ]

    summary = build_summary(records)
    monthly = build_monthly(records)
    leaderboard = build_leaderboard(records)

    assert summary["record_count"] == 2
    assert summary["excluded_record_count"] == 1
    assert summary["review_queue_count"] == 1
    assert summary["review_reason_counts"][TITLE_FORMAT_MISSING] == 1
    assert summary["manual_override_counts"]["patch"] == 1
    assert summary["source_counts"]["manual_patch"] == 1
    assert summary["total_distance_m"] == 1200
    assert summary["total_duration_min"] == 90

    assert len(monthly) == 1
    assert monthly[0]["total_distance_m"] == 1200
    assert monthly[0]["swim_count"] == 2

    assert len(leaderboard["authors"]) == 2
    assert sorted(row["author"] for row in leaderboard["authors"]) == ["A", "C"]


def test_merge_records_upserts_and_normalizes_review_schema():
    existing = [
        {
            "post_id": 101,
            "url": "https://example.com/post/101",
            "title": "old",
            "author": "A",
            "post_datetime": "2026-03-01 07:00:00",
            "post_date": "2026-03-01",
            "distance_m": 400,
            "duration_min": 50,
            "source_type": "text_total",
            "is_excluded": True,
            "exclude_reason": "missing_duration",
            "needs_review": True,
            "review_reason": "TEXT_TIME_MISSING",
            "evidence_text": "old",
        }
    ]

    post = CrawledPost(
        post_id=101,
        url="https://example.com/post/101",
        title="900 / 40\ubd84",
        author="A",
        post_datetime="2026-03-02 08:00:00",
        content_text="\ucd1d\uac70\ub9ac 900\n\uc2dc\uac04 40\ubd84",
        image_urls=[],
    )

    new_records = parse_posts_to_records([post])
    merged = merge_records(existing, new_records, replace_all=False)

    assert len(merged) == 1
    row = merged[0]
    assert row["post_id"] == 101
    assert row["distance_m"] == 900
    assert row["total_seconds"] == 2400
    assert row["total_time_text"] == "40\ubd84"
    assert row["include"] is True
    assert row["source"] == "title_format"
    assert row["review_needed"] is False
    assert row["review_reason_code"] is None
    assert row["exclude_reason_code"] is None


def test_accept_override_marks_record_manual_review():
    with _override_file() as override_path:
        override_path = _write_overrides(
            override_path,
            [{"post_id": 17288, "decision": "accept", "distance_m": "", "total_time_text": "", "note": "checked"}],
        )

        records = apply_manual_review_overrides([_review_queue_record()], override_path=override_path)

        assert len(records) == 1
        row = records[0]
        assert row["include"] is True
        assert row["source"] == "manual_review"
        assert row["exclude_reason_code"] is None
        assert row["review_needed"] is False
        assert row["manual_override_decision"] == "accept"
        assert row["manual_override_applied"] is True
        assert row["automatic_record"]["include"] is False


def test_reject_override_marks_record_manual_rejected():
    with _override_file() as override_path:
        override_path = _write_overrides(
            override_path,
            [{"post_id": 17288, "decision": "reject", "distance_m": "", "total_time_text": "", "note": "reject"}],
        )

        records = apply_manual_review_overrides([_review_queue_record()], override_path=override_path)

        assert len(records) == 1
        row = records[0]
        assert row["include"] is False
        assert row["exclude_reason_code"] == "MANUAL_REJECTED"
        assert row["review_needed"] is False
        assert row["manual_override_decision"] == "reject"
        assert row["manual_override_applied"] is True
        assert row["source"] == "none"


def test_patch_override_applies_values_and_recomputes_total_seconds():
    with _override_file() as override_path:
        override_path = _write_overrides(
            override_path,
            [{"post_id": 17288, "decision": "patch", "distance_m": "1250", "total_time_text": "47:54", "note": "patch"}],
        )

        records = apply_manual_review_overrides([_review_queue_record()], override_path=override_path)

        assert len(records) == 1
        row = records[0]
        assert row["include"] is True
        assert row["source"] == "manual_patch"
        assert row["distance_m"] == 1250
        assert row["total_time_text"] == "47:54"
        assert row["total_seconds"] == 2874
        assert row["review_needed"] is False
        assert row["manual_override_decision"] == "patch"
        assert row["manual_override_applied"] is True


def test_override_is_reversible_from_automatic_snapshot():
    with _override_file() as override_path:
        accept_path = _write_overrides(
            override_path,
            [{"post_id": 17288, "decision": "accept", "distance_m": "", "total_time_text": "", "note": "checked"}],
        )
        overridden = apply_manual_review_overrides([_review_queue_record()], override_path=accept_path)

        empty_path = _write_overrides(override_path, [])
        restored = apply_manual_review_overrides(overridden, override_path=empty_path)

        assert restored[0]["include"] is False
        assert restored[0]["source"] == "none"
        assert restored[0]["review_needed"] is True
        assert restored[0]["manual_override_decision"] is None
        assert restored[0]["manual_override_applied"] is False


def _review_queue_record() -> dict:
    return {
        "post_id": 17288,
        "url": "https://example.com/post/17288",
        "title": "review",
        "author": "tester",
        "post_datetime": "2026-03-08 07:49:43",
        "post_date": "2026-03-08",
        "distance_m": None,
        "total_time_text": None,
        "total_seconds": None,
        "source": "none",
        "include": False,
        "score": 10,
        "exclude_reason_code": TITLE_FORMAT_MISSING,
        "warning_codes": [],
        "evidence_text": "review",
        "review_needed": True,
        "review_reason_code": TITLE_FORMAT_MISSING,
    }


def _write_overrides(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["post_id", "decision", "distance_m", "total_time_text", "note"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


@contextmanager
def _override_file():
    path = Path(__file__).resolve().parents[1] / "data" / f"test_manual_review_overrides_{uuid4().hex}.csv"
    try:
        yield path
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
