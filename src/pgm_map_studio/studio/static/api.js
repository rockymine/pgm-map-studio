/** All server communication for PGM Map Studio. */

// ── Errors ──────────────────────────────────────────────────────────────────

/** Pull the human message out of the structured error envelope
 *  `{error:{code,message}}`, tolerating the legacy flat `{error:"..."}`.
 *  Returns undefined when absent, so callers keep their `|| fallback`. */
export function apiErrorMessage(body) {
  const e = body && body.error;
  if (e && typeof e === "object") return e.message;
  if (typeof e === "string") return e;
  return undefined;
}

// ── Config ────────────────────────────────────────────────────────────────

export async function fetchConfig() {
  const r = await fetch("/api/config");
  if (!r.ok) throw new Error("Failed to load config");
  return r.json();
}

export async function saveConfig(config) {
  const r = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!r.ok) throw new Error(`Failed to save config (${r.status})`);
  return r.json();
}

// ── Sources ───────────────────────────────────────────────────────────────

export async function fetchSources() {
  const r = await fetch("/api/sources");
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(apiErrorMessage(body) ||`Failed to load sources (${r.status})`);
  }
  return r.json();
}

export async function fetchSourceStatus(slug) {
  const r = await fetch(`/api/sources/${encodeURIComponent(slug)}/status`);
  if (!r.ok) throw new Error(`Status fetch failed (${r.status})`);
  return r.json();
}

export async function validateSource(slug) {
  const r = await fetch(`/api/sources/${encodeURIComponent(slug)}/validate`);
  if (!r.ok) throw new Error(`Validation failed (${r.status})`);
  return r.json();
}

export async function importFromUrl(url, name = "") {
  const r = await fetch("/api/import-from-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, name }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Import failed (${r.status})`);
  return body;
}

// ── Pipeline ──────────────────────────────────────────────────────────────

export function streamPipeline(slug, opts = {}) {
  const params = new URLSearchParams();
  if (opts.force)           params.set("force", "1");
  if (opts.force_layout)    params.set("force_layout", "1");
  if (opts.force_symmetry)  params.set("force_symmetry", "1");
  if (opts.force_xml)       params.set("force_xml", "1");
  return new EventSource(`/api/pipeline/${encodeURIComponent(slug)}/run?${params}`);
}

// ── Map data ──────────────────────────────────────────────────────────────

export async function fetchMapData(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}`);
  if (!r.ok) throw new Error(`Failed to load map data (${r.status})`);
  return r.json();
}

export async function saveMetadata(mapName, metadata) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/metadata`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(metadata),
  });
  if (!r.ok) throw new Error(`Failed to save metadata (${r.status})`);
  return r.json();
}

export const patchMapMetadata = saveMetadata;

export async function fetchSegments(mapName, axis = "z") {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/segments?axis=${axis}`);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(apiErrorMessage(body) ||`Failed to fetch segments (${r.status})`);
  }
  return r.json();
}

export async function fetchSymmetry(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/symmetry`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`Failed to load symmetry (${r.status})`);
  return r.json();
}

export async function fetchIslands(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/islands`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`Failed to load islands (${r.status})`);
  return r.json();
}

export async function fetchRegions(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/regions`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load regions (${r.status})`);
  return r.json();
}

export async function fetchRegionsTree(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/regions/tree`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load region tree (${r.status})`);
  return r.json();
}

// B4a authoring split: { primitives, composed, bounding_box } — see region-authoring.md
export async function fetchRegionsAuthoring(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/regions/authoring`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load authoring regions (${r.status})`);
  return r.json();
}

// traversability: spawn<->wool connectivity over navigability (surface u buildable)
export async function fetchTraversability(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/traversability`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load traversability (${r.status})`);
  return r.json();
}

// C14 buildability: per-column verdict grid { bbox, width, height, classes, colors, counts, rows, has_y0 }
export async function fetchBuildability(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/buildability`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load buildability (${r.status})`);
  return r.json();
}

export async function fetchTopSurface(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/layers/top-surface`);
  if (!r.ok) throw new Error(`Failed to load surface layer (${r.status})`);
  return r.json();
}

