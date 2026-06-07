/**
 * dashboard.js — PGM Map Studio dashboard page.
 *
 * State machine:
 *   init → loadConfig → loadSources → renderList
 *   selectMap → fetchStatus → renderDetail
 *   runPipeline → SSE → step updates → refresh
 */

import * as api from "./api.js";
import { showSystemError, clearSystemError, showToast } from "./shared/ui-helpers.js";

const _AVATAR_EMPTY = "data:image/gif;base64,R0lGODlhEAAQAAAAACwAAAAAEAAQAAABEIQBADs=";
function _avatarUrl(uuid) {
  return `https://mc-heads.net/avatar/${encodeURIComponent(uuid)}/16`;
}

// ── State ──────────────────────────────────────────────────────────────────

const state = {
  sources:     [],   // [{slug, display_name, has_xml, editor_ready, info}]
  selected:    null, // slug string
  status:      null, // {steps, all_done, editor_ready, info}
  isRunning:   false,
  filters:     { teams: null, wools: null, symmetry: null },
  filterOpen:  false,
};

// ── DOM ────────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);

const actMapsBtn        = $("dash-act-maps");
const actSketchesBtn    = $("dash-act-sketches");
const actSettingsBtn    = $("dash-act-settings");
const tabMapsContent    = $("tab-maps-content");
const tabSketchContent  = $("tab-sketches-content");
const tabSettingsContent = $("tab-settings-content");
const sketchListEl     = $("sketch-list");
const newSketchBtn     = $("new-sketch-btn");
const mapListEl        = $("map-list");
const mapFilterEl      = $("map-filter");
const mapCountBadge    = $("map-count-badge");
const filterBtn        = $("filter-btn");
const filterPanel      = $("filter-panel");
const urlImportInput   = $("url-import-input");
const urlImportBtn     = $("url-import-btn");
const urlImportStatus  = $("url-import-status");
const mapDetailEmpty   = $("map-detail-empty");
const mapDetailContent = $("map-detail-content");
const detailBadges     = $("detail-badges");
const detailName       = $("detail-name");
const detailVersion    = $("detail-version");
const detailAuthors    = $("detail-authors");
const detailSteps      = $("detail-steps");
const detailThumb           = $("detail-thumb");
const detailThumbPH         = $("detail-thumb-placeholder");
const openEditorBtn         = $("open-editor-btn");
const runPipelineBtn        = $("run-pipeline-btn");
const pipelineConsole       = $("pipeline-console");
const consoleOutput         = $("console-output");
const consoleClearBtn       = $("console-clear-btn");
const mapsFolderInput       = $("maps-folder-input");
const outputFolderInput     = $("output-folder-input");
const saveSettingsBtn       = $("save-settings-btn");
const settingsMsg           = $("settings-msg");
const errorDismissBtn       = $("error-dismiss-btn");
const sketchDetailContent   = $("sketch-detail-content");
const sketchDetailBadges    = $("sketch-detail-badges");
const sketchDetailName      = $("sketch-detail-name");
const sketchDetailVersion   = $("sketch-detail-version");
const sketchDetailSteps     = $("sketch-detail-steps");
const sketchDetailActions   = $("sketch-detail-actions");

// ── Init ──────────────────────────────────────────────────────────────────

errorDismissBtn.addEventListener("click", clearSystemError);

function showDetailEmpty() {
  mapDetailEmpty.hidden      = false;
  mapDetailContent.hidden    = true;
  sketchDetailContent.hidden = true;
  mapDetailEmpty.textContent = "Select an item from the list.";
}

newSketchBtn.addEventListener("click", async () => {
  newSketchBtn.disabled = true;
  try {
    const { id } = await api.createSketch();
    window.location.href = `/sketch?id=${encodeURIComponent(id)}`;
  } catch (err) {
    showSystemError(`Could not create sketch: ${err.message}`);
    newSketchBtn.disabled = false;
  }
});

// ── Activity switching ────────────────────────────────────────────────────

