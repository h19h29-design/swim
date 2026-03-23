import {
  buildMobileUrl,
  buildProfileUrl,
  compareAuthors,
  categoryLabelFromBundle,
  escapeHtml,
  findAuthorMatch,
  formatDistance,
  formatDurationLabel,
  formatInt,
  getAuthorSuggestions,
  getMetricGroup,
  getVisibleDateRangeLabel,
  loadAuthorIndex,
  loadBadgeIndex,
  loadDashboardViews,
  loadPublicSiteConfig,
  loadReviewQueue,
  mergeSiteBundles,
  metricLabel,
  renderBadgeIcon,
  sliceRankFourToTwenty,
  sliceTopThree,
  sourceLabel,
} from "./dashboard-common.js?v=20260323a";

const DEFAULT_NAV = [
  { label_ko: "모바일 보기", href: buildMobileUrl() },
  { label_ko: "배지 갤러리", href: "./badge-gallery.html" },
  { label_ko: "파싱 현황", href: "./parse-status.html" },
];

const CATEGORY_ORDER = ["attendance", "distance", "time", "efficiency", "growth", "season", "gallery", "fun"];
const RANK_SLOT_START = 4;
const RANK_SLOT_END = 20;

const state = {
  dashboard: null,
  authorIndex: null,
  badgeIndex: null,
  reviewQueue: [],
  activeMetric: "swim_count",
  siteBundle: null,
};

async function init() {
  const [dashboard, authorIndex, badgeIndex, reviewQueue, publicSiteConfig] = await Promise.all([
    loadDashboardViews(),
    loadAuthorIndex(),
    loadBadgeIndex(),
    loadReviewQueue(),
    loadPublicSiteConfig(),
  ]);

  state.dashboard = dashboard;
  state.authorIndex = authorIndex;
  state.badgeIndex = badgeIndex;
  state.reviewQueue = reviewQueue;
  state.siteBundle = mergeSiteBundles(publicSiteConfig, dashboard);
  state.activeMetric = resolveInitialMetric();

  bindEvents();
  render();
}

function bindEvents() {
  document.getElementById("rankingTabs")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-metric]");
    if (!button) return;
    state.activeMetric = button.dataset.metric;
    syncMetricQuery();
    renderRanking();
  });

  document.getElementById("searchSuggestionRow")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-author]");
    if (!button) return;
    const input = document.getElementById("authorSearch");
    if (input) input.value = button.dataset.author || "";
    openProfile();
  });

  document.getElementById("authorSearch")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      openProfile();
    }
  });

  document.getElementById("openProfileButton")?.addEventListener("click", openProfile);
}

function resolveInitialMetric() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("metric");
  const metrics = availableMetrics();
  if (requested && metrics.some((item) => item.metric_key === requested)) {
    return requested;
  }
  return state.dashboard?.rankings?.default_metric || metrics[0]?.metric_key || "swim_count";
}

function syncMetricQuery() {
  const url = new URL(window.location.href);
  url.searchParams.set("desktop", "1");
  url.searchParams.set("metric", state.activeMetric);
  url.searchParams.set("v", "20260317a");
  window.history.replaceState({}, "", url);
}

function render() {
  renderHero();
  renderKpis();
  renderRanking();
  renderBadgeShelves();
  renderSearch();
  renderRecentRecords();
  renderOps();
}

