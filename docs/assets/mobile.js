import {
  buildDesktopUrl,
  buildProfileUrl,
  categoryLabelFromBundle,
  compareAuthors,
  escapeHtml,
  findAuthorMatch,
  formatDistance,
  formatDurationLabel,
  formatInt,
  getAuthorSuggestions,
  getDashboardSeasonView,
  getDefaultSeasonViewKey,
  getMetricGroup,
  getSeasonViewOptions,
  loadAuthorIndex,
  loadBadgeIndex,
  loadDashboardViews,
  loadPublicSiteConfig,
  loadReviewQueue,
  mergeSiteBundles,
  metricLabel,
  renderBadgeIcon,
  sourceLabel,
} from "./dashboard-common.js?v=20260323a";

const state = {
  dashboard: null,
  authorIndex: null,
  badgeIndex: null,
  reviewQueue: [],
  activeSeasonKey: null,
  activeMetric: "total_distance_m",
  activeTab: "dashboard",
  siteBundle: null,
};

document.addEventListener("DOMContentLoaded", () => {
  init().catch((error) => {
    console.error(error);
    setHtml("mobileOpsCard", `<p class="empty-state">페이지를 불러오지 못했습니다.</p>`);
  });
});

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
  state.activeSeasonKey = resolveInitialSeasonKey();

  bindEvents();
  render();
}

function bindEvents() {
  document.addEventListener("click", (event) => {
    const tabButton = event.target.closest("[data-tab-target]");
    if (tabButton) {
      setActiveTab(tabButton.dataset.tabTarget);
      return;
    }

    const seasonButton = event.target.closest("[data-mobile-season]");
    if (seasonButton) {
      state.activeSeasonKey = seasonButton.dataset.mobileSeason;
      syncQuery();
      render();
      return;
    }

    const authorButton = event.target.closest("[data-mobile-author]");
    if (authorButton) {
      window.location.assign(buildProfileUrl(authorButton.dataset.mobileAuthor || ""));
    }
  });

  document.getElementById("mobileMetricToggle")?.addEventListener("click", () => {
    state.activeMetric = state.activeMetric === "total_distance_m" ? "swim_count" : "total_distance_m";
    renderRanking();
  });

  document.getElementById("mobileSearchForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = String(document.getElementById("mobileAuthorSearch")?.value || "").trim();
    if (!query) return;
    window.location.assign(buildProfileUrl(findAuthorMatch(state.authorIndex, query)));
  });

  document.querySelector("[data-focus-search]")?.addEventListener("click", () => {
    setActiveTab("menu");
    setTimeout(() => document.getElementById("mobileAuthorSearch")?.focus(), 80);
  });
}

function render() {
  renderHero();
  renderKpis();
  renderAnalysisShortcuts();
  renderWeekly();
  renderRecent();
  renderReview();
  renderBadges();
  renderSeasonTabs();
  renderRanking();
  renderProfile();
  renderSearch();
  renderOps();
  setActiveTab(state.activeTab);
}

function renderHero() {
  const view = getActiveView();
  const gallery = view?.gallery || {};
  const current = gallery.current_title || {};
  const next = gallery.next_title_target || {};
  const progress = gallery.progress || {};
  const ratio = clampRatio(progress.progress_ratio || next.progress_ratio || 0);
  setHtml("mobileHero", `
    <div class="hero-bg-mark">${iconSvg("swimmer")}</div>
    <span class="season-chip">${escapeHtml(view?.short_label_ko || "S2")}</span>
    <p>현재 칭호</p>
    <h1>${escapeHtml(current.name_ko || "푸른물결")}</h1>
    <span>${escapeHtml(progress.remaining_value_text_ko || next.remaining_value_text_ko || "다음 칭호 계산 중")}</span>
    <div class="progress-track"><span style="width:${Math.round(ratio * 100)}%"></span></div>
    <div class="progress-meta">
      <small>${escapeHtml(progress.current_value_text_ko || formatDistance(view?.summary?.total_distance_m))} / ${escapeHtml(progress.target_value_text_ko || next.target_value_text_ko || "-")}</small>
      <small>${Math.round(ratio * 100)}%</small>
    </div>
  `);
}

