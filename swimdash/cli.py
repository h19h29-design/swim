from __future__ import annotations

import argparse
import contextlib
import hmac
import http.server
import json
import logging
import socket
import socketserver
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from swimdash.admin_api import (
    AdminValidationError,
    authenticate_admin_password,
    build_admin_workspace_payload,
    build_manual_override_payload,
    build_logout_cookie_header,
    build_session_cookie_header,
    create_admin_session,
    delete_manual_override,
    extract_session_cookie,
    load_admin_auth_settings,
    parse_admin_session,
    save_badge_icon_asset,
    save_manual_override,
    save_admin_bundle,
    save_admin_document,
    log_admin_runtime_event,
    trigger_admin_rebuild,
)
from swimdash.config import (
    DATA_DIR,
    DEFAULT_RETRY_BACKOFF,
    ERROR_LOG_FILE,
    LOG_DIR,
    resolve_incremental_sync_policy,
)
from swimdash.crawler import DcinsideCrawler
from swimdash.fetcher import HttpClient
from swimdash.io_utils import write_json
from swimdash.pipeline import (
    load_existing_records,
    merge_records,
    parse_posts_to_records,
    write_dashboard_data,
)

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

ADMIN_SAVE_KEYS = {
    "site_config",
    "navigation_config",
    "home_sections",
    "badge_catalog",
    "season_badges",
    "gallery_title_rules",
    "profile_layout_config",
    "badge_art_catalog",
}


