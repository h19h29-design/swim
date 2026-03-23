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
  sliceTopThree,
  sourceLabel,
} from "./dashboard-common.js?v=20260317d";

const state = {
  dashboard: null,
  authorIndex: null,
  badgeIndex: null,
  reviewQueue: [],
  siteBundle: null,
};

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    void init();
  });
}

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

  bindEvents();
  render();
}

function bindEvents() {
  document.addEventListener("submit", (event) => {
    const form = event.target.closest("#mobileSearchForm");
    if (!form) return;
    event.preventDefault();
    openProfile();
  });

  document.addEventListener("click", (event) => {
    const authorButton = event.target.closest("[data-mobile-author]");
    if (authorButton) {
      const author = authorButton.dataset.mobileAuthor || "";
      const input = document.getElementById("mobileAuthorSearch");
      if (input) input.value = author;
      window.location.assign(buildProfileUrl(author));
    }
  });
}

function render() {
  renderHero();
  renderKpis();
  renderRanking();
  renderUnlock();
  renderSearch();
  renderRecent();
  renderOps();
}

function renderHero() {
  const site = state.siteBundle?.site_config || {};
  const hero = site.hero || {};
  const gallery = state.dashboard?.gallery || {};
  const progress = gallery.progress || {};
  const current = gallery.current_title || {};
  const next = gallery.next_title_target || {};

  setText("mobileEyebrow", hero.eyebrow_ko || "손안의 수영 대시보드");
  setText("mobileTitle", hero.headline_ko || "오늘 기록과 랭킹을 가볍게 확인합니다");
  setText(
    "mobileCopy",
    hero.subheadline_ko || "갤 전체 운동량, 현재 랭킹, 다음 해금까지 한 화면에서 빠르게 봅니다.",
  );
  setText(
    "mobileGeneratedAt",
    state.dashboard?.generated_at ? `집계 갱신 ${state.dashboard.generated_at}` : "집계 생성 시각을 불러오는 중입니다.",
  );

  document.getElementById("mobileHeroChips").innerHTML = [
    chip(getVisibleDateRangeLabel(state.dashboard?.visible_date_range)),
    chip(current.short_label_ko || "갤 칭호"),
    chip(`배지 ${formatInt(state.badgeIndex?.badge_count)}개`),
  ].join("");

  document.getElementById("mobileQuickLinks").innerHTML = [
    { label: "데스크톱 보기", href: buildDesktopUrl() },
    { label: "배지 갤러리", href: "./badge-gallery.html" },
    { label: "파싱 현황", href: "./parse-status.html" },
  ].map((item) => `<a class="link-chip" href="${escapeHtml(item.href)}">${escapeHtml(item.label)}</a>`).join("");

  const barWidth = Math.round(clampRatio(progress.progress_ratio || next.progress_ratio || 0) * 100);
  document.getElementById("mobileUnlock").dataset.progressWidth = String(barWidth);
}

function renderKpis() {
  const summary = state.dashboard?.summary || {};
  const labels = state.siteBundle?.site_config?.kpi_labels || {};

  document.getElementById("mobileKpis").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">갤 전체 운동량</p>
      <h2>${escapeHtml(getVisibleDateRangeLabel(state.dashboard?.visible_date_range))}</h2>
      <p class="note">현재 집계 기간 안에서 자동 반영된 운동량만 먼저 보여줍니다.</p>
    </div>
    <div class="kpi-grid">
      ${renderKpi(labels.swim_count || "운동횟수", `${formatInt(summary.swim_count)}회`)}
      ${renderKpi(labels.total_distance_m || "총거리", formatDistance(summary.total_distance_m))}
      ${renderKpi(labels.total_seconds || "총시간", formatDurationLabel(summary.total_seconds))}
      ${renderKpi(labels.active_authors || "참여 인원", `${formatInt(summary.active_authors)}명`)}
    </div>
  `;
}

function renderRanking() {
  const metricKey = state.dashboard?.rankings?.default_metric || "swim_count";
  const group = getMetricGroup(state.dashboard, metricKey);
  const topRows = sliceTopThree(group).slice(0, 3);

  document.getElementById("mobileRanking").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">현재 랭킹</p>
      <h2>${escapeHtml(group.label_ko || metricLabel(metricKey))}</h2>
      <p class="note">${escapeHtml(group.description_ko || "가장 눈에 띄는 상위권 닉네임부터 보여줍니다.")}</p>
    </div>
    ${renderSpotlight(topRows[0], metricKey)}
    <div class="ranking-stack">
      ${[2, 3].map((rank) => renderRankRow(topRows[rank - 1], rank)).join("")}
    </div>
  `;
}

