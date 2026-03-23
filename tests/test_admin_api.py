from __future__ import annotations

import http.client
import json
import shutil
import threading
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from swimdash import admin_api, admin_config, pipeline
from swimdash.cli import _create_http_server, build_docs_handler


def test_trigger_admin_rebuild_uses_current_records(monkeypatch):
    with _scratch_dir() as tmp_path:
        calls: list[list[dict]] = []
        monkeypatch.setattr(admin_api, "load_existing_records", lambda: [{"post_id": 1}, {"post_id": 2}])
        monkeypatch.setattr(admin_api, "write_dashboard_data", lambda records: calls.append(records))
        monkeypatch.setattr(admin_api, "ADMIN_CHANGE_LOG_FILE", tmp_path / "admin_changes.log")

        summary = admin_api.trigger_admin_rebuild(actor={"client_ip": "127.0.0.1"})

        assert summary["rebuild_triggered"] is True
        assert summary["rebuild_summary"]["record_count"] == 2
        assert calls == [[{"post_id": 1}, {"post_id": 2}]]


def test_admin_http_login_validation_and_save(monkeypatch):
    with _scratch_dir() as tmp_path:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "admin.html").write_text("<!doctype html><html><body>admin</body></html>\n", encoding="utf-8")
        (docs_dir / "admin-login.html").write_text("<!doctype html><html><body>login</body></html>\n", encoding="utf-8")
        (docs_dir / "data").mkdir(parents=True, exist_ok=True)
        (docs_dir / "data" / "records.json").write_text("[]\n", encoding="utf-8")

        admin_paths = _copy_admin_bundle(tmp_path)
        admin_log = tmp_path / "logs" / "admin_changes.log"

        monkeypatch.setenv("SWIMDASH_ADMIN_PASSWORD", "open-sesame")
        monkeypatch.setenv("SWIMDASH_ADMIN_SESSION_SECRET", "shared-session-secret")
        monkeypatch.setattr(admin_config, "ADMIN_CONFIG_PATHS", admin_paths)
        monkeypatch.setattr(admin_api, "ADMIN_CONFIG_PATHS", admin_paths)
        monkeypatch.setattr(admin_api, "ADMIN_CHANGE_LOG_FILE", admin_log)
        monkeypatch.setattr(pipeline, "RECORDS_FILE", docs_dir / "data" / "records.json")
        monkeypatch.setattr(pipeline, "MANUAL_REVIEW_OVERRIDE_FILE", tmp_path / "data" / "manual_review_overrides.csv")

        handler = build_docs_handler(docs_dir)
        with _create_http_server(port=0, handler=handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]

                status, headers, _payload = _request("GET", port, "/admin.html")
                assert status == 303
                assert headers["Location"].startswith("/admin-login.html?next=/admin.html")

                status, _headers, payload = _request("POST", port, "/api/admin/save/site_config", body={"payload": {}})
                assert status == 401
                assert payload["error"] == "auth_required"

                status, _headers, payload = _request("GET", port, "/api/admin/session")
                assert status == 200
                assert payload["configured"] is True
                assert payload["authenticated"] is False

                status, headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/login",
                    body={"password": "open-sesame", "next": "/admin.html"},
                )
                assert status == 200
                assert payload["authenticated"] is True
                csrf_token = payload["csrf_token"]
                cookie_header = headers["Set-Cookie"].split(";", 1)[0]

                status, _headers, payload = _request(
                    "GET",
                    port,
                    "/api/admin/bundle",
                    headers={"Cookie": cookie_header},
                )
                assert status == 200
                assert payload["ok"] is True
                assert payload["bundle"]["site_config"]["site_title_ko"]

                invalid_site_config = {
                    "site_title_ko": "broken",
                    "site_subtitle_ko": "broken",
                }
                status, _headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/save/site_config",
                    body={"payload": invalid_site_config},
                    headers={
                        "Cookie": cookie_header,
                        "X-Admin-CSRF": csrf_token,
                        "Origin": f"http://127.0.0.1:{port}",
                    },
                )
                assert status == 400
                assert payload["error"] == "validation_failed"
                assert any("site_config.hero" in item for item in payload["errors"])

                site_config = payload = None
                status, _headers, payload = _request(
                    "GET",
                    port,
                    "/api/admin/bundle",
                    headers={"Cookie": cookie_header},
                )
                site_config = payload["bundle"]["site_config"]
                site_config["site_title_ko"] = "관리자 저장 테스트"

                status, _headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/save/site_config",
                    body={"payload": site_config},
                    headers={
                        "Cookie": cookie_header,
                        "X-Admin-CSRF": csrf_token,
                        "Origin": f"http://127.0.0.1:{port}",
                    },
                )
                assert status == 200
                assert payload["ok"] is True
                assert payload["changed_keys"] == ["site_config"]
                assert payload["rebuild_triggered"] is False
                assert payload["bundle"]["site_config"]["site_title_ko"] == "관리자 저장 테스트"

                saved_payload = json.loads(admin_paths["site_config"].read_text(encoding="utf-8"))
                assert saved_payload["site_title_ko"] == "관리자 저장 테스트"
                assert admin_log.exists()
                log_text = admin_log.read_text(encoding="utf-8")
                assert "save_document" in log_text
                assert "site_config" in log_text
            finally:
                server.shutdown()
                thread.join(timeout=5)


