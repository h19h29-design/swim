const DEFAULT_MODE = "core_only";
const CATEGORY_PREFIX_MAP = {
  att: "attendance",
  dst: "distance",
  tim: "time",
  eff: "efficiency",
  grw: "growth",
  sea: "season",
  gal: "gallery",
  fun: "fun",
};

let badgeRenderSequence = 0;

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

export function renderBadgeIcon(siteBundle, badgeInput, alt, className = "badge-icon") {
  const badgeMeta = resolveBadgeRenderMeta(siteBundle, badgeInput);
  const label = alt || badgeMeta?.name_ko || badgeMeta?.badge_id || badgeMeta?.icon_key || badgeInput || "badge";
  const shellStyle = badgeShellInlineStyle(className);

  if (badgeMeta?.category && badgeMeta?.tier > 0) {
    return `
      <span class="${escapeHtml(className)}" style="${escapeHtml(shellStyle)}" role="img" aria-label="${escapeHtml(label)}">
        ${renderUpgradedBadgeSvg(badgeMeta.category, badgeMeta.tier, label)}
      </span>
    `;
  }

  const iconKey = badgeMeta?.icon_key || stringOrEmpty(badgeInput);
  const asset = findBadgeAsset(siteBundle, iconKey);
  const path = resolveAssetPath(asset?.file_path);
  if (!path) return "";
  return `
    <span class="${escapeHtml(className)}" style="${escapeHtml(shellStyle)}" role="img" aria-label="${escapeHtml(label)}">
      <img src="${escapeHtml(path)}" alt="${escapeHtml(label)}" style="display:block;width:100%;height:100%;object-fit:contain;">
    </span>
  `;
}

function resolveBadgeRenderMeta(siteBundle, badgeInput) {
  const fromInput = isPlainObject(badgeInput) ? badgeInput : {};
  const badgeId = stringOrEmpty(fromInput.badge_id);
  const iconKey = stringOrEmpty(fromInput.icon_key || badgeInput);
  const catalogMatch = badgeId ? findBadgeDefinition(siteBundle, badgeId) : null;
  const category = stringOrEmpty(fromInput.category)
    || stringOrEmpty(catalogMatch?.category)
    || inferCategoryFromBadgeId(badgeId)
    || inferCategoryFromIconKey(iconKey);
  const tier = Number(fromInput.tier || catalogMatch?.tier || 0);

  if (!category || !tier) {
    return iconKey ? { icon_key: iconKey } : null;
  }

  return {
    badge_id: badgeId || stringOrEmpty(catalogMatch?.badge_id),
    name_ko: stringOrEmpty(fromInput.name_ko || catalogMatch?.name_ko),
    category,
    tier,
    icon_key: iconKey || stringOrEmpty(catalogMatch?.icon_key),
  };
}

function findBadgeDefinition(siteBundle, badgeId) {
  const target = stringOrEmpty(badgeId);
  if (!target) return null;

  const badgeCatalog = Array.isArray(siteBundle?.badge_catalog?.badges) ? siteBundle.badge_catalog.badges : [];
  const fromCatalog = badgeCatalog.find((item) => stringOrEmpty(item?.badge_id) === target);
  if (fromCatalog) return fromCatalog;

  const galleryRules = Array.isArray(siteBundle?.gallery_title_rules?.rules) ? siteBundle.gallery_title_rules.rules : [];
  const fromGalleryRules = galleryRules.find((item) => stringOrEmpty(item?.badge_id) === target);
  if (fromGalleryRules) return fromGalleryRules;

  const fallbackTitle = isPlainObject(siteBundle?.gallery_title_rules?.fallback_title) ? siteBundle.gallery_title_rules.fallback_title : null;
  return stringOrEmpty(fallbackTitle?.badge_id) === target ? fallbackTitle : null;
}

function inferCategoryFromBadgeId(badgeId) {
  const match = String(badgeId || "").match(/^([a-z]{3})_/i);
  return match ? (CATEGORY_PREFIX_MAP[match[1].toLowerCase()] || "") : "";
}

function inferCategoryFromIconKey(iconKey) {
  const prefix = String(iconKey || "").split(".")[0].toLowerCase();
  return CATEGORY_PREFIX_MAP[prefix] || (prefix === "gallery_idle" ? "gallery" : "");
}

function badgeShellInlineStyle(className) {
  const normalized = stringOrEmpty(className);
  let style = "display:inline-grid;place-items:center;overflow:hidden;vertical-align:middle;line-height:0;flex:0 0 auto;";

  if (normalized === "top-card-icon") {
    style += "width:48px;height:48px;border-radius:16px;border:1px solid rgba(94,77,68,0.14);background:rgba(255,255,255,0.96);padding:6px;box-shadow:0 10px 20px rgba(52,36,30,0.10);";
  } else if (!normalized || normalized === "badge-icon") {
    style += "width:40px;height:40px;border-radius:14px;border:1px solid rgba(94,77,68,0.14);background:rgba(255,255,255,0.94);padding:6px;box-shadow:0 8px 18px rgba(52,36,30,0.08);";
  }

  return style;
}

