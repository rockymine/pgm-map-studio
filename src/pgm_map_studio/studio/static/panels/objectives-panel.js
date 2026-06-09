/**
 * ObjectivesPanel — left and right panels for the Objectives activity.
 *
 * Left panel (top):  wool list — one row per unique color + "Add Wool" button.
 * Left panel (bottom): wool room regions tree.
 * Right panel: wool inspector (color, location, per-team monuments) OR region inspector.
 */

import * as api from "../api.js";
import { MINECRAFT_DYE_COLORS, dyeColorHex, dyeColorLabel, chatColorHex } from "../shared/game-colors.js";
import { showToast } from "../shared/ui-helpers.js";
import { RegionsPanel }    from "./regions-panel.js";
import { RegionInspector } from "./region-inspector.js";

const WOOL_COLORS = MINECRAFT_DYE_COLORS;
const _nc = s => (s ?? "").replace(/_/g, " ").toLowerCase();

export class ObjectivesPanel {
  constructor(opts = {}) {
    this._mapName            = null;
    this._teams              = [];
    this._wools              = [];
    this._woolRegions        = [];
    this._selectedWoolId     = null;
    this._selectedRegionId   = null;
    this._selectedMonumentId = null;
    this._opts = opts;
    this._abortCtrl = null;

    // Left panel
    this._woolListEl = document.getElementById("po-wool-list");
    this._addWoolBtn = document.getElementById("po-add-wool-btn");

    // Right panel
    this._woolInspEl   = document.getElementById("po-wool-inspector");
    this._regionInspEl = document.getElementById("po-region-inspector");
    this._emptyEl      = document.getElementById("po-inspector-empty");

    this._regionPanel = new RegionsPanel(
      document.getElementById("po-region-list"),
      { onSelect: (node) => this._opts.onRegionRowClick?.(node.id) },
    );

    this._regionInsp = new RegionInspector(
      this._regionInspEl,
      {
        onSelect: (node) => this._opts.onRegionRowClick?.(node.id),
        onDelete: async (node) => {
          if (!this._mapName) return;
          try {
            await api.deleteRegion(this._mapName, node.id);
            this._opts.onDeleteRegion?.(node.id);
            showToast("Region deleted", "success");
          } catch (err) {
            showToast(`Delete failed: ${err.message}`, "error");
          }
        },
        onPatch: async (regionId, payload) => {
          if (!this._mapName) return;
          await api.patchRegion(this._mapName, regionId, payload);
          this._opts.onRegionPatched?.(regionId, payload.id ?? null);
        },
      },
    );

    this._attachStaticListeners();
  }

  async load(mapName) {
    this._mapName = mapName;
    this._wools   = [];
    this._teams   = [];
    try {
      const data = await api.fetchMapData(mapName);
      this._teams = data.teams ?? [];
      this._wools = (data.wools ?? []).map(w => ({
        team: null, location: null, wool_room_region: null, monuments: [],
        ...w,
      }));
    } catch (err) {
      console.error("ObjectivesPanel: failed to load map data:", err);
    }
    this._renderWoolList();
    this._clearSelection();
    this._updateStatusDot();
  }

  setWoolRegions(nodes) {
    this._woolRegions = nodes;
    const groups = nodes.length
      ? [{ name: "wool", label: null, regions: nodes }]
      : [];
    this._regionPanel.build(groups);
  }

  // ── region selection (called by activity) ────────────────────────────────

  onRegionSelect(node) {
    this._selectedRegionId = node.id;
    this._selectedWoolId   = null;
    this._woolInspEl.hidden   = true;
    this._regionInspEl.hidden = false;
    this._emptyEl.hidden      = true;
    this._regionPanel.setSelected(node.id, [node.id]);
    this._regionInsp.show(node);
    this._highlightLists();
  }

  onRegionDeselect() {
    this._selectedRegionId = null;
    this._regionPanel.setSelected(null, []);
    this._showEmpty();
  }

  // ── left panel ────────────────────────────────────────────────────────────

