const G = window.ReviewGuard;

const state = {
  profile: null,
  profileStates: {},
  checklist: null,
  zip: null,
  results: new Map(),
  report: null,
  overrides: [],
  reviewedProfile: null,
  filter: "all",
  expanded: true,
  updatedAt: null,
  busy: false,
};

const $ = (selector) => document.querySelector(selector);
const els = {
  model: $("#modelInput"),
  sourceList: $("#sourceList"),
  profileBar: $("#profileBar"),
  changelogTitle: $("#changelogTitle"),
  changelogNote: $("#changelogNote"),
  changelogLink: $("#changelogLink"),
  changelogList: $("#changelogList"),
  categoryStatus: $("#categoryStatus"),
  policyStatus: $("#policyStatus"),
  generate: $("#generateBtn"),
  updatedAt: $("#updatedAt"),
  dropzone: $("#dropzone"),
  zipInput: $("#zipInput"),
  busyTitle: $("#busyTitle"),
  busyDetail: $("#busyDetail"),
  doneTitle: $("#doneTitle"),
  doneDetail: $("#doneDetail"),
  errorDetail: $("#errorDetail"),
  reviewAgain: $("#reviewAgainBtn"),
  status: $("#status"),
  checklist: $("#checklist"),
  checklistCount: $("#checklistCount"),
  scoreCard: $("#scoreCard"),
  scoreValue: $("#scoreValue"),
  scoreCaption: $("#scoreCaption"),
  scoreFormula: $("#scoreFormula"),
  stateBadge: $("#stateBadge"),
  layerCards: $("#layerCards"),
  scoreMeta: $("#scoreMeta"),
  reportActions: $("#reportActions"),
  copyReport: $("#copyReportBtn"),
  downloadReport: $("#downloadReportBtn"),
  checklistTools: $("#checklistTools"),
  expandAll: $("#expandAllBtn"),
  modal: $("#updateModal"),
  modalBody: $("#modalBody"),
  closeModal: $("#closeModalBtn"),
};

const PROFILE_NAMES = { t3: "Terminus 3", t4: "Terminus 4" };