function renderUpgradedBadgeSvg(category, tier, alt) {
  const palette = paletteForTier(tier);
  const uid = `badge-upgrade-${badgeRenderSequence++}`;
  const glowId = `${uid}-glow`;
  const shellGradientId = `${uid}-shell`;
  const accentGradientId = `${uid}-accent`;

  return `
    <svg viewBox="0 0 64 64" aria-hidden="true" focusable="false" style="display:block;width:100%;height:100%;">
      <defs>
        <linearGradient id="${shellGradientId}" x1="14" y1="8" x2="52" y2="58" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="${palette.shellA}"></stop>
          <stop offset="0.58" stop-color="${palette.shellB}"></stop>
          <stop offset="1" stop-color="${palette.shellC}"></stop>
        </linearGradient>
        <linearGradient id="${accentGradientId}" x1="20" y1="16" x2="46" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="${palette.accent}"></stop>
          <stop offset="1" stop-color="${palette.main}"></stop>
        </linearGradient>
        <filter id="${glowId}" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="${tier >= 8 ? 2.4 : tier >= 5 ? 1.8 : 1.2}" result="blur"></feGaussianBlur>
          <feMerge>
            <feMergeNode in="blur"></feMergeNode>
            <feMergeNode in="SourceGraphic"></feMergeNode>
          </feMerge>
        </filter>
      </defs>
      ${renderBadgeShell(tier, palette, shellGradientId, accentGradientId)}
      ${renderBadgeCorePlate(tier, palette)}
      ${glyphForCategory(category, tier, palette, glowId)}
      ${renderBadgeSparkles(tier, palette, accentGradientId)}
      <title>${escapeHtml(alt || "badge")}</title>
    </svg>
  `;
}

function renderBadgeShell(tier, palette, shellGradientId, accentGradientId) {
  if (tier <= 3) {
    const radius = tier === 1 ? 18 : tier === 2 ? 14 : 20;
    return `
      <rect x="4" y="4" width="56" height="56" rx="${radius}" fill="url(#${shellGradientId})" stroke="${palette.edge}" stroke-width="2.2"></rect>
      <rect x="8" y="8" width="48" height="48" rx="${Math.max(10, radius - 6)}" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="1.4"></rect>
      ${tier >= 2 ? `<path d="M14 18h8M42 14l8 4" stroke="url(#${accentGradientId})" stroke-width="3" stroke-linecap="round"></path>` : ""}
    `;
  }

  if (tier <= 6) {
    const path = tier === 4
      ? "M16 5H48L59 16V44L44 59H20L5 44V16Z"
      : tier === 5
        ? "M32 4C47.5 4 60 16.5 60 32S47.5 60 32 60 4 47.5 4 32 16.5 4 32 4Z"
        : "M32 4L47 9L59 22 54 45 32 60 10 45 5 22 17 9Z";
    const ribbon = tier >= 5
      ? `<path d="M19 46l5 12 8-6 8 6 5-12" fill="url(#${accentGradientId})" opacity="0.84"></path>`
      : "";
    return `
      <path d="${path}" fill="url(#${shellGradientId})" stroke="${palette.edge}" stroke-width="2.2"></path>
      <path d="${path}" fill="none" stroke="rgba(255,255,255,0.52)" stroke-width="1.2" transform="translate(0 1) scale(.94)" transform-origin="32 32"></path>
      ${ribbon}
    `;
  }

  if (tier <= 9) {
    const sealPath = tier === 7
      ? "M32 4L40 10L50 8L56 18L60 28L56 38L58 48L48 54L38 60L28 58L18 60L8 54L6 44L4 34L8 24L6 14L16 8L26 10Z"
      : tier === 8
        ? "M32 4L39 9L48 7L54 14L60 20L58 29L60 38L54 44L50 52L41 54L32 60L23 54L14 56L10 48L4 42L6 33L4 24L10 18L14 10L23 10Z"
        : "M32 4L40 8L49 6L55 13L60 21L57 31L60 41L54 48L49 57L39 56L32 60L25 56L15 58L10 49L4 43L7 33L4 23L10 16L15 7L24 8Z";
    return `
      <path d="${sealPath}" fill="url(#${shellGradientId})" stroke="${palette.edge}" stroke-width="2.1"></path>
      <path d="${sealPath}" fill="none" stroke="rgba(255,255,255,0.48)" stroke-width="1.2" transform="translate(0 1) scale(.94)" transform-origin="32 32"></path>
      ${tier >= 8 ? `<circle cx="32" cy="8.5" r="4.5" fill="url(#${accentGradientId})"></circle>` : ""}
    `;
  }

  return `
    <path d="M32 3L39 8L47 6L52 13L60 16L58 25L61 33L55 40L56 49L48 52L43 60L32 56L21 60L16 52L8 49L9 40L3 33L6 25L4 16L12 13L17 6L25 8Z" fill="url(#${shellGradientId})" stroke="${palette.edge}" stroke-width="2"></path>
    <path d="M32 4L39 9L47 7L52 14L59 17L57 25L60 33L54 39L55 48L47 51L42 58L32 55L22 58L17 51L9 48L10 39L4 33L7 25L5 17L12 14L17 7L25 9Z" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="1.1"></path>
    <path d="M22 10l3-5 7 5 7-5 3 5 8 2-4 6H18l-4-6z" fill="url(#${accentGradientId})" opacity="0.94"></path>
  `;
}