function renderKpis() {
  const summary = getActiveView()?.summary || {};
  const cards = [
    ["이번 시즌 총거리", formatDistance(summary.total_distance_m), "지난 시즌 대비"],
    ["공식 반영 기록", `${formatInt(summary.swim_count)}건`, "자동 후보 반영"],
    ["활성 작성자", `${formatInt(summary.active_authors)}명`, "고정닉 기준"],
    ["검토 대기", `${formatInt(getReviewCount())}건`, "큐 포함"],
  ];
  setHtml("mobileKpis", cards.map(([label, value, note]) => `
    <article class="kpi-card">
      <small>${escapeHtml(label)}</small>
      <strong>${escapeHtml(value)}</strong>
      <span>${escapeHtml(note)}</span>
    </article>
  `).join(""));
}

function renderAnalysisShortcuts() {
  const rows = [
    ["주간 추이", "line"],
    ["영법 비중", "donut"],
    ["월별 누적", "bar"],
    ["평균 페이스", "pace"],
  ];
  setHtml("analysisShortcuts", rows.map(([label, icon]) => `
    <button type="button" data-tab-target="records">
      ${iconSvg(icon)}
      <span>${escapeHtml(label)}</span>
    </button>
  `).join(""));
}

function renderWeekly() {
  const rows = getDailyRows(getActiveView()).slice(-7);
  if (!rows.length) {
    setHtml("mobileWeeklyChart", `<p class="empty-state">주간 거리 데이터가 아직 없습니다.</p>`);
    return;
  }
  setHtml("mobileWeeklyChart", lineChart(rows, "total_distance_m", (row) => shortDate(row.date), (value) => formatDistance(value)));
}

function getDailyRows(view) {
  if (Array.isArray(view?.time_series?.daily) && view.time_series.daily.length) {
    return view.time_series.daily;
  }
  const bucket = new Map();
  (view?.recent_records || []).forEach((row) => {
    const date = row.post_date || "";
    if (!date) return;
    const current = bucket.get(date) || { date, total_distance_m: 0, total_seconds: 0, swim_count: 0 };
    current.total_distance_m += Number(row.distance_m || 0);
    current.total_seconds += Number(row.total_seconds || 0);
    current.swim_count += 1;
    bucket.set(date, current);
  });
  return [...bucket.values()].sort((left, right) => String(left.date).localeCompare(String(right.date)));
}

function renderRecent() {
  const rows = Array.isArray(getActiveView()?.recent_records) ? getActiveView().recent_records : [];
  const preview = rows.slice(0, 3);
  const full = rows.slice(0, 12);
  setHtml("mobileRecentPreview", preview.length ? preview.map(recordRow).join("") : `<p class="empty-state">최근 기록이 아직 없습니다.</p>`);
  setHtml("mobileRecords", full.length ? full.map(recordRow).join("") : `<p class="empty-state">최근 기록이 아직 없습니다.</p>`);
}

function renderReview() {
  const count = getReviewCount();
  const reasonCounts = getActiveView()?.ops?.review_reason_counts || {};
  setHtml("mobileReviewAlert", `
    <div>
      <strong>검토 대기</strong>
      <span>${formatInt(count)}건</span>
      <p>${escapeHtml(buildReviewSummary(reasonCounts))}</p>
    </div>
    <a href="./parse-status.html">더보기</a>
  `);
}

function renderBadges() {
  const unlocks = Array.isArray(getActiveView()?.recent_unlocks) ? getActiveView().recent_unlocks : [];
  const preview = unlocks.slice(0, 1);
  const rows = unlocks.slice(0, 12);
  setHtml("mobileBadgePreview", preview.length ? preview.map((item) => badgeRow(item, "wide")).join("") : `<p class="empty-state">최근 해금 배지가 아직 없습니다.</p>`);
  setHtml("mobileBadges", rows.length ? rows.map((item) => badgeRow(item)).join("") : `<p class="empty-state">보유 배지 데이터가 아직 없습니다.</p>`);
}

function renderSeasonTabs() {
  const options = getSeasonViewOptions(state.dashboard);
  setHtml("mobileSeasonTabs", options.map((item) => `
    <button class="${item.view_key === state.activeSeasonKey ? "is-active" : ""}" type="button" data-mobile-season="${escapeHtml(item.view_key)}">
      ${escapeHtml(item.label_ko)}
    </button>
  `).join(""));
}

