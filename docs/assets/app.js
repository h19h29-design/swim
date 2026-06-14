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
  getDashboardSeasonView,
  getDefaultSeasonViewKey,
  getMetricGroup,
  getSeasonViewOptions,
  getViewDateRangeLabel,
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

const metricCycle = ["total_distance_m", "swim_count"];

const state = {
  dashboard: null,
  authorIndex: null,
  badgeIndex: null,
  reviewQueue: [],
  activeSeasonKey: null,
  activeMetric: "total_distance_m",
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
  state.activeSeasonKey = resolveInitialSeasonKey();
  state.activeMetric = resolveInitialMetric();

  bindEvents();
  render();
}

function bindEvents() {
  document.getElementById("seasonTabs")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-season-view]");
    if (!button) return;
    state.activeSeasonKey = button.dataset.seasonView;
    syncQuery();
    render();
  });

  document.getElementById("toggleMetricButton")?.addEventListener("click", () => {
    const currentIndex = metricCycle.indexOf(state.activeMetric);
    state.activeMetric = metricCycle[(currentIndex + 1) % metricCycle.length] || metricCycle[0];
    syncQuery();
    renderRanking();
  });

  document.getElementById("refreshButton")?.addEventListener("click", () => window.location.reload());
  document.getElementById("openProfileButton")?.addEventListener("click", openProfile);
  document.getElementById("authorSearch")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      openProfile();
    }
  });
}

function render() {
  renderChrome();
  renderSeasonTabs();
  renderKpis();
  renderHero();
  renderCharts();
  renderRanking();
  renderProfileSpotlight();
  renderRecentRecords();
  renderReviewStatus();
  renderBadges();
}

function renderChrome() {
  const activeView = getActiveDashboardView();
  const authors = getAuthorSuggestions(state.authorIndex).sort((a, b) => compareAuthors(a.author, b.author));
  setHtml("authorSuggestions", authors.map((row) => `<option value="${escapeHtml(row.author)}"></option>`).join(""));
  setText("summaryRangeLabel", getViewDateRangeLabel(activeView));
  setText("generatedAtLabel", activeView?.generated_at ? `최종 업데이트: ${activeView.generated_at}` : "업데이트 정보 없음");
  const firstAuthor = activeView?.authors?.[0]?.author || authors[0]?.author || "";
  const pill = document.getElementById("profilePill");
  if (pill && firstAuthor) {
    pill.href = buildProfileUrl(firstAuthor);
    pill.querySelector("span:last-child").textContent = firstAuthor;
  }
}

function renderSeasonTabs() {
  const options = getSeasonViewOptions(state.dashboard);
  setHtml("seasonTabs", options.map((item) => `
    <button class="season-tab${item.view_key === state.activeSeasonKey ? " is-active" : ""}" type="button" data-season-view="${escapeHtml(item.view_key)}">
      <span>${escapeHtml(item.short_label_ko || item.label_ko)}</span>
      <strong>${escapeHtml(item.label_ko)}</strong>
      <small>${escapeHtml(item.is_current ? "진행 중" : getViewDateRangeLabel(item))}</small>
    </button>
  `).join(""));
}

function renderKpis() {
  const activeView = getActiveDashboardView();
  const summary = activeView?.summary || {};
  const growth = summary.growth?.metrics || {};
  const reviewCount = Number(activeView?.ops?.review_queue_count ?? state.reviewQueue.length ?? 0);
  const cards = [
    {
      icon: "wave",
      tone: "blue",
      title: "이번 시즌 총거리",
      value: formatDistance(summary.total_distance_m),
      meta: growth.distance_m ? growthText(growth.distance_m, "distance") : "지난 시즌 대비 준비 중",
    },
    {
      icon: "clipboard",
      tone: "teal",
      title: "공식 반영 기록",
      value: `${formatInt(summary.swim_count)}건`,
      meta: growth.swim_count ? growthText(growth.swim_count, "count") : "제목·본문·OCR 리졸버 기준",
    },
    {
      icon: "users",
      tone: "violet",
      title: "활성 작성자",
      value: `${formatInt(summary.active_authors)}명`,
      meta: "집계 기간 안의 고정닉 기준",
    },
    {
      icon: "clock",
      tone: "orange",
      title: "검토 대기",
      value: `${formatInt(reviewCount)}건`,
      meta: "충돌·저신뢰·누락 후보 포함",
    },
  ];

  setHtml("kpiGrid", cards.map((card) => `
    <article class="kpi-card ${escapeHtml(card.tone)}">
      <span class="kpi-icon">${iconSvg(card.icon)}</span>
      <div>
        <h2>${escapeHtml(card.title)}</h2>
        <strong>${escapeHtml(card.value)}</strong>
        <p>${escapeHtml(card.meta)}</p>
      </div>
    </article>
  `).join(""));
}