function renderBadgeCorePlate(tier, palette) {
  const outer = tier >= 8 ? 18 : tier >= 5 ? 17 : 16;
  const inner = tier >= 8 ? 13 : tier >= 5 ? 12 : 11;
  return `
    <circle cx="32" cy="32" r="${outer + (tier >= 5 ? 2 : 0)}" fill="${palette.soft}" opacity="0.96"></circle>
    ${tier >= 5 ? `<circle cx="32" cy="32" r="${outer + 4}" fill="none" stroke="${palette.accent}" stroke-width="1.4" opacity="0.42"></circle>` : ""}
    <circle cx="32" cy="32" r="${outer}" fill="white" opacity="0.96"></circle>
    <circle cx="32" cy="32" r="${inner}" fill="${palette.tint}" opacity="0.72"></circle>
  `;
}

function renderBadgeSparkles(tier, palette, accentGradientId) {
  if (tier < 5) return "";
  const sparkles = tier >= 10
    ? `<path d="M15 18l1.5 3.5 3.8.4-2.8 2.5.8 3.7-3.3-1.8-3.3 1.8.8-3.7-2.8-2.5 3.8-.4z" fill="${palette.accent}" opacity="0.92"></path>
       <path d="M49 42l1.3 3 3.3.4-2.4 2.1.7 3.2-2.9-1.6-2.9 1.6.7-3.2-2.4-2.1 3.3-.4z" fill="url(#${accentGradientId})" opacity="0.92"></path>`
    : tier >= 7
      ? `<circle cx="16" cy="18" r="2.2" fill="${palette.accent}" opacity="0.86"></circle>
         <circle cx="48" cy="46" r="2.2" fill="url(#${accentGradientId})" opacity="0.86"></circle>`
      : `<circle cx="48" cy="18" r="1.8" fill="${palette.accent}" opacity="0.78"></circle>`;
  return `<g>${sparkles}</g>`;
}

function paletteForTier(tier) {
  if (tier <= 3) {
    return {
      main: "#d06f4c",
      accent: "#ffd966",
      strong: "#9e5538",
      tint: "#fff0df",
      soft: "#fff7ef",
      shellA: "#fff1e5",
      shellB: "#ffd7b5",
      shellC: "#ffb38f",
      edge: "rgba(135,87,61,0.42)",
    };
  }
  if (tier <= 6) {
    return {
      main: "#2f8f83",
      accent: "#7cb7ff",
      strong: "#21606d",
      tint: "#eafffb",
      soft: "#f4fffd",
      shellA: "#ecfffb",
      shellB: "#bfeee6",
      shellC: "#86d7c9",
      edge: "rgba(45,105,110,0.42)",
    };
  }
  if (tier <= 9) {
    return {
      main: "#b2741b",
      accent: "#ffb347",
      strong: "#8b5709",
      tint: "#fff4d7",
      soft: "#fffaf0",
      shellA: "#fff7e4",
      shellB: "#ffe28d",
      shellC: "#ffb56b",
      edge: "rgba(139,87,9,0.42)",
    };
  }
  return {
    main: "#d55d68",
    accent: "#83d6c9",
    strong: "#6b5ac9",
    tint: "#fff0f4",
    soft: "#fff8fb",
    shellA: "#fff3f5",
    shellB: "#ffd1bf",
    shellC: "#9bc6ff",
    edge: "rgba(107,90,201,0.42)",
  };
}

function glyphForCategory(category, tier, p, glowId) {
  switch (category) {
    case "attendance":
      return glyphAttendance(tier, p, glowId);
    case "distance":
      return glyphDistance(tier, p, glowId);
    case "time":
      return glyphTime(tier, p, glowId);
    case "efficiency":
      return glyphEfficiency(tier, p, glowId);
    case "growth":
      return glyphGrowth(tier, p, glowId);
    case "season":
      return glyphSeason(tier, p, glowId);
    case "gallery":
      return glyphGallery(tier, p, glowId);
    case "fun":
      return glyphFun(tier, p, glowId);
    default:
      return `<path d="M32 18l4.5 9.2 10.2 1-7.3 6.4 1.9 10.2-9.3-4.9-9.3 4.9 1.9-10.2-7.3-6.4 10.2-1z" fill="${p.accent}" stroke="${p.main}" stroke-width="2.2"></path>`;
  }
}

