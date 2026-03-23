import {
  categoryLabelFromBundle,
  downloadJson,
  escapeHtml,
  formatInt,
  renderBadgeIcon,
} from "./dashboard-common.js?v=20260317d";

const SAVEABLE_KEYS = new Set([
  "site_config",
  "navigation_config",
  "home_sections",
  "badge_catalog",
  "badge_art_catalog",
  "season_badges",
  "gallery_title_rules",
  "profile_layout_config",
  "bundle",
]);

const state = {
  baseConfig: emptyBundle(),
  config: emptyBundle(),
  adminPreview: {},
  badgeIndex: {},
  csrfToken: "",
  badgeFilter: "all",
  busy: false,
  auth: {},
  status: {
    kind: "info",
    message: "관리자 설정을 불러오는 중입니다.",
    errors: [],
  },
  lastAction: null,
  syncDraft: {
    start_date: "2026-03-01",
    end_date: todayIsoDate(),
  },
  uploadDraft: {
    icon_key: "",
    family: "custom",
    badge_id_prefixes: "fun",
    tier_compatibility: "starter,rally,gold,prism",
    color_notes: "",
    display_notes: "",
    filename: "",
    content_base64: "",
  },
};

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    void init();
  });
}

async function init() {
  bindEvents();
  try {
    await refreshWorkspace({
      message: "관리자 설정을 불러왔습니다. 저장하면 data/admin/*.json 원본이 바뀌고, rebuild 해야 공개 페이지에 반영됩니다.",
      kind: "info",
    });
  } catch (error) {
    if (error?.status === 401) {
      redirectToLogin();
      return;
    }
    setStatus("error", resolveErrorMessage(error, "관리자 설정을 불러오지 못했습니다."), extractErrors(error));
    renderStatusBanner();
  }
}

function bindEvents() {
  document.addEventListener("click", (event) => {
    const exportButton = event.target.closest("[data-export]");
    if (exportButton) {
      exportConfig(exportButton.dataset.export);
      return;
    }

    const filterButton = event.target.closest("[data-badge-filter]");
    if (filterButton) {
      state.badgeFilter = filterButton.dataset.badgeFilter;
      renderBadgeEditor();
      renderBadgePreview();
      return;
    }

    const moveButton = event.target.closest("[data-move-section]");
    if (moveButton) {
      moveSection(Number(moveButton.dataset.index), moveButton.dataset.move);
      renderSectionsEditor();
      renderHeroPreview();
      renderToolbarState();
      return;
    }

    const saveButton = event.target.closest("[data-save]");
    if (saveButton) {
      void saveConfig(saveButton.dataset.save, saveButton.dataset.runRebuild !== "false");
      return;
    }

    if (event.target.closest("[data-rebuild]")) {
      void rebuildPublicData();
      return;
    }

    const syncButton = event.target.closest("[data-run-sync]");
    if (syncButton) {
      void runSync(syncButton.dataset.runSync);
      return;
    }

    if (event.target.closest("[data-logout]")) {
      void logout();
      return;
    }

    const uploadButton = event.target.closest("[data-upload-icon]");
    if (uploadButton) {
      void uploadBadgeIcon(uploadButton.dataset.runRebuild !== "false");
    }
  });

  document.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement)) {
      return;
    }

    if (target.matches("[data-site-path]")) {
      setNestedValue(state.config.site_config, target.dataset.sitePath, target.value);
      renderHeroPreview();
      renderHeader();
      renderToolbarState();
      return;
    }

    if (target.matches("[data-nav-index][data-nav-field]")) {
      const row = state.config.navigation_config.items[Number(target.dataset.navIndex)];
      row[target.dataset.navField] = target.type === "checkbox" ? target.checked : target.value;
      renderHeroPreview();
      renderHeader();
      renderToolbarState();
      return;
    }

    if (target.matches("[data-section-index][data-section-field]")) {
      const row = state.config.home_sections.ranking_sections[Number(target.dataset.sectionIndex)];
      row[target.dataset.sectionField] = target.value;
      renderHeroPreview();
      renderToolbarState();
      return;
    }

    if (target.matches("[data-badge-index][data-badge-field]")) {
      const badge = state.config.badge_catalog.badges[Number(target.dataset.badgeIndex)];
      const field = target.dataset.badgeField;
      if (field === "is_hidden" || field === "is_primary_title_candidate") {
        badge[field] = target.checked;
      } else if (field === "threshold_value" || field === "tier") {
        badge[field] = Number(target.value || 0);
      } else {
        badge[field] = target.value;
      }
      renderBadgePreview();
      renderGalleryPreview();
      renderAuthorPreview();
      renderToolbarState();
      return;
    }

    if (target.matches("[data-upload-field]")) {
      const field = target.dataset.uploadField;
      if (!field || field === "file") return;
      state.uploadDraft[field] = target.value;
      renderToolbarState();
      return;
    }

    if (target.matches("[data-sync-field]")) {
      const field = target.dataset.syncField;
      if (!field) return;
      state.syncDraft[field] = target.value;
      renderToolbarState();
    }
  });

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    if (!target.matches('[data-upload-field="file"]')) return;
    void captureFileContent(target.files?.[0] || null);
  });
}

