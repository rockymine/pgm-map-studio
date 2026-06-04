/**
 * main.js — Editor page bootstrap.
 *
 * Wires the activity rail, handles map loading, and manages the export button.
 * Only Overview and Teams are active in M1 — other rail buttons exist but are disabled.
 */

import { OverviewActivity } from "./activities/overview-activity.js";
import { TeamsActivity }    from "./activities/teams-activity.js";
import * as api             from "./api.js";
import { showSystemError, clearSystemError, showToast, getMapParam } from "./shared/ui-helpers.js";

lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "16", height: "16" } });

// ── DOM ───────────────────────────────────────────────────────────────────

const overviewBtn  = document.getElementById("activity-overview");
const teamsBtn     = document.getElementById("activity-teams");
const objectiveBtn = document.getElementById("activity-objective");
const regionsBtn   = document.getElementById("activity-regions");
const exportBtn    = document.getElementById("export-xml-btn");
const errorDismiss = document.getElementById("error-dismiss-btn");

errorDismiss?.addEventListener("click", clearSystemError);

// ── Activity setup ────────────────────────────────────────────────────────

const ACTIVITIES = {
  "activity-overview": new OverviewActivity({
    onStatusChange: dot => { overviewBtn.dataset.status = dot ?? ""; },
  }),
  "activity-teams": new TeamsActivity({
    onStatusChange: dot => { teamsBtn.dataset.status = dot ?? ""; },
  }),
};

// Stub activities (stubs show placeholder message)
const STUB_IDS = ["activity-objective", "activity-regions"];

let currentId  = "activity-overview";
let currentMap = null;

function switchActivity(id) {
  if (ACTIVITIES[currentId]) ACTIVITIES[currentId].deactivate();

  // Show/hide stub workspaces
  for (const stubId of STUB_IDS) {
    const ws = document.getElementById(stubId.replace("activity-", "") + "-workspace");
    if (ws) ws.hidden = (id !== stubId);
  }

  currentId = id;
  document.querySelectorAll(".activity-btn").forEach(btn => btn.classList.toggle("active", btn.id === id));
  if (ACTIVITIES[id]) {
    ACTIVITIES[id].activate({ mapName: currentMap });
    requestAnimationFrame(() => ACTIVITIES[id].resize());
  }
}

overviewBtn.addEventListener("click",  () => { if (!overviewBtn.disabled)  switchActivity("activity-overview"); });
teamsBtn.addEventListener("click",     () => { if (!teamsBtn.disabled)     switchActivity("activity-teams"); });
objectiveBtn.addEventListener("click", () => { if (!objectiveBtn.disabled) switchActivity("activity-objective"); });
regionsBtn.addEventListener("click",   () => { if (!regionsBtn.disabled)   switchActivity("activity-regions"); });

// ── Export ────────────────────────────────────────────────────────────────

exportBtn.addEventListener("click", async () => {
  if (!currentMap) return;
  try {
    const r = await fetch(`/api/map/${encodeURIComponent(currentMap)}/regions`);
    if (!r.ok) throw new Error(`${r.status}`);
    showToast("Export not yet implemented in M1 — use the API endpoint directly", "error");
  } catch (err) {
    showSystemError(`Export failed: ${err.message}`);
  }
});

// ── Map loading ───────────────────────────────────────────────────────────

async function loadMap(name) {
  currentMap = name;
  overviewBtn.disabled  = true;
  teamsBtn.disabled     = true;
  objectiveBtn.disabled = true;
  regionsBtn.disabled   = true;
  exportBtn.disabled    = true;

  try {
    const data = await api.fetchMapData(name);
    const nameEl = document.getElementById("topbar-map-name");
    const verEl  = document.getElementById("topbar-version");
    if (nameEl) nameEl.textContent = data.name || name.replace(/_/g, " ");
    if (verEl)  verEl.textContent  = data.version ? `v${data.version}` : "";

    overviewBtn.disabled  = false;
    teamsBtn.disabled     = false;
    exportBtn.disabled    = false;
    clearSystemError();

    switchActivity("activity-overview");
  } catch (err) {
    showSystemError(err.status === 404 ? "Map not found" : "Could not load map");
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────

// Activate overview workspace so it's visible on load
ACTIVITIES["activity-overview"].activate({});

const mapParam = getMapParam();
if (mapParam) {
  loadMap(mapParam);
}

window.addEventListener("resize", () => {
  if (ACTIVITIES[currentId]) ACTIVITIES[currentId].resize();
});