function glyphAttendance(tier, p, glowId) {
  if (tier <= 1) return `<path d="M26 32l4 4 8-10" fill="none" stroke="${p.main}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>`;
  if (tier === 2) return `<rect x="22" y="22" width="20" height="20" rx="6" fill="white" stroke="${p.main}" stroke-width="2.4"></rect><circle cx="27" cy="32" r="2" fill="${p.accent}"></circle><path d="M30 32l3 3 6-7" fill="none" stroke="${p.main}" stroke-width="3.3" stroke-linecap="round" stroke-linejoin="round"></path>`;
  if (tier === 3) return `<rect x="21" y="16" width="22" height="28" rx="7" fill="white" stroke="${p.main}" stroke-width="2.3"></rect><rect x="25" y="13" width="4" height="7" rx="2" fill="${p.accent}"></rect><rect x="35" y="13" width="4" height="7" rx="2" fill="${p.accent}"></rect><path d="M25.5 31.5l4 4 8-10" fill="none" stroke="${p.main}" stroke-width="3.3" stroke-linecap="round" stroke-linejoin="round"></path>`;
  if (tier === 4) return `<rect x="23" y="15" width="18" height="30" rx="6" fill="white" stroke="${p.main}" stroke-width="2.4"></rect><rect x="27" y="12" width="10" height="5" rx="2.5" fill="${p.accent}"></rect><path d="M27 25h10M27 32h10M27 39h10" stroke="${p.main}" stroke-width="2.6" stroke-linecap="round"></path><path d="M39 36l3.5 4.5 5.5-7.5" fill="none" stroke="${p.accent}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`;
  if (tier === 5) return `<rect x="23" y="17" width="18" height="24" rx="6" fill="white" stroke="${p.main}" stroke-width="2.4"></rect><circle cx="41.5" cy="39.5" r="7.5" fill="${p.accent}" filter="url(#${glowId})"></circle><path d="M27 26h10M27 32h10" stroke="${p.main}" stroke-width="2.6" stroke-linecap="round"></path><path d="M39 39.5l2.4 2.8 4.5-5.3" fill="none" stroke="white" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"></path>`;
  if (tier === 6) return `<circle cx="32" cy="28" r="10" fill="white" stroke="${p.main}" stroke-width="2.4"></circle><path d="M27 28l4 4 7-8" fill="none" stroke="${p.main}" stroke-width="3.3" stroke-linecap="round" stroke-linejoin="round"></path><path d="M25 37.5l-4 11 7-2.5 3 5.5 4-13.5" fill="${p.accent}"></path><path d="M39 37.5l4 11-7-2.5-3 5.5-4-13.5" fill="${p.main}" opacity="0.94"></path>`;
  if (tier === 7) return `<path d="M18 37c2.6 7 7 11.4 14 14.5" fill="none" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path><path d="M46 37c-2.6 7-7 11.4-14 14.5" fill="none" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path><circle cx="32" cy="28" r="10" fill="white" stroke="${p.main}" stroke-width="2.4"></circle><path d="M27 28l4 4 7-8" fill="none" stroke="${p.main}" stroke-width="3.3" stroke-linecap="round" stroke-linejoin="round"></path>`;
  return `<path d="M18 38c2.8 7.2 7.2 11.8 14 14.8" fill="none" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path><path d="M46 38c-2.8 7.2-7.2 11.8-14 14.8" fill="none" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path><circle cx="32" cy="29" r="10" fill="white" stroke="${p.main}" stroke-width="2.4"></circle><path d="M27 29l4 4 7-8" fill="none" stroke="${p.main}" stroke-width="3.3" stroke-linecap="round" stroke-linejoin="round"></path><path d="M24 17l3-5 5 4 5-4 3 5 6 1-3 5H21l-3-5z" fill="${p.accent}" filter="url(#${glowId})"></path>`;
}

function glyphDistance(tier, p, glowId) {
  if (tier <= 1) return `<path d="M18 38c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.main}" stroke-width="4" stroke-linecap="round"></path>`;
  if (tier === 2) return `<path d="M18 40c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.main}" stroke-width="4" stroke-linecap="round"></path><path d="M22 30l16-10" fill="none" stroke="${p.accent}" stroke-width="4" stroke-linecap="round"></path><path d="M35 18h9v9" fill="none" stroke="${p.accent}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>`;
  if (tier === 3) return `<path d="M16 40c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.main}" stroke-width="4" stroke-linecap="round"></path><path d="M16 48c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.accent}" stroke-width="4" stroke-linecap="round"></path><path d="M22 28l18-11" fill="none" stroke="${p.strong}" stroke-width="4" stroke-linecap="round"></path><circle cx="22" cy="28" r="3" fill="${p.strong}"></circle>`;
  if (tier === 4) return `<circle cx="22" cy="42" r="4" fill="${p.main}"></circle><circle cx="42" cy="22" r="4" fill="${p.accent}"></circle><path d="M22 42c7-7 9-10 12-17 2-5 5-8 8-11" fill="none" stroke="${p.strong}" stroke-width="4" stroke-linecap="round"></path><path d="M16 50c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.main}" stroke-width="3.6" stroke-linecap="round"></path>`;
  if (tier === 5) return `<circle cx="22" cy="42" r="4" fill="${p.main}"></circle><circle cx="42" cy="22" r="4" fill="${p.accent}"></circle><path d="M22 42c7-7 9-10 12-17 2-5 5-8 8-11" fill="none" stroke="${p.strong}" stroke-width="4" stroke-linecap="round"></path><path d="M30 36l8-1-1 8" fill="none" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"></path><path d="M15 52c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.main}" stroke-width="3.6" stroke-linecap="round"></path>`;
  if (tier === 6) return `<circle cx="32" cy="30" r="12" fill="white" stroke="${p.accent}" stroke-width="2.5"></circle><path d="M32 22v16M24 30h16" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path><path d="M32 30l7-7" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path><path d="M14 50c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.main}" stroke-width="3.6" stroke-linecap="round"></path>`;
  if (tier === 7) return `<circle cx="32" cy="31" r="13" fill="white" stroke="${p.accent}" stroke-width="2.5"></circle><circle cx="32" cy="31" r="7" fill="${p.tint}" stroke="${p.strong}" stroke-width="2.4"></circle><path d="M32 18v7M32 37v7M19 31h7M38 31h7" stroke="${p.strong}" stroke-width="2.8" stroke-linecap="round"></path><path d="M15 52c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.main}" stroke-width="3.6" stroke-linecap="round"></path>`;
  return `<path d="M14 51c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.main}" stroke-width="3.6" stroke-linecap="round"></path><path d="M19 43c5-5 10-5 13 0s8 5 13 0" fill="none" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round"></path><path d="M32 14l4 7 8 1-6 5 2 8-8-4-8 4 2-8-6-5 8-1z" fill="white" stroke="${p.strong}" stroke-width="2.4" filter="url(#${glowId})"></path>`;
}