function renderRanking() {
  const view = getActiveView();
  const group = getMetricGroup(view, state.activeMetric);
  const rows = group.rows?.length ? group.rows : [...(group.top3 || []), ...(group.ranks_4_to_20 || [])];
  const top3 = rows.slice(0, 3);
  setHtml("mobilePodium", top3.length ? top3.map((row, index) => `
    <a class="podium-card rank-${index + 1}" href="${escapeHtml(row.profile_url || buildProfileUrl(row.author))}">
      ${renderBadgeIcon(state.siteBundle, row.primary_title, row.author || "랭킹", "podium-avatar")}
      <span>${index + 1}</span>
      <strong>${escapeHtml(row.author || "작성자")}</strong>
      <em>${escapeHtml(row.metric_value_text_ko || "-")}</em>
    </a>
  `).join("") : `<p class="empty-state">랭킹 데이터가 아직 없습니다.</p>`);
  setHtml("mobileRankingList", rows.slice(3, 10).map((row, index) => `
    <a class="ranking-row" href="${escapeHtml(row.profile_url || buildProfileUrl(row.author))}">
      <span>${index + 4}</span>
      <strong>${escapeHtml(row.author || "작성자")}</strong>
      <em>${escapeHtml(row.metric_value_text_ko || "-")}</em>
      <small>${escapeHtml(row.secondary_text_ko || "")}</small>
    </a>
  `).join(""));
  setHtml("mobileRankingStats", `
    <article><span>TOP 10 평균</span><strong>${escapeHtml(averageMetricLabel(rows.slice(0, 10), state.activeMetric))}</strong></article>
    <article><span>전체 참여자</span><strong>${formatInt(view?.summary?.active_authors)}명</strong></article>
    <article><span>시즌 총거리</span><strong>${formatDistance(view?.summary?.total_distance_m)}</strong></article>
  `);
}

function renderProfile() {
  const row = getActiveView()?.authors?.[0] || null;
  if (!row) {
    setHtml("mobileProfileCard", `<p class="empty-state">표시할 개인 프로필이 아직 없습니다.</p>`);
    return;
  }
  setHtml("mobileProfileCard", `
    <div class="profile-cover"></div>
    <div class="profile-head">
      ${renderBadgeIcon(state.siteBundle, row.primary_title, row.author || "프로필", "profile-avatar")}
      <div>
        <h1>${escapeHtml(row.author || "작성자")}</h1>
        <span>${escapeHtml(row.primary_title?.name_ko || row.primary_title?.short_label_ko || "대표 칭호 준비중")}</span>
      </div>
    </div>
    <div class="profile-stats">
      <article><span>기록 수</span><strong>${formatInt(row.swim_count)}</strong></article>
      <article><span>총거리</span><strong>${formatDistance(row.total_distance_m)}</strong></article>
      <article><span>총시간</span><strong>${formatDurationLabel(row.total_seconds)}</strong></article>
      <article><span>평균 페이스</span><strong>${formatPaceFromRow(row)}</strong></article>
    </div>
    <a class="primary-link" href="${escapeHtml(row.profile_url || buildProfileUrl(row.author))}">프로필 보기</a>
  `);
}

function renderSearch() {
  const suggestions = getAuthorSuggestions(state.authorIndex).sort((left, right) => compareAuthors(left.author, right.author));
  setHtml("authorSuggestions", suggestions.map((row) => `<option value="${escapeHtml(row.author)}"></option>`).join(""));
  setHtml("mobileSuggestions", suggestions.slice(0, 8).map((row) => `
    <button type="button" data-mobile-author="${escapeHtml(row.author)}">${escapeHtml(row.author)}</button>
  `).join(""));
}

function renderOps() {
  setHtml("mobileOpsCard", `
    <div class="section-row">
      <h2>운영 상태</h2>
      <a href="./parse-status.html">검토</a>
    </div>
    <div class="ops-mini">
      <article><span>검토 대기</span><strong>${formatInt(getReviewCount())}건</strong></article>
      <article><span>배지 수</span><strong>${formatInt(state.badgeIndex?.badge_count)}개</strong></article>
    </div>
    <a class="primary-link" href="${buildDesktopUrl()}">데스크톱 화면 열기</a>
  `);
}

function recordRow(row) {
  return `
    <a class="record-row" href="${escapeHtml(row.url || "#")}" target="_blank" rel="noreferrer">
      <time>${escapeHtml(shortDate(row.post_date))}</time>
      <span>${escapeHtml(sourceLabel(row.source))}</span>
      <strong>${escapeHtml(formatDistance(row.distance_m))}</strong>
      <em>${escapeHtml(row.total_time_text || formatDurationLabel(row.total_seconds))}</em>
    </a>
  `;
}

function badgeRow(item, mode = "") {
  return `
    <article class="badge-row ${escapeHtml(mode)}">
      ${renderBadgeIcon(state.siteBundle, item, item.name_ko || item.badge_id, "badge-thumb")}
      <div>
        <strong>${escapeHtml(item.name_ko || item.short_label_ko || "배지")}</strong>
        <span>${escapeHtml(categoryLabelFromBundle(state.siteBundle, item.category))}</span>
      </div>
    </article>
  `;
}

