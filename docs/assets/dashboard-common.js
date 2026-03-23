const DEFAULT_MODE = "core_only";

async function safeLoadJson(path, fallback) {
  try {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) {
      return fallback;
    }
    return await response.json();
  } catch (_error) {
    return fallback;
  }
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export async function loadDashboardViews() {
  return normalizeDashboardViews(await safeLoadJson("./data/dashboard_views.json", {}));
}

export async function loadParseStatus() {
  return normalizeParseStatus(await safeLoadJson("./data/parse_status.json", {}));
}

export async function loadAuthorIndex() {
  return normalizeAuthorIndex(await safeLoadJson("./data/author_index.json", {}));
}

export async function loadAuthorProfiles() {
  return normalizeAuthorProfiles(await safeLoadJson("./data/author_profiles.json", {}));
}

export async function loadReviewQueue() {
  const payload = await safeLoadJson("./data/review_queue.json", []);
  return Array.isArray(payload) ? payload : [];
}

export async function loadAdminPreview() {
  return normalizeAdminPreview(await safeLoadJson("./data/admin_preview.json", {}));
}

export async function loadBadgeIndex() {
  return normalizeBadgeIndex(await safeLoadJson("./data/badge_index.json", {}));
}

export async function loadPublicSiteConfig() {
  return normalizePublicSiteConfig(await safeLoadJson("./data/site_config.json", {}));
}

export function normalizeDashboardViews(payload) {
  if (!isPlainObject(payload) || !isPlainObject(payload.summary)) {
    return {
      present: false,
      default_mode: DEFAULT_MODE,
      supported_modes: [DEFAULT_MODE],
      summary: {},
      gallery: {},
      rankings: { default_metric: "swim_count", metrics: {} },
      recent_records: [],
      recent_unlocks: [],
      navigation_config: { items: [] },
      home_sections: { section_order: [], ranking_sections: [] },
      site_config: {},
      ops: {},
      generated_at: "",
      visible_date_range: { start: "", end: "" },
    };
  }

  const rankings = isPlainObject(payload.rankings) ? payload.rankings : { default_metric: "swim_count", metrics: {} };
  return {
    ...payload,
    present: true,
    default_mode: payload.default_mode || DEFAULT_MODE,
    supported_modes: Array.isArray(payload.supported_modes) && payload.supported_modes.length
      ? payload.supported_modes
      : [DEFAULT_MODE],
    summary: isPlainObject(payload.summary) ? payload.summary : {},
    gallery: isPlainObject(payload.gallery) ? payload.gallery : {},
    rankings: {
      default_metric: rankings.default_metric || "swim_count",
      metrics: isPlainObject(rankings.metrics) ? rankings.metrics : {},
    },
    recent_records: Array.isArray(payload.recent_records) ? payload.recent_records : [],
    recent_unlocks: Array.isArray(payload.recent_unlocks) ? payload.recent_unlocks : [],
    navigation_config: isPlainObject(payload.navigation_config) ? payload.navigation_config : { items: [] },
    home_sections: isPlainObject(payload.home_sections) ? payload.home_sections : { section_order: [], ranking_sections: [] },
    site_config: isPlainObject(payload.site_config) ? payload.site_config : {},
    ops: isPlainObject(payload.ops) ? payload.ops : {},
    generated_at: stringOrEmpty(payload.generated_at),
    visible_date_range: normalizeDateRange(payload.visible_date_range),
  };
}

export function normalizeAuthorIndex(payload) {
  const rows = Array.isArray(payload)
    ? payload
    : (Array.isArray(payload?.authors) ? payload.authors : []);

  const authors = rows
    .filter((row) => isPlainObject(row))
    .map((row) => ({
      author: firstText(row.author, row.nickname, row.name),
      search_key: firstText(row.search_key) || firstText(row.author, row.nickname, row.name).toLowerCase(),
      latest_post_date: stringOrEmpty(row.latest_post_date),
      primary_title: isPlainObject(row.primary_title) ? row.primary_title : null,
      unlocked_badge_count: numberOrZero(row.unlocked_badge_count),
      next_badge_progress: isPlainObject(row.next_badge_progress) ? row.next_badge_progress : null,
    }))
    .filter((row) => row.author)
    .sort((left, right) => compareAuthors(left.author, right.author));

  return {
    present: authors.length > 0,
    authors,
    default_mode: payload?.default_mode || DEFAULT_MODE,
    supported_modes: Array.isArray(payload?.supported_modes) && payload.supported_modes.length
      ? payload.supported_modes
      : [DEFAULT_MODE],
    profile_layout_config: isPlainObject(payload?.profile_layout_config) ? payload.profile_layout_config : {},
  };
}