function setStatus(message) {
  els.status.textContent = message;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function safeUrl(url) {
  // Only http(s) links from the server are rendered as anchors.
  return /^https?:\/\//i.test(String(url || "")) ? escapeHtml(url) : "";
}

async function request(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

const profileQuery = () => `profile=${encodeURIComponent(state.profile || "t3")}`;
const modelName = () => (els.model.value || els.model.textContent || "qwen2.5:3b").trim();

// ------------------------------------------------------------------ profile bar

function renderProfileBar() {
  const buttons = ["t3", "t4"].map((key) => {
    const info = state.profileStates[key] || {};
    const on = key === state.profile;
    const unavailable = info.status === "unavailable";
    const badge = key === "t4" && info.status ? `<span class="profile-state ${escapeHtml(info.status)}">${escapeHtml(info.status)}</span>` : "";
    return `<button type="button" class="profile-btn ${on ? "on" : "off"}" data-profile="${key}"
              aria-pressed="${on}" ${unavailable ? "disabled" : ""}
              title="${escapeHtml(info.reason || PROFILE_NAMES[key])}">${PROFILE_NAMES[key]}${badge}</button>`;
  }).join("");
  const t4 = state.profileStates.t4 || {};
  els.profileBar.innerHTML =
    `<span class="profile-label">Policy profile</span>${buttons}` +
    `<span class="profile-detail">${escapeHtml(state.checklistLabel || "")}</span>` +
    (t4.status === "unavailable" ? `<span class="profile-warn">Terminus 4 unavailable: ${escapeHtml(t4.reason)}</span>` : "");
  els.profileBar.hidden = false;
  els.profileBar.querySelectorAll("button[data-profile]").forEach((btn) => {
    btn.addEventListener("click", () => switchProfile(btn.dataset.profile));
  });
}

async function switchProfile(next) {
  if (next === state.profile || state.busy) return;
  Object.assign(state, G.resetForProfileChange(state, next));
  history.replaceState(null, "", `?profile=${encodeURIComponent(next)}`);
  resetScoreCard();
  await Promise.all([loadChecklist(), loadChangelog(), loadCategoryStatus()]);
  if (state.zip && state.stale) {
    setDrop("idle");
    els.reviewAgain.hidden = false;
    els.reviewAgain.textContent = `Review ${state.zip.name} under ${PROFILE_NAMES[next]}?`;
    setStatus(`Switched to ${PROFILE_NAMES[next]}. The previous result was cleared; nothing was re-run.`);
  } else {
    setStatus(`Switched to ${PROFILE_NAMES[next]}.`);
  }
}

// ------------------------------------------------------------------ project updates

function renderSources(panels) {
  const sources = panels?.sources || [];
  els.sourceList.innerHTML = sources.length
    ? sources.map((s) => {
        const tba = s.state !== "ok";
        const href = safeUrl(s.url);
        const inner = `<span class="source-name">${escapeHtml(s.label || s.path)}</span><code>${escapeHtml(s.path)}</code>${tba ? '<span class="tba-tag">TBA</span>' : ""}`;
        return href && !tba
          ? `<a class="source-card" href="${href}" target="_blank" rel="noreferrer">${inner}</a>`
          : `<span class="source-card is-tba">${inner}</span>`;
      }).join("")
    : `<span class="source-card is-tba"><span class="source-name">Sources</span><span class="tba-tag">TBA</span></span>`;
}

function renderUpdatedAt() {
  if (!state.updatedAt) {
    els.updatedAt.textContent = "";
    return;
  }
  // T3: when the saved checklist was last regenerated. T4: the clone's HEAD
  // commit time, which is not necessarily a policy change, hence "source".
  const exact = new Date(state.updatedAt);
  const t4 = state.profile === "t4";
  els.updatedAt.textContent = `${t4 ? "source updated" : "updated"} ${G.relativeTime(state.updatedAt)}`;
  els.updatedAt.title = Number.isNaN(exact.getTime()) ? "" :
    `${exact.toLocaleString()} · ${t4 ? "HEAD commit of the terminal-bench clone" : "last checklist regeneration"}`;
}
setInterval(renderUpdatedAt, 30000);

function applyPanels(panels) {
  if (!panels) return;
  els.changelogTitle.textContent = panels.updates_title || "Project updates";
  els.changelogNote.textContent = panels.updates_note || "";
  const link = safeUrl(panels.changelog_url);
  if (link) els.changelogLink.href = panels.changelog_url;
  els.changelogLink.hidden = !link;
  renderSources(panels);
}

function renderChangelog(payload) {
  const entries = payload.entries || [];
  if (!entries.length) {
    els.changelogList.className = "changelog-list empty";
    els.changelogList.textContent = payload.note || "TBA: no updates published for this profile.";
    return;
  }
  els.changelogList.className = "changelog-list";
  els.changelogList.innerHTML = entries.map((entry) => {
    const href = safeUrl(entry.url);
    const body = `
      <div class="change-meta">
        <span>${escapeHtml(entry.date)}</span>
        <strong>${escapeHtml(entry.type)}</strong>
        ${entry.sha ? `<code>${escapeHtml(entry.sha)}</code>` : ""}
      </div>
      <p>${escapeHtml(entry.change)}</p>`;
    return href
      ? `<a class="change-item" href="${href}" target="_blank" rel="noreferrer">${body}</a>`
      : `<article class="change-item">${body}</article>`;
  }).join("");
}

// Status text is shown as published (emoji included), as the legacy tool did;
// the class only tints it.
function statusCell(text) {
  const value = String(text || "");
  const kind = value.startsWith("✅") ? "ok" : value.startsWith("\u{1F6AB}") ? "no" : /^TBA\b/.test(value) ? "tba" : "info";
  return `<span class="status-${kind}">${escapeHtml(value)}</span>`;
}

function renderStatusTable(table) {
  const headers = table.headers || [];
  const rows = table.rows || [];
  const titleUrl = safeUrl(table.url);
  const title = titleUrl
    ? `<a href="${titleUrl}" target="_blank" rel="noreferrer">${escapeHtml(table.title)} ↗</a>`
    : escapeHtml(table.title);
  return `
    <article class="status-table-block">
      <h4>${title}</h4>
      <div class="table-scroll">
        <table>
          <thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead>
          <tbody>
            ${rows.map((row) => `<tr>${headers.map((h) => {
              const link = safeUrl(row._links?.[h]);
              const cell = h === "Status" ? statusCell(row[h]) : escapeHtml(row[h] || "");
              const cls = h !== "Status" ? "" : String(row[h] || "").length <= 16 ? "status-cell short" : "status-cell";
              return `<td class="${cls}">${link ? `<a href="${link}" target="_blank" rel="noreferrer">${cell}</a>` : cell}</td>`;
            }).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>
    </article>`;
}

function renderCategoryStatus(payload) {
  const tables = payload.tables || [];
  // Policies sit under Latest Changes; categories keep the right column, so the
  // two columns balance instead of one running long.
  const policy = tables.filter((t) => /polic/i.test(t.title || ""));
  const other = tables.filter((t) => !/polic/i.test(t.title || ""));
  els.policyStatus.innerHTML = policy.map(renderStatusTable).join("");
  if (!other.length) {
    els.categoryStatus.className = "status-tables empty";
    els.categoryStatus.textContent = payload.note || "TBA: no category data for this profile.";
    return;
  }
  els.categoryStatus.className = "status-tables";
  els.categoryStatus.innerHTML = other.map(renderStatusTable).join("");
}

// ------------------------------------------------------------------ checklist

const OUTCOME = {
  static: { satisfied: "pass", not_applicable: "not applicable", missing: "fail", partial: "fail" },
  rubric: { missing: "concern" },
};

function outcomeOf(result) {
  if (!result) return "unchecked";
  const layer = result.layer || "rubric";
  if (layer === "static") return OUTCOME.static[result.status] || "unknown";
  if (layer === "rubric") return OUTCOME.rubric[result.status] || result.status.replace("_", " ");
  return result.status === "satisfied" || result.status === "not_applicable" ? "ok" : "open";
}

function bucketOf(item, result) {
  if (!result) return "unchecked";
  const outcome = outcomeOf(result);
  const layer = result.layer || item.layer || "rubric";
  if (layer === "static") return outcome === "fail" ? "failing" : outcome === "unknown" ? "unknown" : "passed";
  if (layer === "rubric") return ["concern", "partial", "unknown"].includes(outcome) ? "rubric" : "passed";
  return outcome === "open" ? "advisory" : "passed";
}

function matchesFilter(bucket) {
  switch (state.filter) {
    case "all": return true;
    case "attention": return ["failing", "unknown", "rubric"].includes(bucket);
    case "failing": return bucket === "failing";
    default: return bucket === state.filter;
  }
}

function renderChecklist(payload) {
  state.checklist = payload.checklist;
  state.checklistLabel = payload.profile_label || "";
  const items = state.checklist.items || [];
  const counts = items.reduce((acc, i) => ((acc[i.layer || "rubric"] = (acc[i.layer || "rubric"] || 0) + 1), acc), {});
  els.checklistCount.textContent =
    `${counts.static || 0} static · ${counts.rubric || 0} rubric · ${counts.advisory || 0} advisory`;
  els.checklist.classList.remove("empty");
  repaintChecklist();
}

function lineageChips(item) {
  return (item.lineage || []).map((l) => {
    const target = l.rule ? escapeHtml(l.rule) : "no counterpart";
    return `<span class="pill lineage" title="Sources: ${escapeHtml(l.sources || "none")}">${escapeHtml(l.version)} · ${target} · ${escapeHtml(l.relation)}</span>`;
  }).join("");
}

function resolveForm(item) {
  return `
    <form class="resolve-form" data-id="${escapeHtml(item.id)}" hidden>
      <p class="resolve-note">Resolve this unknown with evidence. The original result is kept on record.</p>
      <label>Reviewer <input name="reviewer" required maxlength="120" autocomplete="name" /></label>
      <label>Determination
        <select name="determination">
          ${item.layer === "static"
            ? '<option value="pass">pass</option><option value="fail">fail</option>'
            : '<option value="satisfied">satisfied</option><option value="concern">concern</option>'}
        </select>
      </label>
      <label class="wide">Evidence <textarea name="evidence" required maxlength="2000" rows="2"></textarea></label>
      <label class="wide">Reason <input name="reason" required maxlength="500" /></label>
      <div class="resolve-actions">
        <button type="submit" class="small-button">Record override</button>
        <button type="button" class="text-button" data-cancel>Cancel</button>
      </div>
    </form>`;
}

function renderChecklistItem(item, result) {
  const outcome = outcomeOf(result);
  const bucket = bucketOf(item, result);
  const layer = result?.layer || item.layer || "rubric";
  const passed = bucket === "passed";
  const open = state.expanded ? " open" : "";
  const resolvable = G.canResolve(result);
  const detail = result ? `
      <p class="ev"><strong>Evidence</strong> ${escapeHtml(result.evidence || "")}</p>
      <p class="ev"><strong>Fix</strong> ${escapeHtml(result.recommendation || "")}</p>
      <p class="ev src"><strong>Source</strong> ${escapeHtml(result.assessment_source || "unspecified")}</p>` : "";
  return `
    <details class="check-item bucket-${bucket}"${open}>
      <summary class="check-row">
        <input type="checkbox" ${passed ? "checked" : ""} disabled tabindex="-1" aria-label="${escapeHtml(item.criterion)}" />
        <span class="box-text">${escapeHtml(item.criterion)}</span>
        <span class="tag tag-${escapeHtml(layer)}">${escapeHtml(layer)}</span>
        <span class="status-pill s-${escapeHtml(outcome.replace(" ", "-"))}">${escapeHtml(result ? outcome : "not checked")}</span>
      </summary>
      <div class="check-body">
        ${detail}
        <p class="how"><strong>Why</strong> ${escapeHtml(truncate(item.why_it_matters, 320))}</p>
        <p class="how"><strong>Check</strong> ${escapeHtml(truncate(item.how_to_check, 220))}</p>
        <div class="meta">
          <span class="pill">${escapeHtml(item.category)}</span>
          <span class="pill">${escapeHtml(item.severity)}</span>
          <span class="pill mono">${escapeHtml(item.id)}</span>
          ${lineageChips(item)}
          ${resolvable ? `<button type="button" class="text-button" data-resolve="${escapeHtml(item.id)}">Resolve with evidence</button>` : ""}
        </div>
        ${resolvable ? resolveForm({ ...item, layer }) : ""}
      </div>
    </details>`;
}

function truncate(text, max) {
  const value = String(text ?? "");
  return value.length > max ? value.slice(0, max).trimEnd() + "…" : value;
}

function repaintChecklist() {
  const items = state.checklist?.items || [];
  const reviewed = state.results.size > 0;
  const rows = items.map((item) => ({ item, result: state.results.get(item.id) || null }))
    .map((row) => ({ ...row, bucket: bucketOf(row.item, row.result) }));
  const visible = reviewed ? rows.filter((r) => matchesFilter(r.bucket)) : rows;
  const order = { failing: 0, unknown: 1, rubric: 2, advisory: 3, unchecked: 4, passed: 5 };
  visible.sort((a, b) => order[a.bucket] - order[b.bucket]);
  if (!visible.length) {
    els.checklist.innerHTML = `<p class="empty-filter">Nothing in this filter. Try “All”.</p>`;
    return;
  }
  els.checklist.innerHTML = visible.map(({ item, result }) => renderChecklistItem(item, result)).join("");
}

// ------------------------------------------------------------------ score card

function resetScoreCard() {
  els.scoreCard.dataset.state = "empty";
  els.reportActions.hidden = true;
  els.checklistTools.hidden = true;
  state.results = new Map();
  repaintChecklist();
}

function layerCard(title, main, sub, kind) {
  return `<div class="layer-card ${kind}"><span class="layer-title">${title}</span>
            <span class="layer-main">${main}</span><span class="layer-sub">${sub}</span></div>`;
}

function renderReview(payload) {
  state.report = payload;
  state.reviewedProfile = payload.profile;
  state.results = new Map((payload.results || []).map((r) => [r.id, r]));
  const a = payload.assessment || {};
  const s = a.static || {}, r = a.rubric || {}, adv = a.advisory || {};
  const n = (x) => `<b class="num">${escapeHtml(x)}</b>`;
  const staticTotal = (s.pass || 0) + (s.fail || 0) + (s.unknown || 0) + (s.not_applicable || 0);
  const rubricTotal = Object.values(r).reduce((x, y) => x + y, 0);

  const legacy = payload.legacy_score || {};
  els.scoreValue.textContent = legacy.value == null ? "–" : `${legacy.value}%`;
  els.scoreCaption.textContent = `Legacy experimental score over ${legacy.counted ?? 0} resolved items, ` +
    `for reference only. ${legacy.disclaimer || ""} The state beside it is the decision.`;
  els.scoreFormula.textContent = legacy.formula ? `Formula: ${legacy.formula}.` : "";
  els.stateBadge.textContent = payload.overall_state_label || "Review required";
  els.stateBadge.className = `state-badge ${String(payload.overall_state || "review_required").replaceAll("_", "-")}`;
  els.layerCards.innerHTML =
    layerCard("Static gate", `${n(s.pass || 0)}/${n(staticTotal)} passed`,
      `${n(s.fail || 0)} failed · ${n(s.unknown || 0)} unknown · ${n(s.not_applicable || 0)} n/a`, "static") +
    layerCard("Rubric assessment", `${n(r.satisfied || 0)}/${n(rubricTotal)} satisfied`,
      `${n(r.partial || 0)} partial · ${n(r.concern || 0)} concerns · ${n(r.unknown || 0)} unknown`, "rubric") +
    layerCard("Reviewer advisory", `${n(adv.findings || 0)} findings`,
      `of ${n(adv.total || 0)} items · display only`, "advisory");
  const overrides = (payload.human_overrides || []).length;
  els.scoreMeta.innerHTML = [
    `${escapeHtml(PROFILE_NAMES[payload.profile] || payload.profile)} <span class="muted">(${escapeHtml(payload.profile_status || "")})</span>`,
    escapeHtml(payload.model_requested || modelName()),
    escapeHtml(payload.review_mode || ""),
    `${escapeHtml(payload.report_metadata?.duration_sec ?? "?")}s`,
    overrides ? `${overrides} override${overrides > 1 ? "s" : ""}` : "",
  ].filter(Boolean).join(" · ");
  els.scoreCard.dataset.state = "filled";
  els.reportActions.hidden = !payload.report_text;
  els.checklistTools.hidden = false;
  repaintChecklist();
}

// ------------------------------------------------------------------ drop zone + review

let busyTimer = null;

function setDrop(mode, detail) {
  els.dropzone.dataset.state = mode;
  clearInterval(busyTimer);
  if (mode === "busy") {
    const started = Date.now();
    const tick = () => { els.busyDetail.textContent = `${detail} · ${Math.round((Date.now() - started) / 1000)}s`; };
    tick();
    busyTimer = setInterval(tick, 1000);
  }
  if (mode === "error") els.errorDetail.textContent = detail || "";
  els.reviewAgain.hidden = !(mode === "done" || mode === "error");
  els.reviewAgain.textContent = mode === "error" ? "Try again?" : "Review again?";
}

async function startReview(file) {
  if (!file || state.busy) return;
  if (!/\.zip$/i.test(file.name)) {
    setDrop("error", `${file.name} is not a .zip archive.`);
    return;
  }
  const requested = state.profile;
  const guard = G.acceptReview(requested, { profile: requested });
  if (!guard.ok) { setDrop("error", guard.error); return; }

  state.zip = file;
  state.busy = true;
  state.overrides = [];
  els.dropzone.classList.remove("dragging");
  els.busyTitle.textContent = `Reviewing ${file.name}`;
  setDrop("busy", `under ${PROFILE_NAMES[requested]} with ${modelName()}`);
  setStatus(`Reviewing ${file.name}. Nothing from the archive is executed.`);
  try {
    const form = new FormData();
    form.append("checklist", JSON.stringify(state.checklist));
    form.append("zip", file);
    form.append("zip_name", file.name);
    form.append("profile", requested);
    const payload = await request(`/api/review?model=${encodeURIComponent(modelName())}`, { method: "POST", body: form });
    const verdict = G.acceptReview(requested, payload);
    if (!verdict.ok) throw new Error(verdict.error);
    if (state.zip !== file || state.profile !== requested) {
      setDrop("idle");
      setStatus("The .zip or profile changed during the review, so the result was discarded.");
      return;
    }
    renderReview(payload);
    els.doneTitle.textContent = "Review completed";
    els.doneDetail.innerHTML = `using <b>${escapeHtml(payload.model_requested || modelName())}</b> · ${escapeHtml(payload.review_mode)} · ` +
      `${escapeHtml(PROFILE_NAMES[payload.profile])} · ${escapeHtml(payload.report_metadata?.duration_sec ?? "?")}s`;
    setDrop("done");
    setStatus(`${payload.overall_state_label}: ${file.name} under ${PROFILE_NAMES[payload.profile]}.`);
  } catch (error) {
    setDrop("error", error.message);
    setStatus(`Review failed: ${error.message}`);
  } finally {
    state.busy = false;
    els.zipInput.value = "";
  }
}

els.zipInput.addEventListener("change", () => startReview(els.zipInput.files[0]));
els.reviewAgain.addEventListener("click", () => startReview(state.zip));
["dragenter", "dragover"].forEach((type) => els.dropzone.addEventListener(type, (event) => {
  event.preventDefault();
  if (!state.busy) els.dropzone.classList.add("dragging");
}));
["dragleave", "dragend"].forEach((type) => els.dropzone.addEventListener(type, (event) => {
  if (!els.dropzone.contains(event.relatedTarget)) els.dropzone.classList.remove("dragging");
}));
els.dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  els.dropzone.classList.remove("dragging");
  startReview(event.dataTransfer?.files?.[0]);
});

// ------------------------------------------------------------------ overrides

els.checklist.addEventListener("click", (event) => {
  const open = event.target.closest("[data-resolve]");
  if (open) {
    const form = els.checklist.querySelector(`form.resolve-form[data-id="${CSS.escape(open.dataset.resolve)}"]`);
    if (form) { form.hidden = false; form.querySelector("input")?.focus(); }
    return;
  }
  const cancel = event.target.closest("[data-cancel]");
  if (cancel) cancel.closest("form").hidden = true;
});

els.checklist.addEventListener("submit", async (event) => {
  const form = event.target.closest("form.resolve-form");
  if (!form) return;
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form).entries());
  const record = { id: form.dataset.id, ...data };
  try {
    const payload = await request("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review: state.report, checklist: state.checklist,
                             overrides: [...state.overrides, record] }),
    });
    const verdict = G.acceptReview(state.reviewedProfile, payload);
    if (!verdict.ok) throw new Error(verdict.error);
    state.overrides.push(record);
    renderReview(payload);
    setStatus(`Recorded ${data.reviewer}'s override for ${record.id}. The report now lists it.`);
  } catch (error) {
    setStatus(`Override not recorded: ${error.message}`);
  }
});

// ------------------------------------------------------------------ toolbar, update, modal, report

document.querySelectorAll(".filter-chips .chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    state.filter = chip.dataset.filter;
    document.querySelectorAll(".filter-chips .chip").forEach((c) => c.classList.toggle("active", c === chip));
    repaintChecklist();
  });
});