let _activeActivity = "maps";

function switchActivity(activity) {
  _activeActivity = activity;

  actMapsBtn.classList.toggle("active",     activity === "maps");
  actSketchesBtn.classList.toggle("active", activity === "sketches");
  actSettingsBtn.classList.toggle("active", activity === "settings");

  tabMapsContent.hidden     = activity !== "maps";
  tabSketchContent.hidden   = activity !== "sketches";
  tabSettingsContent.hidden = activity !== "settings";

  if (activity === "maps") {
    if (state.selected && state.status) {
      sketchDetailContent.hidden = true;
      mapDetailEmpty.hidden      = true;
      mapDetailContent.hidden    = false;
      renderDetail(state.selected, state.status);
    } else if (state.sources.length) {
      selectMap(state.sources[0].slug);
    } else {
      showDetailEmpty();
    }
  } else if (activity === "sketches") {
    if (_selectedSketchId && _selectedSketchData) {
      mapDetailContent.hidden    = true;
      mapDetailEmpty.hidden      = true;
      sketchDetailContent.hidden = false;
      renderSketchDetail(_selectedSketchData);
    } else if (_sketches.length) {
      selectSketch(_sketches[0].id);
    } else {
      showDetailEmpty();
    }
  } else {
    showDetailEmpty();
  }
}

actMapsBtn.addEventListener("click",     () => switchActivity("maps"));
actSketchesBtn.addEventListener("click", () => switchActivity("sketches"));
actSettingsBtn.addEventListener("click", () => switchActivity("settings"));

async function init() {
  await loadConfig();
  await Promise.all([loadSources(), loadSketches()]);
}

// ── Sketch list ───────────────────────────────────────────────────────────

async function loadSketches() {
  try {
    const sketches = await api.fetchSketches();
    renderSketches(sketches);
    if (_activeActivity === "sketches" && !_selectedSketchId && sketches.length) {
      selectSketch(sketches[0].id);
    }
  } catch {
    sketchListEl.innerHTML = '<div class="list-empty">Could not load sketches.</div>';
  }
}

let _sketches = [];
let _selectedSketchId   = null;
let _selectedSketchData = null;

function renderSketches(sketches) {
  _sketches = sketches;
  if (!sketches.length) {
    sketchListEl.innerHTML = '<div class="list-empty">No sketches yet.</div>';
    return;
  }
  sketchListEl.innerHTML = "";
  for (const s of sketches) {
    const row = document.createElement("div");
    const isExported = !!s.export_slug;
    const dotClass   = isExported ? "map-status-dot--ready" : "map-status-dot--partial";
    const hasName    = !!s.name?.trim();
    const displayName = hasName ? s.name : "Untitled sketch";

    row.className = "list-row" + (s.id === _selectedSketchId ? " list-row--selected" : "");
    row.dataset.sketchId = s.id;
    row.innerHTML = `
      <span class="map-status-dot ${dotClass}"></span>
      <span class="map-list-name${hasName ? "" : " map-list-name--muted"}">${displayName}</span>
    `;
    row.addEventListener("click", () => selectSketch(s.id));
    sketchListEl.appendChild(row);
  }
}

async function selectSketch(id) {
  _selectedSketchId   = id;
  _selectedSketchData = null;
  renderSketches(_sketches);

  showDetailEmpty();
  mapDetailEmpty.textContent = "Loading…";

  try {
    const data = await api.fetchSketch(id);
    _selectedSketchData = data;
    renderSketchDetail(data);
  } catch (err) {
    mapDetailEmpty.textContent = `Could not load sketch: ${err.message}`;
  }
}

