from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from swimdash.config import (
    BADGE_ART_CATALOG_FILE,
    BADGE_CATALOG_FILE,
    GALLERY_TITLE_RULES_FILE,
    HOME_SECTIONS_FILE,
    NAVIGATION_CONFIG_FILE,
    PROFILE_LAYOUT_CONFIG_FILE,
    SEASON_BADGES_FILE,
    SITE_CONFIG_FILE,
)
from swimdash.io_utils import read_json

ADMIN_CONFIG_PATHS = {
    "site_config": SITE_CONFIG_FILE,
    "navigation_config": NAVIGATION_CONFIG_FILE,
    "home_sections": HOME_SECTIONS_FILE,
    "badge_catalog": BADGE_CATALOG_FILE,
    "season_badges": SEASON_BADGES_FILE,
    "gallery_title_rules": GALLERY_TITLE_RULES_FILE,
    "profile_layout_config": PROFILE_LAYOUT_CONFIG_FILE,
    "badge_art_catalog": BADGE_ART_CATALOG_FILE,
}


def load_admin_config_bundle() -> dict:
    bundle: dict[str, object] = {}
    missing: list[str] = []

    for key, path in ADMIN_CONFIG_PATHS.items():
        payload = read_json(path, default=None)
        if payload is None:
            missing.append(f"{key}={path}")
            continue
        bundle[key] = deepcopy(payload)

    if missing:
        joined = ", ".join(missing)
        raise FileNotFoundError(f"Missing admin config files: {joined}")

    return bundle


def admin_config_source_paths() -> dict[str, str]:
    return {key: _posix_path(path) for key, path in ADMIN_CONFIG_PATHS.items()}


def build_public_site_config_payload(*, bundle: dict | None = None, generated_at: str = "") -> dict:
    source = deepcopy(bundle or load_admin_config_bundle())
    payload = {
        "generated_at": generated_at,
        "site_config": source["site_config"],
        "navigation_config": source["navigation_config"],
        "home_sections": source["home_sections"],
        "badge_catalog": source["badge_catalog"],
        "season_badges": source["season_badges"],
        "gallery_title_rules": source["gallery_title_rules"],
        "profile_layout_config": source["profile_layout_config"],
        "badge_art_catalog": source["badge_art_catalog"],
    }

    return payload


def _posix_path(path: Path) -> str:
    return path.as_posix()