  _renderWoolList() {
    this._woolListEl.innerHTML = "";
    if (!this._wools.length) {
      this._woolListEl.innerHTML = '<div class="list-empty">No wool objectives.</div>';
      return;
    }
    for (const wool of this._wools) {
      const row = document.createElement("div");
      row.className = "list-row" + (wool.id === this._selectedWoolId ? " list-row--selected" : "");
      row.dataset.woolId = wool.id;

      const swatch = document.createElement("span");
      swatch.className = "list-swatch";
      swatch.style.backgroundColor = dyeColorHex(wool.color);

      const label = document.createElement("span");
      label.className = "list-label";
      label.textContent = dyeColorLabel(wool.color);

      row.append(swatch, label);
      row.addEventListener("click", () => this._selectWool(wool.id));
      this._woolListEl.appendChild(row);
    }
    const usedNorms = new Set(this._wools.map(w => _nc(w.color)));
    if (this._addWoolBtn) {
      this._addWoolBtn.disabled = WOOL_COLORS.every(c => usedNorms.has(_nc(c.value)));
    }
  }

  // ── wool inspector ────────────────────────────────────────────────────────

  _selectWool(woolId) {
    this._selectedWoolId   = woolId;
    this._selectedRegionId = null;
    this._opts.onDeselectRegion?.();
    this._highlightLists();

    const wool = this._wools.find(w => w.id === woolId);
    if (!wool) return;

    this._woolInspEl.hidden   = false;
    this._regionInspEl.hidden = true;
    this._emptyEl.hidden      = true;

    this._abortCtrl?.abort();
    this._abortCtrl = new AbortController();
    const sig = { signal: this._abortCtrl.signal };
    this._selectedMonumentId = wool.monuments?.[0]?.id ?? null;

    const el = this._woolInspEl;

    // Section title: "<Color> Wool"
    const titleEl = el.querySelector("#po-wool-section-title");
    const _setTitle = (color) => { titleEl.textContent = `${dyeColorLabel(color)} Wool`; };
    _setTitle(wool.color);

    // Color swatch + dropdown — only show unused colors + this wool's current color
    el.querySelector(".po-wool-color-swatch").style.backgroundColor = dyeColorHex(wool.color);
    const colorSel    = el.querySelector("#po-wool-color");
    const colorSwatch = el.querySelector(".po-wool-color-swatch");
    const otherNorms = new Set(this._wools.filter(w => w.id !== woolId).map(w => _nc(w.color)));
    colorSel.innerHTML = WOOL_COLORS
      .filter(c => _nc(c.value) === _nc(wool.color) || !otherNorms.has(_nc(c.value)))
      .map(c => `<option value="${c.value}">${c.label}</option>`).join("");
    colorSel.value = WOOL_COLORS.find(c => _nc(c.value) === _nc(wool.color))?.value ?? wool.color;

    // Owning team swatch + dropdown
    const teamSel    = el.querySelector("#po-wool-team");
    const teamSwatch = el.querySelector("#po-wool-team-swatch");
    const _teamColor = (id) => {
      const t = this._teams.find(t => t.id === id);
      return t ? chatColorHex(t.color) : "var(--border)";
    };
    teamSel.innerHTML = '<option value="">— none —</option>' +
      this._teams.map(t => `<option value="${t.id}">${t.name || t.id}</option>`).join("");
    teamSel.value = wool.team ?? "";
    teamSwatch.style.background = _teamColor(wool.team);

    // Location coords
    el.querySelector("#po-wool-loc-x").value = wool.location?.x ?? "";
    el.querySelector("#po-wool-loc-y").value = wool.location?.y ?? "";
    el.querySelector("#po-wool-loc-z").value = wool.location?.z ?? "";

    // Wool room region
    el.querySelector("#po-wool-room-region").value = wool.wool_room_region ?? "";

    // Save helpers
    const _save = async (patch) => {
      if (!this._mapName) return;
      try {
        const result = await api.updateWool(this._mapName, woolId, patch);
        Object.assign(wool, result.wool ?? patch);
        if ("color" in patch) {
          _setTitle(wool.color);
          colorSwatch.style.backgroundColor = dyeColorHex(wool.color);
          this._renderWoolList();
          // Refresh dropdown to exclude newly-taken color from other wools' options
          const updatedNorms = new Set(this._wools.filter(w => w.id !== woolId).map(w => _nc(w.color)));
          colorSel.innerHTML = WOOL_COLORS
            .filter(c => _nc(c.value) === _nc(wool.color) || !updatedNorms.has(_nc(c.value)))
            .map(c => `<option value="${c.value}">${c.label}</option>`).join("");
          colorSel.value = WOOL_COLORS.find(c => _nc(c.value) === _nc(wool.color))?.value ?? wool.color;
        }
        this._updateStatusDot();
      } catch (err) {
        showToast(`Save failed: ${err.message}`, "error");
      }
    };

    const _locPatch = () => {
      const x = parseFloat(el.querySelector("#po-wool-loc-x").value);
      const y = parseFloat(el.querySelector("#po-wool-loc-y").value);
      const z = parseFloat(el.querySelector("#po-wool-loc-z").value);
      return isNaN(x) && isNaN(y) && isNaN(z) ? null : { x: x || 0, y: y || 0, z: z || 0 };
    };

    colorSel.addEventListener("change", () => _save({ color: colorSel.value }), sig);
    teamSel.addEventListener("change", () => {
      teamSwatch.style.background = _teamColor(teamSel.value);
      _save({ team: teamSel.value || null });
    }, sig);
    for (const inp of el.querySelectorAll(".po-loc-input")) {
      inp.addEventListener("change", () => _save({ location: _locPatch() }), sig);
    }
    el.querySelector("#po-wool-room-region").addEventListener("change", e => {
      _save({ wool_room_region: e.target.value.trim() });
    }, sig);

    // Delete wool
    el.querySelector("#po-delete-wool-btn").addEventListener("click", async () => {
      if (!this._mapName) return;
      try {
        await api.deleteWool(this._mapName, woolId);
        this._wools = this._wools.filter(w => w.id !== woolId);
        this._renderWoolList();
        this._updateStatusDot();
        this._clearSelection();
      } catch (err) {
        showToast(`Delete failed: ${err.message}`, "error");
      }
    }, sig);

    // Monuments
    this._renderMonuments(wool, sig);
  }

