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

// ── State ──────────────────────────────────────────────────────────────────

const state = {
  sources:     [],        // [{slug, display_name, has_xml, editor_ready, info}]
  selected:    null,      // slug string
  status:      null,      // {steps, all_done, editor_ready, info}
  isRunning:   false,
};

// ── DOM ────────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);

const mapListEl        = $("map-list");
const mapFilterEl      = $("map-filter");
const urlImportInput   = $("url-import-input");
const urlImportBtn     = $("url-import-btn");
const urlImportStatus  = $("url-import-status");
const mapDetailEmpty   = $("map-detail-empty");
const mapDetailContent = $("map-detail-content");
const detailName       = $("detail-name");
const detailMeta       = $("detail-meta");
const detailValidation = $("detail-validation");
const detailValidBlock = $("detail-validation-block");
const detailSteps      = $("detail-steps");
const detailThumb      = $("detail-thumb");
const detailThumbPH    = $("detail-thumb-placeholder");
const openEditorBtn    = $("open-editor-btn");
const runPipelineBtn   = $("run-pipeline-btn");
const pipelineConsole  = $("pipeline-console");
const consoleOutput    = $("console-output");
const consoleClearBtn  = $("console-clear-btn");
const settingsBtn      = $("settings-btn");
const settingsPanel    = $("settings-panel");
const mapsFolderInput  = $("maps-folder-input");
const outputFolderInput= $("output-folder-input");
const saveSettingsBtn  = $("save-settings-btn");
const settingsMsg      = $("settings-msg");
const errorDismissBtn  = $("error-dismiss-btn");

// ── Init ──────────────────────────────────────────────────────────────────

errorDismissBtn.addEventListener("click", clearSystemError);

async function init() {
  await loadConfig();
  await loadSources();
}

// ── Settings ──────────────────────────────────────────────────────────────

settingsBtn.addEventListener("click", () => {
  const hidden = settingsPanel.hidden;
  settingsPanel.hidden = !hidden;
  if (!hidden) return;
  // close on outside click
  setTimeout(() => {
    document.addEventListener("click", closeSettings, { once: true, capture: true });
  }, 0);
});

function closeSettings(e) {
  if (!settingsPanel.contains(e.target) && e.target !== settingsBtn) {
    settingsPanel.hidden = true;
  } else {
    document.addEventListener("click", closeSettings, { once: true, capture: true });
  }
}

saveSettingsBtn.addEventListener("click", async () => {
  const cfg = {
    maps_folder:   mapsFolderInput.value.trim(),
    output_folder: outputFolderInput.value.trim(),
  };
  try {
    await api.saveConfig(cfg);
    flashSettingsMsg("Saved");
    settingsPanel.hidden = true;
    await loadSources();
  } catch (err) {
    flashSettingsMsg(`Error: ${err.message}`, true);
  }
});

function flashSettingsMsg(msg, isError = false) {
  settingsMsg.textContent = msg;
  settingsMsg.className   = "settings-msg" + (isError ? " settings-msg--error" : " settings-msg--ok");
  setTimeout(() => { settingsMsg.textContent = ""; settingsMsg.className = "settings-msg"; }, 3000);
}

async function loadConfig() {
  try {
    const cfg = await api.fetchConfig();
    mapsFolderInput.value   = cfg.maps_folder   || "";
    outputFolderInput.value = cfg.output_folder || "";
  } catch (err) {
    showSystemError("Could not load configuration");
  }
}

// ── Source map list ────────────────────────────────────────────────────────

async function loadSources() {
  mapListEl.innerHTML = '<div class="map-list-empty">Loading…</div>';
  try {
    state.sources = await api.fetchSources();
    renderList();
    clearSystemError();
  } catch (err) {
    mapListEl.innerHTML = `<div class="map-list-empty map-list-error">${err.message}</div>`;
  }
}

