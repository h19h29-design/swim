from __future__ import annotations

import base64
import binascii
import contextlib
import csv
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swimdash.admin_config import ADMIN_CONFIG_PATHS, build_public_site_config_payload, load_admin_config_bundle
from swimdash.aggregate import build_admin_preview, build_badge_index
from swimdash.config import (
    ADMIN_CHANGE_LOG_FILE,
    ADMIN_REBUILD_COMMAND,
    BADGE_ART_CATALOG_FILE,
    CUSTOM_BADGE_ASSET_DIR,
    MANUAL_REVIEW_OVERRIDE_FILE,
)
from swimdash.parser import parse_total_time_text_value
from swimdash.pipeline import (
    MANUAL_OVERRIDE_DECISIONS,
    ensure_manual_review_override_file_exists,
    load_existing_records,
    load_manual_review_overrides,
    write_dashboard_data,
)

_COOKIE_NAME_ENV = "SWIMDASH_ADMIN_COOKIE_NAME"
_PASSWORD_ENV = "SWIMDASH_ADMIN_PASSWORD"
_SESSION_SECRET_ENV = "SWIMDASH_ADMIN_SESSION_SECRET"
_SESSION_TTL_ENV = "SWIMDASH_ADMIN_SESSION_TTL_SECONDS"
_DEFAULT_COOKIE_NAME = "swimdash_admin"
_DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60
_SITE_MODE_CORE_ONLY = "core_only"
_MONTH_TOKEN_RE = re.compile(r"^(0[1-9]|1[0-2])$")
_MANUAL_OVERRIDE_FIELDNAMES = ("post_id", "decision", "distance_m", "total_time_text", "note")
_BADGE_ICON_KEY_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_BADGE_ICON_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
_ALLOWED_BADGE_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".webp"}


class AdminValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("Admin config validation failed")
        self.errors = errors


@dataclass(frozen=True, slots=True)
class AdminAuthSettings:
    password: str
    session_secret: str
    cookie_name: str
    session_ttl_seconds: int

    @property
    def configured(self) -> bool:
        return bool(self.password and self.session_secret)


def load_admin_auth_settings() -> AdminAuthSettings:
    ttl_raw = str(os.getenv(_SESSION_TTL_ENV, str(_DEFAULT_SESSION_TTL_SECONDS))).strip()
    try:
        ttl = max(int(ttl_raw), 300)
    except ValueError:
        ttl = _DEFAULT_SESSION_TTL_SECONDS
    return AdminAuthSettings(
        password=str(os.getenv(_PASSWORD_ENV, "")).strip(),
        session_secret=str(os.getenv(_SESSION_SECRET_ENV, "")).strip(),
        cookie_name=str(os.getenv(_COOKIE_NAME_ENV, _DEFAULT_COOKIE_NAME)).strip() or _DEFAULT_COOKIE_NAME,
        session_ttl_seconds=ttl,
    )


def authenticate_admin_password(password: str, settings: AdminAuthSettings | None = None) -> bool:
    auth_settings = settings or load_admin_auth_settings()
    if not auth_settings.configured:
        return False
    return hmac.compare_digest(str(password or ""), auth_settings.password)


