/**
 * main.js — Editor page bootstrap.
 *
 * Wires the activity rail and manages the active activity.
 * Configure is the first activity; the editor auto-opens it when the map
 * has not yet been configured (symmetry.status == "unconfirmed").
 */

import { ConfigureActivity }      from "./activities/configure-activity.js";
import { OverviewActivity }       from "./activities/overview-activity.js";
import { TeamsActivity }          from "./activities/teams-activity.js";
import { BuildRegionsActivity }   from "./activities/build-regions-activity.js";
import * as api                   from "./api.js";
import { showSystemError, clearSystemError, showToast, getMapParam } from "./shared/ui-helpers.js";

lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "16", height: "16" } });

// ── DOM ───────────────────────────────────────────────────────────────────

const configureBtn     = document.getElementById("activity-configure");
const overviewBtn      = document.getElementById("activity-overview");
const teamsBtn         = document.getElementById("activity-teams");
const buildRegionsBtn  = document.getElementById("activity-build-regions");
const objectiveBtn     = document.getElementById("activity-objective");
const regionsBtn       = document.getElementById("activity-regions");
const exportBtn    = document.getElementById("export-xml-btn");
const errorDismiss = document.getElementById("error-dismiss-btn");

errorDismiss?.addEventListener("click", clearSystemError);

// ── Activity setup ────────────────────────────────────────────────────────

const ACTIVITIES = {
  "activity-configure": new ConfigureActivity({
    onStatusChange: dot => { configureBtn.dataset.status = dot ?? ""; },
    onComplete:     ()  => switchActivity("activity-overview"),
  }),
  "activity-overview": new OverviewActivity({
    onStatusChange: dot => { overviewBtn.dataset.status = dot ?? ""; },
  }),
  "activity-teams": new TeamsActivity({
    onStatusChange: dot => { teamsBtn.dataset.status = dot ?? ""; },
  }),
  "activity-build-regions": new BuildRegionsActivity({
    onStatusChange: dot => { buildRegionsBtn.dataset.status = dot ?? ""; },
  }),
};

const STUB_IDS = ["activity-objective", "activity-regions"];

let currentId  = "activity-overview";
let currentMap = null;

function switchActivity(id) {
  if (ACTIVITIES[currentId]) ACTIVITIES[currentId].deactivate();

  for (const stubId of STUB_IDS) {
    const ws = document.getElementById(stubId.replace("activity-", "") + "-workspace");
    if (ws) ws.hidden = (id !== stubId);
  }

  currentId = id;
  document.querySelectorAll(".activity-btn").forEach(btn =>
    btn.classList.toggle("active", btn.id === id)
  );
  if (ACTIVITIES[id]) {
    ACTIVITIES[id].activate({ mapName: currentMap });
    requestAnimationFrame(() => ACTIVITIES[id].resize());
  }
}

configureBtn.addEventListener("click",    () => { if (!configureBtn.disabled)    switchActivity("activity-configure"); });
overviewBtn.addEventListener("click",     () => { if (!overviewBtn.disabled)     switchActivity("activity-overview"); });
teamsBtn.addEventListener("click",        () => { if (!teamsBtn.disabled)        switchActivity("activity-teams"); });
buildRegionsBtn.addEventListener("click", () => { if (!buildRegionsBtn.disabled) switchActivity("activity-build-regions"); });
objectiveBtn.addEventListener("click",    () => { if (!objectiveBtn.disabled)    switchActivity("activity-objective"); });
regionsBtn.addEventListener("click",      () => { if (!regionsBtn.disabled)      switchActivity("activity-regions"); });

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
  configureBtn.disabled    = true;
  overviewBtn.disabled     = true;
  teamsBtn.disabled        = true;
  buildRegionsBtn.disabled = true;
  objectiveBtn.disabled    = true;
  regionsBtn.disabled      = true;
  exportBtn.disabled       = true;

  try {
    const data = await api.fetchMapData(name);
    const nameEl = document.getElementById("topbar-map-name");
    const verEl  = document.getElementById("topbar-version");
    if (nameEl) nameEl.textContent = data.name || name.replace(/_/g, " ");
    if (verEl)  verEl.textContent  = data.version ? `v${data.version}` : "";

    configureBtn.disabled    = false;
    overviewBtn.disabled     = false;
    teamsBtn.disabled        = false;
    buildRegionsBtn.disabled = false;
    exportBtn.disabled       = false;
    clearSystemError();

    // Open Configure if map hasn't been configured yet
    const cfgState = await _fetchConfigureState(name);
    if (!cfgState?.configure_complete) {
      switchActivity("activity-configure");
    } else {
      switchActivity("activity-overview");
    }
  } catch (err) {
    showSystemError(err.status === 404 ? "Map not found" : "Could not load map");
  }
}

async function _fetchConfigureState(name) {
  try {
    const r = await fetch(`/api/configure/${encodeURIComponent(name)}/state`);
    return r.ok ? await r.json() : null;
  } catch (_) {
    return null;
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────

ACTIVITIES["activity-overview"].activate({});

const mapParam = getMapParam();
if (mapParam) {
  loadMap(mapParam);
}

window.addEventListener("resize", () => {
  if (ACTIVITIES[currentId]) ACTIVITIES[currentId].resize();
});