els.expandAll.addEventListener("click", () => {
  state.expanded = !state.expanded;
  els.expandAll.textContent = state.expanded ? "Collapse all" : "Expand all";
  repaintChecklist();
});

els.generate.addEventListener("click", async () => {
  if (els.generate.classList.contains("spinning")) return;
  els.generate.classList.add("spinning");
  els.generate.disabled = true;
  setStatus(state.profile === "t4" ? "Re-reading Terminus 4 policy from the clone…" : "Updating the checklist from the Terminus 3 portal…");
  try {
    const payload = await request(`/api/checklist?model=${encodeURIComponent(modelName())}&${profileQuery()}`, { method: "POST" });
    renderChecklist(payload);
    state.updatedAt = payload.updated_at || state.updatedAt;
    renderUpdatedAt();
    if (payload.diff) renderUpdateModal(payload.diff);
    setStatus(payload.note || "Checklist updated.");
  } catch (error) {
    setStatus(`Update failed: ${error.message}`);
  } finally {
    els.generate.classList.remove("spinning");
    els.generate.disabled = false;
  }
});

function renderUpdateModal(diff) {
  const added = diff?.added || [];
  const changed = diff?.changed || [];
  const removed = diff?.removed || [];
  if (!diff?.has_changes) {
    els.modalBody.innerHTML = `<p>No checklist changes found. Current saved checklist is already up to date.</p>`;
  } else {
    els.modalBody.innerHTML = `
      ${renderDiffSection("New checklist items", added.map((item) => item.criterion))}
      ${renderChangedSection(changed)}
      ${renderDiffSection("Removed checklist items", removed.map((item) => item.criterion))}`;
  }
  els.modal.hidden = false;
}

