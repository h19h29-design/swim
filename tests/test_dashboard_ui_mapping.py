from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_dashboard_common_contracts_work_for_dashboard_and_profile_flows():
    project_root = Path(__file__).resolve().parents[1]
    module_path = project_root / "docs" / "assets" / "dashboard-common.js"

    script = f"""
import {{ pathToFileURL }} from 'url';

const modulePath = pathToFileURL({json.dumps(str(module_path))}).href;
const {{
  normalizeDashboardViews,
  normalizeAuthorIndex,
  normalizeParseStatus,
  normalizePublicSiteConfig,
  mergeSiteBundles,
  findAuthorMatch,
  buildProfileUrl,
  getMetricGroup,
}} = await import(modulePath);

const dashboard = normalizeDashboardViews({{
  generated_at: "2026-03-14 09:00:00 UTC",
  default_mode: "core_only",
  supported_modes: ["core_only"],
  visible_date_range: {{ start: "2026-03-01", end: "2026-03-14" }},
  summary: {{
    swim_count: 12,
    total_distance_m: 18500,
    total_seconds: 25200,
    active_authors: 5,
    has_zero_visible_included_rows: false,
  }},
  gallery: {{
    current_title: {{ name_ko: "대형 파도", short_label_ko: "10km" }},
    next_title_target: {{ name_ko: "바다 개방", remaining_value_text_ko: "15km 남음" }},
    progress: {{ current_value_text_ko: "10km", progress_ratio: 0.4 }},
  }},
  rankings: {{
    default_metric: "swim_count",
    metrics: {{
      swim_count: {{
        metric_key: "swim_count",
        label_ko: "참여횟수",
        description_ko: "가장 꾸준한 닉네임",
        top3: [{{
          rank: 1,
          author: "NTHNG",
          metric_value_text_ko: "7회",
          secondary_text_ko: "7회 · 12km",
          primary_title: {{ short_label_ko: "출석왕" }},
          badge_preview: ["첫 입수", "꾸준러"],
        }}],
        ranks_4_to_20: [{{
          rank: 4,
          author: "BlueFin",
          metric_value_text_ko: "3회",
          secondary_text_ko: "3회 · 4.5km",
          primary_title: {{ short_label_ko: "레인 발도장" }},
        }}],
      }},
    }},
  }},
  recent_records: [{{
    author: "NTHNG",
    post_date: "2026-03-14",
    distance_m: 1500,
    total_seconds: 2100,
    total_time_text: "35:00",
    source: "text_format",
  }}],
  recent_unlocks: [{{ name_ko: "첫 입수", category: "attendance" }}],
  navigation_config: {{
    items: [{{ label_ko: "배지 갤러리", href: "./badge-gallery.html", visible: true }}],
  }},
  home_sections: {{
    section_order: ["hero", "summary_kpis", "rankings"],
    ranking_sections: [{{ metric_key: "swim_count", label_ko: "참여횟수" }}],
  }},
  site_config: {{
    site_title_ko: "수영 스티커북",
    hero: {{ headline_ko: "붙이고 모으는 수영 시즌 보드" }},
  }},
}});

if (!dashboard.present) {{
  throw new Error("dashboard payload should be normalized as present");
}}
if (dashboard.summary.swim_count !== 12) {{
  throw new Error("summary swim_count should survive normalization");
}}
if (dashboard.rankings.metrics.swim_count.top3[0].author !== "NTHNG") {{
  throw new Error("top3 rows should survive normalization");
}}

const legacyGroup = getMetricGroup({{
  rankings: {{
    metrics: {{
      swim_count: {{
        metric_key: "swim_count",
        label_ko: "참여횟수",
        rows: [
          {{ rank: 1, author: "A", metric_value_text_ko: "10회" }},
          {{ rank: 2, author: "B", metric_value_text_ko: "9회" }},
          {{ rank: 3, author: "C", metric_value_text_ko: "8회" }},
          {{ rank: 4, author: "D", metric_value_text_ko: "7회" }},
          {{ rank: 5, author: "E", metric_value_text_ko: "6회" }},
        ],
      }},
    }},
  }},
}}, "swim_count");

if (legacyGroup.top3.length !== 3 || legacyGroup.ranks_4_to_20.length !== 2) {{
  throw new Error("legacy ranking rows should backfill top3 and 4-20 slices");
}}
if (legacyGroup.ranks_4_to_20[0].author !== "D") {{
  throw new Error("rank 4 should be the first fallback rank row");
}}

const parseStatus = normalizeParseStatus({{
  generated_at: "2026-03-16 01:00:00 UTC",
  visible_date_range: {{ start: "2026-03-01", end: "2026-03-16" }},
  visible_record_count: 10,
  parsed_count: 4,
  unparsed_count: 6,
  success_rate_pct: 40,
  failure_reason_counts: {{ TITLE_FORMAT_MISSING: 5, TITLE_FORMAT_INVALID: 1 }},
  parsed_rows: [{{ author: "A", title: "1500 / 42:30" }}],
  unparsed_rows: [{{ author: "B", title: "오늘의 수영", reason_code: "TITLE_FORMAT_MISSING" }}],
  guidance: {{ official_format: "1500 / 42:30", accepted_examples: ["1500 / 42:30"], rules_ko: ["게시글 제목만 파싱합니다."] }},
}});

if (!parseStatus.present) {{
  throw new Error("parse status payload should normalize as present");
}}
if (parseStatus.summary.parsed_count !== 4 || parseStatus.summary.unparsed_count !== 6) {{
  throw new Error("parse status summary counts should survive normalization");
}}
if (parseStatus.unparsed_rows[0].reason_code !== "TITLE_FORMAT_MISSING") {{
  throw new Error("parse status failure rows should survive normalization");
}}

const authorIndex = normalizeAuthorIndex({{
  authors: [
    {{ author: "NTHNG", latest_post_date: "2026-03-14" }},
    {{ nickname: "BlueFin" }},
  ],
}});

if (!authorIndex.present || authorIndex.authors.length !== 2) {{
  throw new Error("author index should normalize authors array");
}}
if (findAuthorMatch(authorIndex, "Blue") !== "BlueFin") {{
  throw new Error("partial nickname should resolve to the matching author");
}}
if (findAuthorMatch(authorIndex, "Unknown") !== "Unknown") {{
  throw new Error("unknown nickname should fall back to the raw query");
}}

const merged = mergeSiteBundles(
  {{
    present: true,
    site_config: {{ site_title_ko: "수영 스티커북", hero: {{ headline_ko: "공개 설정" }} }},
    navigation_config: {{ items: [{{ label_ko: "메인" }}] }},
  }},
  {{
    present: true,
    home_sections: {{ section_order: ["hero", "rankings"] }},
    badge_catalog: {{ badges: [{{ badge_id: "att_01" }}] }},
  }},
);

if (merged.site_config.site_title_ko !== "수영 스티커북") {{
  throw new Error("mergeSiteBundles should keep the first present site config");
}}
if (merged.home_sections.section_order.length !== 2) {{
  throw new Error("mergeSiteBundles should merge home sections from later bundles");
}}
if (buildProfileUrl("NTH NG") !== "./profile.html?author=NTH%20NG") {{
  throw new Error("profile URLs should URL-encode the author nickname");
}}

const nestedSiteConfig = normalizePublicSiteConfig({{
  generated_at: "2026-03-17 12:00:00 KST",
  site_config: {{
    site_config: {{
      site_title_ko: "수영 스티커북",
      hero: {{ headline_ko: "중첩된 설정도 읽기" }},
    }},
    navigation_config: {{ items: [{{ label_ko: "메인" }}] }},
    badge_art_catalog: {{ icons: [{{ icon_key: "custom.wave_gold" }}] }},
  }},
}});

if (nestedSiteConfig.site_config.site_title_ko !== "수영 스티커북") {{
  throw new Error("normalizePublicSiteConfig should unwrap nested admin bundle payloads");
}}
if (nestedSiteConfig.navigation_config.items.length !== 1) {{
  throw new Error("nested navigation_config should survive normalization");
}}
if ((nestedSiteConfig.badge_art_catalog.icons || []).length !== 1) {{
  throw new Error("nested badge_art_catalog should survive normalization");
}}
"""

    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_admin_and_parse_status_modules_import_cleanly():
    project_root = Path(__file__).resolve().parents[1]
    admin_module = project_root / "docs" / "assets" / "admin.js"
    parse_status_module = project_root / "docs" / "assets" / "parse-status.js"

    script = f"""
import {{ pathToFileURL }} from 'url';

await import(pathToFileURL({json.dumps(str(admin_module))}).href);
await import(pathToFileURL({json.dumps(str(parse_status_module))}).href);
"""

    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