function renderHero() {
  const site = state.siteBundle?.site_config || {};
  const hero = site.hero || {};
  const gallery = state.dashboard?.gallery || {};
  const progress = gallery.progress || {};
  const current = gallery.current_title || {};
  const next = gallery.next_title_target || {};
  const navItems = (state.siteBundle?.navigation_config?.items || [])
    .filter((item) => item?.visible !== false && item?.nav_key !== "admin")
    .map((item) => ({ label_ko: item.label_ko, href: item.href || resolveDefaultHref(item.nav_key) }))
    .filter((item) => item.label_ko && item.href);

  setText("heroEyebrow", hero.eyebrow_ko || "SWIM STICKER BOOK");
  setText("heroHeadline", hero.headline_ko || "붙이고 모으는 수영 시즌 보드");
  setText("heroSubtitle", hero.subheadline_ko || "운동 정보, 랭킹, 대표 칭호와 다음 해금을 한 화면에서 보여줍니다.");

  setText("galleryTitleName", current.name_ko || "시즌 준비중");
  setText("galleryTitleDescription", current.description_ko || "아직 첫 갤 칭호가 열리기 전입니다.");
  setText("galleryTitleTier", current.short_label_ko || "갤 칭호");

  setText("nextUnlockName", next.name_ko || "다음 칭호 준비중");
  setText("nextUnlockValue", next.remaining_value_text_ko || "목표 계산 중");
  setText("nextUnlockMeta", `${progress.current_value_text_ko || "0m"} / ${progress.target_value_text_ko || next.target_value_text_ko || "-"}`);
  setText("modeChip", "제목 양식 기준");
  setText("generatedAtLabel", state.dashboard?.generated_at ? `집계 갱신 ${state.dashboard.generated_at}` : "집계 생성 시각 정보가 없습니다.");
  setText("summaryRangeLabel", getVisibleDateRangeLabel(state.dashboard?.visible_date_range));
  setText(
    "nextUnlockProgressMeta",
    `${progress.remaining_value_text_ko || next.remaining_value_text_ko || "남은 목표 계산 중"} · ${Math.round(clampRatio(progress.progress_ratio || next.progress_ratio || 0) * 100)}%`,
  );

  const bar = document.getElementById("nextUnlockBar");
  if (bar) {
    bar.style.width = `${Math.round(clampRatio(progress.progress_ratio || next.progress_ratio || 0) * 100)}%`;
  }

  document.getElementById("galleryTitleMeta").innerHTML = [
    current.icon_key ? chip(renderBadgeIcon(state.siteBundle, current, current.name_ko || "갤 칭호", "inline-badge-icon") + escapeHtml(current.short_label_ko || "현재 칭호"), true) : "",
    chip(`해금된 갤 배지 ${formatInt(progress.unlocked_badge_count || 0)}개`),
  ].join("");

  document.getElementById("heroChipRow").innerHTML = [
    chip(site.site_title_ko || "수영 스티커북"),
    chip(`집계 기간 ${getVisibleDateRangeLabel(state.dashboard?.visible_date_range)}`),
    chip(`다음 해금 ${next.short_label_ko || next.target_value_text_ko || "준비중"}`),
    chip(`전체 배지 ${formatInt(state.badgeIndex?.badge_count)}개`),
  ].join("");

  document.getElementById("quickNavRow").innerHTML = uniqueNav([...navItems, ...DEFAULT_NAV])
    .map((item) => `<a class="nav-chip" href="${escapeHtml(item.href)}">${escapeHtml(item.label_ko)}</a>`)
    .join("");
}

function renderKpis() {
  const summary = state.dashboard?.summary || {};
  const labels = state.siteBundle?.site_config?.kpi_labels || {};
  const cards = [
    { title: labels.swim_count || "갤 전체 운동횟수", value: `${formatInt(summary.swim_count)}회`, note: "제목 양식으로 자동 반영된 기록 수입니다." },
    { title: labels.total_distance_m || "갤 전체 총거리", value: formatDistance(summary.total_distance_m), note: "누적 거리 합계입니다." },
    { title: labels.total_seconds || "갤 전체 총시간", value: formatDurationLabel(summary.total_seconds), note: "누적 운동 시간입니다." },
    { title: labels.active_authors || "참여 인원", value: `${formatInt(summary.active_authors)}명`, note: summary.has_zero_visible_included_rows ? "현재 자동 반영된 닉네임이 아직 적습니다." : "현재 집계 기간 안에서 기록이 잡힌 닉네임 수입니다." },
  ];

  document.getElementById("kpiGrid").innerHTML = cards.map((card) => `
    <article class="kpi-card">
      <h3>${escapeHtml(card.title)}</h3>
      <p class="kpi-value">${escapeHtml(card.value)}</p>
      <span class="kpi-note">${escapeHtml(card.note)}</span>
    </article>
  `).join("");
}

function renderRanking() {
  renderRankingTabs();
  const group = getMetricGroup(state.dashboard, state.activeMetric);
  const topRows = sliceTopThree(group).slice(0, 3);
  const rankRows = sliceRankFourToTwenty(group);

  setText("rankingHeading", `${group.label_ko || metricLabel(state.activeMetric)} 랭킹`);
  setText("rankingSummary", group.description_ko || "이번 시즌 기록 기준으로 순위를 보여줍니다.");
  setText("rankListTitle", "4위부터 20위까지");
  setText("rankListCount", `${formatInt(rankRows.length)}명`);

  document.getElementById("topThree").innerHTML = [1, 2, 3]
    .map((rank, index) => buildTopCard(topRows[index] || null, rank))
    .join("");

  document.getElementById("rankList").innerHTML = Array.from({ length: RANK_SLOT_END - RANK_SLOT_START + 1 }, (_, offset) => {
    const rank = RANK_SLOT_START + offset;
    const row = rankRows.find((item) => Number(item.rank) === rank) || null;
    return buildRankRow(row, rank);
  }).join("");
}