function renderSketchDetail(data) {
  const isExported = !!data.export_slug;
  const hasName    = !!data.name?.trim();

  mapDetailEmpty.hidden     = true;
  mapDetailContent.hidden   = true;
  sketchDetailContent.hidden = false;

  // Badges
  sketchDetailBadges.innerHTML = "";
  _addSketchBadge(isExported ? "exported" : "in progress", isExported ? "success" : "warning");
  if (data.setup?.mirror_mode) _addSketchBadge(data.setup.mirror_mode.replace("_", " "), "neutral");

  // Name + version
  sketchDetailName.textContent    = hasName ? data.name : "Untitled sketch";
  sketchDetailName.className      = "map-detail-name" + (hasName ? "" : " map-detail-name--muted");
  sketchDetailVersion.textContent = data.version ? `v${data.version}` : "";

  // Layout summary
  const shapes  = data.layout?.shapes  ?? [];
  const islands = data.layout?.islands ?? [];
  sketchDetailSteps.innerHTML = "";
  const rows = [
    { label: "Shapes",  value: shapes.length  || "none" },
    { label: "Islands", value: islands.length || "none" },
  ];
  if (data.setup?.bbox) {
    const b = data.setup.bbox;
    rows.push({ label: "Bounds", value: `${b.max_x - b.min_x} × ${b.max_z - b.min_z}` });
  }
  for (const { label, value } of rows) {
    const r = document.createElement("div");
    r.className = "step-row";
    r.innerHTML = `<span class="step-label">${label}</span><span class="step-detail">${value}</span>`;
    sketchDetailSteps.appendChild(r);
  }

  // Action buttons
  sketchDetailActions.innerHTML = "";
  const continueBtn = document.createElement("a");
  continueBtn.className = "action-btn action-btn--primary";
  continueBtn.href = `/sketch?id=${encodeURIComponent(data.id)}`;
  continueBtn.textContent = "Continue editing →";
  sketchDetailActions.appendChild(continueBtn);

  if (isExported) {
    const editorBtn = document.createElement("a");
    editorBtn.className = "action-btn";
    editorBtn.href = `/editor?map=${encodeURIComponent(data.export_slug)}`;
    editorBtn.textContent = "Open in Editor →";
    sketchDetailActions.appendChild(editorBtn);
  }
}

function _addSketchBadge(text, variant) {
  const span = document.createElement("span");
  span.className = `badge badge--${variant}`;
  span.textContent = text;
  sketchDetailBadges.appendChild(span);
}

// ── Settings ──────────────────────────────────────────────────────────────

saveSettingsBtn.addEventListener("click", async () => {
  const cfg = {
    maps_folder:   mapsFolderInput.value.trim(),
    output_folder: outputFolderInput.value.trim(),
  };
  try {
    await api.saveConfig(cfg);
    flashMsg("Saved");
    await loadSources();
  } catch (err) {
    flashMsg(`Error: ${err.message}`, true);
  }
});

function flashMsg(msg, isError = false) {
  settingsMsg.textContent = msg;
  settingsMsg.className   = "settings-msg" + (isError ? " settings-msg--error" : " settings-msg--ok");
  setTimeout(() => { settingsMsg.textContent = ""; settingsMsg.className = "settings-msg"; }, 3000);
}

async function loadConfig() {
  try {
    const cfg = await api.fetchConfig();
    mapsFolderInput.value   = cfg.maps_folder   || "";
    outputFolderInput.value = cfg.output_folder || "";
  } catch {
    showSystemError("Could not load configuration");
  }
}

// ── Filter panel ──────────────────────────────────────────────────────────

filterBtn.addEventListener("click", () => {
  state.filterOpen = !state.filterOpen;
  filterBtn.classList.toggle("action-btn--primary", state.filterOpen);
  filterPanel.hidden = !state.filterOpen;
  if (state.filterOpen) buildFilterPanel();
});

