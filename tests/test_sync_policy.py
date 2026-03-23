from datetime import date

from swimdash.config import resolve_incremental_sync_policy


def test_march_correction_week_policy_covers_from_dashboard_floor():
    policy = resolve_incremental_sync_policy(as_of=date(2026, 3, 11))

    assert policy.policy_name == "march_correction_week"
    assert policy.editable_window_start == date(2026, 3, 1)
    assert policy.editable_window_end == date(2026, 3, 11)
    assert policy.stop_before_date == date(2026, 3, 1)
    assert policy.lookback_days == 11
    assert policy.recent_pages == 80


def test_post_correction_policy_switches_to_rolling_three_day_window():
    policy = resolve_incremental_sync_policy(as_of=date(2026, 3, 16))

    assert policy.policy_name == "rolling_3day_edit_window"
    assert policy.editable_window_start == date(2026, 3, 14)
    assert policy.editable_window_end == date(2026, 3, 16)
    assert policy.stop_before_date == date(2026, 3, 14)
    assert policy.lookback_days == 3
    assert policy.recent_pages == 12


def test_explicit_incremental_overrides_bypass_auto_policy():
    policy = resolve_incremental_sync_policy(
        as_of=date(2026, 3, 11),
        explicit_lookback_days=5,
        explicit_recent_pages=20,
    )

    assert policy.policy_name == "custom_override_window"
    assert policy.lookback_days == 5
    assert policy.recent_pages == 20


def test_force_dashboard_floor_policy_keeps_crawling_from_march_first():
    policy = resolve_incremental_sync_policy(
        as_of=date(2026, 3, 16),
        force_dashboard_floor=True,
    )

    assert policy.policy_name == "dashboard_floor_window"
    assert policy.editable_window_start == date(2026, 3, 1)
    assert policy.stop_before_date == date(2026, 3, 1)
    assert policy.lookback_days == 16
    assert policy.recent_pages == 80
    assert policy.crawl_until_stop_date is True