export function normalizeParseStatus(payload) {
  if (!isPlainObject(payload)) {
    return {
      present: false,
      summary: {
        total_visible_records: 0,
        parsed_count: 0,
        unparsed_count: 0,
        success_rate_pct: 0,
      },
      failure_reason_counts: {},
      parsed_rows: [],
      unparsed_rows: [],
      guidance: { official_format: "", accepted_examples: [], rules_ko: [] },
      site_config: {},
      visible_date_range: { start: "", end: "" },
      generated_at: "",
    };
  }

  return {
    present: true,
    generated_at: stringOrEmpty(payload.generated_at),
    default_mode: payload.default_mode || DEFAULT_MODE,
    supported_modes: Array.isArray(payload.supported_modes) && payload.supported_modes.length
      ? payload.supported_modes
      : [DEFAULT_MODE],
    visible_date_range: normalizeDateRange(payload.visible_date_range),
    site_config: isPlainObject(payload.site_config) ? payload.site_config : {},
    failure_reason_counts: isPlainObject(payload.failure_reason_counts) ? payload.failure_reason_counts : {},
    parsed_rows: Array.isArray(payload.parsed_rows) ? payload.parsed_rows : [],
    unparsed_rows: Array.isArray(payload.unparsed_rows) ? payload.unparsed_rows : [],
    guidance: {
      official_format: stringOrEmpty(payload.guidance?.official_format),
      accepted_examples: Array.isArray(payload.guidance?.accepted_examples) ? payload.guidance.accepted_examples : [],
      rules_ko: Array.isArray(payload.guidance?.rules_ko) ? payload.guidance.rules_ko : [],
    },
    summary: {
      total_visible_records: numberOrZero(payload.visible_record_count),
      parsed_count: numberOrZero(payload.parsed_count),
      unparsed_count: numberOrZero(payload.unparsed_count),
      success_rate_pct: numberOrZero(payload.success_rate_pct),
    },
  };
}

export function normalizeAuthorProfiles(payload) {
  const rows = Array.isArray(payload?.profiles) ? payload.profiles : [];
  return {
    present: rows.length > 0,
    generated_at: stringOrEmpty(payload?.generated_at),
    default_mode: payload?.default_mode || DEFAULT_MODE,
    supported_modes: Array.isArray(payload?.supported_modes) && payload.supported_modes.length
      ? payload.supported_modes
      : [DEFAULT_MODE],
    profile_layout_config: isPlainObject(payload?.profile_layout_config) ? payload.profile_layout_config : {},
    profiles: rows.filter((row) => isPlainObject(row)),
  };
}

export function normalizeAdminPreview(payload) {
  if (!isPlainObject(payload)) {
    return {
      present: false,
      generated_at: "",
      site_config: {},
      navigation_config: { items: [] },
      home_sections: {},
      badge_catalog_summary: {},
      gallery_preview: {},
      author_preview: [],
      profile_layout_config: {},
      season_badges: {},
      gallery_title_rules: {},
    };
  }

  return {
    present: true,
    generated_at: stringOrEmpty(payload.generated_at),
    site_config: isPlainObject(payload.site_config) ? payload.site_config : {},
    navigation_config: isPlainObject(payload.navigation_config) ? payload.navigation_config : { items: [] },
    home_sections: isPlainObject(payload.home_sections) ? payload.home_sections : {},
    badge_catalog_summary: isPlainObject(payload.badge_catalog_summary) ? payload.badge_catalog_summary : {},
    gallery_preview: isPlainObject(payload.gallery_preview) ? payload.gallery_preview : {},
    author_preview: Array.isArray(payload.author_preview) ? payload.author_preview : [],
    profile_layout_config: isPlainObject(payload.profile_layout_config) ? payload.profile_layout_config : {},
    season_badges: isPlainObject(payload.season_badges) ? payload.season_badges : {},
    gallery_title_rules: isPlainObject(payload.gallery_title_rules) ? payload.gallery_title_rules : {},
    source_paths: isPlainObject(payload.source_paths) ? payload.source_paths : {},
  };
}

