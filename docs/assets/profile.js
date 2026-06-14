import {
  buildDesktopUrl,
  buildMobileUrl,
  buildProfileUrl,
  categoryLabelFromBundle,
  compareAuthors,
  escapeHtml,
  findAuthorMatch,
  formatDistance,
  formatDistancePerHour,
  formatDurationLabel,
  formatInt,
  formatSignedDistance,
  formatSignedDuration,
  formatSignedInt,
  getAuthorProfile,
  getAuthorSuggestions,
  getDefaultSeasonViewKey,
  getSeasonViewOptions,
  getViewDateRangeLabel,
  loadAuthorIndex,
  loadAuthorProfiles,
  loadDashboardViews,
  loadPublicSiteConfig,
  mergeSiteBundles,
  renderBadgeIcon,
} from "./dashboard-common.js?v=20260323a";

const CATEGORY_ORDER = ["attendance", "distance", "time", "efficiency", "growth", "season", "gallery", "fun"];

const state = {
  dashboard: null,
  authorIndex: null,
  authorProfiles: null,
  author: "",
  activeSeasonKey: null,
  siteBundle: null,
};

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    init().catch((error) => {
      console.error(error);
      setText("profileTitle", "프로필을 불러오지 못했습니다");
    });
  });
}

async function init() {
  const [dashboard, authorIndex, authorProfiles, publicSiteConfig] = await Promise.all([
    loadDashboardViews(),
    loadAuthorIndex(),
    loadAuthorProfiles(),
    loadPublicSiteConfig(),
  ]);

  state.dashboard = dashboard;
  state.authorIndex = authorIndex;
  state.authorProfiles = authorProfiles;
  state.siteBundle = mergeSiteBundles(publicSiteConfig, dashboard, authorProfiles);
  state.author = resolveAuthorFromQuery();
  state.activeSeasonKey = resolveInitialSeasonKey();

  bindEvents();
  populateSuggestions();
  render();
}

function resolveAuthorFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("author") || "";
  return findAuthorMatch(state.authorIndex, raw);
}

function bindEvents() {
  document.addEventListener("submit", (event) => {
    const form = event.target.closest("#profileSearchForm");
    if (!form) return;
    event.preventDefault();
    navigateToProfile();
  });

  document.addEventListener("click", (event) => {
    const authorButton = event.target.closest("[data-profile-author]");
    if (authorButton) {
      const input = document.getElementById("profileAuthorSearch");
      if (input) input.value = authorButton.dataset.profileAuthor || "";
      navigateToProfile();
      return;
    }

    const seasonButton = event.target.closest("[data-profile-season]");
    if (seasonButton) {
      state.activeSeasonKey = seasonButton.dataset.profileSeason;
      syncSeasonQuery();
      render();
    }
  });
}

function render() {
  renderNav();
  const profile = getAuthorProfile(state.authorProfiles, state.author);
  if (!profile) {
    renderEmpty();
    return;
  }

  document.getElementById("profileEmpty").hidden = true;
  const profileView = getProfileSeasonView(profile);
  renderHero(profile, profileView);
  renderSeason(profileView);
  renderMetrics(profileView);
  renderCompare(profileView);
  renderBadges(profile);
  renderTrend(profileView);
  renderRecords(profileView);
}

function renderNav() {
  setHtml("profileNavLinks", [
    { label: "메인 대시보드", href: buildDesktopUrl() },
    { label: "모바일 보기", href: buildMobileUrl() },
    { label: "배지 갤러리", href: "./badge-gallery.html" },
    { label: "파싱 현황", href: "./parse-status.html" },
  ].map((item) => `<a class="nav-chip" href="${escapeHtml(item.href)}">${escapeHtml(item.label)}</a>`).join(""));
}