function renderRankingTabs() {
  const sections = Array.isArray(state.siteBundle?.home_sections?.ranking_sections)
    ? state.siteBundle.home_sections.ranking_sections
    : availableMetrics();
  document.getElementById("rankingTabs").innerHTML = sections.map((item) => `
    <button class="ranking-tab${item.metric_key === state.activeMetric ? " is-active" : ""}" type="button" data-metric="${escapeHtml(item.metric_key)}">
      ${escapeHtml(item.label_ko || metricLabel(item.metric_key))}
    </button>
  `).join("");
}

function renderBadgeShelves() {
  const recentUnlocks = Array.isArray(state.dashboard?.recent_unlocks) ? state.dashboard.recent_unlocks.slice(0, 4) : [];
  document.getElementById("recentUnlocks").innerHTML = createShelfSlots(recentUnlocks, 4).map((item) => {
    if (!item) {
      return `
        <article class="shelf-item is-placeholder">
          <h3>다음 배지 대기중</h3>
          <p class="record-note">새 기록이 들어오면 최근 해금 칸이 채워집니다.</p>
        </article>
      `;
    }
    return `
      <article class="shelf-item">
        <div class="metric-chip-row">
          ${renderBadgeIcon(state.siteBundle, item, item.name_ko || item.badge_id, "inline-badge-icon")}
          <span class="metric-chip">${escapeHtml(categoryLabelFromBundle(state.siteBundle, item.category))}</span>
        </div>
        <h3>${escapeHtml(item.name_ko || item.short_label_ko || "배지")}</h3>
        <p class="record-note">${escapeHtml(item.author ? `${item.author} 닉네임이 최근에 해금했습니다.` : item.description_ko || "최근 해금 배지입니다.")}</p>
      </article>
    `;
  }).join("");

  const counts = state.badgeIndex?.badge_count_by_category || {};
  const categories = CATEGORY_ORDER.filter((key) => counts[key]);
  document.getElementById("badgeSummary").innerHTML = (categories.length ? categories : CATEGORY_ORDER.slice(0, 4)).map((key) => `
    <article class="shelf-item${counts[key] ? "" : " is-placeholder"}">
      <h3>${escapeHtml(categoryLabelFromBundle(state.siteBundle, key))}</h3>
      <p class="kpi-value">${escapeHtml(`${formatInt(counts[key] || 0)}개`)}</p>
      <p class="record-note">${escapeHtml(buildCategoryNote(key))}</p>
    </article>
  `).join("");
}

function renderSearch() {
  const authors = getAuthorSuggestions(state.authorIndex).sort((a, b) => compareAuthors(a.author, b.author));
  document.getElementById("authorSuggestions").innerHTML = authors.map((row) => `<option value="${escapeHtml(row.author)}"></option>`).join("");
  document.getElementById("searchSuggestionRow").innerHTML = authors.slice(0, 8).map((row) => `
    <button class="suggestion-chip" type="button" data-author="${escapeHtml(row.author)}">${escapeHtml(row.author)}</button>
  `).join("");
  setText(
    "searchHint",
    authors.length ? "닉네임을 입력하면 개인 프로필로 이동합니다." : "아직 집계된 닉네임이 적어서 추천 목록이 비어 있습니다.",
  );
}

function renderRecentRecords() {
  const rows = Array.isArray(state.dashboard?.recent_records) ? state.dashboard.recent_records.slice(0, 8) : [];
  document.getElementById("recentRecords").innerHTML = rows.length ? rows.map((row) => `
    <article class="record-row">
      <div class="record-meta">${escapeHtml(row.post_date || "-")}</div>
      <div class="record-main">
        <div class="record-main-line">
          <h3>${escapeHtml(row.author || "작성자 없음")}</h3>
          <span class="metric-chip">${escapeHtml(sourceLabel(row.source))}</span>
        </div>
        <p>${escapeHtml(`${formatDistance(row.distance_m)} · ${row.total_time_text || formatDurationLabel(row.total_seconds)}`)}</p>
      </div>
      <a class="text-link" href="${escapeHtml(row.url || "#")}" target="_blank" rel="noreferrer">원문 보기</a>
    </article>
  `).join("") : `
    <article class="empty-card">
      <strong>최근 기록이 아직 없습니다.</strong>
      <p>제목 양식 글이 들어오면 최근 기록 목록이 채워집니다.</p>
    </article>
  `;
}

function renderOps() {
  const count = Array.isArray(state.reviewQueue) ? state.reviewQueue.length : 0;
  setText(
    "reviewQueueSummary",
    count
      ? `검토 대기 글이 ${formatInt(count)}건 있습니다. 파싱 현황 페이지에서 실패 사유와 수동 보정 여부를 확인해 주세요.`
      : "현재 검토 대기 글은 없습니다. 새로 보류되는 글이 생기면 여기서 안내합니다.",
  );
}