export function normalizeBadgeIndex(payload) {
  if (!isPlainObject(payload)) {
    return { present: false, badges: [], badge_count_by_category: {}, gallery_titles: [] };
  }
  return {
    present: true,
    generated_at: stringOrEmpty(payload.generated_at),
    category_labels: isPlainObject(payload.category_labels) ? payload.category_labels : {},
    badge_count: numberOrZero(payload.badge_count),
    badge_count_by_category: isPlainObject(payload.badge_count_by_category) ? payload.badge_count_by_category : {},
    gallery_titles: Array.isArray(payload.gallery_titles) ? payload.gallery_titles : [],
    badges: Array.isArray(payload.badges) ? payload.badges : [],
    season_badges: isPlainObject(payload.season_badges) ? payload.season_badges : {},
  };
}

export function normalizePublicSiteConfig(payload) {
  if (!isPlainObject(payload)) {
    return { present: false, site_config: {}, navigation_config: { items: [] }, home_sections: {}, badge_catalog: {}, season_badges: {}, gallery_title_rules: {}, profile_layout_config: {}, badge_art_catalog: {} };
  }
  const source = isPlainObject(payload.site_config) && isPlainObject(payload.site_config.site_config)
    ? payload.site_config
    : payload;
  return {
    present: true,
    generated_at: stringOrEmpty(source.generated_at || payload.generated_at),
    site_config: isPlainObject(source.site_config) ? source.site_config : {},
    navigation_config: isPlainObject(source.navigation_config) ? source.navigation_config : { items: [] },
    home_sections: isPlainObject(source.home_sections) ? source.home_sections : {},
    badge_catalog: isPlainObject(source.badge_catalog) ? source.badge_catalog : {},
    season_badges: isPlainObject(source.season_badges) ? source.season_badges : {},
    gallery_title_rules: isPlainObject(source.gallery_title_rules) ? source.gallery_title_rules : {},
    profile_layout_config: isPlainObject(source.profile_layout_config) ? source.profile_layout_config : {},
    badge_art_catalog: isPlainObject(source.badge_art_catalog) ? source.badge_art_catalog : {},
  };
}

export function mergeSiteBundles(...bundles) {
  const source = bundles.find((item) => item && item.present) || {};
  return {
    generated_at: stringOrEmpty(source.generated_at),
    site_config: firstObject(...bundles.map((item) => item?.site_config)),
    navigation_config: firstObject(...bundles.map((item) => item?.navigation_config), { items: [] }),
    home_sections: firstObject(...bundles.map((item) => item?.home_sections), {}),
    badge_catalog: firstObject(...bundles.map((item) => item?.badge_catalog), {}),
    season_badges: firstObject(...bundles.map((item) => item?.season_badges), {}),
    gallery_title_rules: firstObject(...bundles.map((item) => item?.gallery_title_rules), {}),
    profile_layout_config: firstObject(...bundles.map((item) => item?.profile_layout_config), {}),
    badge_art_catalog: firstObject(...bundles.map((item) => item?.badge_art_catalog), {}),
  };
}

export function resolveAssetPath(filePath) {
  const raw = stringOrEmpty(filePath);
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("./")) return raw;
  if (raw.startsWith("docs/")) return `./${raw.slice(5)}`;
  return `./${raw.replace(/^\/+/, "")}`;
}