function glyphTime(tier, p, glowId) {
  if (tier <= 1) return `<circle cx="32" cy="32" r="12" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><path d="M32 32V24M32 32l7 4" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
  if (tier === 2) return `<rect x="28" y="14" width="8" height="6" rx="3" fill="${p.accent}"></rect><circle cx="32" cy="32" r="12" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><path d="M32 32V24M32 32l7 4" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
  if (tier === 3) return `<rect x="28" y="14" width="8" height="6" rx="3" fill="${p.accent}"></rect><circle cx="32" cy="32" r="12" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><circle cx="32" cy="32" r="17" fill="none" stroke="${p.accent}" stroke-width="2" stroke-dasharray="3 3"></circle><path d="M32 32V24M32 32l7 4" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
  if (tier === 4) return `<path d="M32 18c8 0 13 6 13 13 0 9-7 11-13 17-6-6-13-8-13-17 0-7 5-13 13-13z" fill="white" stroke="${p.main}" stroke-width="2.5"></path><path d="M27 31h10M32 24v14" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
  if (tier === 5) return `<circle cx="32" cy="32" r="13" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><circle cx="32" cy="32" r="18" fill="none" stroke="${p.accent}" stroke-width="2.3"></circle><path d="M32 32V23M32 32l8 4" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
  if (tier === 6) return `<circle cx="32" cy="28" r="12" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><path d="M32 28V20M32 28l7 4" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path><path d="M16 45c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.accent}" stroke-width="3.6" stroke-linecap="round"></path><path d="M16 52c6-6 12-6 18 0s12 6 18 0" fill="none" stroke="${p.main}" stroke-width="3.6" stroke-linecap="round"></path>`;
  if (tier === 7) return `<path d="M22 45c2 5 5 9 10 11M42 45c-2 5-5 9-10 11" fill="none" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path><circle cx="32" cy="28" r="11" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><path d="M32 28V21M32 28l7 4" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
  return `<path d="M25 17l3-5 4 4 4-4 3 5 6 1-3 5H22l-3-5z" fill="${p.accent}" filter="url(#${glowId})"></path><circle cx="32" cy="30" r="12" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><circle cx="32" cy="30" r="17" fill="none" stroke="${p.accent}" stroke-width="2" stroke-dasharray="3 3"></circle><path d="M32 30V22M32 30l8 5" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
}

function glyphEfficiency(tier, p, glowId) {
  if (tier <= 1) return `<path d="M22 39c4-11 12-13 19-12-4 6-6 14-19 12z" fill="${p.main}"></path><path d="M27 37c4-3 7-4 10-4" fill="none" stroke="white" stroke-width="2.4" stroke-linecap="round"></path>`;
  if (tier === 2) return `<path d="M19 39c4-9 10-12 17-11-4 5-5 12-17 11z" fill="${p.main}"></path><path d="M30 38c4-9 10-12 17-11-4 5-5 12-17 11z" fill="${p.accent}"></path>`;
  if (tier === 3) return `<circle cx="32" cy="32" r="6" fill="${p.strong}"></circle><path d="M32 16l5 12-5 3-5-3z" fill="${p.main}"></path><path d="M48 32l-12 5-3-5 3-5z" fill="${p.accent}"></path><path d="M32 48l-5-12 5-3 5 3z" fill="${p.main}"></path>`;
  if (tier === 4) return `<rect x="20" y="24" width="24" height="16" rx="6" fill="white" stroke="${p.main}" stroke-width="2.5"></rect><circle cx="28" cy="32" r="4" fill="${p.main}"></circle><path d="M28 27v10M23 32h10" stroke="white" stroke-width="2.4" stroke-linecap="round"></path><path d="M40 26l7 6-7 6" fill="none" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"></path>`;
  return `<path d="M16 32c8-12 19-15 35-13-8 6-11 12-12 22-7-2-15-5-23-9z" fill="${p.main}" filter="url(#${glowId})"></path><path d="M21 19l9 6M20 46l11-5M43 21l6 6" fill="none" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round"></path><circle cx="39" cy="32" r="5" fill="${p.accent}"></circle>`;
}