  _renderMonuments(wool, sig) {
    const container = document.getElementById("po-monuments-container");
    container.innerHTML = "";
    const monuments = wool.monuments ?? [];

    // Ensure selected monument is still valid after add/delete
    if (!monuments.find(m => m.id === this._selectedMonumentId)) {
      this._selectedMonumentId = monuments[0]?.id ?? null;
    }

    // ── Header section: title + Add button + team badge row ───────────────
    const headerSec = document.createElement("section");
    headerSec.className = "panel-section";

    const hdr = document.createElement("div");
    hdr.className = "section-header section-header--ruled";
    const h2 = document.createElement("h2");
    h2.className = "section-title";
    h2.textContent = "Monuments";
    const usedTeams = new Set(monuments.map(m => m.team));
    const nextTeam = this._teams.find(t => !usedTeams.has(t.id))?.id ?? null;
    const addBtn = document.createElement("button");
    addBtn.className = "action-btn";
    addBtn.textContent = "+ Add";
    addBtn.disabled = nextTeam === null;
    addBtn.addEventListener("click", async () => {
      if (!this._mapName || !nextTeam) return;
      try {
        const result = await api.addMonument(this._mapName, wool.id, { team: nextTeam });
        const mon = { location: null, monument_region: null, ...result.monument };
        wool.monuments = [...monuments, mon];
        this._selectedMonumentId = mon.id;
        this._updateStatusDot();
        this._renderMonuments(wool, sig);
      } catch (err) {
        showToast(`Add monument failed: ${err.message}`, "error");
      }
    }, sig);
    hdr.append(h2, addBtn);
    headerSec.appendChild(hdr);

    if (monuments.length) {
      const badgeRow = document.createElement("div");
      badgeRow.className = "filter-group-options filter-group-options--mt";
      for (const mon of monuments) {
        const team = this._teams.find(t => t.id === mon.team);
        const chip = document.createElement("button");
        chip.className = "filter-chip" + (mon.id === this._selectedMonumentId ? " filter-chip--active" : "");
        chip.textContent = team?.name ?? mon.team ?? "?";
        const teamColor = team ? chatColorHex(team.color) : "";
        if (teamColor) chip.style.color = teamColor;
        chip.addEventListener("click", () => {
          this._selectedMonumentId = mon.id;
          this._renderMonuments(wool, sig);
        }, sig);
        badgeRow.appendChild(chip);
      }
      headerSec.appendChild(badgeRow);
    }
    container.appendChild(headerSec);

    // ── Detail section for selected monument ──────────────────────────────
    const selected = monuments.find(m => m.id === this._selectedMonumentId);
    if (selected) {
      container.appendChild(this._buildMonumentDetail(wool, selected, sig));
    }
  }