class _DualStackThreadingHttpServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self) -> None:
        if self.address_family == socket.AF_INET6:
            with contextlib.suppress(AttributeError, OSError):
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    if args.command == "serve":
        return _run_serve(args.port)
    if args.command == "refresh":
        return _run_refresh(args)
    if args.command == "refresh-from-floor":
        return _run_refresh(args, force_dashboard_floor=True)
    if args.command == "refresh-window":
        return _run_refresh_window(args)
    if args.command == "rebuild":
        return _run_rebuild()
    if args.command == "sample-data":
        return _run_sample_data()
    if args.command == "backfill":
        return _run_crawl(args, mode="full")
    if args.command == "incremental":
        return _run_crawl(args, mode="incremental")

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swimming diary dashboard pipeline")
    sub = parser.add_subparsers(dest="command")

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--max-pages", type=int, default=None, help="Maximum list pages to fetch")
    shared.add_argument("--recent-pages", type=int, default=None, help="Pages for incremental mode (default: auto policy)")
    shared.add_argument("--lookback-days", type=int, default=None, help="Days to recrawl recent posts in incremental mode (default: auto policy)")
    shared.add_argument("--timeout", type=int, default=15)
    shared.add_argument("--retries", type=int, default=4)
    shared.add_argument("--rate-limit", type=float, default=0.45, help="Delay seconds per request")
    shared.add_argument("--user-agent", type=str, default=DEFAULT_USER_AGENT)

    sub.add_parser("backfill", parents=[shared], help="Crawl full history and regenerate JSON")
    sub.add_parser("incremental", parents=[shared], help="Crawl recent editable posts and merge title-format records")
    refresh = sub.add_parser("refresh", parents=[shared], help="Run incremental sync and rebuild dashboard data")
    refresh.add_argument("--skip-incremental", action="store_true", help="Only rebuild dashboard data")
    refresh_floor = sub.add_parser(
        "refresh-from-floor",
        parents=[shared],
        help="Recollect posts from the dashboard floor date (2026-03-01) and rebuild dashboard data",
    )
    refresh_floor.add_argument("--skip-incremental", action="store_true", help="Only rebuild dashboard data")
    refresh_window = sub.add_parser(
        "refresh-window",
        parents=[shared],
        help="Recollect a custom post-date window and rebuild while keeping data outside the window",
    )
    refresh_window.add_argument("--start-date", type=_parse_iso_date_argument, required=True, help="Inclusive YYYY-MM-DD start date")
    refresh_window.add_argument("--end-date", type=_parse_iso_date_argument, default=None, help="Inclusive YYYY-MM-DD end date (default: today)")
    refresh_window.add_argument("--skip-incremental", action="store_true", help="Only rebuild dashboard data")
    sub.add_parser("rebuild", help="Regenerate dashboard data from stored title-format records")
    sample = sub.add_parser("sample-data", help="Generate local sample records for UI checks")
    sample.add_argument("--force", action="store_true", help="Overwrite existing records")
    serve = sub.add_parser("serve", help="Serve docs/ for local preview")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def _run_crawl(
    args: argparse.Namespace,
    mode: str,
    *,
    force_dashboard_floor: bool = False,
    refresh_window: tuple[date, date] | None = None,
) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    client = HttpClient(
        timeout=args.timeout,
        retries=args.retries,
        backoff=DEFAULT_RETRY_BACKOFF,
        rate_limit_sec=args.rate_limit,
        user_agent=args.user_agent,
    )
    crawler = DcinsideCrawler(client=client, error_log_file=ERROR_LOG_FILE)

    try:
        existing = load_existing_records()
        use_refresh_window = mode == "incremental" and refresh_window is not None
        sync_policy = (
            _resolve_incremental_policy(args, force_dashboard_floor=force_dashboard_floor)
            if mode == "incremental" and not use_refresh_window
            else None
        )
        if use_refresh_window:
            window_start, window_end = refresh_window
            seen_ids: set[int] = set()
        elif mode == "incremental" and force_dashboard_floor and sync_policy is not None:
            seen_ids = set()
        else:
            seen_ids = {int(x["post_id"]) for x in existing if "post_id" in x}
        recent_pages = sync_policy.recent_pages if sync_policy is not None else (args.recent_pages or 0)
        if use_refresh_window and args.max_pages is None:
            recent_pages = crawler.fetch_last_page()
        elif mode == "incremental" and sync_policy is not None and sync_policy.crawl_until_stop_date and args.max_pages is None:
            recent_pages = crawler.fetch_last_page()

        posts, stats = crawler.crawl(
            mode=mode,
            seen_post_ids=seen_ids if mode == "incremental" else set(),
            max_pages=args.max_pages,
            recent_pages=recent_pages,
            lookback_days=sync_policy.lookback_days if sync_policy is not None else 0,
            stop_before_date=window_start if use_refresh_window else (sync_policy.stop_before_date if sync_policy is not None else None),
            refresh_window_start=window_start if use_refresh_window else None,
            refresh_window_end=window_end if use_refresh_window else None,
        )
        new_records = parse_posts_to_records(posts)
        if use_refresh_window:
            existing = [
                row
                for row in existing
                if not _post_date_in_range(str(row.get("post_date") or ""), window_start, window_end)
            ]
        elif mode == "incremental" and force_dashboard_floor and sync_policy is not None:
            existing = [
                row
                for row in existing
                if str(row.get("post_date") or "") < sync_policy.editable_window_start.isoformat()
            ]
        merged = merge_records(existing, new_records, replace_all=(mode == "full"))
        write_dashboard_data(merged)

        if use_refresh_window:
            logger.info(
                "incremental sync policy=custom_window editable_window=%s..%s recent_pages=%s",
                window_start,
                window_end,
                recent_pages,
            )
        elif sync_policy is not None:
            logger.info(
                "incremental sync policy=%s editable_window=%s..%s lookback_days=%s recent_pages=%s",
                sync_policy.policy_name,
                sync_policy.editable_window_start,
                sync_policy.editable_window_end,
                sync_policy.lookback_days,
                recent_pages,
            )
        logger.info(
            "crawl done mode=%s pages=%s diary_rows=%s fetched=%s skipped_seen=%s skipped_nonfixed=%s errors=%s total_records=%s lookback_days=%s",
            mode,
            stats.list_pages,
            stats.filtered_diary_rows,
            stats.fetched_detail,
            stats.skipped_seen,
            stats.skipped_nonfixed,
            stats.errors,
            len(merged),
            0 if use_refresh_window else (sync_policy.lookback_days if sync_policy is not None else 0),
        )
        return 0
    finally:
        client.close()