def test_admin_http_manual_override_roundtrip(monkeypatch):
    with _scratch_dir() as tmp_path:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "admin.html").write_text("<!doctype html><html><body>admin</body></html>\n", encoding="utf-8")
        (docs_dir / "admin-login.html").write_text("<!doctype html><html><body>login</body></html>\n", encoding="utf-8")
        (docs_dir / "data").mkdir(parents=True, exist_ok=True)
        (docs_dir / "data" / "records.json").write_text("[]\n", encoding="utf-8")

        admin_paths = _copy_admin_bundle(tmp_path)
        admin_log = tmp_path / "logs" / "admin_changes.log"
        manual_override_path = tmp_path / "data" / "manual_review_overrides.csv"

        monkeypatch.setenv("SWIMDASH_ADMIN_PASSWORD", "open-sesame")
        monkeypatch.setenv("SWIMDASH_ADMIN_SESSION_SECRET", "shared-session-secret")
        monkeypatch.setattr(admin_config, "ADMIN_CONFIG_PATHS", admin_paths)
        monkeypatch.setattr(admin_api, "ADMIN_CONFIG_PATHS", admin_paths)
        monkeypatch.setattr(admin_api, "ADMIN_CHANGE_LOG_FILE", admin_log)
        monkeypatch.setattr(admin_api, "MANUAL_REVIEW_OVERRIDE_FILE", manual_override_path)
        monkeypatch.setattr(pipeline, "RECORDS_FILE", docs_dir / "data" / "records.json")
        monkeypatch.setattr(pipeline, "MANUAL_REVIEW_OVERRIDE_FILE", manual_override_path)

        handler = build_docs_handler(docs_dir)
        with _create_http_server(port=0, handler=handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]

                status, headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/login",
                    body={"password": "open-sesame", "next": "/parse-status.html"},
                )
                assert status == 200
                assert payload["authenticated"] is True
                csrf_token = payload["csrf_token"]
                cookie_header = headers["Set-Cookie"].split(";", 1)[0]

                status, _headers, payload = _request(
                    "GET",
                    port,
                    "/api/admin/manual-overrides",
                    headers={"Cookie": cookie_header},
                )
                assert status == 200
                assert payload["row_count"] == 0

                status, _headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/manual-overrides/save",
                    body={
                        "payload": {
                            "post_id": 17519,
                            "decision": "patch",
                            "distance_m": 1400,
                            "total_time_text": "01:47:28",
                            "note": "typo fix",
                        },
                        "run_rebuild": False,
                    },
                    headers={
                        "Cookie": cookie_header,
                        "X-Admin-CSRF": csrf_token,
                        "Origin": f"http://127.0.0.1:{port}",
                    },
                )
                assert status == 200
                assert payload["ok"] is True
                assert payload["action"] == "save_manual_override"
                assert payload["row_count"] == 1
                assert payload["override"]["total_time_text"] == "01:47:28"

                saved_text = manual_override_path.read_text(encoding="utf-8")
                assert "17519,patch,1400,01:47:28,typo fix" in saved_text

                status, _headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/manual-overrides/delete",
                    body={"post_id": 17519, "run_rebuild": False},
                    headers={
                        "Cookie": cookie_header,
                        "X-Admin-CSRF": csrf_token,
                        "Origin": f"http://127.0.0.1:{port}",
                    },
                )
                assert status == 200
                assert payload["ok"] is True
                assert payload["action"] == "delete_manual_override"
                assert payload["row_count"] == 0

                saved_text = manual_override_path.read_text(encoding="utf-8")
                assert "17519,patch,1400,01:47:28,typo fix" not in saved_text
            finally:
                server.shutdown()
                thread.join(timeout=5)


