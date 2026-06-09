/**
 * sketch-main.js — Sketch page bootstrap.
 *
 * Reads ?id=<session-id> from the URL, loads the session, and activates
 * the Overview activity. Other activities (Setup, Layout) are disabled
 * until their prerequisites are met.
 *
 * Export lives in the topbar (not the activity rail). After a successful
 * export the "Open in Editor" button appears. When any change is saved
 * after an export, the "Changes detected" badge appears.
 */

import { SketchOverviewActivity } from "./activities/sketch-overview-activity.js";
import { SketchSetupActivity }    from "./activities/sketch-setup-activity.js";
import { SketchLayoutActivity }   from "./activities/sketch-layout-activity.js";
import * as api from "./api.js";
import { showSystemError, clearSystemError, showToast } from "./shared/ui-helpers.js";
import { connectPanelResizers } from "./shared/panel-resize.js";

lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "16", height: "16" } });
connectPanelResizers();

// ── DOM ───────────────────────────────────────────────────────────────────────

const overviewBtn    = document.getElementById("sk-activity-overview");
const setupBtn       = document.getElementById("sk-activity-setup");
const layoutBtn      = document.getElementById("sk-activity-layout");
const exportBtn      = document.getElementById("sk-export-btn");
const openEditorBtn  = document.getElementById("sk-open-editor-btn");
const changesBadge   = document.getElementById("sk-changes-badge");
const errorDismiss   = document.getElementById("error-dismiss-btn");

errorDismiss?.addEventListener("click", clearSystemError);

// ── Export state ──────────────────────────────────────────────────────────────

let _canExport      = false;
let _exportedUrl    = null;   // set after first successful export
let _exportStale    = false;  // true when changes made after last export

function _markChanged() {
  if (_exportedUrl && !_exportStale) {
    _exportStale = true;
    changesBadge.hidden = false;
    lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "13", height: "13" }, nodes: changesBadge.querySelectorAll("i[data-lucide]") });
  }
}

// ── Activities ────────────────────────────────────────────────────────────────

const layoutActivity = new SketchLayoutActivity({
  onStatusChange: dot   => { layoutBtn.dataset.status = dot ?? ""; },
  onExportReady:  ready => {
    _canExport = ready;
    if (!exportBtn.dataset.exporting) exportBtn.disabled = !ready;
  },
  onChanged: _markChanged,
});

const overviewActivity = new SketchOverviewActivity({
  onStatusChange: dot => { overviewBtn.dataset.status = dot ?? ""; },
  onChanged: _markChanged,
});

const setupActivity = new SketchSetupActivity({
  onStatusChange: dot   => { setupBtn.dataset.status = dot ?? ""; },
  onSetupSaved:   setup => layoutActivity.updateSetup(setup),
  onChanged: _markChanged,
});

const ACTIVITIES = {
  "sk-activity-overview": overviewActivity,
  "sk-activity-setup":    setupActivity,
  "sk-activity-layout":   layoutActivity,
};

let _currentId = "sk-activity-overview";
let _sketchId  = null;

function switchActivity(id) {
  ACTIVITIES[_currentId]?.deactivate();
  _currentId = id;
  document.querySelectorAll(".activity-btn").forEach(
    btn => btn.classList.toggle("active", btn.id === id),
  );
  ACTIVITIES[id]?.activate({ sketchId: _sketchId });
  requestAnimationFrame(() => ACTIVITIES[id]?.resize?.());
}

overviewBtn.addEventListener("click", () => switchActivity("sk-activity-overview"));
setupBtn.addEventListener("click",    () => { if (!setupBtn.disabled)  switchActivity("sk-activity-setup"); });
layoutBtn.addEventListener("click",   () => { if (!layoutBtn.disabled) switchActivity("sk-activity-layout"); });

// ── Export button ─────────────────────────────────────────────────────────────

exportBtn.addEventListener("click", async () => {
  if (exportBtn.disabled || exportBtn.dataset.exporting) return;
  exportBtn.disabled = true;
  exportBtn.dataset.exporting = "1";
  try {
    const { editor_url } = await api.exportSketch(_sketchId);
    _exportedUrl  = editor_url;
    _exportStale  = false;
    changesBadge.hidden     = true;
    openEditorBtn.href      = editor_url;
    openEditorBtn.hidden    = false;
    showToast("Export complete", "success");
  } catch (err) {
    showSystemError(`Export failed: ${err.message}`);
  } finally {
    delete exportBtn.dataset.exporting;
    exportBtn.disabled = !_canExport;
  }
});

// ── Session loading ───────────────────────────────────────────────────────────

function _getSketchId() {
  return new URLSearchParams(window.location.search).get("id") ?? "";
}

async function boot() {
  _sketchId = _getSketchId();

  if (!_sketchId) {
    showSystemError("No sketch session — returning to dashboard.");
    setTimeout(() => { window.location.href = "/"; }, 2000);
    return;
  }

  try {
    const data = await api.fetchSketch(_sketchId);
    clearSystemError();
    setupBtn.disabled  = false;
    layoutBtn.disabled = false;

    // Restore "Open in Editor" if this sketch was previously exported
    if (data.export_slug) {
      _exportedUrl          = `/editor?map=${encodeURIComponent(data.export_slug)}`;
      openEditorBtn.href    = _exportedUrl;
      openEditorBtn.hidden  = false;
    }

    // Pre-enable export if the saved layout already has ≥ 1 islands.
    // The layout activity will re-evaluate this properly when activated.
    const savedIslands = data.layout?.islands ?? [];
    if (savedIslands.length >= 1) {
      _canExport = true;
      exportBtn.disabled = false;
    }

    // Pre-load layout activity's setup values so the mirror preview is correct
    // when the user first opens Layout. Fall back to Square defaults when no
    // setup has been saved yet (matches sketch-setup-panel defaults).
    layoutActivity.updateSetup(data.setup ?? {
      bbox:        { min_x: -256, max_x: 256, min_z: -256, max_z: 256 },
      center:      { cx: 0, cz: 0 },
      mirror_mode: "rot_180",
    });

    overviewActivity.activate({ sketchId: _sketchId });
  } catch {
    showSystemError("Sketch session not found.");
  }
}

boot();