function openProfile() {
  const input = document.getElementById("authorSearch");
  const query = String(input?.value || "").trim();
  if (!query) return;
  const author = findAuthorMatch(state.authorIndex, query);
  window.location.assign(buildProfileUrl(author));
}

function buildTopCard(row, rank) {
  if (!row) {
    return `
      <article class="top-card top-card--${rank} is-placeholder">
        <div class="metric-chip-row">
          <span class="metric-chip">${rank}위</span>
          <span class="metric-chip">대기중</span>
        </div>
        <h3>다음 닉네임 대기</h3>
        <p class="kpi-value">기록 없음</p>
        <p class="rank-copy">새 기록이 들어오면 이 자리가 채워집니다.</p>
      </article>
    `;
  }

  const badgePreview = Array.isArray(row.badge_preview) ? row.badge_preview.slice(0, 2) : [];
  return `
    <article class="top-card top-card--${rank}">
      <div class="metric-chip-row">
        <span class="metric-chip">${rank}위</span>
        <span class="metric-chip">${escapeHtml(metricLabel(state.activeMetric))}</span>
      </div>
      <div class="top-card-title">
        ${renderBadgeIcon(state.siteBundle, row.primary_title, row.author || "닉네임", "top-card-icon")}
        <div>
          <h3>${escapeHtml(row.author || "작성자 없음")}</h3>
          <p class="record-note">${escapeHtml(row.primary_title?.short_label_ko || row.primary_title?.name_ko || "대표 칭호 준비중")}</p>
        </div>
      </div>
      <p class="kpi-value">${escapeHtml(row.metric_value_text_ko || "-")}</p>
      <p class="rank-copy">${escapeHtml(row.secondary_text_ko || "이번 시즌 기준 기록입니다.")}</p>
      <div class="metric-chip-row">
        ${badgePreview.map((item) => `<span class="metric-chip">${escapeHtml(item)}</span>`).join("")}
      </div>
    </article>
  `;
}

function buildRankRow(row, rank) {
  if (!row) {
    return `
      <article class="rank-row is-placeholder">
        <strong>${rank}위</strong>
        <span>비어 있음</span>
        <span class="rank-copy">아직 기록 없음</span>
      </article>
    `;
  }

  return `
    <article class="rank-row">
      <strong>${rank}위</strong>
      <div class="rank-row-main">
        <div class="rank-row-author">
          ${renderBadgeIcon(state.siteBundle, row.primary_title, row.author || "닉네임", "inline-badge-icon")}
          <span>${escapeHtml(row.author || "작성자 없음")}</span>
        </div>
        <span class="rank-copy">${escapeHtml(row.primary_title?.short_label_ko || row.secondary_text_ko || "대표 칭호 준비중")}</span>
      </div>
      <span class="metric-chip">${escapeHtml(row.metric_value_text_ko || "-")}</span>
    </article>
  `;
}

function availableMetrics() {
  return Object.keys(state.dashboard?.rankings?.metrics || {}).map((metric_key) => ({ metric_key, label_ko: metricLabel(metric_key) }));
}

function uniqueNav(items) {
  const seen = new Set();
  return items.filter((item) => {
    const key = `${item.label_ko}|${item.href}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function resolveDefaultHref(navKey) {
  return {
    home: "./index.html?desktop=1",
    profiles: "./profile.html",
    parse_status: "./parse-status.html",
    badges: "./badge-gallery.html",
  }[navKey] || "./index.html?desktop=1";
}

function createShelfSlots(rows, minimumCount) {
  const items = Array.isArray(rows) ? [...rows] : [];
  while (items.length < minimumCount) items.push(null);
  return items;
}

function buildCategoryNote(category) {
  return {
    attendance: "참여횟수 누적 배지",
    distance: "누적 거리 배지",
    time: "누적 시간 배지",
    efficiency: "시간당 거리 배지",
    growth: "최근 28일 성장 배지",
    season: "월별 시즌 배지",
    gallery: "갤 전체 누적 칭호",
    fun: "보너스와 이벤트 배지",
  }[category] || "배지 카테고리";
}

function chip(content, allowHtml = false) {
  return `<span class="hero-chip">${allowHtml ? content : escapeHtml(content)}</span>`;
}

function clampRatio(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(1, numeric));
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value || "";
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    init().catch((error) => {
      console.error(error);
      setText("reviewQueueSummary", "페이지 렌더링 중 오류가 발생했습니다. 새로고침 후 다시 확인해 주세요.");
    });
  });
}