function buildFilterPanel() {
  filterPanel.innerHTML = "";

  const grouped = {
    teams:    new Set(),
    wools:    new Set(),
    symmetry: new Set(),
  };

  for (const m of state.sources) {
    if (m.info?.teams)    grouped.teams.add(m.info.teams);
    if (m.info?.wools)    grouped.wools.add(m.info.wools);
    if (m.info?.symmetry) grouped.symmetry.add(m.info.symmetry);
  }

  const labels = { teams: "Teams", wools: "Wools", symmetry: "Symmetry" };
  const format = {
    teams:    v => `${v} team${v !== 1 ? "s" : ""}`,
    wools:    v => `${v} wool${v !== 1 ? "s" : ""}`,
    symmetry: v => v.replace("_", " "),
  };

  let anyGroup = false;
  for (const [key, values] of Object.entries(grouped)) {
    if (!values.size) continue;
    anyGroup = true;

    const label = document.createElement("div");
    label.className = "section-title";
    label.textContent = labels[key];
    filterPanel.appendChild(label);

    const opts = document.createElement("div");
    opts.className = "filter-group-options";

    for (const v of [...values].sort((a, b) => String(a).localeCompare(String(b)))) {
      const chip = document.createElement("button");
      chip.className = "filter-chip" + (state.filters[key] === v ? " filter-chip--active" : "");
      chip.textContent = format[key](v);
      chip.addEventListener("click", () => {
        state.filters[key] = state.filters[key] === v ? null : v;
        renderList();
        buildFilterPanel(); // re-render to update active state
      });
      opts.appendChild(chip);
    }
    filterPanel.appendChild(opts);
  }

  if (!anyGroup) {
    const empty = document.createElement("div");
    empty.className = "filter-group-label";
    empty.textContent = "No filter options available";
    filterPanel.appendChild(empty);
  }

  // Clear button if any filter is active
  const anyActive = Object.values(state.filters).some(v => v !== null);
  if (anyActive) {
    const clearBtn = document.createElement("button");
    clearBtn.className = "action-btn action-btn--danger";
    clearBtn.style.alignSelf = "flex-start";
    clearBtn.textContent = "Clear filters";
    clearBtn.addEventListener("click", () => {
      state.filters = { teams: null, wools: null, symmetry: null };
      renderList();
      buildFilterPanel();
    });
    filterPanel.appendChild(clearBtn);
  }
}

// ── Source map list ────────────────────────────────────────────────────────

async function loadSources() {
  mapListEl.innerHTML = '<div class="list-empty">Loading…</div>';
  try {
    state.sources = await api.fetchSources();
    renderList();
    clearSystemError();
    if (_activeActivity === "maps" && !state.selected && state.sources.length) {
      selectMap(state.sources[0].slug);
    }
  } catch (err) {
    mapListEl.innerHTML = `<div class="list-empty" style="color:var(--color-error)">${err.message}</div>`;
  }
}

function _applyFilters(sources) {
  return sources.filter(m => {
    if (state.filters.teams    !== null && m.info?.teams    !== state.filters.teams)    return false;
    if (state.filters.wools    !== null && m.info?.wools    !== state.filters.wools)    return false;
    if (state.filters.symmetry !== null && m.info?.symmetry !== state.filters.symmetry) return false;
    return true;
  });
}

function renderList() {
  const query   = mapFilterEl.value.toLowerCase();
  let visible   = query
    ? state.sources.filter(m =>
        m.slug.toLowerCase().includes(query) ||
        m.display_name.toLowerCase().includes(query))
    : [...state.sources];

  visible = _applyFilters(visible);
  mapCountBadge.textContent = visible.length || "";

  if (!visible.length) {
    mapListEl.innerHTML = '<div class="list-empty">No maps found.</div>';
    return;
  }

  mapListEl.innerHTML = "";
  for (const m of visible) {
    const item = document.createElement("div");
    item.className = "list-row" + (m.slug === state.selected ? " list-row--selected" : "");
    item.dataset.slug = m.slug;

    const dotClass = m.editor_ready    ? "map-status-dot--ready"
                   : (m.has_xml || m.has_region) ? "map-status-dot--partial"
                   : "";
    const version = m.info?.version ? `v${m.info.version}` : "";

    item.innerHTML = `
      <span class="map-status-dot ${dotClass}"></span>
      <span class="map-list-name">${m.display_name}</span>
      <span class="map-list-version">${version}</span>
    `;
    item.addEventListener("click", () => selectMap(m.slug));
    mapListEl.appendChild(item);
  }
}

