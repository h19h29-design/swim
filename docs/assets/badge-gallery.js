import {
  categoryLabelFromBundle,
  escapeHtml,
  formatDistance,
  formatDurationLabel,
  formatInt,
  loadBadgeIndex,
  loadDashboardViews,
  loadPublicSiteConfig,
  mergeSiteBundles,
  renderBadgeIcon,
} from "./dashboard-common.js?v=20260317d";

const CATEGORY_ORDER = ["attendance", "distance", "time", "efficiency", "growth", "season", "gallery", "fun"];

const state = {
  badgeIndex: null,
  dashboard: null,
  siteBundle: null,
};

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    void init();
  });
}

async function init() {
  const [badgeIndex, dashboard, publicSiteConfig] = await Promise.all([
    loadBadgeIndex(),
    loadDashboardViews(),
    loadPublicSiteConfig(),
  ]);

  state.badgeIndex = badgeIndex;
  state.dashboard = dashboard;
  state.siteBundle = mergeSiteBundles(publicSiteConfig, dashboard, badgeIndex);
  render();
}

function render() {
  renderHero();
  renderTitleTrack();
  renderFamilies();
  renderSharedAssets();
  renderPalettes();
  renderBadgeGroups();
}

function renderHero() {
  const badgeCatalog = state.siteBundle?.badge_catalog || {};
  const artCatalog = state.siteBundle?.badge_art_catalog || {};
  const sharedIcons = sharedAssetIcons();

  setText("galleryHeroEyebrow", "BADGE STICKERBOOK");
  setText("galleryHeroTitle", badgeCatalog.title_ko || "배지와 칭호를 한눈에 보는 전시관");
  setText(
    "galleryHeroCopy",
    badgeCatalog.description_ko || "개인 배지, 시즌 배지, 갤 전체 칭호를 카테고리별로 둘러보는 페이지입니다.",
  );

  document.getElementById("galleryHeroChips").innerHTML = [
    chip(`전체 배지 ${formatInt(state.badgeIndex?.badge_count)}개`),
    chip(`아이콘 가족 ${formatInt(Object.keys(artCatalog.family_map || {}).length)}종`),
    chip(`갤 전체 칭호 ${formatInt((state.badgeIndex?.gallery_titles || []).length)}단계`),
    chip(`공용 에셋 ${formatInt(sharedIcons.length)}개`),
  ].join("");

  document.getElementById("galleryHeroStats").innerHTML = [
    statCard("대표 칭호 후보", `${formatInt((state.badgeIndex?.badges || []).filter((badge) => badge.is_primary_title_candidate).length)}개`),
    statCard("숨김 배지", `${formatInt((state.badgeIndex?.badges || []).filter((badge) => badge.is_hidden).length)}개`),
    statCard("시즌 배지", `${formatInt((state.badgeIndex?.season_badges?.months || []).length)}개`),
    statCard("카테고리 수", `${formatInt(Object.keys(state.badgeIndex?.badge_count_by_category || {}).length)}종`),
  ].join("");

  document.getElementById("galleryRuleList").innerHTML = [
    {
      title: "공개 표시 규칙",
      copy: "배지 이름과 설명은 관리자가 수정할 수 있고, 실제 대표 칭호 계산은 백엔드 집계 값을 그대로 따릅니다.",
    },
    {
      title: "아이콘 매핑",
      copy: "badge_id와 icon_key를 연결해서 한 아이콘을 여러 배지에 재사용할 수 있습니다.",
    },
    {
      title: "운영 포인트",
      copy: "아이콘을 추가하면 관리자 페이지에서 바로 저장하고 rebuild 후 공개 페이지에 반영할 수 있습니다.",
    },
  ].map((rule) => `
    <article class="rule-card">
      <strong>${escapeHtml(rule.title)}</strong>
      <p class="rule-copy">${escapeHtml(rule.copy)}</p>
    </article>
  `).join("");
}