function glyphGrowth(tier, p, glowId) {
  if (tier <= 1) return `<path d="M32 46c0-9 1-15 1-21" fill="none" stroke="${p.main}" stroke-width="3.6" stroke-linecap="round"></path><path d="M32 34c-8 0-12-5-12-11 7 0 12 4 12 11z" fill="white" stroke="${p.main}" stroke-width="2.3"></path><path d="M32 30c8 0 12-5 12-11-7 0-12 4-12 11z" fill="${p.accent}" opacity="0.92" stroke="${p.main}" stroke-width="2.3"></path>`;
  if (tier === 2) return `<path d="M32 48V22" fill="none" stroke="${p.main}" stroke-width="3.6" stroke-linecap="round"></path><path d="M32 34c-8 0-12-5-12-11 7 0 12 4 12 11z" fill="white" stroke="${p.main}" stroke-width="2.3"></path><path d="M32 30c8 0 12-5 12-11-7 0-12 4-12 11z" fill="${p.accent}" opacity="0.92" stroke="${p.main}" stroke-width="2.3"></path><path d="M28 47h8" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
  if (tier === 3) return `<path d="M20 44h8V28h-8zM30 44h8V22h-8zM40 44h8V16h-8z" fill="white" stroke="${p.main}" stroke-width="2.4"></path><path d="M19 49h30" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
  if (tier === 4) return `<path d="M20 44h7V32h-7zM30 44h7V24h-7zM40 44h7V16h-7z" fill="white" stroke="${p.main}" stroke-width="2.3"></path><path d="M21 35l7-7 7 2 10-11" fill="none" stroke="${p.accent}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"></path><path d="M39 19h7v7" fill="none" stroke="${p.accent}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`;
  if (tier === 5) return `<path d="M32 49V18" fill="none" stroke="${p.main}" stroke-width="3.5" stroke-linecap="round"></path><path d="M32 31c-10 0-15-6-15-13 9 0 15 5 15 13z" fill="white" stroke="${p.main}" stroke-width="2.4"></path><path d="M32 26c10 0 15-6 15-13-9 0-15 5-15 13z" fill="${p.accent}" stroke="${p.main}" stroke-width="2.4"></path><circle cx="32" cy="17" r="5" fill="${p.accent}" filter="url(#${glowId})"></circle>`;
  if (tier === 6) return `<path d="M24 46l8-24 8 24" fill="none" stroke="${p.main}" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round"></path><path d="M20 34h24" stroke="${p.accent}" stroke-width="3.4" stroke-linecap="round"></path><path d="M32 18l5 6 8 1-6 5 2 8-9-4-9 4 2-8-6-5 8-1z" fill="white" stroke="${p.strong}" stroke-width="2.2"></path>`;
  if (tier === 7) return `<path d="M18 44l14-24 14 24" fill="none" stroke="${p.main}" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round"></path><path d="M23 35h18" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round"></path><path d="M32 15l4 5 7 1-5 4 2 7-8-4-8 4 2-7-5-4 7-1z" fill="white" stroke="${p.strong}" stroke-width="2.2"></path><circle cx="32" cy="15" r="4" fill="${p.accent}" filter="url(#${glowId})"></circle>`;
  return `<path d="M16 44l16-26 16 26" fill="none" stroke="${p.main}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path><path d="M22 34h20" stroke="${p.accent}" stroke-width="3.4" stroke-linecap="round"></path><path d="M32 12l4 6 7 1-5 5 2 7-8-4-8 4 2-7-5-5 7-1z" fill="white" stroke="${p.strong}" stroke-width="2.2" filter="url(#${glowId})"></path><path d="M23 49h18" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
}

function glyphSeason(tier, p, glowId) {
  if (tier <= 1) return `<rect x="20" y="19" width="24" height="24" rx="6" fill="white" stroke="${p.main}" stroke-width="2.5"></rect><rect x="24" y="14" width="4" height="8" rx="2" fill="${p.accent}"></rect><rect x="36" y="14" width="4" height="8" rx="2" fill="${p.accent}"></rect><path d="M25 30h14M25 36h10" stroke="${p.main}" stroke-width="3" stroke-linecap="round"></path>`;
  if (tier === 2) return `<rect x="20" y="19" width="24" height="24" rx="6" fill="white" stroke="${p.main}" stroke-width="2.5"></rect><rect x="24" y="14" width="4" height="8" rx="2" fill="${p.accent}"></rect><rect x="36" y="14" width="4" height="8" rx="2" fill="${p.accent}"></rect><circle cx="32" cy="33" r="5" fill="${p.accent}"></circle>`;
  if (tier === 3) return `<rect x="20" y="19" width="24" height="24" rx="6" fill="white" stroke="${p.main}" stroke-width="2.5"></rect><rect x="24" y="14" width="4" height="8" rx="2" fill="${p.accent}"></rect><rect x="36" y="14" width="4" height="8" rx="2" fill="${p.accent}"></rect><path d="M32 27l2.2 4.5 5 .7-3.6 3.5.9 5-4.5-2.5-4.5 2.5.9-5-3.6-3.5 5-.7z" fill="${p.accent}"></path>`;
  if (tier === 4) return `<circle cx="32" cy="32" r="11" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><path d="M32 16v5M32 43v5M16 32h5M43 32h5M21 21l3.5 3.5M42.5 42.5L39 39M21 43l3.5-3.5M42.5 21.5L39 25" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path><circle cx="32" cy="32" r="4" fill="${p.main}"></circle>`;
  if (tier === 5) return `<path d="M17 34c3-9 10-14 18-14 7 0 12 3 14 8-3 4-8 6-13 6-5 0-9 2-13 7-3 0-5-3-6-7z" fill="white" stroke="${p.main}" stroke-width="2.5"></path><path d="M24 47c5-8 11-12 21-12" fill="none" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round"></path>`;
  if (tier === 6) return `<path d="M32 17l4 8 9 1-6.5 6 1.8 9-8.3-4.4L24.7 41l1.8-9L20 26l9-1z" fill="white" stroke="${p.main}" stroke-width="2.4"></path><circle cx="32" cy="32" r="4" fill="${p.accent}" filter="url(#${glowId})"></circle>`;
  if (tier === 7) return `<path d="M32 16l4 8 9 1-6.5 6 1.8 9-8.3-4.4L24.7 40l1.8-9L20 25l9-1z" fill="white" stroke="${p.main}" stroke-width="2.4"></path><path d="M18 48c5-4 9-4 14 0s9 4 14 0" fill="none" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round"></path><circle cx="32" cy="28" r="4" fill="${p.accent}" filter="url(#${glowId})"></circle>`;
  return `<circle cx="32" cy="32" r="16" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><path d="M32 13l4 7 8 1-6 5 2 8-8-4-8 4 2-8-6-5 8-1z" fill="${p.accent}" filter="url(#${glowId})"></path><path d="M20 45c4-4 8-4 12 0s8 4 12 0" fill="none" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
}

function glyphGallery(tier, p, glowId) {
  if (tier <= 1) return `<circle cx="25" cy="28" r="5" fill="${p.main}"></circle><circle cx="39" cy="28" r="5" fill="${p.accent}"></circle><path d="M18 42c1-6 5-10 11-10s10 4 11 10" fill="white" stroke="${p.main}" stroke-width="2.3"></path><path d="M28 42c1-6 5-10 11-10s10 4 11 10" fill="none" stroke="${p.accent}" stroke-width="2.3"></path>`;
  if (tier === 2) return `<circle cx="23" cy="29" r="4.5" fill="${p.main}"></circle><circle cx="32" cy="24" r="5" fill="${p.accent}"></circle><circle cx="41" cy="29" r="4.5" fill="${p.main}"></circle><path d="M17 43c1-6 5-9 10-9 4 0 7 2 9 5 2-3 5-5 9-5 5 0 9 3 10 9" fill="white" stroke="${p.main}" stroke-width="2.2"></path>`;
  if (tier === 3) return `<circle cx="23" cy="29" r="4.5" fill="${p.main}"></circle><circle cx="32" cy="24" r="5" fill="${p.accent}"></circle><circle cx="41" cy="29" r="4.5" fill="${p.main}"></circle><path d="M17 43c1-6 5-9 10-9 4 0 7 2 9 5 2-3 5-5 9-5 5 0 9 3 10 9" fill="white" stroke="${p.main}" stroke-width="2.2"></path><path d="M32 15l2 4 5 .7-3.5 3.2.9 4.8-4.4-2.3-4.4 2.3.9-4.8-3.5-3.2 5-.7z" fill="${p.accent}"></path>`;
  if (tier === 4) return `<path d="M32 16l4 7 8 1-6 5 2 8-8-4-8 4 2-8-6-5 8-1z" fill="white" stroke="${p.main}" stroke-width="2.4"></path><path d="M20 43c4-4 8-4 12 0s8 4 12 0" fill="none" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round"></path><circle cx="32" cy="28" r="4" fill="${p.main}"></circle>`;
  if (tier === 5) return `<path d="M32 16l4 7 8 1-6 5 2 8-8-4-8 4 2-8-6-5 8-1z" fill="white" stroke="${p.main}" stroke-width="2.4"></path><path d="M17 43c5-4 10-4 15 0s10 4 15 0" fill="none" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round"></path><circle cx="25" cy="28" r="3.2" fill="${p.main}"></circle><circle cx="39" cy="28" r="3.2" fill="${p.main}"></circle><circle cx="32" cy="25" r="3.5" fill="${p.accent}"></circle>`;
  if (tier === 6) return `<path d="M20 22h24v18H20z" fill="white" stroke="${p.main}" stroke-width="2.5"></path><path d="M23 36l6-6 5 4 6-8 4 10z" fill="${p.accent}" opacity="0.9"></path><circle cx="28" cy="28" r="2.8" fill="${p.main}"></circle><path d="M24 47c4-4 8-4 12 0s8 4 12 0" fill="none" stroke="${p.strong}" stroke-width="3.2" stroke-linecap="round"></path>`;
  if (tier === 7) return `<path d="M32 14l4 7 8 1-6 5 2 8-8-4-8 4 2-8-6-5 8-1z" fill="white" stroke="${p.main}" stroke-width="2.4"></path><path d="M22 39h20v10H22z" fill="${p.accent}" opacity="0.18"></path><path d="M22 44c3-3 6-3 10 0s7 3 10 0" fill="none" stroke="${p.accent}" stroke-width="3.2" stroke-linecap="round"></path><path d="M26 20l6-7 6 7" fill="none" stroke="${p.strong}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`;
  return `<path d="M32 12l4 7 8 1-6 5 2 8-8-4-8 4 2-8-6-5 8-1z" fill="${p.accent}" filter="url(#${glowId})"></path><path d="M18 45c5-5 9-5 14 0s9 5 14 0" fill="none" stroke="${p.main}" stroke-width="3.4" stroke-linecap="round"></path><circle cx="24" cy="29" r="3" fill="${p.main}"></circle><circle cx="32" cy="24" r="3.4" fill="${p.strong}"></circle><circle cx="40" cy="29" r="3" fill="${p.main}"></circle>`;
}