def _run_refresh(
    args: argparse.Namespace,
    *,
    force_dashboard_floor: bool = False,
    refresh_window: tuple[date, date] | None = None,
) -> int:
    if not args.skip_incremental:
        crawl_kwargs = {
            "force_dashboard_floor": force_dashboard_floor,
        }
        if refresh_window is not None:
            crawl_kwargs["refresh_window"] = refresh_window
        exit_code = _run_crawl(args, mode="incremental", **crawl_kwargs)
        if exit_code != 0:
            return exit_code
    return _run_rebuild()


def _run_refresh_window(args: argparse.Namespace) -> int:
    start_date = args.start_date
    end_date = args.end_date or date.today()
    if end_date < start_date:
        raise SystemExit("--end-date must be on or after --start-date")
    return _run_refresh(args, refresh_window=(start_date, end_date))


def _run_rebuild() -> int:
    records = load_existing_records()
    write_dashboard_data(records)
    logger.info("rebuild done records=%s", len(records))
    return 0


def _run_sample_data() -> int:
    sample = [
        {
            "post_id": 1001,
            "url": "https://example.com/post/1001",
            "title": "1200 / 55분",
            "author": "샘플고정닉",
            "post_datetime": "2026-03-01 07:10:00",
            "post_date": "2026-03-01",
            "distance_m": 1200,
            "total_time_text": "55분",
            "total_seconds": 3300,
            "source": "title_format",
            "include": True,
            "score": 100,
            "exclude_reason_code": None,
            "warning_codes": [],
            "evidence_text": "1200 / 55분",
            "review_needed": False,
            "review_reason_code": None,
        },
        {
            "post_id": 1002,
            "url": "https://example.com/post/1002",
            "title": "950m / 48:00",
            "author": "샘플고정닉2",
            "post_datetime": "2026-03-02 21:05:00",
            "post_date": "2026-03-02",
            "distance_m": 950,
            "total_time_text": "48:00",
            "total_seconds": 2880,
            "source": "title_format",
            "include": True,
            "score": 100,
            "exclude_reason_code": None,
            "warning_codes": [],
            "evidence_text": "950m / 48:00",
            "review_needed": False,
            "review_reason_code": None,
        },
    ]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json(Path("docs/data/records.json"), sample)
    write_dashboard_data(sample)
    logger.info("sample data created")
    return 0