def create_admin_session(settings: AdminAuthSettings | None = None) -> tuple[str, dict[str, Any]]:
    auth_settings = settings or load_admin_auth_settings()
    if not auth_settings.configured:
        raise RuntimeError("Admin auth is not configured")

    now = int(time.time())
    payload = {
        "v": 1,
        "iat": now,
        "exp": now + auth_settings.session_ttl_seconds,
        "csrf": secrets.token_urlsafe(24),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = f"{_base64url_encode(raw)}.{_sign_bytes(raw, auth_settings.session_secret)}"
    return token, payload


def parse_admin_session(token: str | None, settings: AdminAuthSettings | None = None) -> dict[str, Any] | None:
    auth_settings = settings or load_admin_auth_settings()
    if not auth_settings.configured:
        return None
    if not token or "." not in token:
        return None

    encoded, supplied_signature = token.split(".", 1)
    raw = _base64url_decode(encoded)
    if raw is None:
        return None

    expected_signature = _sign_bytes(raw, auth_settings.session_secret)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    now = int(time.time())
    expires_at = _coerce_int(payload.get("exp"))
    if expires_at is None or expires_at < now:
        return None
    csrf_token = payload.get("csrf")
    if not isinstance(csrf_token, str) or not csrf_token:
        return None
    return payload


def build_session_cookie_header(
    token: str,
    *,
    settings: AdminAuthSettings | None = None,
    secure: bool = False,
) -> str:
    auth_settings = settings or load_admin_auth_settings()
    parts = [
        f"{auth_settings.cookie_name}={token}",
        "Path=/",
        "HttpOnly",
        "SameSite=Strict",
        f"Max-Age={auth_settings.session_ttl_seconds}",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def build_logout_cookie_header(
    *,
    settings: AdminAuthSettings | None = None,
    secure: bool = False,
) -> str:
    auth_settings = settings or load_admin_auth_settings()
    parts = [
        f"{auth_settings.cookie_name}=",
        "Path=/",
        "HttpOnly",
        "SameSite=Strict",
        "Max-Age=0",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def extract_session_cookie(cookie_header: str | None, settings: AdminAuthSettings | None = None) -> str | None:
    auth_settings = settings or load_admin_auth_settings()
    if not cookie_header:
        return None
    for chunk in cookie_header.split(";"):
        name, separator, value = chunk.strip().partition("=")
        if separator and name == auth_settings.cookie_name:
            return value or None
    return None


def build_admin_workspace_payload() -> dict[str, Any]:
    bundle = load_admin_config_bundle()
    records = load_existing_records()
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    return {
        "bundle": deepcopy(bundle),
        "preview": build_admin_preview(records, admin_bundle=bundle),
        "badge_index": build_badge_index(records, admin_bundle=bundle),
        "public_site_config": build_public_site_config_payload(bundle=bundle, generated_at=generated_at),
        "source_paths": {key: path.as_posix() for key, path in ADMIN_CONFIG_PATHS.items()},
        "rebuild_command": ADMIN_REBUILD_COMMAND,
        "rebuild_recommended": True,
        "save_targets": list(ADMIN_CONFIG_PATHS.keys()),
    }


def build_manual_override_payload() -> dict[str, Any]:
    rows = load_manual_override_rows()
    return {
        "rows": rows,
        "row_count": len(rows),
        "source_path": MANUAL_REVIEW_OVERRIDE_FILE.as_posix(),
        "rebuild_command": ADMIN_REBUILD_COMMAND,
        "rebuild_recommended": True,
    }


def load_manual_override_rows(path: Path | None = None) -> list[dict[str, Any]]:
    overrides = load_manual_review_overrides(path or MANUAL_REVIEW_OVERRIDE_FILE)
    rows: list[dict[str, Any]] = []
    for post_id in sorted(overrides):
        override = overrides[post_id]
        rows.append(
            {
                "post_id": post_id,
                "decision": override.get("decision"),
                "distance_m": override.get("distance_m"),
                "total_time_text": override.get("total_time_text"),
                "note": override.get("note"),
            }
        )
    return rows


def save_manual_override(
    payload: Any,
    *,
    actor: dict[str, Any] | None = None,
    run_rebuild: bool = False,
) -> dict[str, Any]:
    validated = validate_manual_override_payload(payload)
    current_rows = load_manual_override_rows()
    current_map = {int(row["post_id"]): dict(row) for row in current_rows}
    previous = current_map.get(int(validated["post_id"]))
    current_map[int(validated["post_id"])] = dict(validated)
    changed = previous != current_map[int(validated["post_id"])]
    _write_manual_override_rows(current_map.values())
    rebuild_summary = _maybe_rebuild(run_rebuild)
    summary = {
        "action": "save_manual_override",
        "post_id": validated["post_id"],
        "changed": changed,
        "override": validated,
        "row_count": len(current_map),
        "source_path": MANUAL_REVIEW_OVERRIDE_FILE.as_posix(),
        "rebuild_triggered": rebuild_summary["triggered"],
        "rebuild_summary": rebuild_summary["summary"],
        "rebuild_command": ADMIN_REBUILD_COMMAND,
        "rebuild_recommended": True,
    }
    _append_change_log(
        {
            **_actor_metadata(actor),
            **summary,
            "timestamp": _utc_now(),
            "payload_digest": _payload_digest(validated),
        }
    )
    return summary


def delete_manual_override(
    post_id: Any,
    *,
    actor: dict[str, Any] | None = None,
    run_rebuild: bool = False,
) -> dict[str, Any]:
    normalized_post_id = _coerce_int(post_id)
    if normalized_post_id is None or normalized_post_id <= 0:
        raise AdminValidationError(["post_id must be a positive integer"])
    current_rows = load_manual_override_rows()
    current_map = {int(row["post_id"]): dict(row) for row in current_rows}
    removed = current_map.pop(normalized_post_id, None)
    _write_manual_override_rows(current_map.values())
    rebuild_summary = _maybe_rebuild(run_rebuild)
    summary = {
        "action": "delete_manual_override",
        "post_id": normalized_post_id,
        "deleted": removed is not None,
        "row_count": len(current_map),
        "source_path": MANUAL_REVIEW_OVERRIDE_FILE.as_posix(),
        "rebuild_triggered": rebuild_summary["triggered"],
        "rebuild_summary": rebuild_summary["summary"],
        "rebuild_command": ADMIN_REBUILD_COMMAND,
        "rebuild_recommended": True,
    }
    _append_change_log(
        {
            **_actor_metadata(actor),
            **summary,
            "timestamp": _utc_now(),
        }
    )
    return summary


def validate_manual_override_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        raise AdminValidationError(["manual override payload must be a JSON object"])

    post_id = _coerce_int(payload.get("post_id"))
    decision_raw = _clean_string(payload.get("decision"))
    decision = decision_raw.lower() if isinstance(decision_raw, str) else None
    note = _clean_string(payload.get("note"))

    if post_id is None:
        errors.append("post_id must be a positive integer")
    elif post_id <= 0:
        errors.append("post_id must be >= 1")

    if decision not in MANUAL_OVERRIDE_DECISIONS:
        errors.append(f"decision must be one of: {', '.join(sorted(MANUAL_OVERRIDE_DECISIONS))}")

    distance_m = _coerce_int(payload.get("distance_m"))
    total_time_text = _clean_string(payload.get("total_time_text"))

    if decision == "patch":
        if distance_m is None:
            errors.append("patch override requires distance_m")
        elif distance_m <= 0:
            errors.append("patch override distance_m must be >= 1")

        if not total_time_text:
            errors.append("patch override requires total_time_text")
        else:
            parsed = parse_total_time_text_value(total_time_text)
            if parsed is None:
                errors.append("patch override total_time_text must be a valid duration string")
            else:
                total_time_text = parsed[0]

    if errors:
        raise AdminValidationError(errors)

    return {
        "post_id": int(post_id),
        "decision": str(decision),
        "distance_m": distance_m if decision == "patch" else None,
        "total_time_text": total_time_text if decision == "patch" else None,
        "note": note,
    }


def validate_admin_document(key: str, payload: Any, *, bundle: dict[str, Any] | None = None) -> Any:
    current_bundle = deepcopy(bundle) if bundle is not None else load_admin_config_bundle()
    candidate = deepcopy(current_bundle)
    candidate[key] = deepcopy(payload)
    validated = validate_admin_bundle(candidate)
    return deepcopy(validated[key])


def validate_admin_bundle(bundle: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(bundle, dict):
        raise AdminValidationError(["bundle must be a JSON object"])

    normalized = deepcopy(bundle)
    expected_keys = set(ADMIN_CONFIG_PATHS.keys())
    actual_keys = set(normalized.keys())
    missing_keys = sorted(expected_keys - actual_keys)
    extra_keys = sorted(actual_keys - expected_keys)
    if missing_keys:
        errors.append(f"bundle is missing required keys: {', '.join(missing_keys)}")
    if extra_keys:
        errors.append(f"bundle contains unsupported keys: {', '.join(extra_keys)}")

    if "site_config" in normalized:
        _validate_site_config(errors, normalized["site_config"])
    if "navigation_config" in normalized:
        _validate_navigation_config(errors, normalized["navigation_config"])
    if "home_sections" in normalized:
        _validate_home_sections(errors, normalized["home_sections"])
    if "badge_catalog" in normalized:
        _validate_badge_catalog(errors, normalized["badge_catalog"])
    if "season_badges" in normalized:
        _validate_season_badges(errors, normalized["season_badges"])
    if "gallery_title_rules" in normalized:
        _validate_gallery_title_rules(errors, normalized["gallery_title_rules"])
    if "profile_layout_config" in normalized:
        _validate_profile_layout_config(errors, normalized["profile_layout_config"])
    if "badge_art_catalog" in normalized:
        _validate_badge_art_catalog(errors, normalized["badge_art_catalog"])

    if not errors:
        _validate_cross_references(errors, normalized)

    if errors:
        raise AdminValidationError(errors)
    return normalized


def save_admin_document(
    key: str,
    payload: Any,
    *,
    actor: dict[str, Any] | None = None,
    run_rebuild: bool = False,
) -> dict[str, Any]:
    if key not in ADMIN_CONFIG_PATHS:
        raise KeyError(key)

    current_bundle = load_admin_config_bundle()
    candidate = deepcopy(current_bundle)
    candidate[key] = deepcopy(payload)
    validated_bundle = validate_admin_bundle(candidate)
    changed_keys, changed_files = _persist_admin_bundle(current_bundle, validated_bundle, keys=[key])
    rebuild_summary = _maybe_rebuild(run_rebuild)
    summary = {
        "action": "save_document",
        "saved_key": key,
        "changed_keys": changed_keys,
        "changed_files": changed_files,
        "rebuild_triggered": rebuild_summary["triggered"],
        "rebuild_summary": rebuild_summary["summary"],
        "rebuild_command": ADMIN_REBUILD_COMMAND,
        "rebuild_recommended": True,
    }
    _append_change_log(
        {
            **_actor_metadata(actor),
            **summary,
            "timestamp": _utc_now(),
            "payload_digest": _payload_digest(validated_bundle[key]),
        }
    )
    return summary


def validate_badge_icon_upload_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        raise AdminValidationError(["badge icon payload must be a JSON object"])

    icon_key = _clean_string(payload.get("icon_key"))
    family = _clean_string(payload.get("family"))
    filename = _clean_string(payload.get("filename"))
    content_base64 = _clean_string(payload.get("content_base64"))
    color_notes = _clean_string(payload.get("color_notes")) or ""
    display_notes = _clean_string(payload.get("display_notes")) or ""
    tier_compatibility = payload.get("tier_compatibility")
    badge_id_prefixes = payload.get("badge_id_prefixes")

    if not icon_key or not _BADGE_ICON_KEY_RE.match(icon_key):
        errors.append("icon_key must use lowercase letters, numbers, dots, underscores, or hyphens")
    if not family:
        errors.append("family is required")
    if not filename or not _BADGE_ICON_FILENAME_RE.match(filename):
        errors.append("filename is required and must be safe")
    if not content_base64:
        errors.append("content_base64 is required")

    extension = Path(filename or "").suffix.lower()
    if extension not in _ALLOWED_BADGE_EXTENSIONS:
        errors.append("filename extension must be one of: .svg, .png, .jpg, .jpeg, .webp")

    content = b""
    if content_base64:
        try:
            content = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError):
            errors.append("content_base64 must be valid base64")
    if content and len(content) > 2 * 1024 * 1024:
        errors.append("badge icon file must be <= 2MB")

    if not isinstance(tier_compatibility, list) or not tier_compatibility:
        tier_compatibility = ["starter", "rally", "gold", "prism"]
    else:
        tier_compatibility = [str(item).strip() for item in tier_compatibility if str(item).strip()]

    if not isinstance(badge_id_prefixes, list):
        badge_id_prefixes = []
    else:
        badge_id_prefixes = [str(item).strip() for item in badge_id_prefixes if str(item).strip()]

    if errors:
        raise AdminValidationError(errors)

    return {
        "icon_key": icon_key,
        "family": family,
        "filename": filename,
        "extension": extension,
        "content": content,
        "tier_compatibility": tier_compatibility,
        "color_notes": color_notes,
        "display_notes": display_notes,
        "badge_id_prefixes": badge_id_prefixes,
    }


def save_admin_bundle(
    bundle: Any,
    *,
    actor: dict[str, Any] | None = None,
    run_rebuild: bool = False,
) -> dict[str, Any]:
    current_bundle = load_admin_config_bundle()
    validated_bundle = validate_admin_bundle(bundle)
    changed_keys, changed_files = _persist_admin_bundle(current_bundle, validated_bundle, keys=ADMIN_CONFIG_PATHS.keys())
    rebuild_summary = _maybe_rebuild(run_rebuild)
    summary = {
        "action": "save_bundle",
        "changed_keys": changed_keys,
        "changed_files": changed_files,
        "rebuild_triggered": rebuild_summary["triggered"],
        "rebuild_summary": rebuild_summary["summary"],
        "rebuild_command": ADMIN_REBUILD_COMMAND,
        "rebuild_recommended": True,
    }
    _append_change_log(
        {
            **_actor_metadata(actor),
            **summary,
            "timestamp": _utc_now(),
            "bundle_digest": _payload_digest(validated_bundle),
        }
    )
    return summary


def trigger_admin_rebuild(*, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    records = load_existing_records()
    write_dashboard_data(records)
    summary = {
        "action": "rebuild",
        "rebuild_triggered": True,
        "rebuild_summary": {
            "record_count": len(records),
            "generated_at": _utc_now(),
        },
        "rebuild_command": ADMIN_REBUILD_COMMAND,
        "rebuild_recommended": True,
    }
    _append_change_log(
        {
            **_actor_metadata(actor),
            **summary,
            "timestamp": _utc_now(),
        }
    )
    return summary


def log_admin_runtime_event(action: str, payload: dict[str, Any], *, actor: dict[str, Any] | None = None) -> None:
    _append_change_log(
        {
            **_actor_metadata(actor),
            "action": action,
            "timestamp": _utc_now(),
            **payload,
        }
    )


def save_badge_icon_asset(
    payload: Any,
    *,
    actor: dict[str, Any] | None = None,
    run_rebuild: bool = False,
) -> dict[str, Any]:
    validated = validate_badge_icon_upload_payload(payload)
    CUSTOM_BADGE_ASSET_DIR.mkdir(parents=True, exist_ok=True)

    extension = validated["extension"]
    filename = f"{validated['icon_key'].replace('.', '-')}{extension}"
    target_path = CUSTOM_BADGE_ASSET_DIR / filename
    target_path.write_bytes(validated["content"])

    bundle = load_admin_config_bundle()
    art_catalog = deepcopy(bundle["badge_art_catalog"])
    icons = art_catalog.setdefault("icons", [])
    if not isinstance(icons, list):
        raise AdminValidationError(["badge_art_catalog.icons must be a list"])

    file_path = target_path.as_posix()
    icon_entry = {
        "icon_key": validated["icon_key"],
        "file_path": file_path,
        "family": validated["family"],
        "tier_compatibility": validated["tier_compatibility"],
        "color_notes": validated["color_notes"],
        "display_notes": validated["display_notes"],
        "badge_id_prefixes": validated["badge_id_prefixes"],
    }

    replaced = False
    for index, item in enumerate(icons):
        if isinstance(item, dict) and str(item.get("icon_key") or "") == validated["icon_key"]:
            icons[index] = icon_entry
            replaced = True
            break
    if not replaced:
        icons.append(icon_entry)

    validated_bundle = validate_admin_bundle({**bundle, "badge_art_catalog": art_catalog})
    changed_keys, changed_files = _persist_admin_bundle(bundle, validated_bundle, keys=["badge_art_catalog"])
    rebuild_summary = _maybe_rebuild(run_rebuild)
    summary = {
        "action": "upload_badge_icon",
        "saved_key": "badge_art_catalog",
        "icon_key": validated["icon_key"],
        "file_path": file_path,
        "changed_keys": changed_keys,
        "changed_files": changed_files,
        "rebuild_triggered": rebuild_summary["triggered"],
        "rebuild_summary": rebuild_summary["summary"],
        "rebuild_command": ADMIN_REBUILD_COMMAND,
        "rebuild_recommended": True,
    }
    _append_change_log(
        {
            **_actor_metadata(actor),
            **summary,
            "timestamp": _utc_now(),
            "payload_digest": _payload_digest(icon_entry),
        }
    )
    return summary


def _maybe_rebuild(run_rebuild: bool) -> dict[str, Any]:
    if not run_rebuild:
        return {"triggered": False, "summary": None}
    records = load_existing_records()
    write_dashboard_data(records)
    return {
        "triggered": True,
        "summary": {
            "record_count": len(records),
            "generated_at": _utc_now(),
        },
    }


def _persist_admin_bundle(
    current_bundle: dict[str, Any],
    candidate_bundle: dict[str, Any],
    *,
    keys,
) -> tuple[list[str], dict[str, str]]:
    changed_keys: list[str] = []
    changed_files: dict[str, str] = {}
    for key in keys:
        current_payload = current_bundle.get(key)
        next_payload = candidate_bundle.get(key)
        if current_payload == next_payload:
            continue
        target_path = ADMIN_CONFIG_PATHS[str(key)]
        _write_json_atomic(target_path, next_payload)
        changed_keys.append(str(key))
        changed_files[str(key)] = target_path.as_posix()
    return changed_keys, changed_files


def _write_manual_override_rows(rows: Any, path: Path | None = None) -> None:
    target = path or MANUAL_REVIEW_OVERRIDE_FILE
    ensure_manual_review_override_file_exists(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = _coerce_int(row.get("post_id"))
        decision = _clean_string(row.get("decision"))
        if post_id is None or post_id <= 0 or decision is None:
            continue
        normalized_rows.append(
            {
                "post_id": int(post_id),
                "decision": decision,
                "distance_m": _coerce_int(row.get("distance_m")),
                "total_time_text": _clean_string(row.get("total_time_text")),
                "note": _clean_string(row.get("note")),
            }
        )

    normalized_rows.sort(key=lambda item: int(item["post_id"]))

    fd, temp_name = tempfile.mkstemp(prefix=f"{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=_MANUAL_OVERRIDE_FIELDNAMES)
            writer.writeheader()
            for row in normalized_rows:
                writer.writerow(
                    {
                        "post_id": row["post_id"],
                        "decision": row["decision"],
                        "distance_m": row["distance_m"] if row["distance_m"] is not None else "",
                        "total_time_text": row["total_time_text"] or "",
                        "note": row["note"] or "",
                    }
                )
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            with contextlib.suppress(OSError):
                os.remove(temp_name)


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(rendered)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            with contextlib.suppress(OSError):
                os.remove(temp_name)


def _append_change_log(entry: dict[str, Any]) -> None:
    ADMIN_CHANGE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ADMIN_CHANGE_LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def _actor_metadata(actor: dict[str, Any] | None) -> dict[str, Any]:
    payload = actor or {}
    return {
        "client_ip": payload.get("client_ip"),
        "forwarded_for": payload.get("forwarded_for"),
        "user_agent": payload.get("user_agent"),
    }


def _validate_site_config(errors: list[str], payload: Any) -> None:
    site = _require_object(errors, "site_config", payload)
    _require_string(errors, "site_config.site_title_ko", site.get("site_title_ko"))
    _require_string(errors, "site_config.site_subtitle_ko", site.get("site_subtitle_ko"))
    _require_string(errors, "site_config.product_mode", site.get("product_mode"))
    if isinstance(site.get("product_mode"), str) and site.get("product_mode") != _SITE_MODE_CORE_ONLY:
        errors.append("site_config.product_mode must stay 'core_only'")
    _require_string(errors, "site_config.theme_direction_ko", site.get("theme_direction_ko"))
    _require_string(errors, "site_config.empty_state_ko", site.get("empty_state_ko"))
    _require_string(errors, "site_config.admin_edit_note_ko", site.get("admin_edit_note_ko"))
    _require_string_list(errors, "site_config.main_experience_notes_ko", site.get("main_experience_notes_ko"), min_items=1)

    hero = _require_object(errors, "site_config.hero", site.get("hero"))
    _require_string(errors, "site_config.hero.eyebrow_ko", hero.get("eyebrow_ko"))
    _require_string(errors, "site_config.hero.headline_ko", hero.get("headline_ko"))
    _require_string(errors, "site_config.hero.subheadline_ko", hero.get("subheadline_ko"))

    kpi_labels = _require_object(errors, "site_config.kpi_labels", site.get("kpi_labels"))
    for field in ("swim_count", "total_distance_m", "total_seconds", "active_authors"):
        _require_string(errors, f"site_config.kpi_labels.{field}", kpi_labels.get(field))

    gallery_labels = _require_object(errors, "site_config.gallery_labels", site.get("gallery_labels"))
    for field in ("current_title_ko", "next_title_ko", "recent_unlocks_ko"):
        _require_string(errors, f"site_config.gallery_labels.{field}", gallery_labels.get(field))


def _validate_navigation_config(errors: list[str], payload: Any) -> None:
    navigation = _require_object(errors, "navigation_config", payload)
    default_nav_key = navigation.get("default_nav_key")
    _require_string(errors, "navigation_config.default_nav_key", default_nav_key)
    items = _require_object_list(errors, "navigation_config.items", navigation.get("items"), min_items=1)

    nav_keys: list[str] = []
    for index, item in enumerate(items):
        base = f"navigation_config.items[{index}]"
        nav_key = item.get("nav_key")
        _require_string(errors, f"{base}.nav_key", nav_key)
        _require_string(errors, f"{base}.label_ko", item.get("label_ko"))
        _require_string(errors, f"{base}.description_ko", item.get("description_ko"))
        _require_bool(errors, f"{base}.visible", item.get("visible"))
        if isinstance(nav_key, str):
            nav_keys.append(nav_key)

    if nav_keys and len(nav_keys) != len(set(nav_keys)):
        errors.append("navigation_config.items must not contain duplicate nav_key values")
    if isinstance(default_nav_key, str) and nav_keys and default_nav_key not in nav_keys:
        errors.append("navigation_config.default_nav_key must match one of navigation_config.items[].nav_key")


def _validate_home_sections(errors: list[str], payload: Any) -> None:
    home = _require_object(errors, "home_sections", payload)
    default_metric = home.get("default_ranking_metric")
    _require_string(errors, "home_sections.default_ranking_metric", default_metric)
    _require_string_list(errors, "home_sections.section_order", home.get("section_order"), min_items=1)
    _require_positive_int(errors, "home_sections.recent_unlock_limit", home.get("recent_unlock_limit"))
    _require_positive_int(errors, "home_sections.recent_record_limit", home.get("recent_record_limit"))

    sections = _require_object_list(errors, "home_sections.ranking_sections", home.get("ranking_sections"), min_items=1)
    metric_keys: list[str] = []
    for index, item in enumerate(sections):
        base = f"home_sections.ranking_sections[{index}]"
        metric_key = item.get("metric_key")
        _require_string(errors, f"{base}.metric_key", metric_key)
        _require_string(errors, f"{base}.label_ko", item.get("label_ko"))
        _require_string(errors, f"{base}.description_ko", item.get("description_ko"))
        if isinstance(metric_key, str):
            metric_keys.append(metric_key)

    if metric_keys and len(metric_keys) != len(set(metric_keys)):
        errors.append("home_sections.ranking_sections must not contain duplicate metric_key values")
    if isinstance(default_metric, str) and metric_keys and default_metric not in metric_keys:
        errors.append("home_sections.default_ranking_metric must match one of home_sections.ranking_sections[].metric_key")


def _validate_badge_catalog(errors: list[str], payload: Any) -> None:
    catalog = _require_object(errors, "badge_catalog", payload)
    _require_positive_int(errors, "badge_catalog.version", catalog.get("version"), allow_zero=False)
    _require_string(errors, "badge_catalog.title_ko", catalog.get("title_ko"))
    _require_string(errors, "badge_catalog.description_ko", catalog.get("description_ko"))
    category_labels = _require_string_map(errors, "badge_catalog.category_labels", catalog.get("category_labels"), min_items=1)
    badges = _require_object_list(errors, "badge_catalog.badges", catalog.get("badges"), min_items=1)

    badge_ids: list[str] = []
    for index, item in enumerate(badges):
        base = f"badge_catalog.badges[{index}]"
        badge_id = item.get("badge_id")
        category = item.get("category")
        _require_string(errors, f"{base}.badge_id", badge_id)
        _require_string(errors, f"{base}.category", category)
        _require_string(errors, f"{base}.name_ko", item.get("name_ko"))
        _require_string(errors, f"{base}.short_label_ko", item.get("short_label_ko"))
        _require_string(errors, f"{base}.description_ko", item.get("description_ko"))
        _require_string(errors, f"{base}.threshold_type", item.get("threshold_type"))
        _require_number(errors, f"{base}.threshold_value", item.get("threshold_value"))
        _require_string(errors, f"{base}.icon_key", item.get("icon_key"))
        _require_nonnegative_int(errors, f"{base}.tier", item.get("tier"))
        _require_bool(errors, f"{base}.is_primary_title_candidate", item.get("is_primary_title_candidate"))
        _require_bool(errors, f"{base}.is_hidden", item.get("is_hidden"))
        _require_optional_string(errors, f"{base}.season_tag", item.get("season_tag"))
        if isinstance(badge_id, str):
            badge_ids.append(badge_id)
        if isinstance(category, str) and category_labels and category not in category_labels:
            errors.append(f"{base}.category must match badge_catalog.category_labels")

    if badge_ids and len(badge_ids) != len(set(badge_ids)):
        errors.append("badge_catalog.badges must not contain duplicate badge_id values")


def _validate_season_badges(errors: list[str], payload: Any) -> None:
    season = _require_object(errors, "season_badges", payload)
    _require_string(errors, "season_badges.season_key", season.get("season_key"))
    _require_string(errors, "season_badges.season_name_ko", season.get("season_name_ko"))
    _require_string(errors, "season_badges.unlock_rule_ko", season.get("unlock_rule_ko"))
    months = _require_object_list(errors, "season_badges.months", season.get("months"), min_items=1)

    seen_months: list[str] = []
    for index, item in enumerate(months):
        base = f"season_badges.months[{index}]"
        month = item.get("month")
        _require_string(errors, f"{base}.month", month)
        _require_string(errors, f"{base}.label_ko", item.get("label_ko"))
        _require_string(errors, f"{base}.badge_id", item.get("badge_id"))
        if isinstance(month, str):
            seen_months.append(month)
            if not _MONTH_TOKEN_RE.match(month):
                errors.append(f"{base}.month must be a two-digit month token like '03'")

    if seen_months and len(seen_months) != len(set(seen_months)):
        errors.append("season_badges.months must not contain duplicate month values")


def _validate_gallery_title_rules(errors: list[str], payload: Any) -> None:
    rules_payload = _require_object(errors, "gallery_title_rules", payload)
    _require_string(errors, "gallery_title_rules.metric_key", rules_payload.get("metric_key"))
    _require_string(errors, "gallery_title_rules.title_basis_ko", rules_payload.get("title_basis_ko"))
    _require_string(errors, "gallery_title_rules.progress_label_ko", rules_payload.get("progress_label_ko"))

    fallback_title = _require_object(errors, "gallery_title_rules.fallback_title", rules_payload.get("fallback_title"))
    _require_string(errors, "gallery_title_rules.fallback_title.badge_id", fallback_title.get("badge_id"))
    _require_string(errors, "gallery_title_rules.fallback_title.name_ko", fallback_title.get("name_ko"))
    _require_string(errors, "gallery_title_rules.fallback_title.short_label_ko", fallback_title.get("short_label_ko"))
    _require_string(errors, "gallery_title_rules.fallback_title.description_ko", fallback_title.get("description_ko"))
    _require_string(errors, "gallery_title_rules.fallback_title.icon_key", fallback_title.get("icon_key"))
    _require_nonnegative_int(errors, "gallery_title_rules.fallback_title.tier", fallback_title.get("tier"))

    rules = _require_object_list(errors, "gallery_title_rules.rules", rules_payload.get("rules"), min_items=1)
    seen_badge_ids: list[str] = []
    thresholds: list[float] = []
    for index, item in enumerate(rules):
        base = f"gallery_title_rules.rules[{index}]"
        badge_id = item.get("badge_id")
        _require_string(errors, f"{base}.badge_id", badge_id)
        _require_string(errors, f"{base}.name_ko", item.get("name_ko"))
        _require_string(errors, f"{base}.short_label_ko", item.get("short_label_ko"))
        _require_string(errors, f"{base}.description_ko", item.get("description_ko"))
        _require_string(errors, f"{base}.threshold_type", item.get("threshold_type"))
        _require_number(errors, f"{base}.threshold_value", item.get("threshold_value"))
        _require_string(errors, f"{base}.icon_key", item.get("icon_key"))
        _require_nonnegative_int(errors, f"{base}.tier", item.get("tier"))
        if isinstance(badge_id, str):
            seen_badge_ids.append(badge_id)
        threshold_value = item.get("threshold_value")
        if _is_number(threshold_value):
            thresholds.append(float(threshold_value))

    if seen_badge_ids and len(seen_badge_ids) != len(set(seen_badge_ids)):
        errors.append("gallery_title_rules.rules must not contain duplicate badge_id values")
    if thresholds and thresholds != sorted(thresholds):
        errors.append("gallery_title_rules.rules must stay sorted by threshold_value")


def _validate_profile_layout_config(errors: list[str], payload: Any) -> None:
    layout = _require_object(errors, "profile_layout_config", payload)
    _require_string_list(errors, "profile_layout_config.header_stat_keys", layout.get("header_stat_keys"), min_items=1)
    _require_string_list(errors, "profile_layout_config.section_order", layout.get("section_order"), min_items=1)
    _require_string_list(errors, "profile_layout_config.badge_category_order", layout.get("badge_category_order"), min_items=1)
    _require_positive_int(errors, "profile_layout_config.recent_unlock_limit", layout.get("recent_unlock_limit"))
    _require_positive_int(errors, "profile_layout_config.badge_preview_limit", layout.get("badge_preview_limit"))
    _require_string(errors, "profile_layout_config.next_badge_label_ko", layout.get("next_badge_label_ko"))


def _validate_badge_art_catalog(errors: list[str], payload: Any) -> None:
    catalog = _require_object(errors, "badge_art_catalog", payload)
    _require_string(errors, "badge_art_catalog.asset_root", catalog.get("asset_root"))
    _require_string(errors, "badge_art_catalog.naming_rule", catalog.get("naming_rule"))
    _require_object(errors, "badge_art_catalog.family_map", catalog.get("family_map"))
    _require_object_list(errors, "badge_art_catalog.tier_palettes", catalog.get("tier_palettes"), min_items=1)
    icons = _require_object_list(errors, "badge_art_catalog.icons", catalog.get("icons"), min_items=1)
    icon_keys: list[str] = []
    for index, item in enumerate(icons):
        base = f"badge_art_catalog.icons[{index}]"
        icon_key = item.get("icon_key")
        _require_string(errors, f"{base}.icon_key", icon_key)
        _require_string(errors, f"{base}.file_path", item.get("file_path"))
        _require_string(errors, f"{base}.family", item.get("family"))
        if item.get("tier_compatibility") is not None:
            _require_string_list(errors, f"{base}.tier_compatibility", item.get("tier_compatibility"), min_items=1)
        if item.get("badge_id_prefixes") is not None:
            _require_string_list(errors, f"{base}.badge_id_prefixes", item.get("badge_id_prefixes"))
        if isinstance(icon_key, str):
            icon_keys.append(icon_key)
    if icon_keys and len(icon_keys) != len(set(icon_keys)):
        errors.append("badge_art_catalog.icons must not contain duplicate icon_key values")


def _validate_cross_references(errors: list[str], bundle: dict[str, Any]) -> None:
    badge_catalog = bundle.get("badge_catalog", {})
    badges = badge_catalog.get("badges", []) if isinstance(badge_catalog, dict) else []
    badge_ids = {
        item.get("badge_id")
        for item in badges
        if isinstance(item, dict) and isinstance(item.get("badge_id"), str)
    }
    category_labels = badge_catalog.get("category_labels", {}) if isinstance(badge_catalog, dict) else {}

    season_badges = bundle.get("season_badges", {})
    months = season_badges.get("months", []) if isinstance(season_badges, dict) else []
    for index, item in enumerate(months):
        if not isinstance(item, dict):
            continue
        badge_id = item.get("badge_id")
        if isinstance(badge_id, str) and badge_id not in badge_ids:
            errors.append(f"season_badges.months[{index}].badge_id must reference badge_catalog.badges[].badge_id")

    gallery_rules = bundle.get("gallery_title_rules", {})
    rules = gallery_rules.get("rules", []) if isinstance(gallery_rules, dict) else []
    for index, item in enumerate(rules):
        if not isinstance(item, dict):
            continue
        badge_id = item.get("badge_id")
        if isinstance(badge_id, str) and badge_id not in badge_ids:
            errors.append(f"gallery_title_rules.rules[{index}].badge_id must reference badge_catalog.badges[].badge_id")

    profile_layout = bundle.get("profile_layout_config", {})
    category_order = profile_layout.get("badge_category_order", []) if isinstance(profile_layout, dict) else []
    for index, category in enumerate(category_order):
        if isinstance(category, str) and category not in category_labels:
            errors.append(f"profile_layout_config.badge_category_order[{index}] must exist in badge_catalog.category_labels")


def _require_object(errors: list[str], path: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return {}
    return value


def _require_object_list(errors: list[str], path: str, value: Any, *, min_items: int = 0) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    if len(value) < min_items:
        errors.append(f"{path} must contain at least {min_items} item(s)")
    items: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{path}[{index}] must be an object")
            continue
        items.append(item)
    return items


def _require_string_list(errors: list[str], path: str, value: Any, *, min_items: int = 0) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{path} must be an array of strings")
        return []
    if len(value) < min_items:
        errors.append(f"{path} must contain at least {min_items} item(s)")
    rows: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{path}[{index}] must be a string")
            continue
        rows.append(item)
    return rows


def _require_string_map(errors: list[str], path: str, value: Any, *, min_items: int = 0) -> dict[str, str]:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object of strings")
        return {}
    if len(value) < min_items:
        errors.append(f"{path} must contain at least {min_items} item(s)")
    rows: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            errors.append(f"{path} keys must be strings")
            continue
        if not isinstance(item, str):
            errors.append(f"{path}.{key} must be a string")
            continue
        rows[key] = item
    return rows


def _require_string(errors: list[str], path: str, value: Any) -> None:
    if not isinstance(value, str):
        errors.append(f"{path} must be a string")


def _require_optional_string(errors: list[str], path: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        errors.append(f"{path} must be a string or null")


def _require_bool(errors: list[str], path: str, value: Any) -> None:
    if not isinstance(value, bool):
        errors.append(f"{path} must be a boolean")


def _require_number(errors: list[str], path: str, value: Any) -> None:
    if not _is_number(value):
        errors.append(f"{path} must be a number")


def _require_positive_int(errors: list[str], path: str, value: Any, *, allow_zero: bool = False) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{path} must be an integer")
        return
    minimum = 0 if allow_zero else 1
    if value < minimum:
        errors.append(f"{path} must be >= {minimum}")


def _require_nonnegative_int(errors: list[str], path: str, value: Any) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{path} must be an integer")
        return
    if value < 0:
        errors.append(f"{path} must be >= 0")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _payload_digest(payload: Any) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _sign_bytes(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _base64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes | None:
    if not value:
        return None
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, binascii.Error):
        return None


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