mapFilterEl.addEventListener("input", renderList);

// ── Map selection + detail ────────────────────────────────────────────────

async function selectMap(slug) {
  state.selected = slug;
  _selectedSketchId = null;
  renderList();
  sketchDetailContent.hidden = true;
  mapDetailEmpty.hidden      = true;
  mapDetailContent.hidden    = false;

  detailBadges.innerHTML    = "";
  detailName.textContent    = "";
  detailVersion.textContent = "";
  detailAuthors.innerHTML   = "";
  detailSteps.innerHTML     = '<div class="step-row"><span class="step-label" style="color:var(--text-muted)">Loading…</span></div>';
  openEditorBtn.hidden    = true;
  runPipelineBtn.hidden   = true;
  pipelineConsole.hidden  = true;

  // Thumbnail
  detailThumb.hidden   = true;
  detailThumbPH.hidden = false;
  const thumbUrl = `/api/sources/${encodeURIComponent(slug)}/thumbnail`;
  const img = new Image();
  img.onload = () => { detailThumb.src = thumbUrl; detailThumb.hidden = false; detailThumbPH.hidden = true; };
  img.src = thumbUrl;

  const m = state.sources.find(s => s.slug === slug);
  if (m?.display_name) detailName.textContent = m.display_name;

  try {
    const status = await api.fetchSourceStatus(slug);
    state.status = status;
    renderDetail(slug, status);
  } catch (err) {
    detailSteps.innerHTML = `<span style="color:var(--color-error);font-size:12px">${err.message}</span>`;
  }
}

function renderDetail(slug, status) {
  const { steps, editor_ready, info } = status;

  // ── Badge row ──────────────────────────────────────────────────────────
  detailBadges.innerHTML = "";
  if (info?.gamemode) _addBadge(info.gamemode, "neutral");
  if (info?.teams)    _addBadge(`${info.teams} team${info.teams !== 1 ? "s" : ""}`, "neutral");
  if (info?.wools)    _addBadge(`${info.wools} wool${info.wools !== 1 ? "s" : ""}`, "neutral");
  if (info?.symmetry) _addBadge(info.symmetry.replace("_", " "), "dim");

  // ── Name + version ─────────────────────────────────────────────────────
  detailName.textContent    = info?.name || slug;
  detailVersion.textContent = info?.version ? `v${info.version}` : "";

  // ── Authors — render placeholders then resolve names async ─────────────
  detailAuthors.innerHTML = "";
  for (const author of (info?.authors ?? [])) {
    const chip = _makeAuthorChip(author.uuid, null);
    detailAuthors.appendChild(chip);
    // Resolve name in background; update chip when done
    api.fetchMinecraftPlayer(author.uuid)
      .then(player => {
        const nameEl = chip.querySelector(".map-author-name");
        if (nameEl) nameEl.textContent = player.name;
        const avatarEl = chip.querySelector(".map-author-avatar");
        if (avatarEl) avatarEl.src = _avatarUrl(player.uuid);
      })
      .catch(() => { /* leave UUID placeholder */ });
  }

  // ── Pipeline steps ─────────────────────────────────────────────────────
  detailSteps.innerHTML = "";
  for (const step of steps) {
    const row = document.createElement("div");
    row.className = "step-row";
    const dot = step.done ? "step-dot--done" : "step-dot";
    row.innerHTML = `
      <span class="step-dot ${dot}"></span>
      <span class="step-label">${step.label}</span>
      <span class="step-detail">${step.done ? step.file : "not run"}</span>
    `;
    detailSteps.appendChild(row);
  }

  // ── Action buttons ─────────────────────────────────────────────────────
  openEditorBtn.hidden      = !editor_ready;
  openEditorBtn.href        = `/editor?map=${encodeURIComponent(slug)}`;
  openEditorBtn.textContent = "Open in Editor →";
  runPipelineBtn.hidden     = false;
  runPipelineBtn.textContent = editor_ready ? "Re-run Pipeline" : "Run Pipeline";
  runPipelineBtn.disabled   = state.isRunning;
  runPipelineBtn.onclick    = () => runPipeline(slug);
}