function glyphFun(tier, p, glowId) {
  if (tier <= 1) return `<circle cx="32" cy="32" r="12" fill="white" stroke="${p.main}" stroke-width="2.5"></circle><circle cx="27" cy="29" r="2" fill="${p.main}"></circle><circle cx="37" cy="29" r="2" fill="${p.main}"></circle><path d="M26 36c2 2 4 3 6 3s4-1 6-3" fill="none" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path>`;
  if (tier === 2) return `<circle cx="28" cy="30" r="11" fill="white" stroke="${p.main}" stroke-width="2.4"></circle><path d="M37 20c5 0 9 4 9 9 0 4-2 7-5 9-2-5-4-8-9-10 1-4 3-8 5-8z" fill="${p.accent}" opacity="0.9"></path><circle cx="24" cy="28" r="2" fill="${p.main}"></circle><path d="M22 34c2 2 4 3 6 3" fill="none" stroke="${p.main}" stroke-width="3" stroke-linecap="round"></path>`;
  if (tier === 3) return `<circle cx="29" cy="31" r="10" fill="white" stroke="${p.main}" stroke-width="2.4"></circle><path d="M39 22c4 1 7 4 7 8 0 4-2 7-5 9-2-5-4-8-9-10 1-4 3-7 7-7z" fill="${p.accent}" opacity="0.9"></path><path d="M18 24l3 2M43 18l2-3M45 42l4 2" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path><circle cx="25" cy="29" r="2" fill="${p.main}"></circle>`;
  if (tier === 4) return `<path d="M20 37c3-10 9-16 18-17 4 2 7 5 9 9-3 7-11 14-24 12-2-1-3-2-3-4z" fill="white" stroke="${p.main}" stroke-width="2.4"></path><circle cx="30" cy="31" r="2.3" fill="${p.main}"></circle><path d="M28 38c2 1 4 2 7 1" fill="none" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path>`;
  if (tier === 5) return `<path d="M19 36c3-10 10-16 20-17 4 2 7 5 9 9-4 8-12 15-26 12-2-1-3-2-3-4z" fill="white" stroke="${p.main}" stroke-width="2.4"></path><path d="M44 16l2 4 4 .5-3 3 .8 4-3.8-2-3.8 2 .8-4-3-3 4-.5z" fill="${p.accent}"></path><circle cx="31" cy="31" r="2.3" fill="${p.main}"></circle>`;
  if (tier === 6) return `<path d="M32 16l4 6 7 1-5 5 1 7-7-4-7 4 1-7-5-5 7-1z" fill="${p.accent}" opacity="0.9"></path><circle cx="25" cy="35" r="4.5" fill="${p.main}"></circle><circle cx="39" cy="35" r="4.5" fill="${p.main}"></circle><path d="M20 46c4-4 8-6 12-6s8 2 12 6" fill="none" stroke="${p.strong}" stroke-width="3.4" stroke-linecap="round"></path>`;
  if (tier === 7) return `<path d="M32 14l4 7 8 1-6 5 2 8-8-4-8 4 2-8-6-5 8-1z" fill="${p.accent}" filter="url(#${glowId})"></path><circle cx="24" cy="36" r="4.2" fill="${p.main}"></circle><circle cx="40" cy="36" r="4.2" fill="${p.main}"></circle><path d="M19 46c4-4 8-6 13-6s9 2 13 6" fill="none" stroke="${p.strong}" stroke-width="3.4" stroke-linecap="round"></path><path d="M18 24l3-3M46 24l-3-3" stroke="${p.accent}" stroke-width="3" stroke-linecap="round"></path>`;
  return `<path d="M32 12l4 7 8 1-6 5 2 8-8-4-8 4 2-8-6-5 8-1z" fill="${p.accent}" filter="url(#${glowId})"></path><circle cx="24" cy="37" r="4" fill="${p.main}"></circle><circle cx="40" cy="37" r="4" fill="${p.main}"></circle><path d="M18 47c4-5 9-7 14-7s10 2 14 7" fill="none" stroke="${p.strong}" stroke-width="3.4" stroke-linecap="round"></path><circle cx="32" cy="26" r="3.5" fill="white" stroke="${p.main}" stroke-width="2"></circle>`;
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
