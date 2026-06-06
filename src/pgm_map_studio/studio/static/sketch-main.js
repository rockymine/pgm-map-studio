/**
 * sketch-main.js — Sketch page bootstrap.
 *
 * Reads ?id=<session-id> from the URL, loads the session, and activates
 * the Overview activity. Other activities (Setup, Layout, Export) are
 * disabled until their prerequisites are met.
 */

import { SketchOverviewActivity } from "./activities/sketch-overview-activity.js";
import { SketchSetupActivity }    from "./activities/sketch-setup-activity.js";
import * as api from "./api.js";
import { showSystemError, clearSystemError } from "./shared/ui-helpers.js";

lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "16", height: "16" } });

// ── DOM ───────────────────────────────────────────────────────────────────

const overviewBtn  = document.getElementById("sk-activity-overview");
const setupBtn     = document.getElementById("sk-activity-setup");
const errorDismiss = document.getElementById("error-dismiss-btn");

errorDismiss?.addEventListener("click", clearSystemError);

// ── Activities ────────────────────────────────────────────────────────────

const overviewActivity = new SketchOverviewActivity({
  onStatusChange: dot => { overviewBtn.dataset.status = dot ?? ""; },
});
const setupActivity = new SketchSetupActivity({
  onStatusChange: dot => { setupBtn.dataset.status = dot ?? ""; },
});

const ACTIVITIES = {
  "sk-activity-overview": overviewActivity,
  "sk-activity-setup":    setupActivity,
};

let _currentId  = "sk-activity-overview";
let _sketchId   = null;

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
setupBtn.addEventListener("click",    () => { if (!setupBtn.disabled) switchActivity("sk-activity-setup"); });

// ── Session loading ───────────────────────────────────────────────────────

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
    await api.fetchSketch(_sketchId);
    clearSystemError();
    setupBtn.disabled = false;
    overviewActivity.activate({ sketchId: _sketchId });
  } catch {
    showSystemError("Sketch session not found.");
  }
}

boot();