function renderUnlock() {
  const gallery = state.dashboard?.gallery || {};
  const progress = gallery.progress || {};
  const current = gallery.current_title || {};
  const next = gallery.next_title_target || {};
  const recentUnlockCount = Array.isArray(state.dashboard?.recent_unlocks) ? state.dashboard.recent_unlocks.length : 0;
  const progressRatio = Math.round(clampRatio(progress.progress_ratio || next.progress_ratio || 0) * 100);

  document.getElementById("mobileUnlock").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">해금 진행도</p>
      <h2>${escapeHtml(current.name_ko || "시즌 준비중")}</h2>
      <p class="note">${escapeHtml(current.description_ko || "갤 전체 누적으로 해금되는 칭호입니다.")}</p>
    </div>
    <article class="unlock-card">
      <strong>${escapeHtml(next.name_ko || "다음 칭호 준비중")}</strong>
      <p class="record-note">${escapeHtml(`${progress.current_value_text_ko || "0m"} / ${progress.target_value_text_ko || next.target_value_text_ko || "-"}`)}</p>
      <div class="progress-track"><span style="width:${progressRatio}%"></span></div>
      <p class="note">${escapeHtml(progress.remaining_value_text_ko || next.remaining_value_text_ko || "다음 해금 계산 중")}</p>
    </article>
    <div class="unlock-mini-grid">
      <article class="unlock-mini-card">
        <small>대표 칭호</small>
        <strong>${escapeHtml(current.short_label_ko || "대기중")}</strong>
      </article>
      <article class="unlock-mini-card">
        <small>최근 해금</small>
        <strong>${escapeHtml(`${formatInt(recentUnlockCount)}개`)}</strong>
      </article>
      <article class="unlock-mini-card">
        <small>전체 배지</small>
        <strong>${escapeHtml(`${formatInt(state.badgeIndex?.badge_count)}개`)}</strong>
      </article>
      <article class="unlock-mini-card">
        <small>다음 목표</small>
        <strong>${escapeHtml(next.short_label_ko || next.target_value_text_ko || "준비중")}</strong>
      </article>
    </div>
    <a class="unlock-link" href="./badge-gallery.html">배지 갤러리 열기</a>
  `;
}

function renderSearch() {
  const suggestions = getAuthorSuggestions(state.authorIndex).sort((left, right) => compareAuthors(left.author, right.author));
  document.getElementById("authorSuggestions").innerHTML = suggestions
    .map((row) => `<option value="${escapeHtml(row.author)}"></option>`)
    .join("");

  document.getElementById("mobileSearch").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">개인 페이지 찾기</p>
      <h2>닉네임으로 내 수영 앨범 열기</h2>
      <p class="note">닉네임을 입력하면 대표 칭호, 배지, 최근 기록을 바로 볼 수 있습니다.</p>
    </div>
    <form class="search-form" id="mobileSearchForm">
      <label for="mobileAuthorSearch">닉네임 입력</label>
      <div class="search-row">
        <input id="mobileAuthorSearch" name="author" list="authorSuggestions" placeholder="닉네임 입력">
        <button type="submit">열기</button>
      </div>
    </form>
    <div class="search-suggestions">
      ${suggestions.slice(0, 6).map((row) => `<button class="suggestion-chip" type="button" data-mobile-author="${escapeHtml(row.author)}">${escapeHtml(row.author)}</button>`).join("")}
    </div>
  `;
}