async function refreshWorkspace(status = null) {
  const payload = await apiJson("/api/admin/bundle");
  applyWorkspace(payload);
  if (status) {
    setStatus(status.kind || "info", status.message || "", status.errors || []);
  }
  render();
}

async function saveConfig(kind, runRebuild = true) {
  if (!SAVEABLE_KEYS.has(kind)) return;
  setBusy(true);
  setStatus("info", runRebuild ? "설정을 저장하고 rebuild 하는 중입니다." : "설정을 저장하는 중입니다.");
  renderToolbarState();

  const path = kind === "bundle" ? "/api/admin/save/bundle" : `/api/admin/save/${kind}`;
  const body = kind === "bundle"
    ? { bundle: state.config, run_rebuild: runRebuild }
    : { payload: cloneJson(state.config[kind]), run_rebuild: runRebuild };

  try {
    const payload = await apiJson(path, { method: "POST", body, csrf: true });
    applyWorkspace(payload);
    state.lastAction = {
      action: payload.action || "save",
      changedKeys: Array.isArray(payload.changed_keys) ? payload.changed_keys : [],
      rebuildTriggered: Boolean(payload.rebuild_triggered),
      rebuildSummary: payload.rebuild_summary || null,
    };

    const changedLabel = state.lastAction.changedKeys.length
      ? `${state.lastAction.changedKeys.join(", ")} 저장 완료.`
      : "변경점이 없거나 같은 값으로 저장되었습니다.";
    const rebuildLabel = state.lastAction.rebuildTriggered
      ? "공개 데이터 rebuild 도 함께 실행했습니다."
      : "공개 페이지에 반영하려면 rebuild 를 실행해 주세요.";
    setStatus("success", `${changedLabel} ${rebuildLabel}`);
    render();
  } catch (error) {
    setStatus("error", resolveErrorMessage(error, "설정을 저장하지 못했습니다."), extractErrors(error));
    renderStatusBanner();
  } finally {
    setBusy(false);
    renderToolbarState();
  }
}

async function rebuildPublicData() {
  setBusy(true);
  setStatus("info", "공개 docs/data 데이터를 rebuild 하는 중입니다.");
  renderToolbarState();
  try {
    const payload = await apiJson("/api/admin/rebuild", {
      method: "POST",
      body: {},
      csrf: true,
    });
    applyWorkspace(payload);
    state.lastAction = {
      action: "rebuild",
      changedKeys: [],
      rebuildTriggered: true,
      rebuildSummary: payload.rebuild_summary || null,
    };
    setStatus("success", "rebuild 완료. 공개 페이지를 새로고침하면 최신 설정과 집계가 보입니다.");
    render();
  } catch (error) {
    setStatus("error", resolveErrorMessage(error, "rebuild 를 실행하지 못했습니다."), extractErrors(error));
    renderStatusBanner();
  } finally {
    setBusy(false);
    renderToolbarState();
  }
}

async function logout() {
  try {
    await apiJson("/api/admin/logout", { method: "POST", body: {} });
  } catch (_error) {
    // Network interruption should not block redirecting to the login page.
  }
  redirectToLogin();
}

function applyWorkspace(payload) {
  state.baseConfig = cloneJson(payload.bundle || emptyBundle());
  state.config = cloneJson(payload.bundle || emptyBundle());
  state.adminPreview = payload.preview || {};
  state.badgeIndex = payload.badge_index || {};
  state.csrfToken = payload.csrf_token || state.csrfToken || "";
  state.auth = payload.auth || {};

  const filters = Object.keys(getLiveBadgeSummary().badge_count_by_category || {});
  if (!filters.includes(state.badgeFilter)) {
    state.badgeFilter = "all";
  }
}

function render() {
  renderHeader();
  renderStatusBanner();
  renderSiteEditor();
  renderNavigationEditor();
  renderSectionsEditor();
  renderSyncEditor();
  renderBadgeEditor();
  renderBadgeArtEditor();
  renderHeroPreview();
  renderBadgePreview();
  renderGalleryPreview();
  renderAuthorPreview();
  renderToolbarState();
}

function renderHeader() {
  const site = state.config.site_config || {};
  const badgeSummary = getLiveBadgeSummary();
  const dirty = hasUnsavedChanges();
  setText("adminEyebrow", site.site_title_ko || "관리자");
  setText("adminTitle", "관리자 설정 워크스페이스");
  setText(
    "adminCopy",
    site.admin_edit_note_ko || "배지, 문구, 홈 섹션 순서를 수정하고 저장한 뒤 rebuild 해서 공개 페이지에 반영합니다.",
  );

  const chips = [
    chip(dirty ? "저장 전 변경 있음" : "현재 저장 상태"),
    chip(`미리보기 생성 ${state.adminPreview.generated_at || "-"}`),
    chip(`배지 ${formatInt(badgeSummary.badge_count)}개`),
    chip(`카테고리 ${formatInt(Object.keys(badgeSummary.badge_count_by_category || {}).length)}개`),
  ];

  if (state.auth?.expires_at) {
    chips.push(chip(`세션 만료 ${formatExpiry(state.auth.expires_at)}`));
  }

  document.getElementById("adminMeta").innerHTML = chips.join("");
}