function renderTitleTrack() {
  const galleryTitles = Array.isArray(state.badgeIndex?.gallery_titles) ? state.badgeIndex.gallery_titles : [];
  const currentTitleId = state.dashboard?.gallery?.current_title?.badge_id;
  const nextTitleId = state.dashboard?.gallery?.next_title_target?.badge_id;

  document.getElementById("galleryTitleTrack").innerHTML = galleryTitles.length
    ? galleryTitles.map((title) => `
      <article class="title-card">
        <p class="section-kicker">${title.badge_id === currentTitleId ? "현재 칭호" : title.badge_id === nextTitleId ? "다음 칭호" : "갤 칭호"}</p>
        <h3>${escapeHtml(title.name_ko || title.badge_id)}</h3>
        <p class="meta">${escapeHtml(title.description_ko || "갤 전체 누적으로 해금되는 칭호입니다.")}</p>
        <div class="badge-meta-row">
          <span class="meta-chip">${escapeHtml(formatThreshold(title.threshold_type, title.threshold_value))}</span>
          <span class="file-chip">${escapeHtml(title.badge_id || "-")}</span>
        </div>
      </article>
    `).join("")
    : `
      <article class="title-card">
        <h3>갤 칭호 데이터가 아직 없습니다.</h3>
        <p class="meta">gallery_title_rules 와 dashboard_views 생성 상태를 확인해 주세요.</p>
      </article>
    `;
}

function renderFamilies() {
  const families = Object.entries(state.siteBundle?.badge_art_catalog?.family_map || {});
  document.getElementById("galleryFamilyGrid").innerHTML = families.length
    ? families.map(([familyKey, family]) => {
      const iconKey = `${familyKey}.base`;
      const category = categoryFromFamily(familyKey);
      const badgeCount = state.badgeIndex?.badge_count_by_category?.[category] || 0;
      return `
        <article class="family-card">
          <div class="badge-meta-row">
            ${renderBadgeIcon(state.siteBundle, iconKey, family.label_ko || familyKey, "badge-thumb")}
          </div>
          <strong>${escapeHtml(family.label_ko || familyKey)}</strong>
          <p class="meta">${escapeHtml(family.display_note || "같은 카테고리 배지에 공통으로 쓰이는 아이콘 가족입니다.")}</p>
          <div class="badge-meta-row">
            <span class="meta-chip">${escapeHtml(`${formatInt(badgeCount)}개`)}</span>
            ${(family.badge_id_prefixes || []).map((prefix) => `<span class="file-chip">${escapeHtml(prefix)}</span>`).join("")}
          </div>
        </article>
      `;
    }).join("")
    : `
      <article class="family-card">
        <strong>아이콘 가족 정보가 아직 없습니다.</strong>
        <p class="meta">badge_art_catalog.family_map 이 비어 있습니다.</p>
      </article>
    `;
}

function renderSharedAssets() {
  const sharedIcons = sharedAssetIcons();
  document.getElementById("gallerySharedAssets").innerHTML = sharedIcons.length
    ? sharedIcons.map((asset) => `
      <article class="asset-card">
        <div class="badge-meta-row">
          ${asset.icon_key ? renderBadgeIcon(state.siteBundle, asset.icon_key, asset.icon_key, "badge-thumb") : ""}
        </div>
        <strong>${escapeHtml(asset.icon_key || "-")}</strong>
        <p class="meta">${escapeHtml(asset.display_notes || asset.color_notes || "공용 프레임 또는 강조 에셋입니다.")}</p>
        <div class="badge-meta-row">
          <span class="file-chip">${escapeHtml(shortAssetPath(asset.file_path))}</span>
        </div>
      </article>
    `).join("")
    : `
      <article class="asset-card">
        <strong>공용 에셋이 아직 없습니다.</strong>
      </article>
    `;
}

