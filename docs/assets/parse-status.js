import {
  escapeHtml,
  formatDistance,
  formatDurationLabel,
  formatInt,
  getVisibleDateRangeLabel,
  loadParseStatus,
  loadPublicSiteConfig,
  mergeSiteBundles,
} from "./dashboard-common.js?v=20260317d";

const state = {
  parseStatus: null,
  siteBundle: null,
  query: "",
  admin: {
    configured: false,
    authenticated: false,
    csrfToken: "",
    sourcePath: "",
  },
  overridesById: new Map(),
  draftsById: new Map(),
  busyPostId: null,
};

async function init() {
  await refreshAll({ reloadOverrides: true });
  bindEvents();
}

function bindEvents() {
  document.getElementById("statusSearch")?.addEventListener("input", (event) => {
    state.query = String(event.target.value || "").trim().toLowerCase();
    renderRows();
  });

  document.getElementById("unparsedRows")?.addEventListener("input", (event) => {
    const field = event.target?.dataset?.overrideField;
    const postId = Number(event.target?.dataset?.postId || 0);
    if (!field || !postId) return;
    const current = getDraft(postId, findUnparsedRow(postId));
    current[field] = String(event.target.value || "");
    state.draftsById.set(postId, current);
  });

  document.getElementById("unparsedRows")?.addEventListener("click", (event) => {
    const action = event.target?.dataset?.overrideAction;
    const postId = Number(event.target?.dataset?.postId || 0);
    if (!action || !postId) return;
    void handleOverrideAction(action, postId);
  });
}

async function refreshAll({ reloadOverrides = false } = {}) {
  const [parseStatus, publicSiteConfig, session] = await Promise.all([
    loadParseStatus(),
    loadPublicSiteConfig(),
    loadAdminSession(),
  ]);

  state.parseStatus = parseStatus;
  state.siteBundle = mergeSiteBundles(publicSiteConfig, parseStatus);
  state.admin = session;

  if (reloadOverrides && session.authenticated) {
    await loadManualOverrides();
  } else if (!session.authenticated) {
    state.overridesById = new Map();
    state.draftsById = new Map();
  }

  render();
}

