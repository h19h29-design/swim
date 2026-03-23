import argparse

from swimdash import cli


def test_refresh_runs_incremental_then_rebuild(monkeypatch):
    calls = []

    def fake_run_crawl(args, mode, force_dashboard_floor=False):
        calls.append(("crawl", mode, force_dashboard_floor))
        return 0

    def fake_run_rebuild():
        calls.append(("rebuild", None))
        return 0

    monkeypatch.setattr(cli, "_run_crawl", fake_run_crawl)
    monkeypatch.setattr(cli, "_run_rebuild", fake_run_rebuild)

    args = argparse.Namespace(skip_incremental=False)
    assert cli._run_refresh(args) == 0
    assert calls == [("crawl", "incremental", False), ("rebuild", None)]


def test_refresh_can_skip_incremental(monkeypatch):
    calls = []

    def fake_run_rebuild():
        calls.append(("rebuild", None))
        return 0

    monkeypatch.setattr(cli, "_run_rebuild", fake_run_rebuild)

    args = argparse.Namespace(skip_incremental=True)
    assert cli._run_refresh(args) == 0
    assert calls == [("rebuild", None)]


def test_refresh_from_floor_runs_incremental_with_floor_policy(monkeypatch):
    calls = []

    def fake_run_crawl(args, mode, force_dashboard_floor=False):
        calls.append(("crawl", mode, force_dashboard_floor))
        return 0

    def fake_run_rebuild():
        calls.append(("rebuild", None))
        return 0

    monkeypatch.setattr(cli, "_run_crawl", fake_run_crawl)
    monkeypatch.setattr(cli, "_run_rebuild", fake_run_rebuild)

    args = argparse.Namespace(skip_incremental=False)
    assert cli._run_refresh(args, force_dashboard_floor=True) == 0
    assert calls == [("crawl", "incremental", True), ("rebuild", None)]


def test_refresh_window_runs_incremental_with_window(monkeypatch):
    calls = []

    def fake_run_crawl(args, mode, force_dashboard_floor=False, refresh_window=None):
        calls.append(("crawl", mode, force_dashboard_floor, refresh_window))
        return 0

    def fake_run_rebuild():
        calls.append(("rebuild", None))
        return 0

    monkeypatch.setattr(cli, "_run_crawl", fake_run_crawl)
    monkeypatch.setattr(cli, "_run_rebuild", fake_run_rebuild)

    args = argparse.Namespace(skip_incremental=False, start_date=cli.date(2026, 3, 1), end_date=cli.date(2026, 3, 5))
    assert cli._run_refresh_window(args) == 0
    assert calls == [("crawl", "incremental", False, (cli.date(2026, 3, 1), cli.date(2026, 3, 5))), ("rebuild", None)]


def test_refresh_window_rejects_inverted_dates():
    args = argparse.Namespace(skip_incremental=False, start_date=cli.date(2026, 3, 5), end_date=cli.date(2026, 3, 1))
    try:
        cli._run_refresh_window(args)
    except SystemExit as exc:
        assert "--end-date must be on or after --start-date" in str(exc)
    else:
        raise AssertionError("expected SystemExit for inverted date range")