function renderHero(profile, profileView) {
  const primaryTitle = profile.primary_title;

  setText("profileEyebrow", "SWIMMER PROFILE");
  setText("profileTitle", `${profile.author}님의 수영 프로필`);
  setText("profileSubtitle", `${profileView?.label_ko || "시즌"} 기준 기록과 누적 배지 상태를 함께 보여줍니다.`);
  setText("profileGeneratedAt", state.authorProfiles?.generated_at ? `집계 갱신 ${state.authorProfiles.generated_at}` : "집계 생성 시각 정보가 없습니다.");

  setHtml("profileHeroChips", [
    chip(primaryTitle?.short_label_ko || "대표 칭호 대기중"),
    chip(`배지 ${formatInt(profile.unlocked_badge_count || profile.unlocked_badges?.length || 0)}개`),
    chip(`${profileView?.short_label_ko || "S2"} · ${getViewDateRangeLabel(profileView)}`),
  ].join(""));

  const nextBadge = profile.next_badge_progress;
  setHtml("profileHeroGrid", [
    `
      <article class="is-accent">
        <p class="section-kicker">대표 칭호</p>
        <h2>${escapeHtml(primaryTitle?.name_ko || "아직 대표 칭호가 없습니다")}</h2>
        <p class="record-note">${escapeHtml(primaryTitle?.description_ko || "누적 배지가 쌓이면 가장 높은 칭호가 이 자리에 걸립니다.")}</p>
        <div class="hero-meta-row">
          ${primaryTitle?.icon_key ? renderBadgeIcon(state.siteBundle, primaryTitle, primaryTitle.name_ko || "대표 칭호", "inline-badge-icon") : ""}
          ${primaryTitle?.short_label_ko ? `<span class="hero-chip">${escapeHtml(primaryTitle.short_label_ko)}</span>` : ""}
        </div>
      </article>
    `,
    `
      <article class="is-mint">
        <p class="section-kicker">다음 해금</p>
        <h2>${escapeHtml(nextBadge?.name_ko || "다음 배지 계산 중")}</h2>
        <p class="record-note">${escapeHtml(nextBadge?.remaining_value_text_ko || "다음 해금 목표를 계산하는 중입니다.")}</p>
        <div class="hero-meta-row">
          ${nextBadge?.icon_key ? renderBadgeIcon(state.siteBundle, nextBadge, nextBadge.name_ko || "다음 해금", "inline-badge-icon") : ""}
          ${nextBadge?.target_value_text_ko ? `<span class="hero-chip">목표 ${escapeHtml(nextBadge.target_value_text_ko)}</span>` : ""}
        </div>
      </article>
    `,
  ].join(""));
}

function renderSeason(profileView) {
  const options = getSeasonViewOptions(state.dashboard);
  setHtml("profileSeason", `
    <div class="panel-head">
      <p class="section-kicker">PROFILE SEASON VIEW</p>
      <h2>${escapeHtml(profileView?.theme_label_ko || profileView?.label_ko || "시즌별 기록")}</h2>
      <p class="note">요약, 성장 비교, 월별 추이, 최근 기록이 선택한 시즌으로 바뀝니다.</p>
    </div>
    <div class="season-tabs">
      ${options.map((item) => `
        <button class="season-tab${item.view_key === state.activeSeasonKey ? " is-active" : ""}" type="button" data-profile-season="${escapeHtml(item.view_key)}">
          <span>${escapeHtml(item.short_label_ko || item.label_ko)}</span>
          <strong>${escapeHtml(item.label_ko)}</strong>
        </button>
      `).join("")}
    </div>
  `);
}

function renderMetrics(profileView) {
  const summary = profileView?.summary || {};
  const cards = [
    { label: "운동횟수", value: `${formatInt(summary.swim_count)}회`, note: "선택한 시즌의 공식 반영 횟수입니다." },
    { label: "총거리", value: formatDistance(summary.total_distance_m), note: "선택한 시즌에 쌓인 거리입니다." },
    { label: "총시간", value: formatDurationLabel(summary.total_seconds), note: "선택한 시즌의 운동 시간입니다." },
    { label: "시간당 거리", value: formatDistancePerHour(summary.distance_per_hour_m), note: "거리와 시간으로 계산한 효율입니다." },
  ];

  setHtml("profileMetrics", cards.map((card) => `
    <article class="metric-card">
      <small>${escapeHtml(card.label)}</small>
      <strong>${escapeHtml(card.value)}</strong>
      <p class="note">${escapeHtml(card.note)}</p>
    </article>
  `).join(""));
}