function lineChart(rows, valueKey, labelFn, valueFn) {
  const values = rows.map((row) => Number(row[valueKey] || 0));
  const max = Math.max(...values, 1);
  const points = rows.map((row, index) => {
    const x = rows.length === 1 ? 50 : (index / (rows.length - 1)) * 100;
    const y = 86 - (Number(row[valueKey] || 0) / max) * 66;
    return { x, y, row, raw: Number(row[valueKey] || 0) };
  });
  return `
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0 86 H100 M0 64 H100 M0 42 H100 M0 20 H100" class="grid"/>
      <polyline points="${points.map((point) => `${point.x},${point.y}`).join(" ")}" class="line"/>
      ${points.map((point) => `<circle cx="${point.x}" cy="${point.y}" r="2" class="dot"/>`).join("")}
    </svg>
    <div class="mobile-chart-labels">
      ${points.map((point) => `<span><small>${escapeHtml(labelFn(point.row))}</small><strong>${escapeHtml(valueFn(point.raw))}</strong></span>`).join("")}
    </div>
  `;
}

function setActiveTab(tab) {
  state.activeTab = tab || "dashboard";
  document.querySelectorAll("[data-mobile-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.mobilePanel === state.activeTab);
  });
  document.querySelectorAll(".bottom-tabs [data-tab-target]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tabTarget === state.activeTab);
  });
  window.scrollTo({ top: 0 });
}

function getActiveView() {
  return getDashboardSeasonView(state.dashboard, state.activeSeasonKey);
}

function getReviewCount() {
  return Number(getActiveView()?.ops?.review_queue_count ?? state.reviewQueue.length ?? 0);
}

function buildReviewSummary(reasonCounts) {
  const parts = Object.entries(reasonCounts || {}).slice(0, 3).map(([key, value]) => `${key} ${value}`);
  return parts.length ? parts.join(" · ") : "OCR 충돌·본문 누락·수동 확인 대상이 여기에 표시됩니다.";
}

function averageMetricLabel(rows, metricKey) {
  const values = rows.map((row) => Number(row[metricKey] ?? row.metric_value ?? 0)).filter((value) => Number.isFinite(value));
  if (!values.length) return "-";
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
  if (metricKey === "total_distance_m") return formatDistance(avg);
  return `${formatInt(avg)}건`;
}

function formatPaceFromRow(row) {
  const distance = Number(row.total_distance_m || 0);
  const seconds = Number(row.total_seconds || 0);
  if (distance <= 0 || seconds <= 0) return "-";
  const pace = Math.round((seconds / distance) * 100);
  const minutes = Math.floor(pace / 60);
  return `${minutes}:${String(pace % 60).padStart(2, "0")}/100m`;
}

function shortDate(raw) {
  const text = String(raw || "");
  return text.length >= 10 ? text.slice(5, 10).replace("-", ".") : text || "-";
}

function resolveInitialSeasonKey() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("view");
  const options = getSeasonViewOptions(state.dashboard);
  if (requested && options.some((item) => item.view_key === requested)) return requested;
  const fallback = getDefaultSeasonViewKey(state.dashboard);
  const seasonViews = state.dashboard?.season_views?.views || {};
  const nonEmpty = options.find((item) => Number(seasonViews[item.view_key]?.summary?.swim_count || 0) > 0);
  return nonEmpty?.view_key || fallback;
}

function syncQuery() {
  const url = new URL(window.location.href);
  url.searchParams.set("view", state.activeSeasonKey || getDefaultSeasonViewKey(state.dashboard));
  window.history.replaceState({}, "", url);
}

function iconSvg(name) {
  const icons = {
    swimmer: '<path d="M3 15c4-3 7-3 11 0s7 3 11 0"/><path d="M3 20c4-3 7-3 11 0s7 3 11 0"/><circle cx="11" cy="6" r="3"/><path d="M6 12c4-5 9-7 15-5"/>',
    line: '<path d="M4 18 9 12l4 3 7-9"/><path d="M4 21h16"/>',
    donut: '<circle cx="12" cy="12" r="8"/><path d="M12 4v8l6 4"/>',
    bar: '<path d="M5 19V9h3v10M11 19V5h3v14M17 19v-7h3v7"/>',
    pace: '<path d="M4 14a8 8 0 1 1 16 0"/><path d="m12 14 4-4"/><path d="M7 20h10"/>',
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.line}</svg>`;
}

function clampRatio(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(1, numeric));
}

function setHtml(id, html) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = html || "";
}