  _buildMonumentDetail(wool, mon, sig) {
    const sec = document.createElement("section");
    sec.className = "panel-section";

    const body = document.createElement("div");
    body.className = "section-body";

    // Team dropdown with color swatch
    const teamField = document.createElement("div");
    teamField.className = "field";
    const teamLabel = document.createElement("label");
    teamLabel.className = "field-label";
    teamLabel.textContent = "Team";
    const teamPickRow = document.createElement("div");
    teamPickRow.className = "field-pick-row";
    const teamSwatch = document.createElement("span");
    teamSwatch.className = "field-swatch";
    const _teamColor = (id) => {
      const t = this._teams.find(t => t.id === id);
      return t ? chatColorHex(t.color) : "var(--border)";
    };
    teamSwatch.style.background = _teamColor(mon.team);
    const teamSel = document.createElement("select");
    teamSel.className = "field-input";
    teamSel.innerHTML = '<option value="">— none —</option>' +
      this._teams.map(t => `<option value="${t.id}">${t.name || t.id}</option>`).join("");
    teamSel.value = mon.team ?? "";
    teamPickRow.append(teamSwatch, teamSel);
    teamField.append(teamLabel, teamPickRow);
    body.appendChild(teamField);

    // Monument location XYZ
    const locField = document.createElement("div");
    locField.className = "field";
    const locLabel = document.createElement("label");
    locLabel.className = "field-label";
    locLabel.textContent = "Block Position";
    const locRow = document.createElement("div");
    locRow.className = "ctrl-row";
    const xInp = _coordInput("X", mon.location?.x ?? "");
    const yInp = _coordInput("Y", mon.location?.y ?? "");
    const zInp = _coordInput("Z", mon.location?.z ?? "");
    locRow.append(xInp.el, yInp.el, zInp.el);
    locField.append(locLabel, locRow);
    body.appendChild(locField);

    // Monument region
    const regField = document.createElement("div");
    regField.className = "field";
    const regLabel = document.createElement("label");
    regLabel.className = "field-label";
    regLabel.textContent = "Monument Region";
    const regInp = document.createElement("input");
    regInp.className = "field-input";
    regInp.type = "text";
    regInp.spellcheck = false;
    regInp.placeholder = "region-id (optional)";
    regInp.value = mon.monument_region ?? "";
    regField.append(regLabel, regInp);
    body.appendChild(regField);

    sec.appendChild(body);

    // Delete button
    const actions = document.createElement("div");
    actions.className = "section-footer section-footer--separated";
    const delBtn = document.createElement("button");
    delBtn.className = "action-btn action-btn--danger action-btn--fill";
    delBtn.textContent = "Delete Monument";
    delBtn.addEventListener("click", async () => {
      if (!this._mapName) return;
      try {
        await api.deleteMonument(this._mapName, wool.id, mon.id);
        wool.monuments = wool.monuments.filter(m => m.id !== mon.id);
        this._selectedMonumentId = wool.monuments[0]?.id ?? null;
        this._updateStatusDot();
        this._renderMonuments(wool, sig);
      } catch (err) {
        showToast(`Delete failed: ${err.message}`, "error");
      }
    }, sig);
    actions.appendChild(delBtn);
    sec.appendChild(actions);

    // Save helpers
    const _saveMonument = async (patch) => {
      try {
        const result = await api.updateMonument(this._mapName, wool.id, mon.id, patch);
        Object.assign(mon, result.monument ?? patch);
        if ("team" in patch) {
          this._renderMonuments(wool, sig); // re-render badges with updated team name
        } else {
          this._updateStatusDot();
        }
      } catch (err) {
        showToast(`Save failed: ${err.message}`, "error");
      }
    };

    const _monLocPatch = () => {
      const x = parseFloat(xInp.inp.value);
      const y = parseFloat(yInp.inp.value);
      const z = parseFloat(zInp.inp.value);
      return isNaN(x) && isNaN(y) && isNaN(z) ? null : { x: x || 0, y: y || 0, z: z || 0 };
    };

    teamSel.addEventListener("change", () => _saveMonument({ team: teamSel.value }), sig);
    for (const inp of [xInp.inp, yInp.inp, zInp.inp]) {
      inp.addEventListener("change", () => _saveMonument({ location: _monLocPatch() }), sig);
    }
    regInp.addEventListener("change", () => _saveMonument({ monument_region: regInp.value.trim() }), sig);

    return sec;
  }