function renderRecent() {
  const recent = Array.isArray(state.dashboard?.recent_records) ? state.dashboard.recent_records.slice(0, 6) : [];
  document.getElementById("mobileRecent").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">최근 반영 기록</p>
      <h2>방금 들어온 수영 기록</h2>
    </div>
    <div class="record-list">
      ${recent.length ? recent.map(renderRecentRow).join("") : `
        <article class="record-card">
          <strong>최근 반영 기록이 아직 없습니다.</strong>
          <p class="record-note">제목 양식으로 작성된 글이 들어오면 이 칸이 채워집니다.</p>
        </article>
      `}
    </div>
  `;
}

function renderOps() {
  const reviewCount = Array.isArray(state.reviewQueue) ? state.reviewQueue.length : 0;
  document.getElementById("mobileOps").innerHTML = `
    <div class="panel-head">
      <p class="section-kicker">검토와 더보기</p>
      <h2>운영용 페이지 바로가기</h2>
      <p class="note">자동 반영에 실패한 제목과 수동 보정 현황은 아래 링크에서 확인합니다.</p>
    </div>
    <div class="record-list">
      <article class="ops-card">
        <strong>검토 대기 ${escapeHtml(`${formatInt(reviewCount)}건`)}</strong>
        <p class="record-note">제목 양식이 모호하거나 수동 보정이 필요한 글입니다.</p>
        <a class="unlock-link" href="./parse-status.html">파싱 현황 보기</a>
      </article>
      <article class="ops-card">
        <strong>배지 전시관</strong>
        <p class="record-note">배지 종류와 아이콘 구성을 카테고리별로 확인합니다.</p>
        <a class="unlock-link" href="./badge-gallery.html">배지 갤러리 열기</a>
      </article>
    </div>
  `;
}

function renderKpi(title, value) {
  return `
    <article class="kpi-card">
      <small>${escapeHtml(title)}</small>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `;
}

function renderSpotlight(row, metricKey) {
  if (!row) {
    return `
      <article class="spotlight-card is-placeholder">
        <div class="spotlight-head">
          <span class="mini-chip">1위</span>
          <span class="stat-chip">자리 준비중</span>
        </div>
        <h3>아직 1위 닉네임이 없습니다</h3>
        <p class="record-note">새로운 제목 양식 기록이 들어오면 가장 먼저 채워집니다.</p>
      </article>
    `;
  }

  return `
    <article class="spotlight-card">
      <div class="spotlight-head">
        <span class="mini-chip">1위</span>
        <span class="stat-chip">${escapeHtml(row.primary_title?.short_label_ko || "랭킹 선두")}</span>
      </div>
      <h3>${escapeHtml(row.author || "닉네임")}</h3>
      <p class="spotlight-value">${escapeHtml(row.metric_value_text_ko || metricLabel(metricKey))}</p>
      <p class="record-note">${escapeHtml(row.secondary_text_ko || "이번 시즌 기준 기록입니다.")}</p>
      <div class="stat-chip-row">
        ${row.primary_title?.icon_key ? renderBadgeIcon(state.siteBundle, row.primary_title.icon_key, row.author || "닉네임", "inline-badge-icon") : ""}
        ${(row.badge_preview || []).slice(0, 2).map((item) => `<span class="stat-chip">${escapeHtml(item)}</span>`).join("")}
      </div>
    </article>
  `;
}

function renderRankRow(row, rank) {
  if (!row) {
    return `
      <article class="rank-card is-placeholder">
        <div class="rank-head">
          <span class="mini-chip">${rank}위</span>
        </div>
        <strong>빈 자리</strong>
        <p class="record-note">새 기록이 들어오면 이 순위가 채워집니다.</p>
      </article>
    `;
  }

  return `
    <article class="rank-card">
      <div class="rank-head">
        <span class="mini-chip">${escapeHtml(`${rank}위`)}</span>
        <span class="stat-chip">${escapeHtml(row.primary_title?.short_label_ko || "기록 중")}</span>
      </div>
      <strong>${escapeHtml(row.author || "닉네임")}</strong>
      <p class="record-note">${escapeHtml(row.metric_value_text_ko || "-")}</p>
      <p class="note">${escapeHtml(row.secondary_text_ko || "시즌 누적 기록입니다.")}</p>
    </article>
  `;
}

function renderRecentRow(row) {
  return `
    <article class="record-card">
      <strong>${escapeHtml(row.author || "닉네임")}</strong>
      <p class="record-note">${escapeHtml(`${formatDistance(row.distance_m)} · ${row.total_time_text || formatDurationLabel(row.total_seconds)}`)}</p>
      <div class="mini-chip-row">
        <span class="mini-chip">${escapeHtml(row.post_date || "-")}</span>
        <span class="mini-chip">${escapeHtml(sourceLabel(row.source))}</span>
      </div>
    </article>
  `;
}

function openProfile() {
  const query = String(document.getElementById("mobileAuthorSearch")?.value || "").trim();
  if (!query) return;
  const author = findAuthorMatch(state.authorIndex, query);
  window.location.assign(buildProfileUrl(author));
}

function chip(label) {
  return `<span class="hero-chip">${escapeHtml(label)}</span>`;
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