function renderCompare(profileView) {
  const compare = profileView?.recent_28d_vs_previous_28d || {};
  const metrics = compare.metrics || {};
  const rows = [
    {
      label: "최근 28일 수영 횟수",
      delta: formatSignedInt(metrics.swim_count?.delta_value),
      detail: `${formatInt(metrics.swim_count?.recent_value)}회 / 이전 ${formatInt(metrics.swim_count?.previous_value)}회`,
    },
    {
      label: "최근 28일 거리",
      delta: formatSignedDistance(metrics.distance_m?.delta_value),
      detail: `${formatDistance(metrics.distance_m?.recent_value)} / 이전 ${formatDistance(metrics.distance_m?.previous_value)}`,
    },
    {
      label: "최근 28일 시간",
      delta: formatSignedDuration(metrics.total_seconds?.delta_value),
      detail: `${formatDurationLabel(metrics.total_seconds?.recent_value)} / 이전 ${formatDurationLabel(metrics.total_seconds?.previous_value)}`,
    },
  ];

  setHtml("profileCompare", `
    <div class="panel-head">
      <p class="section-kicker">최근 28일 비교</p>
      <h2>이전 28일과 비교한 성장</h2>
      <p class="note">${escapeHtml(`${compare.recent_window?.start || "-"} ~ ${compare.recent_window?.end || "-"}`)}</p>
    </div>
    <div class="compare-grid">
      ${rows.map((row) => `
        <article class="compare-row">
          <small>${escapeHtml(row.label)}</small>
          <strong>${escapeHtml(row.delta)}</strong>
          <p class="record-note">${escapeHtml(row.detail)}</p>
        </article>
      `).join("")}
    </div>
  `);
}

function renderBadges(profile) {
  const recentUnlocks = Array.isArray(profile.recent_unlocks) ? profile.recent_unlocks.slice(0, 6) : [];
  const counts = profile.badge_counts_by_category || {};

  setHtml("profileBadges", `
    <div class="panel-head">
      <p class="section-kicker">누적 배지</p>
      <h2>보유 배지와 최근 해금</h2>
      <p class="note">배지는 시즌을 넘어 누적 프로필의 정체성으로 표시합니다.</p>
    </div>
    <div class="compare-grid">
      <article class="badge-card">
        <strong>보유 배지 요약</strong>
        <p class="record-note">카테고리별 해금 개수입니다.</p>
        <div class="badge-chip-row">
          ${CATEGORY_ORDER.map((key) => `<span class="badge-chip">${escapeHtml(categoryLabelFromBundle(state.siteBundle, key))} ${escapeHtml(String(counts[key] || 0))}</span>`).join("")}
        </div>
      </article>
      <article class="badge-card">
        <strong>최근 해금</strong>
        <p class="record-note">가장 최근에 열린 배지입니다.</p>
        <div class="badge-chip-row">${buildRecentUnlockChips(recentUnlocks)}</div>
      </article>
      <article class="badge-card">
        <strong>대표 칭호 규칙</strong>
        <p class="record-note">보유 배지 중 우선순위가 높은 칭호 후보가 프로필 상단에 걸립니다.</p>
      </article>
    </div>
  `);
}

function renderTrend(profileView) {
  const monthly = Array.isArray(profileView?.monthly_trend) ? profileView.monthly_trend : [];
  const maxDistance = Math.max(1, ...monthly.map((row) => Number(row.total_distance_m || 0)));

  setHtml("profileTrend", `
    <div class="panel-head">
      <p class="section-kicker">월간 추이</p>
      <h2>${escapeHtml(profileView?.label_ko || "시즌")} 월별 거리 흐름</h2>
      <p class="note">${monthly.length ? "월별로 얼마나 쌓였는지 막대 그래프로 보여줍니다." : "월간 추이를 그릴 기록이 아직 없습니다."}</p>
    </div>
    <div class="record-list">
      ${monthly.length ? monthly.map((row) => `
        <div class="trend-row">
          <div class="bar-label">${escapeHtml(row.month || "-")} · ${escapeHtml(formatDistance(row.total_distance_m))}</div>
          <div class="bar"><span style="width:${Math.round((Number(row.total_distance_m || 0) / maxDistance) * 100)}%"></span></div>
        </div>
      `).join("") : `
        <article class="record-card">
          <strong>월간 추이가 아직 비어 있습니다.</strong>
          <p class="record-note">선택한 시즌에 기록이 쌓이면 차트가 채워집니다.</p>
        </article>
      `}
    </div>
  `);
}