function _makeAuthorChip(uuid, name) {
  const chip = document.createElement("div");
  chip.className = "map-author-chip";
  const avatarSrc = uuid ? _avatarUrl(uuid) : _AVATAR_EMPTY;
  const displayName = name ?? uuid?.slice(0, 8) ?? "…";
  chip.innerHTML = `
    <img class="map-author-avatar" src="${avatarSrc}" alt="" loading="lazy"/>
    <span class="map-author-name">${displayName}</span>
  `;
  return chip;
}

function _addBadge(text, variant) {
  const span = document.createElement("span");
  span.className = `badge badge--${variant}`;
  span.textContent = text;
  detailBadges.appendChild(span);
}

// ── URL Import ────────────────────────────────────────────────────────────

urlImportBtn.addEventListener("click", async () => {
  const url = urlImportInput.value.trim();
  if (!url) return;
  _setImportStatus("Importing…", "loading");
  try {
    const result = await api.importFromUrl(url);
    _setImportStatus("Imported!", "ok");
    urlImportInput.value = "";
    await loadSources();
    selectMap(result.slug);
  } catch (err) {
    _setImportStatus(err.message, "error");
  }
});

function _setImportStatus(msg, type) {
  urlImportStatus.hidden = false;
  urlImportStatus.textContent = msg;
  urlImportStatus.className = `url-import-status url-import-status--${type}`;
  if (type !== "loading") {
    setTimeout(() => { urlImportStatus.hidden = true; }, 4000);
  }
}

// ── Pipeline ──────────────────────────────────────────────────────────────

consoleClearBtn.addEventListener("click", () => { consoleOutput.innerHTML = ""; });

function runPipeline(slug) {
  if (state.isRunning) return;
  state.isRunning = true;
  runPipelineBtn.disabled = true;
  pipelineConsole.hidden  = false;

  const dots = detailSteps.querySelectorAll(".step-dot");
  dots.forEach(d => { d.className = "step-dot step-dot--running"; });

  const es = api.streamPipeline(slug);

  es.addEventListener("step", e => {
    const { id, status } = JSON.parse(e.data);
    _appendConsoleLine(`[${id}] ${status}`, status === "error" ? "error" : "");
    const allRows = detailSteps.querySelectorAll(".step-row");
    const stepIds = ["layout", "symmetry", "xml"];
    const idx = stepIds.indexOf(id);
    if (idx >= 0 && allRows[idx]) {
      const dot = allRows[idx].querySelector(".step-dot");
      if (dot) dot.className = `step-dot step-dot--${status === "done" ? "done" : status === "error" ? "error" : "running"}`;
    }
  });

  es.addEventListener("done", async () => {
    es.close();
    state.isRunning = false;
    _appendConsoleLine("Pipeline complete.", "success");
    await loadSources();
    if (state.selected === slug) {
      const st = await api.fetchSourceStatus(slug).catch(() => null);
      if (st) { state.status = st; renderDetail(slug, st); }
    }
    runPipelineBtn.disabled = false;
    showToast("Pipeline complete", "success");
  });

  es.addEventListener("error", e => {
    es.close();
    state.isRunning = false;
    runPipelineBtn.disabled = false;
    const msg = e.data ? JSON.parse(e.data).message : "Pipeline failed";
    _appendConsoleLine(msg, "error");
    showToast("Pipeline failed", "error");
  });
}

function _appendConsoleLine(text, type = "") {
  const line = document.createElement("div");
  line.className = `console-line${type ? ` console-line--${type}` : ""}`;
  line.textContent = text;
  consoleOutput.appendChild(line);
  consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

// ── Boot ──────────────────────────────────────────────────────────────────

init();
