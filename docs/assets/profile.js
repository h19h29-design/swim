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
  getVisibleDateRangeLabel,
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
  siteBundle: null,
};

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    void init();
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
    const button = event.target.closest("[data-profile-author]");
    if (!button) return;
    const input = document.getElementById("profileAuthorSearch");
    if (input) input.value = button.dataset.profileAuthor || "";
    navigateToProfile();
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
  renderHero(profile);
  renderMetrics(profile);
  renderCompare(profile);
  renderBadges(profile);
  renderTrend(profile);
  renderRecords(profile);
}

function renderNav() {
  document.getElementById("profileNavLinks").innerHTML = [
    { label: "메인 대시보드", href: buildDesktopUrl() },
    { label: "모바일 보기", href: buildMobileUrl() },
    { label: "배지 갤러리", href: "./badge-gallery.html" },
    { label: "파싱 현황", href: "./parse-status.html" },
  ].map((item) => `<a class="nav-chip" href="${escapeHtml(item.href)}">${escapeHtml(item.label)}</a>`).join("");
}

function renderHero(profile) {
  const primaryTitle = profile.primary_title;
  const nextBadge = profile.next_badge_progress;

  setText("profileEyebrow", "내 수영 앨범");
  setText("profileTitle", `${profile.author}의 수영 앨범`);
  setText(
    "profileSubtitle",
    `${getVisibleDateRangeLabel(state.dashboard?.visible_date_range)} 기준으로 대표 칭호, 최근 28일 변화, 다음 해금을 정리했습니다.`,
  );
  setText(
    "profileGeneratedAt",
    state.authorProfiles?.generated_at ? `집계 갱신 ${state.authorProfiles.generated_at}` : "집계 생성 시각을 불러오는 중입니다.",
  );

  document.getElementById("profileHeroChips").innerHTML = [
    chip(profile.primary_title?.short_label_ko || "대표 칭호 대기중"),
    chip(`배지 ${formatInt(profile.unlocked_badge_count || 0)}개`),
    chip(getVisibleDateRangeLabel(state.dashboard?.visible_date_range)),
  ].join("");

  document.getElementById("profileHeroGrid").innerHTML = [
    `
      <article class="is-accent">
        <p class="section-kicker">대표 칭호</p>
        <h2>${escapeHtml(primaryTitle?.name_ko || "아직 대표 칭호가 없습니다")}</h2>
        <p class="record-note">${escapeHtml(primaryTitle?.description_ko || "누적 배지 티어가 가장 높은 칭호가 이 자리에 걸립니다.")}</p>
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
  ].join("");
}

function renderMetrics(profile) {
  const summary = profile.summary || {};
  const cards = [
    {
      label: "운동횟수",
      value: `${formatInt(summary.swim_count)}회`,
      note: "현재 집계 기간 누적입니다.",
    },
    {
      label: "총거리",
      value: formatDistance(summary.total_distance_m),
      note: "제목 양식으로 잡힌 누적 거리입니다.",
    },
    {
      label: "총시간",
      value: formatDurationLabel(summary.total_seconds),
      note: "누적 운동 시간입니다.",
    },
    {
      label: "시간당 거리",
      value: formatDistancePerHour(summary.distance_per_hour_m),
      note: "거리와 시간으로 계산한 효율입니다.",
    },
  ];

  document.getElementById("profileMetrics").innerHTML = cards.map((card) => `
    <article class="metric-card">
      <small>${escapeHtml(card.label)}</small>
      <strong>${escapeHtml(card.value)}</strong>
      <p class="note">${escapeHtml(card.note)}</p>
    </article>
  `).join("");
}

function renderCompare(profile) {
  const compare = profile.recent_28d_vs_previous_28d || {};
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

  document.getElementById("profileCompare").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">최근 28일 비교</p>
      <h2>이전 28일과 비교해서 얼마나 달라졌는지 봅니다</h2>
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
  `;
}

function renderBadges(profile) {
  const recentUnlocks = Array.isArray(profile.recent_unlocks) ? profile.recent_unlocks.slice(0, 6) : [];
  const counts = profile.badge_counts_by_category || {};

  document.getElementById("profileBadges").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">배지 선반</p>
      <h2>지금까지 모은 배지와 최근 해금</h2>
    </div>
    <div class="compare-grid">
      <article class="badge-card">
        <strong>보유 배지 요약</strong>
        <p class="record-note">카테고리별로 몇 개씩 열었는지 먼저 봅니다.</p>
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
        <p class="record-note">보유 배지 중 티어가 가장 높은 대표 칭호 후보가 개인 프로필 상단에 걸립니다.</p>
      </article>
    </div>
  `;
}

function renderTrend(profile) {
  const monthly = Array.isArray(profile.monthly_trend) ? profile.monthly_trend : [];
  const maxDistance = Math.max(1, ...monthly.map((row) => Number(row.total_distance_m || 0)));

  document.getElementById("profileTrend").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">월간 추이</p>
      <h2>월별 누적 거리 흐름</h2>
      <p class="note">${monthly.length ? "월별로 얼마나 꾸준히 쌓았는지 막대 그래프로 보여줍니다." : "월간 추이를 그릴 만큼 데이터가 아직 없습니다."}</p>
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
          <p class="record-note">제목 양식 기록이 더 쌓이면 이 칸이 채워집니다.</p>
        </article>
      `}
    </div>
  `;
}

function renderRecords(profile) {
  const recentRecords = Array.isArray(profile.recent_records) ? profile.recent_records.slice(0, 8) : [];
  document.getElementById("profileRecords").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">최근 기록</p>
      <h2>가장 최근에 반영된 수영 기록</h2>
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
          <p class="record-note">제목 양식으로 적힌 새 글이 들어오면 이 칸이 채워집니다.</p>
        </article>
      `}
    </div>
  `;
}

function renderEmpty() {
  const empty = document.getElementById("profileEmpty");
  empty.hidden = false;
  document.getElementById("profileHeroGrid").innerHTML = "";
  document.getElementById("profileMetrics").innerHTML = "";
  document.getElementById("profileCompare").innerHTML = "";
  document.getElementById("profileBadges").innerHTML = "";
  document.getElementById("profileTrend").innerHTML = "";
  document.getElementById("profileRecords").innerHTML = "";

  setText("profileEyebrow", "내 수영 앨범");
  setText("profileTitle", state.author ? `"${state.author}" 기록을 찾지 못했습니다` : "닉네임을 먼저 입력해 주세요");
  setText(
    "profileSubtitle",
    state.author ? "해당 닉네임으로 아직 공개 프로필이 생성되지 않았습니다." : "검색창에서 닉네임을 입력하면 개인 페이지를 바로 열 수 있습니다.",
  );
  setText(
    "profileGeneratedAt",
    state.authorProfiles?.generated_at ? `집계 갱신 ${state.authorProfiles.generated_at}` : "집계 생성 시각을 불러오는 중입니다.",
  );
  document.getElementById("profileHeroChips").innerHTML = "";
  empty.innerHTML = `<p>${escapeHtml(state.siteBundle?.site_config?.empty_state_ko || "제목 양식 기록이 아직 없어서 프로필을 만들지 못했습니다.")}</p>`;
}

function populateSuggestions() {
  const rows = getAuthorSuggestions(state.authorIndex).sort((left, right) => compareAuthors(left.author, right.author));
  document.getElementById("profileAuthorSuggestions").innerHTML = rows
    .map((row) => `<option value="${escapeHtml(row.author)}"></option>`)
    .join("");
  document.getElementById("profileAuthorSearch").value = state.author || "";
  document.getElementById("profileSuggestionRow").innerHTML = rows
    .slice(0, 8)
    .map((row) => `<button class="suggestion-chip" type="button" data-profile-author="${escapeHtml(row.author)}">${escapeHtml(row.author)}</button>`)
    .join("");
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

function navigateToProfile() {
  const query = String(document.getElementById("profileAuthorSearch")?.value || "").trim();
  if (!query) return;
  const author = findAuthorMatch(state.authorIndex, query);
  window.location.assign(buildProfileUrl(author));
}

function chip(label) {
  return `<span class="hero-chip">${escapeHtml(label)}</span>`;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value || "";
}