  // ── helpers ───────────────────────────────────────────────────────────────

  _showEmpty() {
    this._woolInspEl.hidden   = true;
    this._regionInspEl.hidden = true;
    this._emptyEl.hidden      = false;
    this._selectedRegionId = null;
    this._highlightLists();
  }

  _clearSelection() {
    this._selectedWoolId     = null;
    this._selectedMonumentId = null;
    this._showEmpty();
  }

  _highlightLists() {
    for (const row of this._woolListEl?.querySelectorAll(".list-row") ?? []) {
      row.classList.toggle("list-row--selected", row.dataset.woolId === this._selectedWoolId);
    }
  }

  _attachStaticListeners() {
    this._addWoolBtn?.addEventListener("click", async () => {
      if (!this._mapName) return;
      const usedNorms = new Set(this._wools.map(w => _nc(w.color)));
      const nextColor = WOOL_COLORS.find(c => !usedNorms.has(_nc(c.value)))?.value ?? null;
      if (!nextColor) return; // button should be disabled, but guard anyway
      try {
        const result = await api.addWool(this._mapName, { color: nextColor });
        const wool = { location: null, wool_room_region: null, monuments: [], ...result.wool };
        this._wools.push(wool);
        this._renderWoolList();
        this._updateStatusDot();
        this._selectWool(wool.id);
        showToast("Wool added", "success");
      } catch (err) {
        showToast(`Add wool failed: ${err.message}`, "error");
      }
    });
  }

  _updateStatusDot() {
    if (!this._opts.onStatusChange) return;
    const valid = this._wools.length >= 1 &&
      this._wools.every(w => w.location && w.monuments?.length > 0 &&
        w.monuments.every(m => m.team && m.location));
    this._opts.onStatusChange(valid ? "green" : "yellow");
  }
}

// ── module helpers ────────────────────────────────────────────────────────────

function _coordInput(prefix, value) {
  const el = document.createElement("div");
  el.className = "coord-field";
  const pre = document.createElement("span");
  pre.className = "coord-prefix";
  pre.textContent = prefix;
  const inp = document.createElement("input");
  inp.className = "coord-input";
  inp.type = "number";
  inp.step = "1";
  inp.placeholder = "—";
  inp.value = value !== null && value !== undefined && value !== "" ? value : "";
  el.append(pre, inp);
  return { el, inp };
}
