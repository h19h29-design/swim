from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

BASE_URL = "https://gall.dcinside.com"
LIST_PATH = "/mini/board/lists/"
BOARD_ID = "swimmingdiary"
DIARY_SUBJECT = "\uc77c\uae30"

DEFAULT_TIMEOUT = 15
DEFAULT_RATE_LIMIT_SEC = 0.45
DEFAULT_RETRY_TOTAL = 4
DEFAULT_RETRY_BACKOFF = 0.6
DEFAULT_INCREMENTAL_PAGES = 12
DEFAULT_LOOKBACK_DAYS = 3
DEFAULT_EDITABLE_POST_DAYS = 3
MARCH_CORRECTION_WEEK_END = date(2026, 3, 15)
MARCH_CORRECTION_RECENT_PAGES = 80
DASHBOARD_DATE_FLOOR = date(2026, 3, 1)

DATA_DIR = Path("docs/data")
OPS_DATA_DIR = Path("data")
ADMIN_DATA_DIR = OPS_DATA_DIR / "admin"
LOG_DIR = Path("logs")
BADGE_ASSET_DIR = Path("docs/assets/badges")
CUSTOM_BADGE_ASSET_DIR = BADGE_ASSET_DIR / "custom"
ADMIN_CHANGE_LOG_FILE = LOG_DIR / "admin_changes.log"
ADMIN_REBUILD_COMMAND = "python -m swimdash rebuild"
ERROR_LOG_FILE = LOG_DIR / "crawler_errors.log"

RECORDS_FILE = DATA_DIR / "records.json"
SUMMARY_FILE = DATA_DIR / "summary.json"
MONTHLY_FILE = DATA_DIR / "monthly.json"
LEADERBOARD_FILE = DATA_DIR / "leaderboard.json"
REVIEW_QUEUE_FILE = DATA_DIR / "review_queue.json"
PARSE_STATUS_FILE = DATA_DIR / "parse_status.json"
AUTHOR_INDEX_FILE = DATA_DIR / "author_index.json"
AUTHOR_PROFILES_FILE = DATA_DIR / "author_profiles.json"
DASHBOARD_VIEWS_FILE = DATA_DIR / "dashboard_views.json"
BADGE_INDEX_FILE = DATA_DIR / "badge_index.json"
ADMIN_PREVIEW_FILE = DATA_DIR / "admin_preview.json"
PUBLIC_SITE_CONFIG_FILE = DATA_DIR / "site_config.json"
PUBLIC_BADGE_ART_CATALOG_FILE = DATA_DIR / "badge_art_catalog.json"
MANUAL_REVIEW_OVERRIDE_FILE = OPS_DATA_DIR / "manual_review_overrides.csv"
SITE_CONFIG_FILE = ADMIN_DATA_DIR / "site_config.json"
NAVIGATION_CONFIG_FILE = ADMIN_DATA_DIR / "navigation_config.json"
HOME_SECTIONS_FILE = ADMIN_DATA_DIR / "home_sections.json"
BADGE_CATALOG_FILE = ADMIN_DATA_DIR / "badge_catalog.json"
SEASON_BADGES_FILE = ADMIN_DATA_DIR / "season_badges.json"
GALLERY_TITLE_RULES_FILE = ADMIN_DATA_DIR / "gallery_title_rules.json"
PROFILE_LAYOUT_CONFIG_FILE = ADMIN_DATA_DIR / "profile_layout_config.json"
BADGE_ART_CATALOG_FILE = ADMIN_DATA_DIR / "badge_art_catalog.json"


@dataclass(frozen=True, slots=True)
class IncrementalSyncPolicy:
    as_of: date
    policy_name: str
    lookback_days: int
    recent_pages: int
    crawl_until_stop_date: bool
    editable_window_start: date
    editable_window_end: date
    stop_before_date: date
    dashboard_date_floor: date
    correction_week_end: date


def resolve_incremental_sync_policy(
    *,
    as_of: date | None = None,
    explicit_lookback_days: int | None = None,
    explicit_recent_pages: int | None = None,
    force_dashboard_floor: bool = False,
) -> IncrementalSyncPolicy:
    today = as_of or date.today()
    if force_dashboard_floor:
        editable_window_start = DASHBOARD_DATE_FLOOR
        lookback_days = max(
            DEFAULT_LOOKBACK_DAYS,
            (today - DASHBOARD_DATE_FLOOR).days + 1,
        )
        recent_pages = MARCH_CORRECTION_RECENT_PAGES
        policy_name = "dashboard_floor_window"
        crawl_until_stop_date = True
    else:
        use_march_catchup = (
            explicit_lookback_days is None
            and explicit_recent_pages is None
            and today <= MARCH_CORRECTION_WEEK_END
        )

        if use_march_catchup:
            editable_window_start = DASHBOARD_DATE_FLOOR
            lookback_days = max(
                DEFAULT_LOOKBACK_DAYS,
                (today - DASHBOARD_DATE_FLOOR).days + 1,
            )
            recent_pages = MARCH_CORRECTION_RECENT_PAGES
            policy_name = "march_correction_week"
        else:
            lookback_days = explicit_lookback_days if explicit_lookback_days is not None else DEFAULT_LOOKBACK_DAYS
            recent_pages = explicit_recent_pages if explicit_recent_pages is not None else DEFAULT_INCREMENTAL_PAGES
            editable_window_start = max(
                DASHBOARD_DATE_FLOOR,
                today - timedelta(days=max(lookback_days - 1, 0)),
            )
            if explicit_lookback_days is not None or explicit_recent_pages is not None:
                policy_name = "custom_override_window"
            else:
                policy_name = "rolling_3day_edit_window"
        crawl_until_stop_date = False

    return IncrementalSyncPolicy(
        as_of=today,
        policy_name=policy_name,
        lookback_days=lookback_days,
        recent_pages=recent_pages,
        crawl_until_stop_date=crawl_until_stop_date,
        editable_window_start=editable_window_start,
        editable_window_end=today,
        stop_before_date=editable_window_start,
        dashboard_date_floor=DASHBOARD_DATE_FLOOR,
        correction_week_end=MARCH_CORRECTION_WEEK_END,
    )


@dataclass(slots=True)
class CrawlOptions:
    mode: str
    max_pages: int | None = None
    recent_pages: int = DEFAULT_INCREMENTAL_PAGES
    rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC
    timeout: int = DEFAULT_TIMEOUT
    retries: int = DEFAULT_RETRY_TOTAL
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
