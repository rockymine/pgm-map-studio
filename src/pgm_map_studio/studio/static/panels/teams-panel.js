/**
 * TeamsPanel — left and right panels for the Teams activity.
 *
 * Left panel (top):  team list with color swatches + "+ Add team" button.
 * Left panel (bottom): spawn region list with linked team name.
 * Right panel: team inspector OR spawn assignment, depending on selection.
 */

import * as api from "../api.js";
import {
  PGM_CHAT_COLORS, MINECRAFT_DYE_COLORS,
  chatColorHex, dyeColorHex,
} from "../shared/game-colors.js";
import { showToast } from "../shared/ui-helpers.js";

export class TeamsPanel {
  constructor(opts = {}) {
    this._mapName         = null;
    this._teams           = [];
    this._spawns          = [];
    this._spawnRegions    = [];
    this._selectedTeamId  = null;
    this._selectedSpawnId = null;
    this._opts = opts;

    // Left panel DOM
    this._teamsListEl = document.getElementById("pt-teams-list");
    this._spawnListEl = document.getElementById("pt-spawn-list");
    this._addTeamBtn  = document.getElementById("pt-add-team-btn");

    // Right panel DOM
    this._teamInspEl     = document.getElementById("pt-team-inspector");
    this._spawnInspEl    = document.getElementById("pt-spawn-inspector");
    this._spawnAssignEl  = document.getElementById("pt-spawn-assignment");
    this._emptyEl        = document.getElementById("pt-inspector-empty");

    // Team inspector inputs
    this._teamIdInput        = document.getElementById("pt-team-id");
    this._teamNameInput      = document.getElementById("pt-team-name");
    this._teamColorSel       = document.getElementById("pt-team-color");
    this._teamColorSwatch    = document.getElementById("pt-team-color-swatch");
    this._teamDyeColorSel    = document.getElementById("pt-team-dye-color");
    this._teamDyeColorSwatch = document.getElementById("pt-team-dye-color-swatch");
    this._teamMaxInput       = document.getElementById("pt-team-max");
    this._teamMinInput       = document.getElementById("pt-team-min");

    // Spawn assignment inputs
    this._spawnTeamSel   = document.getElementById("pt-spawn-team");
    this._spawnYawInput  = document.getElementById("pt-spawn-yaw");
    this._spawnKitInput  = document.getElementById("pt-spawn-kit");
    this._spawnUnlinkBtn = document.getElementById("pt-spawn-unlink-btn");

    this._teamAbort  = null;
    this._spawnAbort = null;

    this._buildColorDropdowns();
    this._attachStaticListeners();
  }

  getSelectedRegionId() { return this._selectedSpawnId; }
  getSpawnLink(regionId) {
    return this._spawns.find(s => (typeof s.region === "string" ? s.region : s.region?.id) === regionId) ?? null;
  }

  async load(mapName) {
    this._mapName = mapName;
    this._teams   = [];
    this._spawns  = [];
    try {
      const data = await api.fetchMapData(mapName);
      this._teams  = data.teams  ?? [];
      this._spawns = data.spawns ?? [];
      this._updateStatusDot();
    } catch (err) {
      console.error("TeamsPanel: failed to load map data:", err);
    }
    this._renderTeamList();
    this._showEmpty();
  }

  async reloadSpawnList(mapName) {
    try {
      const data = await api.fetchMapData(mapName);
      this._spawns = data.spawns ?? [];
    } catch { /* silent */ }
    this._renderSpawnList();
    this._updateStatusDot();
  }

  // ── region inspector (called by activity) ────────────────────────────────

  onRegionSelect(node) {
    this._selectedSpawnId = node.id;
    this._selectedTeamId  = null;
    this._showSpawnInspector(node);
  }

  onRegionDeselect() {
    this._selectedSpawnId = null;
    this._showEmpty();
  }

  async onCanvasDraw(mapName, drawResult, createRegionFn) {
    const { type, min_x, min_z, max_x, max_z, base_x, base_z, radius } = drawResult;
    let coords;
    if (type === "cylinder") {
      coords = { base: { x: base_x ?? (min_x + max_x) / 2, y: 0, z: base_z ?? (min_z + max_z) / 2 }, radius: radius ?? 1, height: 10 };
    } else if (type === "point") {
      coords = { position: { x: min_x + 0.5, y: 0, z: min_z + 0.5 } };
    } else {
      return null;
    }
    try {
      const result = await createRegionFn({ type, ...coords });
      if (result?.id) {
        await this.reloadSpawnList(mapName);
        return result.id;
      }
    } catch (err) {
      showToast(`Failed to create region: ${err.message}`, "error");
    }
    return null;
  }

  // ── team list ─────────────────────────────────────────────────────────────