def test_admin_http_badge_icon_upload_roundtrip(monkeypatch):
    with _scratch_dir() as tmp_path:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "admin.html").write_text("<!doctype html><html><body>admin</body></html>\n", encoding="utf-8")
        (docs_dir / "admin-login.html").write_text("<!doctype html><html><body>login</body></html>\n", encoding="utf-8")
        (docs_dir / "data").mkdir(parents=True, exist_ok=True)
        (docs_dir / "data" / "records.json").write_text("[]\n", encoding="utf-8")

        admin_paths = _copy_admin_bundle(tmp_path)
        admin_log = tmp_path / "logs" / "admin_changes.log"
        custom_badges_dir = docs_dir / "assets" / "badges" / "custom"
        custom_badges_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setenv("SWIMDASH_ADMIN_PASSWORD", "open-sesame")
        monkeypatch.setenv("SWIMDASH_ADMIN_SESSION_SECRET", "shared-session-secret")
        monkeypatch.setattr(admin_config, "ADMIN_CONFIG_PATHS", admin_paths)
        monkeypatch.setattr(admin_api, "ADMIN_CONFIG_PATHS", admin_paths)
        monkeypatch.setattr(admin_api, "ADMIN_CHANGE_LOG_FILE", admin_log)
        monkeypatch.setattr(admin_api, "CUSTOM_BADGE_ASSET_DIR", custom_badges_dir)
        monkeypatch.setattr(pipeline, "RECORDS_FILE", docs_dir / "data" / "records.json")

        handler = build_docs_handler(docs_dir)
        with _create_http_server(port=0, handler=handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]

                status, headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/login",
                    body={"password": "open-sesame", "next": "/admin.html"},
                )
                assert status == 200
                assert payload["authenticated"] is True
                csrf_token = payload["csrf_token"]
                cookie_header = headers["Set-Cookie"].split(";", 1)[0]

                svg_base64 = "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiByeD0iMTYiIGZpbGw9IiNGRkQ5NjUiLz48L3N2Zz4="
                status, _headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/badge-icons/upload",
                    body={
                        "payload": {
                            "icon_key": "custom.wave_gold",
                            "family": "custom",
                            "filename": "wave-gold.svg",
                            "content_base64": svg_base64,
                            "tier_compatibility": ["gold", "prism"],
                            "badge_id_prefixes": ["dst", "fun"],
                            "color_notes": "gold accent",
                            "display_notes": "test icon",
                        },
                        "run_rebuild": False,
                    },
                    headers={
                        "Cookie": cookie_header,
                        "X-Admin-CSRF": csrf_token,
                        "Origin": f"http://127.0.0.1:{port}",
                    },
                )
                assert status == 200
                assert payload["ok"] is True
                assert payload["action"] == "upload_badge_icon"
                assert payload["icon_key"] == "custom.wave_gold"

                saved_asset = custom_badges_dir / "custom-wave_gold.svg"
                assert saved_asset.exists()

                saved_catalog = json.loads(admin_paths["badge_art_catalog"].read_text(encoding="utf-8"))
                saved_icon = next(item for item in saved_catalog["icons"] if item["icon_key"] == "custom.wave_gold")
                assert saved_icon["file_path"].endswith("custom/custom-wave_gold.svg")
                assert saved_icon["badge_id_prefixes"] == ["dst", "fun"]
                assert saved_icon["tier_compatibility"] == ["gold", "prism"]
            finally:
                server.shutdown()
                thread.join(timeout=5)