export function findBadgeAsset(siteBundle, iconKey) {
  const key = stringOrEmpty(iconKey);
  const icons = Array.isArray(siteBundle?.badge_art_catalog?.icons) ? siteBundle.badge_art_catalog.icons : [];
  return icons.find((item) => stringOrEmpty(item?.icon_key) === key) || null;
}

export function renderBadgeIcon(siteBundle, iconKey, alt, className = "badge-icon") {
  const asset = findBadgeAsset(siteBundle, iconKey);
  const path = resolveAssetPath(asset?.file_path);
  if (!path) return "";
  return `<img class="${escapeHtml(className)}" src="${escapeHtml(path)}" alt="${escapeHtml(alt || iconKey || "badge")}">`;
}

export function categoryLabelFromBundle(siteBundle, category) {
  const labels = siteBundle?.badge_catalog?.category_labels || {};
  return stringOrEmpty(labels?.[category]) || {
    attendance: "출석",
    distance: "거리",
    time: "시간",
    efficiency: "효율",
    growth: "성장",
    season: "시즌",
    gallery: "갤 전체",
    fun: "보너스",
  }[category] || stringOrEmpty(category);
}

export function getMetricGroup(dashboardViews, metricKey) {
  const metrics = dashboardViews?.rankings?.metrics || {};
  const rawGroup = isPlainObject(metrics[metricKey]) ? metrics[metricKey] : {};
  const rows = Array.isArray(rawGroup.rows) ? rawGroup.rows.filter((row) => isPlainObject(row)) : [];
  const rankRows = rows
    .filter((row) => Number.isFinite(Number(row.rank)))
    .sort((left, right) => Number(left.rank) - Number(right.rank));
  const fallbackRows = rankRows.length ? rankRows : rows;
  const top3 = normalizeTopThree(rawGroup, fallbackRows);
  const ranks4To20 = normalizeRanksFourToTwenty(rawGroup, fallbackRows);

  return {
    metric_key: rawGroup.metric_key || metricKey,
    label_ko: rawGroup.label_ko || metricLabel(metricKey),
    description_ko: rawGroup.description_ko || "",
    top3,
    ranks_4_to_20: ranks4To20,
    rows,
    total_ranked_rows: Number(rawGroup.total_ranked_rows || rawGroup.row_count || rows.length || top3.length + ranks4To20.length || 0),
  };
}

export function metricLabel(metricKey) {
  return {
    swim_count: "참여횟수",
    total_distance_m: "거리",
    total_seconds: "시간",
    distance_per_hour_m: "시간당 거리",
    growth_swim_count: "성장: 횟수",
    growth_distance_m: "성장: 거리",
    growth_total_seconds: "성장: 시간",
  }[metricKey] || metricKey;
}

export function buildDesktopUrl() {
  return "./index.html?desktop=1";
}

export function buildMobileUrl() {
  return "./mobile.html";
}

export function buildProfileUrl(author) {
  return `./profile.html?author=${encodeURIComponent(author || "")}`;
}

export function compareAuthors(left, right) {
  return String(left || "").localeCompare(String(right || ""), "ko", { sensitivity: "base" });
}

export function findAuthorMatch(authorIndex, query) {
  const keyword = String(query || "").trim();
  if (!keyword) return "";
  const rows = Array.isArray(authorIndex?.authors) ? authorIndex.authors : [];
  const exact = rows.find((row) => row.author === keyword || row.search_key === keyword.toLowerCase());
  if (exact) return exact.author;
  const partial = rows.find((row) => row.author.includes(keyword) || row.search_key.includes(keyword.toLowerCase()));
  return partial ? partial.author : keyword;
}

export function getAuthorSuggestions(authorIndex) {
  return Array.isArray(authorIndex?.authors) ? authorIndex.authors : [];
}

export function getAuthorProfile(authorProfiles, author) {
  const keyword = String(author || "").trim();
  if (!keyword) return null;
  const rows = Array.isArray(authorProfiles?.profiles) ? authorProfiles.profiles : [];
  return rows.find((row) => row.author === keyword || row.search_key === keyword.toLowerCase()) || null;
}

export function formatInt(value) {
  return new Intl.NumberFormat("ko-KR").format(numberOrZero(value));
}

