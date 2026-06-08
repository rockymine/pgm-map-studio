/** All server communication for PGM Map Studio. */

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
    throw new Error(body.error || `Failed to load sources (${r.status})`);
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
  if (!r.ok) throw new Error(body.error || `Import failed (${r.status})`);
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
    throw new Error(body.error || `Failed to fetch segments (${r.status})`);
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
  if (!r.ok) throw new Error(body.error || `Add team failed (${r.status})`);
  return body;
}

export async function updateTeam(mapName, teamId, fields) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/teams/${encodeURIComponent(teamId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Update team failed (${r.status})`);
  return body;
}

export async function deleteTeam(mapName, teamId) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/teams/${encodeURIComponent(teamId)}`, {
    method: "DELETE",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Delete team failed (${r.status})`);
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
  if (!r.ok) throw new Error(body.error || `Create region failed (${r.status})`);
  return body;
}

export async function patchRegion(mapName, regionId, payload) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/region/${encodeURIComponent(regionId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Patch region failed (${r.status})`);
  return body;
}

export async function deleteRegion(mapName, regionId) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/region/${encodeURIComponent(regionId)}`, {
    method: "DELETE",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Delete region failed (${r.status})`);
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
  if (!r.ok) throw new Error(body.error || `Add spawn failed (${r.status})`);
  return body;
}

export async function updateSpawn(mapName, regionId, fields) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/spawn/${encodeURIComponent(regionId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Update spawn failed (${r.status})`);
  return body;
}

export async function setObserverSpawn(mapName, payload) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/observer-spawn`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Set observer spawn failed (${r.status})`);
  return body;
}

export async function deleteObserverSpawn(mapName) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/observer-spawn`, {
    method: "DELETE",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Delete observer spawn failed (${r.status})`);
  return body;
}

export async function deleteSpawn(mapName, regionId) {
  const r = await fetch(`/api/map/${encodeURIComponent(mapName)}/spawn/${encodeURIComponent(regionId)}`, {
    method: "DELETE",
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `Delete spawn failed (${r.status})`);
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
  if (!r.ok) throw new Error(body.error || `Export failed (${r.status})`);
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