function renderPalettes() {
  const palettes = Array.isArray(state.siteBundle?.badge_art_catalog?.tier_palettes)
    ? state.siteBundle.badge_art_catalog.tier_palettes
    : [];
  document.getElementById("galleryPaletteGrid").innerHTML = palettes.length
    ? palettes.map((palette) => `
      <article class="palette-card">
        <strong>${escapeHtml(palette.label_ko || palette.id || "팔레트")}</strong>
        <p class="meta">${escapeHtml(palette.color_notes || "티어별 색상 규칙입니다.")}</p>
        <div class="swatch-row">
          ${(palette.swatch || []).map((color) => `<span style="background:${escapeHtml(color)}"></span>`).join("")}
        </div>
        <div class="badge-meta-row">
          <span class="file-chip">${escapeHtml(palette.id || "-")}</span>
        </div>
      </article>
    `).join("")
    : `
      <article class="palette-card">
        <strong>팔레트 데이터가 아직 없습니다.</strong>
      </article>
    `;
}

function renderBadgeGroups() {
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    label: categoryLabelFromBundle(state.siteBundle, category),
    badges: (state.badgeIndex?.badges || []).filter((badge) => badge.category === category),
  })).filter((group) => group.badges.length);

  document.getElementById("galleryBadgeGroups").innerHTML = groups.length
    ? groups.map((group) => `
      <section class="badge-group">
        <div class="section-head">
          <div>
            <p class="section-kicker">${escapeHtml(group.label)}</p>
            <h2>${escapeHtml(`${group.label} 배지 ${formatInt(group.badges.length)}개`)}</h2>
          </div>
        </div>
        <div class="badge-grid">
          ${group.badges.map(renderBadgeCard).join("")}
        </div>
      </section>
    `).join("")
    : `
      <article class="badge-group">
        <strong>표시할 배지 데이터가 아직 없습니다.</strong>
      </article>
    `;
}

function renderBadgeCard(badge) {
  return `
    <article class="badge-card">
      <div class="badge-meta-row">
        ${badge.icon_key ? renderBadgeIcon(state.siteBundle, badge.icon_key, badge.name_ko || badge.badge_id, "badge-thumb") : ""}
      </div>
      <strong>${escapeHtml(badge.name_ko || badge.badge_id)}</strong>
      <p class="meta">${escapeHtml(badge.description_ko || "배지 설명이 아직 없습니다.")}</p>
      <div class="badge-meta-row">
        <span class="meta-chip">${escapeHtml(badge.short_label_ko || formatThreshold(badge.threshold_type, badge.threshold_value))}</span>
        <span class="file-chip">${escapeHtml(badge.badge_id || "-")}</span>
        <span class="file-chip">${escapeHtml(badge.icon_key || "-")}</span>
        ${badge.is_hidden ? '<span class="meta-chip">숨김</span>' : ""}
      </div>
    </article>
  `;
}

function formatThreshold(type, value) {
  if (type?.includes("distance")) return formatDistance(value);
  if (type?.includes("seconds")) return formatDurationLabel(value);
  if (type?.includes("swim_count")) return `${formatInt(value)}회`;
  if (type === "author_distance_per_hour_m") return `${formatInt(value)}m/h`;
  return String(value ?? "-");
}

function categoryFromFamily(familyKey) {
  return {
    att: "attendance",
    dst: "distance",
    tim: "time",
    eff: "efficiency",
    grw: "growth",
    sea: "season",
    gal: "gallery",
    fun: "fun",
  }[familyKey] || familyKey;
}

function sharedAssetIcons() {
  return (state.siteBundle?.badge_art_catalog?.icons || [])
    .filter((asset) => asset.family === "shared" || String(asset.icon_key || "").startsWith("frame.") || String(asset.icon_key || "").startsWith("special."));
}

function shortAssetPath(filePath) {
  const value = String(filePath || "");
  return value.split("/").slice(-2).join("/");
}

function chip(label) {
  return `<span class="hero-chip">${escapeHtml(label)}</span>`;
}

function statCard(label, value) {
  return `
    <article class="stat-card">
      <small>${escapeHtml(label)}</small>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value || "";
}