// ── Teams ────────────────────────────────────────────────────────────────

export async function addTeam(mapName, team) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/teams`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(team),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Add team failed (${r.status})`);
  return body;
}

export async function updateTeam(mapName, teamId, fields) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/teams/${encodeURIComponent(teamId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Update team failed (${r.status})`);
  return body;
}

export async function deleteTeam(mapName, teamId) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/teams/${encodeURIComponent(teamId)}`, {
    method: "DELETE",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Delete team failed (${r.status})`);
  return body;
}

// ── Regions ──────────────────────────────────────────────────────────────

export async function createRegion(mapName, payload) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/regions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Create region failed (${r.status})`);
  return body;
}

export async function patchRegion(mapName, regionId, payload) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/regions/${encodeURIComponent(regionId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Patch region failed (${r.status})`);
  return body;
}

export async function deleteRegion(mapName, regionId) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/regions/${encodeURIComponent(regionId)}`, {
    method: "DELETE",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Delete region failed (${r.status})`);
  return body;
}

export async function groupRegions(mapName, payload) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/regions/group`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) || `Group regions failed (${r.status})`);
  return body;
}

export async function ungroupRegion(mapName, regionId) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/regions/ungroup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region_id: regionId }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) || `Ungroup region failed (${r.status})`);
  return body;
}

export async function restoreRegion(mapName, snapshot) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/regions/restore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ snapshot }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) || `Restore region failed (${r.status})`);
  return body;
}

export async function changeRegionType(mapName, regionId, type) {
  const r = await fetch(
    `/api/map/${encodeURIComponent(mapName)}/regions/${encodeURIComponent(regionId)}/change-type`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type }) },
  );
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) || `Change region type failed (${r.status})`);
  return body;
}

export async function removeFromGroup(mapName, regionId, childId) {
  const r = await fetch(
    `/api/map/${encodeURIComponent(mapName)}/regions/${encodeURIComponent(regionId)}/remove-from-group`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ child_id: childId }) },
  );
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) || `Remove from group failed (${r.status})`);
  return body;
}

export async function setBaseChild(mapName, regionId, childId) {
  const r = await fetch(
    `/api/map/${encodeURIComponent(mapName)}/regions/${encodeURIComponent(regionId)}/set-base-child`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ child_id: childId }) },
  );
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) || `Set base child failed (${r.status})`);
  return body;
}

export async function createCounterpart(mapName, regionId, payload) {
  const r = await fetch(
    `/api/map/${encodeURIComponent(mapName)}/regions/${encodeURIComponent(regionId)}/counterpart`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
  );
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) || `Create counterpart failed (${r.status})`);
  return body;
}

// ── Spawns ───────────────────────────────────────────────────────────────

export async function addSpawn(mapName, spawn) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/spawns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spawn),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Add spawn failed (${r.status})`);
  return body;
}

export async function updateSpawn(mapName, regionId, fields) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/spawns/${encodeURIComponent(regionId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Update spawn failed (${r.status})`);
  return body;
}

export async function setObserverSpawn(mapName, payload) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/observer-spawn`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Set observer spawn failed (${r.status})`);
  return body;
}

export async function deleteObserverSpawn(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/observer-spawn`, {
    method: "DELETE",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Delete observer spawn failed (${r.status})`);
  return body;
}

export async function deleteSpawn(mapName, regionId) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/spawns/${encodeURIComponent(regionId)}`, {
    method: "DELETE",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Delete spawn failed (${r.status})`);
  return body;
}

// ── Sketch ───────────────────────────────────────────────────────────────

export async function fetchSketches() {
  const r = await fetch("/api/sketch");
  if (!r.ok) throw new Error(`Failed to load sketches (${r.status})`);
  return r.json();
}