def test_admin_http_run_sync_roundtrip(monkeypatch):
    with _scratch_dir() as tmp_path:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "admin.html").write_text("<!doctype html><html><body>admin</body></html>\n", encoding="utf-8")
        (docs_dir / "admin-login.html").write_text("<!doctype html><html><body>login</body></html>\n", encoding="utf-8")
        (docs_dir / "data").mkdir(parents=True, exist_ok=True)
        (docs_dir / "data" / "records.json").write_text("[]\n", encoding="utf-8")

        admin_paths = _copy_admin_bundle(tmp_path)
        admin_log = tmp_path / "logs" / "admin_changes.log"

        monkeypatch.setenv("SWIMDASH_ADMIN_PASSWORD", "open-sesame")
        monkeypatch.setenv("SWIMDASH_ADMIN_SESSION_SECRET", "shared-session-secret")
        monkeypatch.setattr(admin_config, "ADMIN_CONFIG_PATHS", admin_paths)
        monkeypatch.setattr(admin_api, "ADMIN_CONFIG_PATHS", admin_paths)
        monkeypatch.setattr(admin_api, "ADMIN_CHANGE_LOG_FILE", admin_log)
        monkeypatch.setattr(pipeline, "RECORDS_FILE", docs_dir / "data" / "records.json")

        def fake_run_admin_sync(mode, payload=None, actor=None):  # noqa: ANN001
            return {
                "action": "run_sync",
                "sync_mode": mode,
                "sync_window": {
                    "start": "2026-03-01",
                    "end": "2026-03-03",
                } if mode == "window" else None,
                "rebuild_triggered": True,
                "rebuild_summary": {"record_count": 12},
            }

        monkeypatch.setattr("swimdash.cli._run_admin_sync", fake_run_admin_sync)

        handler = build_docs_handler(docs_dir)
        with _create_http_server(port=0, handler=handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]

                status, headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/login",
                    body={"password": "open-sesame", "next": "/admin.html"},
                )
                assert status == 200
                csrf_token = payload["csrf_token"]
                cookie_header = headers["Set-Cookie"].split(";", 1)[0]

                status, _headers, payload = _request(
                    "POST",
                    port,
                    "/api/admin/run-sync",
                    body={"mode": "window", "start_date": "2026-03-01", "end_date": "2026-03-03"},
                    headers={
                        "Cookie": cookie_header,
                        "X-Admin-CSRF": csrf_token,
                        "Origin": f"http://127.0.0.1:{port}",
                    },
                )
                assert status == 200
                assert payload["ok"] is True
                assert payload["action"] == "run_sync"
                assert payload["sync_mode"] == "window"
                assert payload["sync_window"] == {"start": "2026-03-01", "end": "2026-03-03"}
                assert payload["rebuild_triggered"] is True
            finally:
                server.shutdown()
                thread.join(timeout=5)


def _request(
    method: str,
    port: int,
    path: str,
    *,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], dict | None]:
    request_headers = {
        "Accept": "application/json",
        **(headers or {}),
    }
    raw_body = None
    if body is not None:
        raw_body = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
        request_headers["Content-Length"] = str(len(raw_body))

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, body=raw_body, headers=request_headers)
        response = conn.getresponse()
        payload_raw = response.read()
        payload = json.loads(payload_raw.decode("utf-8")) if payload_raw else None
        header_map = {key: value for key, value in response.getheaders()}
        return response.status, header_map, payload
    finally:
        conn.close()


def _copy_admin_bundle(tmp_path: Path) -> dict[str, Path]:
    source_dir = Path(__file__).resolve().parents[1] / "data" / "admin"
    target_dir = tmp_path / "data" / "admin"
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for key, filename in {
        "site_config": "site_config.json",
        "navigation_config": "navigation_config.json",
        "home_sections": "home_sections.json",
        "badge_catalog": "badge_catalog.json",
        "badge_art_catalog": "badge_art_catalog.json",
        "season_badges": "season_badges.json",
        "gallery_title_rules": "gallery_title_rules.json",
        "profile_layout_config": "profile_layout_config.json",
    }.items():
        source = source_dir / filename
        target = target_dir / filename
        shutil.copyfile(source, target)
        copied[key] = target
    return copied


@contextmanager
def _scratch_dir():
    base = Path(__file__).resolve().parents[1] / ".pytest_tmp_admin_api" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)