def build_docs_handler(docs_dir: Path) -> type[http.server.SimpleHTTPRequestHandler]:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(docs_dir), **kwargs)

        def end_headers(self) -> None:
            request_path = self._request_path()
            if request_path in {"/admin.html", "/admin-login.html"}:
                self.send_header("Cache-Control", "no-store")
                self.send_header("Pragma", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            super().end_headers()

        def do_GET(self) -> None:
            if self._handle_admin_get():
                return
            super().do_GET()

        def do_POST(self) -> None:
            if self._handle_admin_post():
                return
            self.send_error(404)

        def _handle_admin_get(self) -> bool:
            request_path = self._request_path()
            parsed = urlsplit(self.path)

            if request_path == "/admin.html":
                session = self._session_payload()
                if session is None:
                    self._redirect_to_login(parsed.path, parsed.query)
                    return True
                return False

            if request_path == "/admin-login.html" and self._session_payload() is not None:
                self._redirect(self._normalized_next_path(self._next_param(parsed.query)))
                return True

            if request_path == "/api/admin/session":
                settings = load_admin_auth_settings()
                session = self._session_payload()
                payload: dict[str, object] = {
                    "configured": settings.configured,
                    "authenticated": session is not None,
                    "login_path": "/admin-login.html",
                }
                if session is not None:
                    payload["csrf_token"] = session.get("csrf")
                    payload["expires_at"] = session.get("exp")
                if not settings.configured:
                    payload["required_env"] = [
                        "SWIMDASH_ADMIN_PASSWORD",
                        "SWIMDASH_ADMIN_SESSION_SECRET",
                    ]
                self._send_json(200, payload)
                return True

            if request_path == "/api/admin/bundle":
                session = self._require_admin_session()
                if session is None:
                    return True
                try:
                    payload = build_admin_workspace_payload()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("admin bundle load failed")
                    self._send_json(
                        500,
                        {
                            "ok": False,
                            "error": "admin_bundle_load_failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    return True

                payload.update(
                    {
                        "ok": True,
                        "authenticated": True,
                        "csrf_token": session.get("csrf"),
                        "auth": {
                            "expires_at": session.get("exp"),
                        },
                    }
                )
                self._send_json(200, payload)
                return True

            if request_path == "/api/admin/manual-overrides":
                session = self._require_admin_session()
                if session is None:
                    return True
                try:
                    payload = build_manual_override_payload()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("manual override load failed")
                    self._send_json(
                        500,
                        {
                            "ok": False,
                            "error": "manual_override_load_failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    return True

                payload.update(
                    {
                        "ok": True,
                        "authenticated": True,
                        "csrf_token": session.get("csrf"),
                    }
                )
                self._send_json(200, payload)
                return True

            return False

        def _handle_admin_post(self) -> bool:
            request_path = self._request_path()
            if request_path == "/api/admin/login":
                body = self._read_json_body()
                if body is None:
                    return True
                settings = load_admin_auth_settings()
                if not settings.configured:
                    self._send_json(
                        503,
                        {
                            "ok": False,
                            "error": "admin_auth_not_configured",
                            "message": "Set SWIMDASH_ADMIN_PASSWORD and SWIMDASH_ADMIN_SESSION_SECRET before using admin save features.",
                        },
                    )
                    return True

                password = body.get("password")
                if not isinstance(password, str):
                    self._send_json(400, {"ok": False, "error": "password_required", "message": "password must be a string"})
                    return True
                if not authenticate_admin_password(password, settings):
                    self._send_json(401, {"ok": False, "error": "invalid_credentials", "message": "Admin password did not match"})
                    return True

                token, session = create_admin_session(settings)
                next_path = self._normalized_next_path(body.get("next"))
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "authenticated": True,
                        "csrf_token": session.get("csrf"),
                        "expires_at": session.get("exp"),
                        "next": next_path,
                    },
                    headers={
                        "Set-Cookie": build_session_cookie_header(
                            token,
                            settings=settings,
                            secure=self._is_secure_request(),
                        )
                    },
                )
                return True

            if request_path == "/api/admin/logout":
                settings = load_admin_auth_settings()
                self._send_json(
                    200,
                    {"ok": True, "authenticated": False},
                    headers={
                        "Set-Cookie": build_logout_cookie_header(
                            settings=settings,
                            secure=self._is_secure_request(),
                        )
                    },
                )
                return True

            if (
                request_path.startswith("/api/admin/save/")
                or request_path == "/api/admin/rebuild"
                or request_path == "/api/admin/run-sync"
                or request_path == "/api/admin/badge-icons/upload"
                or request_path.startswith("/api/admin/manual-overrides/")
            ):
                session = self._require_admin_session()
                if session is None:
                    return True
                if not self._validate_admin_write_request(session):
                    return True

            if request_path == "/api/admin/save/bundle":
                body = self._read_json_body()
                if body is None:
                    return True
                bundle = body.get("bundle")
                run_rebuild = _coerce_request_bool(body.get("run_rebuild"))
                try:
                    summary = save_admin_bundle(
                        bundle,
                        actor=self._actor_metadata(),
                        run_rebuild=run_rebuild,
                    )
                    payload = build_admin_workspace_payload()
                except AdminValidationError as exc:
                    self._send_json(400, {"ok": False, "error": "validation_failed", "errors": exc.errors})
                    return True
                except Exception as exc:  # noqa: BLE001
                    logger.exception("admin bundle save failed")
                    self._send_json(
                        500,
                        {
                            "ok": False,
                            "error": "save_failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    return True

                payload.update(
                    {
                        "ok": True,
                        "csrf_token": (self._session_payload() or {}).get("csrf"),
                        **summary,
                    }
                )
                self._send_json(200, payload)
                return True

            if request_path.startswith("/api/admin/save/"):
                body = self._read_json_body()
                if body is None:
                    return True
                save_key = request_path.rsplit("/", 1)[-1]
                if save_key not in ADMIN_SAVE_KEYS:
                    self._send_json(404, {"ok": False, "error": "unknown_save_target", "message": save_key})
                    return True
                run_rebuild = _coerce_request_bool(body.get("run_rebuild"))
                try:
                    summary = save_admin_document(
                        save_key,
                        body.get("payload"),
                        actor=self._actor_metadata(),
                        run_rebuild=run_rebuild,
                    )
                    payload = build_admin_workspace_payload()
                except AdminValidationError as exc:
                    self._send_json(400, {"ok": False, "error": "validation_failed", "errors": exc.errors})
                    return True
                except Exception as exc:  # noqa: BLE001
                    logger.exception("admin document save failed")
                    self._send_json(
                        500,
                        {
                            "ok": False,
                            "error": "save_failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    return True

                payload.update(
                    {
                        "ok": True,
                        "csrf_token": (self._session_payload() or {}).get("csrf"),
                        **summary,
                    }
                )
                self._send_json(200, payload)
                return True

            if request_path == "/api/admin/rebuild":
                try:
                    summary = trigger_admin_rebuild(actor=self._actor_metadata())
                    payload = build_admin_workspace_payload()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("admin rebuild failed")
                    self._send_json(
                        500,
                        {
                            "ok": False,
                            "error": "rebuild_failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    return True

                payload.update(
                    {
                        "ok": True,
                        "csrf_token": (self._session_payload() or {}).get("csrf"),
                        **summary,
                    }
                )
                self._send_json(200, payload)
                return True

            if request_path == "/api/admin/run-sync":
                body = self._read_json_body()
                if body is None:
                    return True
                try:
                    summary = _run_admin_sync(
                        str(body.get("mode") or ""),
                        body,
                        actor=self._actor_metadata(),
                    )
                    payload = build_admin_workspace_payload()
                except AdminValidationError as exc:
                    self._send_json(400, {"ok": False, "error": "validation_failed", "errors": exc.errors})
                    return True
                except Exception as exc:  # noqa: BLE001
                    logger.exception("admin run sync failed")
                    self._send_json(
                        500,
                        {
                            "ok": False,
                            "error": "run_sync_failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    return True

                payload.update(
                    {
                        "ok": True,
                        "csrf_token": (self._session_payload() or {}).get("csrf"),
                        **summary,
                    }
                )
                self._send_json(200, payload)
                return True

            if request_path == "/api/admin/badge-icons/upload":
                body = self._read_json_body()
                if body is None:
                    return True
                run_rebuild = _coerce_request_bool(body.get("run_rebuild"))
                try:
                    summary = save_badge_icon_asset(
                        body.get("payload"),
                        actor=self._actor_metadata(),
                        run_rebuild=run_rebuild,
                    )
                    payload = build_admin_workspace_payload()
                except AdminValidationError as exc:
                    self._send_json(400, {"ok": False, "error": "validation_failed", "errors": exc.errors})
                    return True
                except Exception as exc:  # noqa: BLE001
                    logger.exception("badge icon upload failed")
                    self._send_json(
                        500,
                        {
                            "ok": False,
                            "error": "badge_icon_upload_failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    return True

                payload.update(
                    {
                        "ok": True,
                        "csrf_token": (self._session_payload() or {}).get("csrf"),
                        **summary,
                    }
                )
                self._send_json(200, payload)
                return True

            if request_path == "/api/admin/manual-overrides/save":
                body = self._read_json_body()
                if body is None:
                    return True
                run_rebuild = _coerce_request_bool(body.get("run_rebuild"))
                try:
                    summary = save_manual_override(
                        body.get("payload"),
                        actor=self._actor_metadata(),
                        run_rebuild=run_rebuild,
                    )
                    payload = build_manual_override_payload()
                except AdminValidationError as exc:
                    self._send_json(400, {"ok": False, "error": "validation_failed", "errors": exc.errors})
                    return True
                except Exception as exc:  # noqa: BLE001
                    logger.exception("manual override save failed")
                    self._send_json(
                        500,
                        {
                            "ok": False,
                            "error": "manual_override_save_failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    return True

                payload.update(
                    {
                        "ok": True,
                        "csrf_token": (self._session_payload() or {}).get("csrf"),
                        **summary,
                    }
                )
                self._send_json(200, payload)
                return True

            if request_path == "/api/admin/manual-overrides/delete":
                body = self._read_json_body()
                if body is None:
                    return True
                run_rebuild = _coerce_request_bool(body.get("run_rebuild"))
                try:
                    summary = delete_manual_override(
                        body.get("post_id"),
                        actor=self._actor_metadata(),
                        run_rebuild=run_rebuild,
                    )
                    payload = build_manual_override_payload()
                except AdminValidationError as exc:
                    self._send_json(400, {"ok": False, "error": "validation_failed", "errors": exc.errors})
                    return True
                except Exception as exc:  # noqa: BLE001
                    logger.exception("manual override delete failed")
                    self._send_json(
                        500,
                        {
                            "ok": False,
                            "error": "manual_override_delete_failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    return True

                payload.update(
                    {
                        "ok": True,
                        "csrf_token": (self._session_payload() or {}).get("csrf"),
                        **summary,
                    }
                )
                self._send_json(200, payload)
                return True

            return False

        def _request_path(self) -> str:
            return urlsplit(self.path).path or "/"

        def _send_json(self, status: int, payload: Mapping[str, object], headers: Mapping[str, str] | None = None) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, location: str) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _redirect_to_login(self, path: str, query: str) -> None:
            next_path = path
            if query:
                next_path = f"{next_path}?{query}"
            self._redirect(f"/admin-login.html?next={quote(next_path, safe='/')}")

        def _session_payload(self) -> dict | None:
            settings = load_admin_auth_settings()
            token = extract_session_cookie(self.headers.get("Cookie"), settings)
            return parse_admin_session(token, settings)

        def _require_admin_session(self) -> dict | None:
            session = self._session_payload()
            if session is None:
                self._send_json(401, {"ok": False, "error": "auth_required", "message": "Admin login is required"})
            return session

        def _validate_admin_write_request(self, session: dict) -> bool:
            csrf_token = session.get("csrf")
            header_token = self.headers.get("X-Admin-CSRF", "")
            if not isinstance(csrf_token, str) or not hmac.compare_digest(header_token, csrf_token):
                self._send_json(403, {"ok": False, "error": "csrf_failed", "message": "Missing or invalid admin CSRF token"})
                return False

            origin = self.headers.get("Origin", "").strip()
            host = self.headers.get("Host", "").strip().lower()
            if origin:
                origin_parts = urlsplit(origin)
                if origin_parts.netloc.lower() != host:
                    self._send_json(403, {"ok": False, "error": "origin_failed", "message": "Cross-origin admin writes are not allowed"})
                    return False
            return True

        def _read_json_body(self) -> dict | None:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = max(int(raw_length), 0)
            except ValueError:
                self._send_json(400, {"ok": False, "error": "invalid_content_length"})
                return None
            body = self.rfile.read(length) if length else b"{}"
            if not body.strip():
                return {}
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "invalid_json", "message": "Request body must be valid JSON"})
                return None
            if not isinstance(payload, dict):
                self._send_json(400, {"ok": False, "error": "invalid_json_shape", "message": "Request body must be a JSON object"})
                return None
            return payload

        def _actor_metadata(self) -> dict[str, str | None]:
            forwarded_for = self.headers.get("X-Forwarded-For")
            return {
                "client_ip": self.client_address[0] if self.client_address else None,
                "forwarded_for": forwarded_for,
                "user_agent": self.headers.get("User-Agent"),
            }

        def _normalized_next_path(self, raw_value) -> str:  # noqa: ANN001
            if not isinstance(raw_value, str):
                return "/admin.html"
            parsed = urlsplit(raw_value)
            if parsed.scheme or parsed.netloc:
                return "/admin.html"
            path = parsed.path or "/admin.html"
            if not path.startswith("/") or path.startswith("//") or path.startswith("/api/"):
                return "/admin.html"
            if parsed.query:
                return f"{path}?{parsed.query}"
            return path

        def _next_param(self, query: str) -> str:
            values = parse_qs(query).get("next", [])
            return values[0] if values else "/admin.html"

        def _is_secure_request(self) -> bool:
            forwarded_proto = self.headers.get("X-Forwarded-Proto", "").strip().lower()
            if forwarded_proto == "https":
                return True
            cf_visitor = self.headers.get("CF-Visitor", "")
            return '"scheme":"https"' in cf_visitor.lower()

    return Handler


def _run_serve(port: int) -> int:
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    handler = build_docs_handler(docs_dir)

    with _create_http_server(port=port, handler=handler) as httpd:
        logger.info("serving docs at http://localhost:%s", port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("server stopped")
            return 0

    return 0


def _create_http_server(
    port: int,
    handler: type[http.server.BaseHTTPRequestHandler],
) -> socketserver.BaseServer:
    last_error: OSError | None = None
    families: list[tuple[int, str]] = [(socket.AF_INET, "0.0.0.0")]
    if socket.has_ipv6:
        families.insert(0, (socket.AF_INET6, "::"))

    for family, host in families:
        try:
            class Server(_DualStackThreadingHttpServer):
                address_family = family

            return Server((host, port), handler)
        except OSError as exc:
            last_error = exc

    assert last_error is not None
    raise last_error


def _coerce_request_bool(value) -> bool:  # noqa: ANN001
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


def _parse_iso_date_argument(value: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def _post_date_in_range(raw_value: str, start_date: date, end_date: date) -> bool:
    try:
        current = date.fromisoformat(raw_value[:10])
    except ValueError:
        return False
    return start_date <= current <= end_date


def _default_runtime_args(**overrides) -> argparse.Namespace:
    payload = {
        "max_pages": None,
        "recent_pages": None,
        "lookback_days": None,
        "timeout": 15,
        "retries": 4,
        "rate_limit": 0.45,
        "user_agent": DEFAULT_USER_AGENT,
        "skip_incremental": False,
        "start_date": None,
        "end_date": None,
    }
    payload.update(overrides)
    return argparse.Namespace(**payload)


def _run_admin_sync(action: str, payload: Mapping[str, object] | None = None, *, actor: Mapping[str, object] | None = None) -> dict[str, object]:
    body = dict(payload or {})
    if action == "recent":
        args = _default_runtime_args()
        exit_code = _run_refresh(args)
        command = "python -m swimdash refresh"
        window = None
    elif action == "floor":
        args = _default_runtime_args()
        exit_code = _run_refresh(args, force_dashboard_floor=True)
        command = "python -m swimdash refresh-from-floor"
        window = {
            "start": str(resolve_incremental_sync_policy(force_dashboard_floor=True).editable_window_start),
            "end": str(date.today()),
        }
    elif action == "window":
        start_value = body.get("start_date")
        end_value = body.get("end_date") or date.today().isoformat()
        try:
            start_date = _parse_iso_date_argument(str(start_value))
            end_date = _parse_iso_date_argument(str(end_value))
        except argparse.ArgumentTypeError as exc:
            raise AdminValidationError([str(exc)]) from exc
        if end_date < start_date:
            raise AdminValidationError(["end_date must be on or after start_date"])
        args = _default_runtime_args(start_date=start_date, end_date=end_date)
        exit_code = _run_refresh_window(args)
        command = f"python -m swimdash refresh-window --start-date {start_date.isoformat()} --end-date {end_date.isoformat()}"
        window = {"start": start_date.isoformat(), "end": end_date.isoformat()}
    else:
        raise AdminValidationError(["sync mode must be one of: recent, floor, window"])

    if exit_code != 0:
        raise RuntimeError(f"sync command failed with exit code {exit_code}")

    records = load_existing_records()
    summary = {
        "action": "run_sync",
        "sync_mode": action,
        "sync_command": command,
        "sync_window": window,
        "rebuild_triggered": True,
        "rebuild_summary": {
            "record_count": len(records),
        },
    }
    log_admin_runtime_event("run_sync", {**summary, "record_count": len(records)}, actor=dict(actor or {}))
    return summary


def _resolve_incremental_policy(args: argparse.Namespace, *, force_dashboard_floor: bool = False):
    return resolve_incremental_sync_policy(
        as_of=date.today(),
        explicit_lookback_days=args.lookback_days,
        explicit_recent_pages=args.recent_pages,
        force_dashboard_floor=force_dashboard_floor,
    )