function renderRecords(profileView) {
  const recentRecords = Array.isArray(profileView?.recent_records) ? profileView.recent_records.slice(0, 8) : [];
  setHtml("profileRecords", `
    <div class="panel-head">
      <p class="section-kicker">최근 기록</p>
      <h2>${escapeHtml(profileView?.label_ko || "시즌")} 최근 반영 기록</h2>
    </div>
    <div class="record-list">
      ${recentRecords.length ? recentRecords.map((row) => `
        <article class="record-card">
          <strong>${escapeHtml(row.post_date || "-")}</strong>
          <p class="record-note">${escapeHtml(`${formatDistance(row.distance_m)} · ${row.total_time_text || formatDurationLabel(row.total_seconds)}`)}</p>
        </article>
      `).join("") : `
        <article class="record-card">
          <strong>최근 기록이 아직 없습니다.</strong>
          <p class="record-note">선택한 시즌에 반영된 글이 생기면 여기에 표시됩니다.</p>
        </article>
      `}
    </div>
  `);
}

function renderEmpty() {
  const empty = document.getElementById("profileEmpty");
  empty.hidden = false;
  ["profileSeason", "profileHeroGrid", "profileMetrics", "profileCompare", "profileBadges", "profileTrend", "profileRecords"].forEach((id) => setHtml(id, ""));

  setText("profileEyebrow", "SWIMMER PROFILE");
  setText("profileTitle", state.author ? `"${state.author}" 기록을 찾지 못했습니다` : "닉네임을 먼저 입력해 주세요");
  setText("profileSubtitle", state.author ? "해당 닉네임으로 아직 공개 프로필이 생성되지 않았습니다." : "검색창에서 닉네임을 입력하면 개인 프로필을 바로 열 수 있습니다.");
  setText("profileGeneratedAt", state.authorProfiles?.generated_at ? `집계 갱신 ${state.authorProfiles.generated_at}` : "집계 생성 시각 정보가 없습니다.");
  setHtml("profileHeroChips", "");
  empty.innerHTML = `<p>${escapeHtml(state.siteBundle?.site_config?.empty_state_ko || "공식 반영 기록이 아직 없어 프로필을 만들지 못했습니다.")}</p>`;
}

function populateSuggestions() {
  const rows = getAuthorSuggestions(state.authorIndex).sort((left, right) => compareAuthors(left.author, right.author));
  setHtml("profileAuthorSuggestions", rows.map((row) => `<option value="${escapeHtml(row.author)}"></option>`).join(""));
  const input = document.getElementById("profileAuthorSearch");
  if (input) input.value = state.author || "";
  setHtml("profileSuggestionRow", rows.slice(0, 8).map((row) => `<button class="suggestion-chip" type="button" data-profile-author="${escapeHtml(row.author)}">${escapeHtml(row.author)}</button>`).join(""));
}

function buildRecentUnlockChips(rows) {
  return rows.length
    ? rows.map((row) => `
      <span class="badge-chip">
        ${row.icon_key ? renderBadgeIcon(state.siteBundle, row, row.name_ko || row.badge_id, "inline-badge-icon") : ""}
        ${escapeHtml(row.name_ko || row.short_label_ko || row.badge_id || "배지")}
      </span>
    `).join("")
    : '<span class="badge-chip">최근 해금 없음</span>';
}

function getProfileSeasonView(profile) {
  const views = profile?.season_views?.views || {};
  return views[state.activeSeasonKey] || views[getDefaultSeasonViewKey(state.dashboard)] || profile;
}

function resolveInitialSeasonKey() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("view");
  const options = getSeasonViewOptions(state.dashboard);
  if (requested && options.some((item) => item.view_key === requested)) {
    return requested;
  }
  return getDefaultSeasonViewKey(state.dashboard);
}

function syncSeasonQuery() {
  const url = new URL(window.location.href);
  url.searchParams.set("author", state.author || "");
  url.searchParams.set("view", state.activeSeasonKey || getDefaultSeasonViewKey(state.dashboard));
  url.searchParams.set("v", "20260317a");
  window.history.replaceState({}, "", url);
}

function navigateToProfile() {
  const query = String(document.getElementById("profileAuthorSearch")?.value || "").trim();
  if (!query) return;
  const author = findAuthorMatch(state.authorIndex, query);
  const url = new URL(buildProfileUrl(author), window.location.href);
  url.searchParams.set("view", state.activeSeasonKey || getDefaultSeasonViewKey(state.dashboard));
  window.location.assign(url.pathname.split("/").pop() + url.search);
}

function chip(label) {
  return `<span class="hero-chip">${escapeHtml(label)}</span>`;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value || "";
}

function setHtml(id, html) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = html || "";
}