function renderStatusBanner() {
  const node = document.getElementById("saveStatus");
  const note = document.getElementById("saveNote");
  if (!node || !note) return;

  const kind = state.status.kind || "info";
  const dirty = hasUnsavedChanges();
  node.className = `status-banner status-banner--${kind}`;
  node.innerHTML = [
    `<strong>${escapeHtml(state.status.message || "")}</strong>`,
    state.status.errors.length
      ? `<ul class="status-errors">${state.status.errors.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
      : "",
  ].join("");

  if (state.lastAction?.action === "rebuild" && state.lastAction?.rebuildTriggered) {
    note.innerHTML = '공개 <code>docs/data/*.json</code> 데이터를 다시 만들었습니다. 메인 페이지를 새로고침해서 결과를 확인해 주세요.';
    return;
  }

  if (state.lastAction?.changedKeys?.length && !state.lastAction?.rebuildTriggered) {
    note.innerHTML = `방금 저장한 항목: <code>${escapeHtml(state.lastAction.changedKeys.join(", "))}</code>. 공개 페이지에 반영하려면 <code>rebuild</code> 를 실행해 주세요.`;
    return;
  }

  note.innerHTML = dirty
    ? '아직 저장하지 않은 변경이 있습니다. 저장하면 <code>data/admin/*.json</code> 원본이 바뀌고, 이후 <code>rebuild</code> 해야 공개 데이터가 갱신됩니다.'
    : '현재 저장된 설정을 보고 있습니다. 필요할 때 수정 후 저장하고, 마지막에 <code>rebuild</code> 를 실행해 주세요.';
}

function renderToolbarState() {
  for (const button of document.querySelectorAll("[data-save], [data-rebuild], [data-logout], [data-upload-icon], [data-run-sync]")) {
    button.disabled = state.busy;
  }
}

function renderSiteEditor() {
  const site = state.config.site_config || {};
  document.getElementById("siteEditor").innerHTML = `
    <div>
      <p class="section-kicker">site_config</p>
      <h2>사이트 기본 문구</h2>
      <p class="section-note">페이지 제목, 히어로 문구, 빈 상태 안내 같은 기본 카피를 조정합니다.</p>
    </div>
    <div class="field-grid">
      ${textField("사이트 제목", "site_title_ko", site.site_title_ko || "")}
      ${textField("사이트 부제", "site_subtitle_ko", site.site_subtitle_ko || "")}
      ${textField("Hero Eyebrow", "hero.eyebrow_ko", site.hero?.eyebrow_ko || "")}
      ${textField("Hero Headline", "hero.headline_ko", site.hero?.headline_ko || "")}
      ${textAreaField("Hero Subheadline", "hero.subheadline_ko", site.hero?.subheadline_ko || "")}
      ${textAreaField("빈 상태 문구", "empty_state_ko", site.empty_state_ko || "")}
    </div>
  `;
}

function renderNavigationEditor() {
  const items = Array.isArray(state.config.navigation_config?.items) ? state.config.navigation_config.items : [];
  document.getElementById("navigationEditor").innerHTML = `
    <div>
      <p class="section-kicker">navigation_config</p>
      <h2>상단 메뉴 문구</h2>
      <p class="section-note">메뉴에 보이는 이름과 설명, 표시 여부를 수정합니다.</p>
    </div>
    <div class="field-grid">
      ${items.map((item, index) => `
        <article class="section-row">
          <strong>${escapeHtml(item.nav_key || `nav_${index + 1}`)}</strong>
          <div class="field-row">
            <label class="field"><span>메뉴 이름</span><input type="text" data-nav-index="${index}" data-nav-field="label_ko" value="${escapeHtml(item.label_ko || "")}"></label>
            <label class="field"><span>설명</span><input type="text" data-nav-index="${index}" data-nav-field="description_ko" value="${escapeHtml(item.description_ko || "")}"></label>
          </div>
          <label class="toggle"><input type="checkbox" data-nav-index="${index}" data-nav-field="visible" ${item.visible === false ? "" : "checked"}>보이기</label>
        </article>
      `).join("")}
    </div>
  `;
}

function renderSectionsEditor() {
  const sections = Array.isArray(state.config.home_sections?.ranking_sections) ? state.config.home_sections.ranking_sections : [];
  document.getElementById("sectionsEditor").innerHTML = `
    <div>
      <p class="section-kicker">home_sections</p>
      <h2>랭킹 탭 순서와 문구</h2>
      <p class="section-note">홈에서 보이는 랭킹 탭 순서를 바꾸고 이름과 설명을 조정합니다.</p>
    </div>
    <div class="section-list">
      ${sections.map((item, index) => `
        <article class="section-row">
          <div class="section-actions">
            <strong>${escapeHtml(item.metric_key || `metric_${index + 1}`)}</strong>
            <button class="mini-button" type="button" data-move-section data-index="${index}" data-move="up">위로</button>
            <button class="mini-button" type="button" data-move-section data-index="${index}" data-move="down">아래로</button>
          </div>
          <label class="field"><span>탭 이름</span><input type="text" data-section-index="${index}" data-section-field="label_ko" value="${escapeHtml(item.label_ko || "")}"></label>
          <label class="field"><span>설명</span><input type="text" data-section-index="${index}" data-section-field="description_ko" value="${escapeHtml(item.description_ko || "")}"></label>
        </article>
      `).join("")}
    </div>
  `;
}

function renderSyncEditor() {
  const syncStart = state.syncDraft.start_date || "2026-03-01";
  const syncEnd = state.syncDraft.end_date || todayIsoDate();
  document.getElementById("syncEditor").innerHTML = `
    <div>
      <p class="section-kicker">runtime sync</p>
      <h2>파싱 실행 제어</h2>
      <p class="section-note">일상 스케줄은 최근 3일만 누적 갱신하고, 필요할 때만 특정 기간을 다시 수집해서 그 구간만 덮어쓴 뒤 전체 누적본과 합칩니다.</p>
    </div>
    <div class="field-grid">
      <article class="section-row">
        <strong>기본 갱신</strong>
        <p class="helper">최근 3일만 다시 읽고 누적 데이터를 유지합니다. DSM 스케줄러 10:00 / 22:00 작업도 이 동작을 쓰면 됩니다.</p>
        <div class="section-actions">
          <button class="export-button strong" type="button" data-run-sync="recent">최근 3일 갱신</button>
        </div>
      </article>
      <article class="section-row">
        <strong>3월 1일부터 다시 수집</strong>
        <p class="helper">3월 1일 이후 구간만 다시 모아 최신 제목 기준으로 덮어씁니다. 이전 누적본 전체를 날리는 동작은 아닙니다.</p>
        <div class="section-actions">
          <button class="export-button" type="button" data-run-sync="floor">3월 1일부터 재수집</button>
        </div>
      </article>
      <article class="section-row">
        <strong>기간 지정 재수집</strong>
        <p class="helper">선택한 날짜 범위만 다시 수집하고, 그 범위 안의 기존 레코드만 교체합니다. 바깥 날짜의 누적 기록은 그대로 둡니다.</p>
        <div class="field-row">
          <label class="field"><span>시작일</span><input type="date" data-sync-field="start_date" value="${escapeHtml(syncStart)}"></label>
          <label class="field"><span>종료일</span><input type="date" data-sync-field="end_date" value="${escapeHtml(syncEnd)}"></label>
        </div>
        <div class="section-actions">
          <button class="export-button" type="button" data-run-sync="window">기간 지정 재수집</button>
        </div>
      </article>
      <article class="section-row">
        <strong>파싱 기준 메모</strong>
        <p class="helper">공식 제목 형식은 <code>거리 / 시간</code> 입니다. 예: <code>1500 / 42:30</code>, <code>1500m / 55분</code>, <code>총거리 1000 / 시간 49분17초</code>.</p>
        <p class="helper">날짜, 오늘의 수영, 메모는 제목이 아니라 본문에 적는 것이 안전합니다.</p>
      </article>
    </div>
  `;
}

function renderBadgeEditor() {
  const catalog = Array.isArray(state.config.badge_catalog?.badges) ? state.config.badge_catalog.badges : [];
  const badgeSummary = getLiveBadgeSummary();
  const filters = ["all", ...Object.keys(badgeSummary.badge_count_by_category || {})];
  if (!filters.includes(state.badgeFilter)) {
    state.badgeFilter = "all";
  }
  const filtered = catalog.filter((item) => state.badgeFilter === "all" || item.category === state.badgeFilter);
  document.getElementById("badgeEditor").innerHTML = `
    <div>
      <p class="section-kicker">badge_catalog</p>
      <h2>배지 텍스트와 기준 수정</h2>
      <p class="section-note">입력 중에는 에디터 전체를 다시 그리지 않아서, 한 글자씩 수정해도 커서가 튀지 않습니다.</p>
    </div>
    <div class="chip-row">
      ${filters.map((filter) => `<button class="export-button${state.badgeFilter === filter ? " strong" : ""}" type="button" data-badge-filter="${filter}">${escapeHtml(filter === "all" ? "전체" : filter)}</button>`).join("")}
    </div>
    <div class="badge-grid">
      ${filtered.map((badge) => {
        const index = catalog.findIndex((item) => item.badge_id === badge.badge_id);
        return `
          <article class="badge-row">
            <strong>${escapeHtml(badge.badge_id)}</strong>
            <div class="field-row">
              <label class="field"><span>이름</span><input type="text" data-badge-index="${index}" data-badge-field="name_ko" value="${escapeHtml(badge.name_ko || "")}"></label>
              <label class="field"><span>짧은 라벨</span><input type="text" data-badge-index="${index}" data-badge-field="short_label_ko" value="${escapeHtml(badge.short_label_ko || "")}"></label>
            </div>
            <label class="field"><span>설명</span><input type="text" data-badge-index="${index}" data-badge-field="description_ko" value="${escapeHtml(badge.description_ko || "")}"></label>
            <div class="field-row">
              <label class="field"><span>기준값</span><input type="number" data-badge-index="${index}" data-badge-field="threshold_value" value="${escapeHtml(String(badge.threshold_value ?? 0))}"></label>
              <label class="field"><span>아이콘 키</span><input type="text" data-badge-index="${index}" data-badge-field="icon_key" value="${escapeHtml(badge.icon_key || "")}"></label>
              <label class="field"><span>티어</span><input type="number" data-badge-index="${index}" data-badge-field="tier" value="${escapeHtml(String(badge.tier ?? 0))}"></label>
            </div>
            <div class="field-row">
              <label class="toggle"><input type="checkbox" data-badge-index="${index}" data-badge-field="is_hidden" ${badge.is_hidden ? "checked" : ""}>숨김</label>
              <label class="toggle"><input type="checkbox" data-badge-index="${index}" data-badge-field="is_primary_title_candidate" ${badge.is_primary_title_candidate ? "checked" : ""}>대표 칭호 후보</label>
            </div>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function renderBadgeArtEditor() {
  const artCatalog = state.config.badge_art_catalog || {};
  const icons = Array.isArray(artCatalog.icons) ? artCatalog.icons : [];
  document.getElementById("badgeArtEditor").innerHTML = `
    <div>
      <p class="section-kicker">badge_art_catalog</p>
      <h2>배지 아이콘 업로드</h2>
      <p class="section-note">SVG/PNG/JPG/WEBP 파일을 올리면 custom 폴더에 저장되고, icon_key 로 배지와 연결할 수 있습니다.</p>
    </div>
    <div class="field-grid icon-upload-grid">
      <label class="field"><span>icon_key</span><input type="text" data-upload-field="icon_key" value="${escapeHtml(state.uploadDraft.icon_key)}" placeholder="예: custom.wave_gold"></label>
      <label class="field"><span>family</span><input type="text" data-upload-field="family" value="${escapeHtml(state.uploadDraft.family)}" placeholder="예: custom"></label>
      <label class="field"><span>badge_id_prefixes</span><input type="text" data-upload-field="badge_id_prefixes" value="${escapeHtml(state.uploadDraft.badge_id_prefixes)}" placeholder="예: dst,fun"></label>
      <label class="field"><span>tier_compatibility</span><input type="text" data-upload-field="tier_compatibility" value="${escapeHtml(state.uploadDraft.tier_compatibility)}" placeholder="예: starter,rally,gold,prism"></label>
      <label class="field"><span>color_notes</span><input type="text" data-upload-field="color_notes" value="${escapeHtml(state.uploadDraft.color_notes)}" placeholder="예: 산호 포인트, 금색 테두리"></label>
      <label class="field"><span>display_notes</span><input type="text" data-upload-field="display_notes" value="${escapeHtml(state.uploadDraft.display_notes)}" placeholder="예: 대표 칭호용 파도 메달"></label>
      <label class="field"><span>파일 선택</span><input type="file" data-upload-field="file" accept=".svg,.png,.jpg,.jpeg,.webp"></label>
      <div class="upload-actions">
        <button class="export-button" type="button" data-upload-icon>아이콘 저장</button>
        <button class="export-button strong" type="button" data-upload-icon data-run-rebuild="true">아이콘 저장 + rebuild</button>
      </div>
    </div>
    <div class="chip-row">
      <span class="badge-chip">현재 아이콘 ${escapeHtml(`${formatInt(icons.length)}개`)}</span>
      ${state.uploadDraft.filename ? `<span class="badge-chip">선택 파일 ${escapeHtml(state.uploadDraft.filename)}</span>` : ""}
    </div>
    <div class="badge-grid badge-art-grid">
      ${icons.slice(0, 12).map((item) => `
        <article class="badge-row">
          <div class="section-actions">
            <strong>${escapeHtml(item.icon_key || "-")}</strong>
            ${item.icon_key ? renderBadgeIcon(state.config, item.icon_key, item.icon_key, "badge-thumb") : ""}
          </div>
          <p class="helper">${escapeHtml(item.display_notes || item.color_notes || "설명 없음")}</p>
          <div class="chip-row">
            <span class="badge-chip">${escapeHtml(item.family || "family")}</span>
            ${(item.badge_id_prefixes || []).map((prefix) => `<span class="badge-chip">${escapeHtml(prefix)}</span>`).join("")}
          </div>
        </article>
      `).join("")}
    </div>
  `;
}

function renderHeroPreview() {
  const site = state.config.site_config || {};
  const visibleNavItems = Array.isArray(state.config.navigation_config?.items)
    ? state.config.navigation_config.items.filter((item) => item.visible !== false)
    : [];
  document.getElementById("previewHero").innerHTML = `
    <div>
      <p class="section-kicker">미리보기</p>
      <h2>Hero 문구</h2>
      <p class="preview-note">홈 첫 화면에서 보이는 제목과 메뉴 분위기를 바로 확인합니다.</p>
    </div>
    <article class="preview-card">
      <p class="eyebrow">${escapeHtml(site.hero?.eyebrow_ko || "")}</p>
      <h3>${escapeHtml(site.hero?.headline_ko || "")}</h3>
      <p class="helper">${escapeHtml(site.hero?.subheadline_ko || "")}</p>
      <div class="chip-row">${visibleNavItems.map((item) => `<span class="badge-chip">${escapeHtml(item.label_ko || item.nav_key)}</span>`).join("")}</div>
    </article>
  `;
}

function renderBadgePreview() {
  const counts = Object.entries(getLiveBadgeSummary().badge_count_by_category || {});
  const featuredBadges = (state.config.badge_catalog?.badges || []).filter((badge) => badge.is_primary_title_candidate).slice(0, 4);
  document.getElementById("previewBadges").innerHTML = `
    <div>
      <p class="section-kicker">미리보기</p>
      <h2>배지 카테고리 요약</h2>
      <p class="preview-note">현재 badge_catalog 기준으로 카테고리별 개수를 바로 봅니다.</p>
    </div>
    <article class="preview-card">
      <div class="chip-row">${counts.map(([key, value]) => `<span class="badge-chip">${escapeHtml(categoryLabelFromBundle(state.config, key))} ${escapeHtml(String(value))}</span>`).join("")}</div>
      <div class="chip-row">
        ${featuredBadges.map((badge) => `
          <span class="badge-chip">
            ${badge.icon_key ? renderBadgeIcon(state.config, badge.icon_key, badge.name_ko || badge.badge_id, "inline-badge-icon") : ""}
            ${escapeHtml(badge.name_ko || badge.badge_id)}
          </span>
        `).join("")}
      </div>
    </article>
  `;
}

function renderGalleryPreview() {
  const preview = state.adminPreview.gallery_preview || {};
  const currentTitle = decorateBadgePayload(preview.current_title);
  const nextTitle = decorateBadgePayload(preview.next_title_target);
  document.getElementById("previewGallery").innerHTML = `
    <div>
      <p class="section-kicker">미리보기</p>
      <h2>갤 전체 칭호</h2>
      <p class="preview-note">갤 전체 누적 기준으로 현재 칭호와 다음 목표를 확인합니다.</p>
    </div>
    <article class="preview-card">
      <strong>${escapeHtml(currentTitle?.name_ko || "아직 대기 중")}</strong>
      <p class="helper">${escapeHtml(nextTitle?.name_ko || "다음 칭호 대기 중")}</p>
      <p class="preview-note">${escapeHtml(preview.progress?.remaining_value_text_ko || "다음 해금 계산 대기 중")}</p>
      <div class="chip-row">
        ${currentTitle?.icon_key ? renderBadgeIcon(state.config, currentTitle.icon_key, currentTitle.name_ko || "현재 칭호", "inline-badge-icon") : ""}
        ${nextTitle?.icon_key ? renderBadgeIcon(state.config, nextTitle.icon_key, nextTitle.name_ko || "다음 칭호", "inline-badge-icon") : ""}
      </div>
    </article>
  `;
}

function renderAuthorPreview() {
  const rows = Array.isArray(state.adminPreview.author_preview) ? state.adminPreview.author_preview : [];
  document.getElementById("previewAuthors").innerHTML = `
    <div>
      <p class="section-kicker">미리보기</p>
      <h2>대표 닉네임 카드</h2>
      <p class="preview-note">개인 페이지에서 보이는 대표 칭호와 다음 해금 흐름을 요약해 보여줍니다.</p>
    </div>
    <div class="field-grid">
      ${rows.map((row) => {
        const primaryTitle = decorateBadgePayload(row.primary_title);
        const nextBadge = decorateBadgePayload(row.next_badge_progress);
        return `
          <article class="preview-card">
            <strong>${escapeHtml(row.author || "작성자 없음")}</strong>
            <p class="helper">${escapeHtml(primaryTitle?.name_ko || primaryTitle?.short_label_ko || "대표 칭호 대기 중")}</p>
            <div class="chip-row">
              ${primaryTitle?.icon_key ? renderBadgeIcon(state.config, primaryTitle.icon_key, primaryTitle.name_ko || "대표 칭호", "inline-badge-icon") : ""}
              <span class="badge-chip">배지 ${escapeHtml(String(row.unlocked_badge_count || 0))}개</span>
              ${nextBadge?.short_label_ko ? `<span class="badge-chip">다음 ${escapeHtml(nextBadge.short_label_ko)}</span>` : ""}
            </div>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function exportConfig(kind) {
  const targets = {
    site: ["site_config.preview.json", state.config.site_config],
    navigation: ["navigation_config.preview.json", state.config.navigation_config],
    home: ["home_sections.preview.json", state.config.home_sections],
    badges: ["badge_catalog.preview.json", state.config.badge_catalog],
    badge_art: ["badge_art_catalog.preview.json", state.config.badge_art_catalog],
    season: ["season_badges.preview.json", state.config.season_badges],
    gallery: ["gallery_title_rules.preview.json", state.config.gallery_title_rules],
    profile: ["profile_layout_config.preview.json", state.config.profile_layout_config],
    bundle: ["admin_bundle.preview.json", state.config],
  };
  const target = targets[kind];
  if (!target) return;
  downloadJson(target[0], target[1]);
}

function moveSection(index, direction) {
  const list = Array.isArray(state.config.home_sections?.ranking_sections) ? [...state.config.home_sections.ranking_sections] : [];
  const nextIndex = direction === "up" ? index - 1 : index + 1;
  if (nextIndex < 0 || nextIndex >= list.length) return;
  [list[index], list[nextIndex]] = [list[nextIndex], list[index]];
  state.config.home_sections.ranking_sections = list;
}

function textField(label, key, value) {
  return `
    <label class="field">
      <span>${escapeHtml(label)}</span>
      <input type="text" data-site-path="${escapeHtml(key)}" value="${escapeHtml(value)}">
    </label>
  `;
}

function textAreaField(label, key, value) {
  return `
    <label class="field">
      <span>${escapeHtml(label)}</span>
      <textarea data-site-path="${escapeHtml(key)}">${escapeHtml(value)}</textarea>
    </label>
  `;
}

function decorateBadgePayload(payload) {
  if (!payload || typeof payload !== "object") return payload || null;
  const badgeId = payload.badge_id;
  if (!badgeId) return payload;
  const lookup = buildBadgeLookup();
  const nextMeta = lookup.get(badgeId);
  if (!nextMeta) return payload;
  return {
    ...payload,
    name_ko: nextMeta.name_ko || payload.name_ko,
    short_label_ko: nextMeta.short_label_ko || payload.short_label_ko,
    description_ko: nextMeta.description_ko || payload.description_ko,
    icon_key: nextMeta.icon_key || payload.icon_key,
    tier: nextMeta.tier ?? payload.tier,
  };
}

function buildBadgeLookup() {
  const map = new Map();
  const badges = Array.isArray(state.config.badge_catalog?.badges) ? state.config.badge_catalog.badges : [];
  for (const badge of badges) {
    if (badge?.badge_id) {
      map.set(badge.badge_id, badge);
    }
  }
  const rules = Array.isArray(state.config.gallery_title_rules?.rules) ? state.config.gallery_title_rules.rules : [];
  for (const rule of rules) {
    if (rule?.badge_id && !map.has(rule.badge_id)) {
      map.set(rule.badge_id, rule);
    }
  }
  const fallback = state.config.gallery_title_rules?.fallback_title;
  if (fallback?.badge_id && !map.has(fallback.badge_id)) {
    map.set(fallback.badge_id, fallback);
  }
  return map;
}

function getLiveBadgeSummary() {
  const badges = Array.isArray(state.config.badge_catalog?.badges) ? state.config.badge_catalog.badges : [];
  const badge_count_by_category = {};
  for (const badge of badges) {
    const category = badge?.category || "unknown";
    badge_count_by_category[category] = (badge_count_by_category[category] || 0) + 1;
  }
  return {
    badge_count: badges.length,
    badge_count_by_category,
  };
}

async function runSync(mode) {
  setBusy(true);
  const syncLabel = {
    recent: "최근 3일 갱신",
    floor: "3월 1일부터 재수집",
    window: "기간 지정 재수집",
  }[mode] || "파싱 실행";
  setStatus("info", `${syncLabel}을(를) 실행하는 중입니다.`);
  renderToolbarState();
  renderStatusBanner();

  try {
    const payload = await apiJson("/api/admin/run-sync", {
      method: "POST",
      csrf: true,
      body: {
        mode,
        start_date: state.syncDraft.start_date,
        end_date: state.syncDraft.end_date,
      },
    });
    applyWorkspace(payload);
    state.lastAction = {
      action: payload.action || "run_sync",
      changedKeys: [],
      rebuildTriggered: Boolean(payload.rebuild_triggered),
      rebuildSummary: payload.rebuild_summary || null,
    };
    const windowText = payload.sync_window
      ? ` (${payload.sync_window.start} ~ ${payload.sync_window.end})`
      : "";
    setStatus("success", `${syncLabel}${windowText} 완료. 최신 집계로 다시 렌더했습니다.`);
    render();
  } catch (error) {
    setStatus("error", resolveErrorMessage(error, `${syncLabel}에 실패했습니다.`), extractErrors(error));
    renderStatusBanner();
  } finally {
    setBusy(false);
    renderToolbarState();
  }
}

async function uploadBadgeIcon(runRebuild = false) {
  if (!state.uploadDraft.content_base64) {
    setStatus("warning", "업로드할 이미지 파일을 먼저 선택해 주세요.");
    renderStatusBanner();
    return;
  }

  setBusy(true);
  setStatus("info", runRebuild ? "아이콘을 저장하고 rebuild 하는 중입니다." : "아이콘을 저장하는 중입니다.");
  renderToolbarState();

  try {
    const payload = await apiJson("/api/admin/badge-icons/upload", {
      method: "POST",
      csrf: true,
      body: {
        payload: {
          icon_key: state.uploadDraft.icon_key,
          family: state.uploadDraft.family,
          filename: state.uploadDraft.filename,
          content_base64: state.uploadDraft.content_base64,
          color_notes: state.uploadDraft.color_notes,
          display_notes: state.uploadDraft.display_notes,
          tier_compatibility: csvToList(state.uploadDraft.tier_compatibility),
          badge_id_prefixes: csvToList(state.uploadDraft.badge_id_prefixes),
        },
        run_rebuild: runRebuild,
      },
    });

    await refreshWorkspace();
    state.lastAction = {
      action: payload.action || "upload_badge_icon",
      changedKeys: Array.isArray(payload.changed_keys) ? payload.changed_keys : ["badge_art_catalog"],
      rebuildTriggered: Boolean(payload.rebuild_triggered),
      rebuildSummary: payload.rebuild_summary || null,
    };
    clearUploadDraft();
    setStatus("success", runRebuild ? "아이콘 업로드와 rebuild 가 완료되었습니다." : "아이콘을 저장했습니다. 공개 페이지 반영은 rebuild 후 확인해 주세요.");
    render();
  } catch (error) {
    setStatus("error", resolveErrorMessage(error, "아이콘 업로드에 실패했습니다."), extractErrors(error));
    renderStatusBanner();
  } finally {
    setBusy(false);
    renderToolbarState();
  }
}

async function captureFileContent(file) {
  if (!file) {
    clearUploadDraft();
    renderBadgeArtEditor();
    return;
  }

  state.uploadDraft.filename = file.name;
  state.uploadDraft.content_base64 = await fileToBase64(file);
  renderBadgeArtEditor();
  renderToolbarState();
}

async function fileToBase64(file) {
  const arrayBuffer = await file.arrayBuffer();
  const bytes = new Uint8Array(arrayBuffer);
  let binary = "";
  for (let index = 0; index < bytes.byteLength; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary);
}

function clearUploadDraft() {
  state.uploadDraft = {
    icon_key: "",
    family: "custom",
    badge_id_prefixes: "fun",
    tier_compatibility: "starter,rally,gold,prism",
    color_notes: "",
    display_notes: "",
    filename: "",
    content_base64: "",
  };
}

function csvToList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function hasUnsavedChanges() {
  return JSON.stringify(state.baseConfig) !== JSON.stringify(state.config);
}

async function apiJson(path, options = {}) {
  const headers = {
    Accept: "application/json",
    ...(options.headers || {}),
  };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.csrf && state.csrfToken) {
    headers["X-Admin-CSRF"] = state.csrfToken;
  }

  const response = await fetch(path, {
    method: options.method || "GET",
    cache: "no-store",
    credentials: "same-origin",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch (_error) {
    payload = null;
  }

  if (response.status === 401) {
    redirectToLogin();
  }

  if (!response.ok) {
    const error = new Error(resolveErrorMessage({ payload, status: response.status }, `${options.method || "GET"} ${path} 실패`));
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload || {};
}

function redirectToLogin() {
  const next = `${window.location.pathname}${window.location.search || ""}`;
  window.location.href = `./admin-login.html?next=${encodeURIComponent(next)}`;
}

function resolveErrorMessage(error, fallback) {
  const payload = error?.payload || error;
  return payload?.message || payload?.error || error?.message || fallback;
}

function extractErrors(error) {
  const errors = error?.payload?.errors;
  return Array.isArray(errors) ? errors : [];
}

function setStatus(kind, message, errors = []) {
  state.status = {
    kind,
    message,
    errors: Array.isArray(errors) ? errors : [],
  };
}

function setBusy(value) {
  state.busy = Boolean(value);
}

function setNestedValue(target, path, value) {
  const segments = String(path || "").split(".").filter(Boolean);
  if (!segments.length) return;
  let cursor = target;
  for (const segment of segments.slice(0, -1)) {
    if (!cursor[segment] || typeof cursor[segment] !== "object" || Array.isArray(cursor[segment])) {
      cursor[segment] = {};
    }
    cursor = cursor[segment];
  }
  cursor[segments[segments.length - 1]] = value;
}

function chip(label) {
  return `<span class="meta-chip">${escapeHtml(label)}</span>`;
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value || {}));
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value || "";
}

function formatExpiry(epochSeconds) {
  const numeric = Number(epochSeconds || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "-";
  return new Date(numeric * 1000).toLocaleString("ko-KR", { hour12: false });
}

function emptyBundle() {
  return {
    site_config: {},
    navigation_config: { items: [] },
    home_sections: { ranking_sections: [] },
    badge_catalog: { badges: [] },
    badge_art_catalog: { icons: [], family_map: {}, tier_palettes: [] },
    season_badges: {},
    gallery_title_rules: { rules: [], fallback_title: {} },
    profile_layout_config: {},
  };
}