function renderDiffSection(title, lines) {
  if (!lines.length) return "";
  return `<section class="diff-section"><h3>${escapeHtml(title)}</h3>
    <ul>${lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul></section>`;
}

function renderChangedSection(changed) {
  if (!changed.length) return "";
  return `<section class="diff-section"><h3>Changed checklist items</h3>
    ${changed.map((item) => `<article class="changed-item"><strong>${escapeHtml(item.criterion || item.id)}</strong>
      <ul>${(item.changes || []).map((change) => `<li><code>${escapeHtml(change.field)}</code>
        changed from "${escapeHtml(change.before)}" to "${escapeHtml(change.after)}"</li>`).join("")}</ul>
    </article>`).join("")}</section>`;
}

els.closeModal.addEventListener("click", () => { els.modal.hidden = true; });
els.modal.addEventListener("click", (event) => { if (event.target === els.modal) els.modal.hidden = true; });

// Reports stay in memory until the user explicitly copies or downloads one.
els.copyReport.addEventListener("click", async () => {
  if (!state.report?.report_text) return;
  try {
    await navigator.clipboard.writeText(state.report.report_text);
    setStatus("Report copied.");
  } catch {
    setStatus("Clipboard access was unavailable. Use Download TXT instead.");
  }
});

els.downloadReport.addEventListener("click", () => {
  if (!state.report?.report_text) return;
  const url = URL.createObjectURL(new Blob([state.report.report_text], { type: "text/plain;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = state.report.report_filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  setStatus("Report download requested.");
});

// ------------------------------------------------------------------ loading

async function loadChecklist() {
  try {
    const payload = await request(`/api/checklist?${profileQuery()}`);
    state.profile = payload.profile;
    history.replaceState(null, "", `?profile=${encodeURIComponent(payload.profile)}`);
    state.profileStates = payload.profile_states || {};
    state.updatedAt = payload.updated_at || null;
    renderChecklist(payload);
    applyPanels(payload.panels);
    renderProfileBar();
    renderUpdatedAt();
    if (payload.recovery) {
      setStatus(`Warning: ${payload.recovery.reason} ${payload.recovery.action}`);
    } else if (payload.profile_requested_unavailable) {
      setStatus(`Terminus 4 is unavailable (${state.profileStates.t4?.reason}). Showing Terminus 3.`);
    } else {
      setStatus(`${PROFILE_NAMES[state.profile]} checklist loaded. Drop a task .zip to review it.`);
    }
  } catch (error) {
    setStatus(`Could not load checklist: ${error.message}`);
  }
}

async function loadChangelog() {
  try {
    renderChangelog(await request(`/api/changelog?limit=4&${profileQuery()}`));
  } catch (error) {
    els.changelogList.textContent = `Could not load changes: ${error.message}`;
  }
}

async function loadCategoryStatus() {
  try {
    renderCategoryStatus(await request(`/api/category-status?${profileQuery()}`));
  } catch (error) {
    els.categoryStatus.textContent = `Could not load category status: ${error.message}`;
  }
}

state.profile = new URLSearchParams(location.search).get("profile") || "t3";
loadChecklist().then(() => Promise.all([loadChangelog(), loadCategoryStatus()]));