export function formatDistance(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return "0m";
  if (Math.abs(numeric) >= 1000) {
    const km = numeric / 1000;
    const rounded = Math.abs(km - Math.round(km)) < 0.001 ? String(Math.round(km)) : km.toFixed(1);
    return `${rounded}km`;
  }
  return `${Math.round(numeric)}m`;
}

export function formatSignedDistance(value) {
  const numeric = Number(value || 0);
  if (numeric > 0) return `+${formatDistance(numeric)}`;
  if (numeric < 0) return `-${formatDistance(Math.abs(numeric))}`;
  return "0m";
}

export function formatDurationLabel(totalSeconds) {
  const seconds = Math.max(0, Math.round(Number(totalSeconds || 0)));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remain = seconds % 60;
  if (hours > 0) {
    return remain > 0 ? `${hours}시간 ${minutes}분 ${remain}초` : `${hours}시간 ${minutes}분`;
  }
  if (remain > 0) {
    return `${minutes}분 ${remain}초`;
  }
  return `${minutes}분`;
}

export function formatSignedDuration(totalSeconds) {
  const numeric = Number(totalSeconds || 0);
  if (numeric > 0) return `+${formatDurationLabel(numeric)}`;
  if (numeric < 0) return `-${formatDurationLabel(Math.abs(numeric))}`;
  return "0분";
}

export function formatDistancePerHour(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "기록 없음";
  return `${Math.round(numeric)}m/h`;
}

export function formatSignedInt(value) {
  const numeric = Math.round(Number(value || 0));
  if (numeric > 0) return `+${numeric}`;
  return String(numeric);
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function getVisibleDateRangeLabel(range) {
  const start = stringOrEmpty(range?.start);
  const end = stringOrEmpty(range?.end);
  if (!start && !end) return "집계 기간 준비 중";
  if (start && end) return `${start} ~ ${end}`;
  return start || end;
}

export function sliceTopThree(group) {
  return Array.isArray(group?.top3) ? group.top3 : [];
}

export function sliceRankFourToTwenty(group) {
  return Array.isArray(group?.ranks_4_to_20) ? group.ranks_4_to_20 : [];
}

export function sourceLabel(source) {
  const labels = {
    title_format: "제목 양식",
    manual_review: "수동 승인",
    manual_patch: "수동 보정",
    none: "미분류",
  };
  return labels[source] || String(source || "-");
}

export function downloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function firstObject(...values) {
  for (const value of values) {
    if (isPlainObject(value)) return value;
  }
  return {};
}

function normalizeTopThree(group, fallbackRows) {
  if (Array.isArray(group?.top3) && group.top3.length > 0) {
    return group.top3;
  }

  const ranked = fallbackRows.filter((row) => {
    const rank = Number(row.rank);
    return Number.isFinite(rank) ? rank >= 1 && rank <= 3 : true;
  });

  if (ranked.length > 0) {
    return ranked.slice(0, 3);
  }

  return fallbackRows.slice(0, 3);
}

function normalizeRanksFourToTwenty(group, fallbackRows) {
  if (Array.isArray(group?.ranks_4_to_20) && group.ranks_4_to_20.length > 0) {
    return group.ranks_4_to_20;
  }
  if (Array.isArray(group?.rank_4_to_20) && group.rank_4_to_20.length > 0) {
    return group.rank_4_to_20;
  }

  const ranked = fallbackRows.filter((row) => {
    const rank = Number(row.rank);
    return Number.isFinite(rank) ? rank >= 4 && rank <= 20 : false;
  });

  if (ranked.length > 0) {
    return ranked;
  }

  return fallbackRows.slice(3, 20).map((row, index) => ({
    ...row,
    rank: Number.isFinite(Number(row.rank)) ? Number(row.rank) : index + 4,
  }));
}

function normalizeDateRange(value) {
  return {
    start: stringOrEmpty(value?.start),
    end: stringOrEmpty(value?.end),
  };
}

function firstText(...values) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

function stringOrEmpty(value) {
  return typeof value === 'string' ? value : '';
}

function numberOrZero(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}