  _renderTeamList() {
    this._teamsListEl.innerHTML = "";
    if (!this._teams.length) {
      this._teamsListEl.innerHTML = '<div class="list-empty">No teams defined.</div>';
      this._renderSpawnList();
      return;
    }
    for (const team of this._teams) {
      const row = document.createElement("div");
      row.className = "list-row" + (team.id === this._selectedTeamId ? " list-row--selected" : "");
      row.dataset.id = team.id;
      const swatch = document.createElement("span");
      swatch.className = "list-swatch";
      swatch.style.backgroundColor = chatColorHex(team.color);
      const label = document.createElement("span");
      label.className = "list-label";
      label.textContent = team.name || team.id;
      row.appendChild(swatch);
      row.appendChild(label);
      row.addEventListener("click", () => {
        this._selectTeam(team.id);
      });
      this._teamsListEl.appendChild(row);
    }
    this._renderSpawnList();
  }

  _renderSpawnList() {
    this._spawnListEl.innerHTML = "";
    if (!this._spawnRegions.length) {
      this._spawnListEl.innerHTML = '<div class="list-empty">No spawn regions.</div>';
      return;
    }
    for (const region of this._spawnRegions) {
      const spawn = this._spawns.find(s => (typeof s.region === "string" ? s.region : s.region?.id) === region.id);
      const team  = spawn ? this._teams.find(t => t.id === spawn.team) : null;
      const row   = document.createElement("div");
      row.className = "list-row list-row--compact" + (region.id === this._selectedSpawnId ? " list-row--selected" : "");
      row.dataset.regionId = region.id;

      const dot = document.createElement("span");
      dot.className = "team-dot";
      dot.style.backgroundColor = team ? chatColorHex(team.color) : "var(--border)";

      const label = document.createElement("span");
      label.className = "list-label list-label--mono";
      label.textContent = region.id;

      const tag = document.createElement("span");
      tag.className = "list-tag";
      tag.textContent = team?.name ?? "—";

      row.appendChild(dot);
      row.appendChild(label);
      row.appendChild(tag);
      row.addEventListener("click", () => {
        this._opts.onSpawnRowClick?.(region.id);
      });
      this._spawnListEl.appendChild(row);
    }
  }

  setSpawnRegions(nodes) {
    this._spawnRegions = nodes;
    this._renderSpawnList();
  }

  // ── team inspector ────────────────────────────────────────────────────────

  _selectTeam(teamId) {
    this._selectedTeamId  = teamId;
    this._selectedSpawnId = null;
    this._opts.onDeselectRegion?.();

    const team = this._teams.find(t => t.id === teamId);
    if (!team) return;

    // Highlight in list
    for (const row of this._teamsListEl.querySelectorAll(".list-row")) {
      row.classList.toggle("list-row--selected", row.dataset.id === teamId);
    }
    for (const row of this._spawnListEl.querySelectorAll(".list-row")) {
      row.classList.remove("list-row--selected");
    }

    this._teamInspEl.hidden = false;
    this._spawnInspEl.hidden = true;
    this._emptyEl.hidden = true;

    this._teamAbort?.abort();
    this._teamAbort = new AbortController();
    const sig = { signal: this._teamAbort.signal };

    this._teamIdInput.value   = team.id;
    this._teamNameInput.value = team.name || "";
    this._teamColorSel.value  = (team.color ?? "red").replace(/_/g, " ");
    this._teamColorSwatch.style.backgroundColor = chatColorHex(team.color);
    this._teamDyeColorSel.value = (team.dye_color ?? "").replace(/_/g, " ");
    this._teamDyeColorSwatch.style.backgroundColor = dyeColorHex(team.dye_color);
    this._teamMaxInput.value = team.max_players ?? 20;
    this._teamMinInput.value = team.min_players ?? 0;

    const _save = async () => {
      if (!this._mapName) return;
      try {
        const payload = {
          name:        this._teamNameInput.value.trim() || team.id,
          color:       this._teamColorSel.value,
          dye_color:   this._teamDyeColorSel.value || undefined,
          max_players: parseInt(this._teamMaxInput.value) || 20,
          min_players: parseInt(this._teamMinInput.value) || 0,
        };
        const newId = this._teamIdInput.value.trim();
        if (newId && newId !== teamId) payload.id = newId;
        await api.updateTeam(this._mapName, teamId, payload);
        const data = await api.fetchMapData(this._mapName);
        this._teams  = data.teams  ?? [];
        this._spawns = data.spawns ?? [];
        this._renderTeamList();
        this._updateStatusDot();
        showToast("Team saved", "success");
        if (newId && newId !== teamId) this._selectTeam(newId);
      } catch (err) {
        showToast(`Save failed: ${err.message}`, "error");
      }
    };

    this._teamColorSel.addEventListener("change", () => {
      this._teamColorSwatch.style.backgroundColor = chatColorHex(this._teamColorSel.value);
      _save();
    }, sig);
    this._teamDyeColorSel.addEventListener("change", () => {
      this._teamDyeColorSwatch.style.backgroundColor = dyeColorHex(this._teamDyeColorSel.value);
      _save();
    }, sig);
    for (const el of [this._teamIdInput, this._teamNameInput, this._teamMaxInput, this._teamMinInput]) {
      el.addEventListener("change", _save, sig);
    }

    const delBtn = document.getElementById("pt-delete-team-btn");
    if (delBtn) {
      delBtn.addEventListener("click", async () => {
        if (!this._mapName) return;
        try {
          await api.deleteTeam(this._mapName, teamId);
          const data = await api.fetchMapData(this._mapName);
          this._teams  = data.teams  ?? [];
          this._spawns = data.spawns ?? [];
          this._renderTeamList();
          this._updateStatusDot();
          this._showEmpty();
          showToast("Team deleted", "success");
        } catch (err) {
          showToast(`Delete failed: ${err.message}`, "error");
        }
      }, sig);
    }
  }