export async function createSketch() {
  const r = await fetch("/api/sketch", { method: "POST" });
  if (!r.ok) throw new Error(`Failed to create sketch (${r.status})`);
  return r.json();
}

export async function fetchSketch(sketchId) {
  const r = await fetch(`/api/sketch/${encodeURIComponent(sketchId)}`);
  if (!r.ok) throw new Error(`Sketch not found (${r.status})`);
  return r.json();
}

export async function saveSketchSetup(sketchId, fields) {
  const r = await fetch(`/api/sketch/${encodeURIComponent(sketchId)}/setup`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!r.ok) throw new Error(`Failed to save setup (${r.status})`);
  return r.json();
}

export async function saveSketchLayout(sketchId, shapes, islands) {
  const r = await fetch(`/api/sketch/${encodeURIComponent(sketchId)}/layout`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ shapes, islands }),
  });
  if (!r.ok) throw new Error(`Failed to save layout (${r.status})`);
  return r.json();
}

export async function saveSketchOverview(sketchId, fields) {
  const r = await fetch(`/api/sketch/${encodeURIComponent(sketchId)}/overview`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!r.ok) throw new Error(`Failed to save overview (${r.status})`);
  return r.json();
}

export async function exportSketch(sketchId) {
  const r = await fetch(`/api/sketch/${encodeURIComponent(sketchId)}/export`, {
    method: "POST",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Export failed (${r.status})`);
  return body;
}

// ── Wools ─────────────────────────────────────────────────────────────────

export async function addWool(mapName, payload) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/wools`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Add wool failed (${r.status})`);
  return body;
}

export async function updateWool(mapName, woolId, fields) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/wools/${encodeURIComponent(woolId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Update wool failed (${r.status})`);
  return body;
}

export async function deleteWool(mapName, woolId) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/wools/${encodeURIComponent(woolId)}`, {
    method: "DELETE",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Delete wool failed (${r.status})`);
  return body;
}

export async function addMonument(mapName, woolId, payload) {
  const r = await fetch(
    `/api/map/${encodeURIComponent(mapName)}/wools/${encodeURIComponent(woolId)}/monuments`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
  );
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Add monument failed (${r.status})`);
  return body;
}

export async function updateMonument(mapName, woolId, monId, fields) {
  const r = await fetch(
    `/api/map/${encodeURIComponent(mapName)}/wools/${encodeURIComponent(woolId)}/monuments/${encodeURIComponent(monId)}`,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields) },
  );
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Update monument failed (${r.status})`);
  return body;
}

// C12 wool availability/detection — see editor-objectives.md Sub-step 3
export async function fetchWoolSourcesInRegion(mapName, bounds) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/wool-sources`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ bounds }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) || `Wool sources failed (${r.status})`);
  return body;
}

export async function fetchWoolAvailability(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/wool-availability`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load wool availability (${r.status})`);
  return r.json();
}

export async function fetchWoolSuggestions(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/wool-suggestions`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load wool suggestions (${r.status})`);
  return r.json();
}

export async function deleteMonument(mapName, woolId, monId) {
  const r = await fetch(
    `/api/map/${encodeURIComponent(mapName)}/wools/${encodeURIComponent(woolId)}/monuments/${encodeURIComponent(monId)}`,
    { method: "DELETE" },
  );
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(apiErrorMessage(body) ||`Delete monument failed (${r.status})`);
  return body;
}

// ── Minecraft ────────────────────────────────────────────────────────────

export async function fetchMinecraftPlayer(nameOrUuid) {
  const isUuid = nameOrUuid.includes("-") && nameOrUuid.length > 30;
  const param  = isUuid ? `uuid=${encodeURIComponent(nameOrUuid)}` : `name=${encodeURIComponent(nameOrUuid)}`;
  const r = await fetch(`/api/minecraft/player?${param}`);
  if (!r.ok) throw new Error(`Player not found: ${nameOrUuid}`);
  return r.json();
}
