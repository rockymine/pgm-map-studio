/**
 * sketch-main.js — Sketch page bootstrap.
 *
 * Reads ?id=<session-id> from the URL, loads the session, and activates
 * the Overview activity. Other activities (Setup, Layout, Export) are
 * disabled until their prerequisites are met.
 */

import { SketchOverviewActivity } from "./activities/sketch-overview-activity.js";
import * as api from "./api.js";
import { showSystemError, clearSystemError } from "./shared/ui-helpers.js";

lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "16", height: "16" } });

// ── DOM ───────────────────────────────────────────────────────────────────

const overviewBtn  = document.getElementById("sk-activity-overview");
const errorDismiss = document.getElementById("error-dismiss-btn");

errorDismiss?.addEventListener("click", clearSystemError);

// ── Activity setup ────────────────────────────────────────────────────────

const overviewActivity = new SketchOverviewActivity({
  onStatusChange: dot => { overviewBtn.dataset.status = dot ?? ""; },
});

overviewBtn.addEventListener("click", () => {
  overviewActivity.activate({ sketchId: _sketchId });
});

// ── Session loading ───────────────────────────────────────────────────────

let _sketchId = null;

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
    overviewActivity.activate({ sketchId: _sketchId });
  } catch {
    showSystemError("Sketch session not found.");
  }
}

boot();