function renderList() {
  const filter  = mapFilterEl.value.toLowerCase();
  const visible = filter
    ? state.sources.filter(m =>
        m.slug.toLowerCase().includes(filter) ||
        m.display_name.toLowerCase().includes(filter))
    : state.sources;

  if (!visible.length) {
    mapListEl.innerHTML = '<div class="map-list-empty">No maps found.</div>';
    return;
  }

  mapListEl.innerHTML = "";
  for (const m of visible) {
    const item = document.createElement("div");
    item.className = "map-list-item" + (m.slug === state.selected ? " map-list-item--selected" : "");
    item.dataset.slug = m.slug;

    const dotClass = m.editor_ready ? "map-status-dot--ready"
                   : (m.has_xml || m.has_region) ? "map-status-dot--partial"
                   : "";
    const version = m.info?.version ? ` v${m.info.version}` : "";

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
  renderList();
  mapDetailEmpty.hidden   = true;
  mapDetailContent.hidden = false;

  const m = state.sources.find(s => s.slug === slug);
  detailName.textContent = m?.display_name ?? slug;
  detailMeta.innerHTML = "";
  detailSteps.innerHTML = '<div class="step-row"><span class="step-label" style="color:var(--text-muted)">Loading…</span></div>';
  openEditorBtn.hidden = true;
  runPipelineBtn.hidden = true;
  pipelineConsole.hidden = true;

  // Thumbnail
  detailThumb.hidden = true;
  detailThumbPH.hidden = false;
  const thumbUrl = `/api/sources/${encodeURIComponent(slug)}/thumbnail`;
  const img = new Image();
  img.onload = () => { detailThumb.src = thumbUrl; detailThumb.hidden = false; detailThumbPH.hidden = true; };
  img.src = thumbUrl;

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

  // Meta tags
  detailMeta.innerHTML = "";
  if (info?.version)  _addTag(detailMeta, `v${info.version}`, "highlight");
  if (info?.gamemode) _addTag(detailMeta, info.gamemode);
  if (info?.teams)    _addTag(detailMeta, `${info.teams} team${info.teams !== 1 ? "s" : ""}`);
  if (info?.wools)    _addTag(detailMeta, `${info.wools} wool${info.wools !== 1 ? "s" : ""}`);
  if (info?.authors?.length) _addTag(detailMeta, info.authors.slice(0, 2).join(", "));

  // Pipeline steps
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

  // CTA buttons
  openEditorBtn.hidden = !editor_ready;
  openEditorBtn.href   = `/editor?map=${encodeURIComponent(slug)}`;
  openEditorBtn.textContent = "Open in Editor →";

  runPipelineBtn.hidden = false;
  runPipelineBtn.textContent = editor_ready ? "Re-run Pipeline" : "Run Pipeline";
  runPipelineBtn.disabled = state.isRunning;
  runPipelineBtn.onclick = () => runPipeline(slug);
}

function _addTag(parent, text, variant = "") {
  const span = document.createElement("span");
  span.className = `map-meta-tag${variant ? ` map-meta-tag--${variant}` : ""}`;
  span.textContent = text;
  parent.appendChild(span);
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
  pipelineConsole.hidden = false;

  // Reset step dots
  const dots = detailSteps.querySelectorAll(".step-dot");
  dots.forEach(d => { d.className = "step-dot step-dot--running"; });

  const es = api.streamPipeline(slug);

  es.addEventListener("step", e => {
    const { id, status } = JSON.parse(e.data);
    _appendConsoleLine(`[${id}] ${status}`, status === "error" ? "error" : "");
    const allRows = detailSteps.querySelectorAll(".step-row");
    const steps = ["layout", "symmetry", "xml"];
    const idx = steps.indexOf(id);
    if (idx >= 0 && allRows[idx]) {
      const dot = allRows[idx].querySelector(".step-dot");
      if (dot) {
        dot.className = `step-dot step-dot--${status === "done" ? "done" : status === "error" ? "error" : "running"}`;
      }
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