function renderHero() {
  const activeView = getActiveDashboardView();
  const gallery = activeView?.gallery || {};
  const current = gallery.current_title || {};
  const next = gallery.next_title_target || {};
  const progress = gallery.progress || {};
  const ratio = clampRatio(progress.progress_ratio || next.progress_ratio || 0);
  const currentValue = progress.current_value_text_ko || gallery.metric_value_text_ko || formatDistance(activeView?.summary?.total_distance_m);
  const targetValue = progress.target_value_text_ko || next.target_value_text_ko || "-";

  setHtml("seasonHero", `
    <div class="hero-watermark" aria-hidden="true">${iconSvg("swimmer")}</div>
    <div class="hero-title-block">
      <span class="section-label">${escapeHtml(activeView?.theme_label_ko || "Deep Lane Club")}</span>
      <h1>${escapeHtml(current.name_ko || "물결 준비중")}</h1>
      <p>${escapeHtml(current.description_ko || "우리 갤러리의 여정은 계속됩니다.")}</p>
    </div>
    <div class="hero-progress-block">
      <div class="hero-progress-head">
        <span>다음 칭호까지</span>
        <strong>${escapeHtml(progress.remaining_value_text_ko || next.remaining_value_text_ko || "계산 중")}</strong>
      </div>
      <div class="progress-track"><span style="width:${Math.round(ratio * 100)}%"></span></div>
      <div class="hero-progress-meta">
        <span>${escapeHtml(currentValue)} / ${escapeHtml(targetValue)}</span>
        <span>${Math.round(ratio * 100)}%</span>
      </div>
    </div>
    <div class="hero-next-badge">
      ${renderBadgeIcon(state.siteBundle, next, next.name_ko || "다음 칭호", "hero-badge-icon")}
      <span>다음 칭호</span>
      <strong>${escapeHtml(next.short_label_ko || next.name_ko || "대기중")}</strong>
    </div>
  `);
}

function renderCharts() {
  const activeView = getActiveDashboardView();
  renderWeeklyChart(activeView);
  renderSourceDonut(activeView);
  renderMonthlyChart(activeView);
  renderPaceChart(activeView);
}

function renderWeeklyChart(activeView) {
  const daily = getDailyRows(activeView).slice(-8);
  if (!daily.length) {
    setHtml("weeklyChart", emptyState("주간 거리 데이터가 아직 없습니다."));
    return;
  }
  setHtml("weeklyChart", lineChart(daily, "total_distance_m", (row) => shortDate(row.date), (value) => `${(Number(value) / 1000).toFixed(1)}km`));
}

function renderSourceDonut(activeView) {
  const counts = activeView?.summary?.included_source_counts || activeView?.summary?.source_counts || {};
  const entries = Object.entries(counts).filter(([, value]) => Number(value) > 0);
  if (!entries.length) {
    setHtml("strokeChart", emptyState("영법 또는 출처 비중 데이터가 아직 없습니다."));
    return;
  }
  const total = entries.reduce((sum, [, value]) => sum + Number(value || 0), 0);
  let cursor = 0;
  const colors = ["#1d7cf2", "#1fc4c6", "#ff9f2e", "#7258f2", "#0f2f68"];
  const stops = entries.map(([key, value], index) => {
    const start = cursor;
    cursor += (Number(value) / total) * 100;
    return `${colors[index % colors.length]} ${start}% ${cursor}%`;
  }).join(", ");
  setHtml("strokeChart", `
    <div class="donut" style="background:conic-gradient(${stops})"><strong>${formatInt(total)}건</strong></div>
    <div class="donut-legend">
      ${entries.map(([key, value], index) => `
        <span><i style="background:${colors[index % colors.length]}"></i>${escapeHtml(sourceLabel(key))} ${formatInt(value)}건</span>
      `).join("")}
    </div>
  `);
}