  // ── spawn inspector ───────────────────────────────────────────────────────

  _showSpawnInspector(node) {
    this._teamInspEl.hidden  = true;
    this._spawnInspEl.hidden = false;
    this._emptyEl.hidden     = true;

    // Highlight in spawn list
    for (const row of this._spawnListEl.querySelectorAll(".list-row")) {
      row.classList.toggle("list-row--selected", row.dataset.regionId === node.id);
    }
    for (const row of this._teamsListEl.querySelectorAll(".list-row")) {
      row.classList.remove("list-row--selected");
    }

    const spawn = this._spawns.find(s => (typeof s.region === "string" ? s.region : s.region?.id) === node.id);

    this._spawnAbort?.abort();
    this._spawnAbort = new AbortController();
    const sig = { signal: this._spawnAbort.signal };

    // Populate team dropdown
    this._spawnTeamSel.innerHTML = '<option value="">—</option>' +
      this._teams.map(t => `<option value="${t.id}" ${spawn?.team === t.id ? "selected" : ""}>${t.name || t.id}</option>`).join("");
    this._spawnYawInput.value = spawn?.yaw ?? 0;
    this._spawnKitInput.value = spawn?.kit ?? "";

    const _saveSpawn = async () => {
      if (!this._mapName) return;
      const payload = {
        team: this._spawnTeamSel.value,
        yaw:  parseFloat(this._spawnYawInput.value) || 0,
        kit:  this._spawnKitInput.value.trim(),
      };
      try {
        if (spawn) {
          await api.updateSpawn(this._mapName, node.id, payload);
        } else {
          await api.addSpawn(this._mapName, { region_id: node.id, ...payload });
        }
        await this.reloadSpawnList(this._mapName);
        showToast("Spawn link saved", "success");
      } catch (err) {
        showToast(`Save failed: ${err.message}`, "error");
      }
    };

    for (const el of [this._spawnTeamSel, this._spawnYawInput, this._spawnKitInput]) {
      el.addEventListener("change", _saveSpawn, sig);
    }

    this._spawnUnlinkBtn.addEventListener("click", async () => {
      if (!this._mapName || !spawn) return;
      try {
        await api.deleteSpawn(this._mapName, node.id);
        await this.reloadSpawnList(this._mapName);
        showToast("Spawn link removed", "success");
        this._opts.onDeselectRegion?.();
        this._showEmpty();
      } catch (err) {
        showToast(`Remove failed: ${err.message}`, "error");
      }
    }, sig);
  }

  // ── helpers ───────────────────────────────────────────────────────────────

  _showEmpty() {
    this._teamInspEl.hidden  = true;
    this._spawnInspEl.hidden = true;
    this._emptyEl.hidden     = false;
    this._selectedTeamId  = null;
    this._selectedSpawnId = null;
    for (const row of this._teamsListEl.querySelectorAll(".list-row")) row.classList.remove("list-row--selected");
    for (const row of this._spawnListEl.querySelectorAll(".list-row")) row.classList.remove("list-row--selected");
  }

  _buildColorDropdowns() {
    if (!this._teamColorSel) return;
    this._teamColorSel.innerHTML = PGM_CHAT_COLORS
      .map(c => `<option value="${c.value}">${c.label}</option>`).join("");
    this._teamDyeColorSel.innerHTML = '<option value="">None</option>' +
      MINECRAFT_DYE_COLORS.map(c => `<option value="${c.value}">${c.label}</option>`).join("");
  }

  _attachStaticListeners() {
    if (!this._addTeamBtn) return;
    this._addTeamBtn.addEventListener("click", async () => {
      if (!this._mapName) return;
      const usedIds = new Set(this._teams.map(t => t.id));
      let slug = "new-team";
      let n = 2;
      while (usedIds.has(slug)) { slug = `new-team-${n++}`; }
      try {
        await api.addTeam(this._mapName, { id: slug, name: "New Team", color: "blue", max_players: 20, min_players: 0 });
        const data = await api.fetchMapData(this._mapName);
        this._teams  = data.teams  ?? [];
        this._spawns = data.spawns ?? [];
        this._renderTeamList();
        this._updateStatusDot();
        this._selectTeam(slug);
        showToast("Team added", "success");
      } catch (err) {
        showToast(`Add team failed: ${err.message}`, "error");
      }
    });
  }

  _updateStatusDot() {
    if (!this._opts.onStatusChange) return;
    if (!this._teams.length) {
      this._opts.onStatusChange("yellow");
      return;
    }
    const allLinked = this._spawnRegions.every(r =>
      this._spawns.some(s => (typeof s.region === "string" ? s.region : s.region?.id) === r.id && s.team)
    );
    this._opts.onStatusChange(allLinked ? "green" : "yellow");
  }
}