async function loadAdminSession() {
  try {
    const response = await fetch("/api/admin/session", {
      cache: "no-store",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    return {
      configured: Boolean(payload.configured),
      authenticated: Boolean(payload.authenticated),
      csrfToken: String(payload.csrf_token || ""),
      sourcePath: String(payload.source_path || ""),
    };
  } catch (_error) {
    return { configured: false, authenticated: false, csrfToken: "", sourcePath: "" };
  }
}

async function loadManualOverrides() {
  const payload = await adminJson("/api/admin/manual-overrides", { method: "GET" });
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  state.admin.sourcePath = String(payload.source_path || "");
  state.overridesById = new Map(rows.map((row) => [Number(row.post_id), row]));
}

function render() {
  renderHero();
  renderAdminPanel();
  renderGuidance();
  renderSummary();
  renderRows();
}

function renderHero() {
  const site = state.siteBundle?.site_config || state.parseStatus?.site_config || {};
  setText("statusEyebrow", "PARSING STATUS");
  setText("statusTitle", "파싱 현황 보드");
  setText(
    "statusCopy",
    site.admin_edit_note_ko
      ? `${site.admin_edit_note_ko} 지금 어떤 글이 자동 반영되고, 어떤 글이 제목 양식 문제로 보류되는지 바로 확인합니다.`
      : "현재 대시보드는 게시글 제목만 공식적으로 읽습니다. 자동 반영된 글과 보류된 글을 여기서 바로 확인할 수 있습니다.",
  );
  setText("statusRange", getVisibleDateRangeLabel(state.parseStatus?.visible_date_range));
  setText(
    "statusGeneratedAt",
    state.parseStatus?.generated_at ? `마지막 생성: ${state.parseStatus.generated_at}` : "생성 시각 정보가 없습니다.",
  );

  document.getElementById("statusHeroChips").innerHTML = [
    chip(`집계 기간 ${getVisibleDateRangeLabel(state.parseStatus?.visible_date_range)}`),
    chip(`파싱 성공 ${formatInt(state.parseStatus?.summary?.parsed_count)}건`, "success"),
    chip(`파싱 실패 ${formatInt(state.parseStatus?.summary?.unparsed_count)}건`, "danger"),
  ].join("");
}

function renderAdminPanel() {
  const panel = document.getElementById("adminPanelStatus");
  if (!panel) return;

  if (!state.admin.configured) {
    panel.className = "status-banner status-banner--danger";
    panel.innerHTML = "<strong>관리자 인증 환경변수가 아직 설정되지 않았습니다.</strong>";
    return;
  }

  if (!state.admin.authenticated) {
    const next = encodeURIComponent("/parse-status.html");
    panel.className = "status-banner status-banner--info";
    panel.innerHTML = `
      <strong>관리자로 로그인하면 실패 건을 원문 수정 없이 수동 보정할 수 있습니다.</strong>
      <p class="panel-muted">보정값은 <code>data/manual_review_overrides.csv</code>에만 저장되고 원문 글은 건드리지 않습니다.</p>
      <a class="row-link" href="./admin-login.html?next=${next}">관리자 로그인</a>
    `;
    return;
  }

  const overrideCount = state.overridesById.size;
  const sourcePath = state.admin.sourcePath || "data/manual_review_overrides.csv";
  panel.className = "status-banner status-banner--success";
  panel.innerHTML = `
    <strong>관리자 보정이 활성화되어 있습니다.</strong>
    <p class="panel-muted">현재 수동 보정 ${escapeHtml(String(overrideCount))}건이 저장되어 있고, 보정값은 <code>${escapeHtml(sourcePath)}</code>에 기록됩니다. 저장하면 rebuild까지 함께 실행해 화면 반영을 바로 확인합니다.</p>
  `;
}

function renderGuidance() {
  const guidance = state.parseStatus?.guidance || {};
  const rules = Array.isArray(guidance.rules_ko) ? guidance.rules_ko : [];
  const examples = Array.isArray(guidance.accepted_examples) ? guidance.accepted_examples : [];

  document.getElementById("statusRules").innerHTML = rules
    .map((rule) => `<li>${escapeHtml(rule)}</li>`)
    .join("");
  setText("officialFormat", guidance.official_format || "1500 / 42:30");
  document.getElementById("acceptedExamples").innerHTML = examples
    .map((example) => chip(example))
    .join("");
}

function renderSummary() {
  const summary = state.parseStatus?.summary || {};
  const cards = [
    {
      title: "집계 대상 글",
      value: `${formatInt(summary.total_visible_records)}건`,
      note: "현재 집계 기간 안에서 확인한 전체 글입니다.",
    },
    {
      title: "파싱 성공",
      value: `${formatInt(summary.parsed_count)}건`,
      note: "제목 양식이 맞아서 자동 반영된 글입니다.",
    },
    {
      title: "파싱 실패",
      value: `${formatInt(summary.unparsed_count)}건`,
      note: "제목 양식이 맞지 않아서 보류된 글입니다.",
    },
    {
      title: "성공률",
      value: `${Number(summary.success_rate_pct || 0).toFixed(1)}%`,
      note: "집계 대상 글 대비 자동 반영 비율입니다.",
    },
  ];

  document.getElementById("statusKpis").innerHTML = cards
    .map(
      (card) => `
        <article class="kpi-card">
          <small>${escapeHtml(card.title)}</small>
          <strong>${escapeHtml(card.value)}</strong>
          <p class="row-note">${escapeHtml(card.note)}</p>
        </article>
      `,
    )
    .join("");

  const reasons = Object.entries(state.parseStatus?.failure_reason_counts || {});
  document.getElementById("failureReasons").innerHTML = reasons.length
    ? reasons.map(([reason, count]) => chip(`${reasonLabel(reason)} ${formatInt(count)}건`, "danger")).join("")
    : chip("현재 실패 사유 없음", "success");
}

function renderRows() {
  const parsedRows = filterRows(state.parseStatus?.parsed_rows || []);
  const unparsedRows = filterRows(state.parseStatus?.unparsed_rows || []);

  setText("parsedHeading", `자동 반영된 글 ${formatInt(parsedRows.length)}건`);
  setText("unparsedHeading", `제목 양식 문제로 보류된 글 ${formatInt(unparsedRows.length)}건`);
  setText(
    "statusFilterNote",
    state.query
      ? `"${state.query}" 검색 결과 기준으로 보여주고 있습니다.`
      : "검색어 없이 보면 전체 목록이 보입니다.",
  );

  document.getElementById("parsedRows").innerHTML = parsedRows.length
    ? parsedRows.map(renderParsedRow).join("")
    : emptyCard("현재 조건에 맞는 파싱 성공 글이 없습니다.");

  document.getElementById("unparsedRows").innerHTML = unparsedRows.length
    ? unparsedRows.map(renderUnparsedRow).join("")
    : emptyCard("현재 조건에 맞는 파싱 실패 글이 없습니다.");
}

function renderParsedRow(row) {
  const source = sourceLabel(row.source);
  const overrideChip = row.manual_override_decision ? chip(`수동 처리 ${manualDecisionLabel(row.manual_override_decision)}`, "success") : "";
  return `
    <article class="row">
      <div class="row-main">
        <div class="row-head">
          <strong class="row-title">${escapeHtml(row.title || "(제목 없음)")}</strong>
          <span class="meta-pill meta-pill--success">${escapeHtml(source)}</span>
          ${overrideChip}
        </div>
        <div class="row-meta">
          <span class="meta-pill">${escapeHtml(row.author || "작성자 없음")}</span>
          <span class="meta-pill">${escapeHtml(row.post_date || "-")}</span>
          <span class="meta-pill">${escapeHtml(formatDistance(row.distance_m))}</span>
          <span class="meta-pill">${escapeHtml(row.total_time_text || formatDurationLabel(row.total_seconds))}</span>
        </div>
      </div>
      <a class="row-link" href="${escapeHtml(row.url || "#")}" target="_blank" rel="noreferrer">원문 보기</a>
    </article>
  `;
}

function renderUnparsedRow(row) {
  const postId = Number(row.post_id || 0);
  const draft = getDraft(postId, row);
  const override = state.overridesById.get(postId) || null;
  const adminControls = state.admin.authenticated
    ? `
      <section class="row-admin">
        <div class="override-grid">
          <label class="override-field">
            <span>보정 거리(m)</span>
            <input type="number" min="1" step="1" data-post-id="${postId}" data-override-field="distance_m" value="${escapeHtml(draft.distance_m || "")}" placeholder="예: 1400">
          </label>
          <label class="override-field">
            <span>보정 시간</span>
            <input type="text" data-post-id="${postId}" data-override-field="total_time_text" value="${escapeHtml(draft.total_time_text || "")}" placeholder="예: 01:47:28">
          </label>
          <label class="override-field override-field--wide">
            <span>메모</span>
            <input type="text" data-post-id="${postId}" data-override-field="note" value="${escapeHtml(draft.note || "")}" placeholder="예: 분 오타 보정">
          </label>
        </div>
        <div class="override-actions">
          <button class="action-button action-button--accent" type="button" data-post-id="${postId}" data-override-action="patch" ${state.busyPostId === postId ? "disabled" : ""}>보정 저장 + rebuild</button>
          <button class="action-button" type="button" data-post-id="${postId}" data-override-action="accept" ${state.busyPostId === postId ? "disabled" : ""}>수동 승인</button>
          <button class="action-button" type="button" data-post-id="${postId}" data-override-action="reject" ${state.busyPostId === postId ? "disabled" : ""}>제외 처리</button>
          <button class="action-button" type="button" data-post-id="${postId}" data-override-action="delete" ${state.busyPostId === postId ? "disabled" : ""}>보정 해제</button>
        </div>
        <p class="panel-muted">원문 글은 수정하지 않고, 이 페이지에서 입력한 값만 수동 보정 파일에 저장합니다.</p>
        ${override ? `<p class="panel-muted">현재 저장된 보정: <strong>${escapeHtml(manualDecisionLabel(override.decision))}</strong>${override.total_time_text ? ` / ${escapeHtml(override.total_time_text)}` : ""}${override.note ? ` / ${escapeHtml(override.note)}` : ""}</p>` : ""}
      </section>
    `
    : "";

  return `
    <article class="row row--stacked">
      <div class="row-main">
        <div class="row-head">
          <strong class="row-title">${escapeHtml(row.title || "(제목 없음)")}</strong>
          <span class="meta-pill meta-pill--danger">${escapeHtml(reasonLabel(row.reason_code))}</span>
        </div>
        <div class="row-meta">
          <span class="meta-pill">${escapeHtml(row.author || "작성자 없음")}</span>
          <span class="meta-pill">${escapeHtml(row.post_date || "-")}</span>
          <span class="meta-pill">post_id ${escapeHtml(String(postId || "-"))}</span>
        </div>
        <p class="row-note">${escapeHtml(row.evidence_text || "실패 근거가 없습니다.")}</p>
        ${adminControls}
      </div>
      <a class="row-link" href="${escapeHtml(row.url || "#")}" target="_blank" rel="noreferrer">원문 보기</a>
    </article>
  `;
}

async function handleOverrideAction(action, postId) {
  const row = findUnparsedRow(postId);
  if (!row) return;
  state.busyPostId = postId;
  renderRows();

  try {
    if (action === "delete") {
      await adminJson("/api/admin/manual-overrides/delete", {
        method: "POST",
        body: { post_id: postId, run_rebuild: true },
      });
    } else {
      const draft = getDraft(postId, row);
      await adminJson("/api/admin/manual-overrides/save", {
        method: "POST",
        body: {
          payload: {
            post_id: postId,
            decision: action,
            distance_m: draft.distance_m,
            total_time_text: draft.total_time_text,
            note: draft.note,
          },
          run_rebuild: true,
        },
      });
    }

    state.draftsById.delete(postId);
    await refreshAll({ reloadOverrides: true });
    setAdminMessage("success", action === "delete" ? "수동 보정을 해제하고 rebuild 했습니다." : "수동 보정을 저장하고 rebuild 했습니다.");
  } catch (error) {
    setAdminMessage("danger", resolveErrorMessage(error));
  } finally {
    state.busyPostId = null;
    renderRows();
  }
}

function getDraft(postId, row) {
  if (state.draftsById.has(postId)) {
    return state.draftsById.get(postId);
  }
  const override = state.overridesById.get(postId);
  const draft = {
    distance_m: override?.distance_m ? String(override.distance_m) : guessDistanceFromTitle(row?.title),
    total_time_text: override?.total_time_text || "",
    note: override?.note || "",
  };
  state.draftsById.set(postId, draft);
  return draft;
}

function guessDistanceFromTitle(title) {
  const text = String(title || "");
  const slashMatch = text.match(/(?:총거리\s*)?(\d{2,5})(?:\s*m)?\s*\//i);
  if (slashMatch?.[1]) return slashMatch[1];
  const genericMatch = text.match(/(?:총거리\s*)?(\d{2,5})(?:\s*m)?/i);
  return genericMatch?.[1] || "";
}

function findUnparsedRow(postId) {
  return (state.parseStatus?.unparsed_rows || []).find((row) => Number(row.post_id) === Number(postId)) || null;
}

function filterRows(rows) {
  if (!state.query) return rows;
  return rows.filter((row) => {
    const haystack = `${row.author || ""} ${row.title || ""} ${row.reason_code || ""}`.toLowerCase();
    return haystack.includes(state.query);
  });
}

async function adminJson(path, { method = "GET", body = null } = {}) {
  const headers = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-Admin-CSRF"] = state.admin.csrfToken || "";
  }
  const response = await fetch(path, {
    method,
    cache: "no-store",
    credentials: "same-origin",
    headers,
    body: body ? JSON.stringify(body) : null,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.message || payload.error || "요청을 처리하지 못했습니다.");
    error.payload = payload;
    throw error;
  }
  return payload;
}

function setAdminMessage(kind, message) {
  const panel = document.getElementById("adminPanelStatus");
  if (!panel) return;
  panel.className = `status-banner status-banner--${kind}`;
  panel.innerHTML = `<strong>${escapeHtml(message)}</strong>`;
}

function chip(label, kind = "") {
  const className = kind ? `chip chip--${kind}` : "chip";
  return `<span class="${className}">${escapeHtml(label)}</span>`;
}

function emptyCard(message) {
  return `<article class="empty-card"><p class="empty-note">${escapeHtml(message)}</p></article>`;
}

function reasonLabel(reasonCode) {
  return {
    TITLE_FORMAT_MISSING: "제목 양식 없음",
    TITLE_FORMAT_INVALID: "제목 양식 불일치",
  }[reasonCode] || String(reasonCode || "UNKNOWN");
}

function manualDecisionLabel(decision) {
  return {
    patch: "수동 보정",
    accept: "수동 승인",
    reject: "제외 처리",
  }[decision] || String(decision || "-");
}

function sourceLabel(source) {
  return {
    title_format: "제목 양식 성공",
    manual_review: "수동 승인",
    manual_patch: "수동 보정",
  }[source] || String(source || "unknown");
}

function resolveErrorMessage(error) {
  const payload = error?.payload;
  if (Array.isArray(payload?.errors) && payload.errors.length) {
    return payload.errors.join(" / ");
  }
  return error?.message || "요청을 처리하지 못했습니다.";
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value || "";
}

if (typeof document !== "undefined") {
  init().catch((error) => {
    console.error(error);
    setText("statusTitle", "파싱 현황 보드를 불러오지 못했습니다.");
    setText("statusCopy", "parse_status.json 또는 site_config.json을 확인해 주세요.");
  });
}