function renderMonthlyChart(activeView) {
  const rows = Array.isArray(activeView?.monthly) ? activeView.monthly.slice(-6) : [];
  if (!rows.length) {
    setHtml("monthlyChart", emptyState("월별 누적 데이터가 아직 없습니다."));
    return;
  }
  const max = Math.max(...rows.map((row) => Number(row.total_distance_m || 0)), 1);
  setHtml("monthlyChart", rows.map((row) => {
    const value = Number(row.total_distance_m || 0);
    return `
      <div class="bar-item">
        <div class="bar-track"><span style="height:${Math.max(6, (value / max) * 100)}%"></span></div>
        <strong>${escapeHtml(formatDistance(value))}</strong>
        <small>${escapeHtml(monthLabel(row.month))}</small>
      </div>
    `;
  }).join(""));
}

function renderPaceChart(activeView) {
  const recent = Array.isArray(activeView?.recent_records) ? activeView.recent_records.slice(0, 8).reverse() : [];
  const rows = recent
    .filter((row) => Number(row.distance_m) > 0 && Number(row.total_seconds) > 0)
    .map((row) => ({ ...row, pace_seconds: (Number(row.total_seconds) / Number(row.distance_m)) * 100 }));
  if (!rows.length) {
    setText("paceAverageChip", "시즌 평균 없음");
    setHtml("paceChart", emptyState("평균 페이스를 계산할 기록이 아직 없습니다."));
    return;
  }
  const average = rows.reduce((sum, row) => sum + row.pace_seconds, 0) / rows.length;
  setText("paceAverageChip", `시즌 평균 ${formatPace(average)}`);
  setHtml("paceChart", lineChart(rows, "pace_seconds", (row) => shortDate(row.post_date), formatPace, { invert: true }));
}

function getDailyRows(activeView) {
  if (Array.isArray(activeView?.time_series?.daily) && activeView.time_series.daily.length) {
    return activeView.time_series.daily;
  }
  const bucket = new Map();
  (activeView?.recent_records || []).forEach((row) => {
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

function renderRanking() {
  const activeView = getActiveDashboardView();
  const group = getMetricGroup(activeView, state.activeMetric);
  const rows = group.rows?.length ? group.rows : [...(group.top3 || []), ...(group.ranks_4_to_20 || [])];
  const topRows = rows.slice(0, 10);
  setText("rankingMetricLabel", group.label_ko || metricLabel(state.activeMetric));
  setText("toggleMetricButton", state.activeMetric === "total_distance_m" ? "참여횟수 랭킹 보기" : "거리 랭킹 보기");

  setHtml("rankingList", topRows.length ? topRows.map((row, index) => `
    <a class="rank-line" href="${escapeHtml(row.profile_url || buildProfileUrl(row.author))}">
      <span class="rank-medal">${rankLabel(row.rank || index + 1)}</span>
      <strong>${escapeHtml(row.author || "작성자 없음")}</strong>
      <span>${escapeHtml(row.metric_value_text_ko || "-")}</span>
      <small>${escapeHtml(row.secondary_text_ko || row.latest_post_date || "")}</small>
    </a>
  `).join("") : emptyState("선택한 시즌 랭킹 데이터가 아직 없습니다."));
}

function renderProfileSpotlight() {
  const activeView = getActiveDashboardView();
  const row = activeView?.authors?.[0] || null;
  if (!row) {
    setHtml("profileSpotlight", `
      <div class="card-title-row"><h3>오늘의 프로필</h3></div>
      ${emptyState("아직 표시할 프로필이 없습니다.")}
    `);
    return;
  }
  setHtml("profileSpotlight", `
    <div class="profile-cover"></div>
    <div class="profile-row">
      ${renderBadgeIcon(state.siteBundle, row.primary_title, row.author || "대표 프로필", "profile-avatar")}
      <div>
        <span class="section-label">오늘의 프로필</span>
        <h3>${escapeHtml(row.author || "작성자")}</h3>
        <p>${escapeHtml(row.primary_title?.name_ko || row.primary_title?.short_label_ko || "대표 칭호 준비중")}</p>
      </div>
    </div>
    <div class="profile-stats">
      <span><strong>${escapeHtml(row.metric_value_text_ko || formatDistance(row.total_distance_m))}</strong><small>랭킹 지표</small></span>
      <span><strong>${formatInt(row.swim_count)}건</strong><small>기록 수</small></span>
      <span><strong>${formatDurationLabel(row.total_seconds)}</strong><small>총시간</small></span>
    </div>
    <a class="wide-button" href="${escapeHtml(row.profile_url || buildProfileUrl(row.author))}">프로필 보기</a>
  `);
}

function renderRecentRecords() {
  const activeView = getActiveDashboardView();
  const rows = Array.isArray(activeView?.recent_records) ? activeView.recent_records.slice(0, 6) : [];
  setHtml("recentRecords", rows.length ? rows.map((row) => `
    <a class="record-line" href="${escapeHtml(row.url || "#")}" target="_blank" rel="noreferrer">
      <time>${escapeHtml(shortDate(row.post_date))}</time>
      <strong>${escapeHtml(formatDistance(row.distance_m))}</strong>
      <span>${escapeHtml(row.total_time_text || formatDurationLabel(row.total_seconds))}</span>
      <small>${escapeHtml(row.author || "작성자")} · ${escapeHtml(sourceLabel(row.source))}</small>
    </a>
  `).join("") : emptyState("최근 반영 기록이 아직 없습니다."));
}

function renderReviewStatus() {
  const activeView = getActiveDashboardView();
  const ops = activeView?.ops || {};
  const reviewCount = Number(ops.review_queue_count ?? state.reviewQueue.length ?? 0);
  const reasonCounts = ops.review_reason_counts || {};
  const ocrIssues = Object.entries(reasonCounts).filter(([key]) => key.startsWith("OCR_"));
  const statusCards = [
    ["OCR 정상", formatInt(Math.max(0, Number(activeView?.summary?.swim_count || 0))), "자동 반영 기록"],
    ["충돌", formatInt(reasonCounts.CANDIDATE_CONFLICT || 0), "후보 불일치"],
    ["저신뢰", formatInt(reasonCounts.OCR_LOW_CONFIDENCE || 0), "OCR 재검토"],
    ["검토 대기", formatInt(reviewCount), "전체 큐"],
  ];

  setHtml("reviewStatus", `
    <div class="status-grid">
      ${statusCards.map(([label, value, note]) => `
        <article>
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
          <small>${escapeHtml(note)}</small>
        </article>
      `).join("")}
    </div>
    <div class="review-table">
      ${(state.reviewQueue || []).slice(0, 5).map((row) => `
        <a href="${escapeHtml(row.url || "#")}" target="_blank" rel="noreferrer">
          <span>${escapeHtml(row.post_date || "-")}</span>
          <strong>${escapeHtml(row.author || "작성자")}</strong>
          <em>${escapeHtml(row.review_reason_code || row.exclude_reason_code || "검토 필요")}</em>
        </a>
      `).join("") || `<p class="empty-note">검토 대기 글이 없습니다.</p>`}
    </div>
    ${ocrIssues.length ? `<p class="empty-note">OCR 이슈: ${escapeHtml(ocrIssues.map(([key, value]) => `${key} ${value}`).join(" · "))}</p>` : ""}
  `);
}

function renderBadges() {
  const activeView = getActiveDashboardView();
  const unlocks = Array.isArray(activeView?.recent_unlocks) ? activeView.recent_unlocks.slice(0, 6) : [];
  setHtml("recentUnlocks", unlocks.length ? unlocks.map((item) => `
    <article class="badge-item">
      ${renderBadgeIcon(state.siteBundle, item, item.name_ko || item.badge_id, "badge-thumb")}
      <strong>${escapeHtml(item.short_label_ko || item.name_ko || "배지")}</strong>
      <span>${escapeHtml(categoryLabelFromBundle(state.siteBundle, item.category))}</span>
    </article>
  `).join("") : emptyState("최근 해금 배지가 아직 없습니다."));
}

function openProfile() {
  const query = String(document.getElementById("authorSearch")?.value || "").trim();
  if (!query) return;
  const author = findAuthorMatch(state.authorIndex, query);
  window.location.assign(buildProfileUrl(author));
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

function resolveInitialMetric() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("metric");
  return metricCycle.includes(requested) ? requested : metricCycle[0];
}

function syncQuery() {
  const url = new URL(window.location.href);
  url.searchParams.set("desktop", "1");
  url.searchParams.set("view", state.activeSeasonKey || getDefaultSeasonViewKey(state.dashboard));
  url.searchParams.set("metric", state.activeMetric);
  window.history.replaceState({}, "", url);
}

function getActiveDashboardView() {
  return getDashboardSeasonView(state.dashboard, state.activeSeasonKey);
}

function lineChart(rows, valueKey, labelFn, valueFn, options = {}) {
  const values = rows.map((row) => Number(row[valueKey] || 0));
  const max = Math.max(...values, 1);
  const min = options.invert ? Math.min(...values, max) : 0;
  const span = Math.max(max - min, 1);
  const points = rows.map((row, index) => {
    const x = rows.length === 1 ? 50 : (index / (rows.length - 1)) * 100;
    const raw = Number(row[valueKey] || 0);
    const normalized = options.invert ? (max - raw) / span : (raw - min) / span;
    const y = 86 - normalized * 66;
    return { x, y, row, raw };
  });
  const polyline = points.map((point) => `${point.x},${point.y}`).join(" ");
  return `
    <svg class="line-chart" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0 86 H100 M0 64 H100 M0 42 H100 M0 20 H100" class="grid-lines"/>
      <polyline points="${polyline}" class="line-path"/>
      ${points.map((point) => `<circle cx="${point.x}" cy="${point.y}" r="1.8" class="line-dot"/>`).join("")}
    </svg>
    <div class="chart-labels">
      ${points.map((point) => `<span><small>${escapeHtml(labelFn(point.row))}</small><strong>${escapeHtml(valueFn(point.raw))}</strong></span>`).join("")}
    </div>
  `;
}

function emptyState(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function growthText(metric, type) {
  const delta = Number(metric.delta_value || 0);
  if (type === "distance") return delta >= 0 ? `${formatDistance(delta)} 증가` : `${formatDistance(Math.abs(delta))} 감소`;
  return delta >= 0 ? `+${formatInt(delta)}건` : `-${formatInt(Math.abs(delta))}건`;
}

function rankLabel(rank) {
  const numeric = Number(rank);
  return `${numeric || "-"}위`;
}

function formatPace(secondsPer100m) {
  const seconds = Math.max(0, Math.round(Number(secondsPer100m || 0)));
  const minutes = Math.floor(seconds / 60);
  const remain = seconds % 60;
  return `${minutes}:${String(remain).padStart(2, "0")}/100m`;
}

function shortDate(raw) {
  const text = String(raw || "");
  return text.length >= 10 ? text.slice(5, 10).replace("-", "/") : text || "-";
}

function monthLabel(raw) {
  const text = String(raw || "");
  return text.length >= 7 ? `${Number(text.slice(5, 7))}월` : text || "-";
}

function iconSvg(name) {
  const icons = {
    wave: '<path d="M3 15c4-4 7-4 11 0s7 4 11 0" /><path d="M3 20c4-4 7-4 11 0s7 4 11 0" /><circle cx="12" cy="7" r="3" /><path d="M8 12c4-5 8-7 14-5" />',
    clipboard: '<rect x="6" y="5" width="12" height="16" rx="2" /><path d="M9 5a3 3 0 0 1 6 0" /><path d="M9 12h6M9 16h4" />',
    users: '<circle cx="9" cy="8" r="3" /><circle cx="17" cy="9" r="2.5" /><path d="M3 20c1-4 3-6 6-6s5 2 6 6" /><path d="M14 20c.5-3 2-5 5-5 2 0 3.5 1.4 4 5" />',
    clock: '<circle cx="12" cy="12" r="9" /><path d="M12 7v6l4 2" />',
    swimmer: '<path d="M3 15c4-3 7-3 11 0s7 3 11 0" /><path d="M3 20c4-3 7-3 11 0s7 3 11 0" /><circle cx="11" cy="6" r="3" /><path d="M6 12c4-5 9-7 15-5" />',
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.wave}</svg>`;
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

function setHtml(id, html) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = html || "";
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    init().catch((error) => {
      console.error(error);
      setHtml("reviewStatus", emptyState("페이지 렌더링 중 오류가 발생했습니다."));
    });
  });
}
