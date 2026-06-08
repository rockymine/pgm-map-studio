import * as api from "../api.js";
import { OverviewRenderer } from "../canvas/overview-renderer.js";
import { showToast } from "../shared/ui-helpers.js";

const _AVATAR_EMPTY = "data:image/gif;base64,R0lGODlhEAAQAAAAACwAAAAAEAAQAAABEIQBADs=";

function _avatarUrl(uuid) {
  return `https://mc-heads.net/avatar/${encodeURIComponent(uuid)}/16`;
}

function _esc(str) {
  return String(str).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

export class OverviewPanel {
  constructor(el, { onStatusChange } = {}) {
    this._el             = el;
    this._map            = null;
    this._data           = null;
    this._dirty          = false;
    this._onStatusChange = onStatusChange ?? null;

    this._nameEl         = el.querySelector("#ov-name");
    this._versionEl      = el.querySelector("#ov-version");
    this._objectiveEl    = el.querySelector("#ov-objective");
    this._gamemodeEl     = el.querySelector("#ov-gamemode");
    this._authorsEl      = el.querySelector("#ov-authors-list");
    this._contributorsEl = el.querySelector("#ov-contributors-list");
    this._saveBtn        = el.querySelector("#ov-save-btn");
    this._statusEl       = el.querySelector("#ov-save-status");

    this._canvas = new OverviewRenderer(
      el.querySelector("#ov-map-svg"),
      el.querySelector("#ov-canvas-wrap"),
    );

    for (const field of [this._nameEl, this._versionEl, this._objectiveEl, this._gamemodeEl]) {
      field.addEventListener("input", () => this._setDirty(true));
    }
    this._saveBtn.addEventListener("click", () => this._save());

    el.querySelector("#ov-add-author").addEventListener("click", () => {
      this._addPersonRow(this._authorsEl, {});
      this._setDirty(true);
    });
    el.querySelector("#ov-add-contributor").addEventListener("click", () => {
      this._addPersonRow(this._contributorsEl, {});
      this._setDirty(true);
    });
  }

  resize() {
    this._canvas?.resize();
  }

  async load(mapName) {
    this._map = mapName;
    this._setDirty(false);
    this._statusEl.textContent = "";

    try {
      const [mapData, regionsData, topSurface] = await Promise.all([
        api.fetchMapData(mapName),
        api.fetchRegions(mapName),
        api.fetchTopSurface(mapName).catch(() => null),
      ]);

      this._data = mapData;
      this._populate();

      if (regionsData.bounding_box) {
        this._canvas.render(regionsData.bounding_box);
        if (topSurface) {
          this._canvas.loadBlockLayer(topSurface);
          this._canvas.setBlocksVisible(true);
        }
      }
    } catch (err) {
      this._statusEl.textContent = `Failed to load: ${err.message}`;
    }
  }

  // ── form ─────────────────────────────────────────────────────────────────

  _populate() {
    const d = this._data;
    this._nameEl.value      = d.name      ?? "";
    this._versionEl.value   = d.version   ?? "";
    this._objectiveEl.value = d.objective ?? "";
    this._gamemodeEl.value  = d.gamemode  ?? "";
    this._authorsEl.innerHTML      = "";
    this._contributorsEl.innerHTML = "";
    for (const person of (d.authors ?? [])) {
      const listEl = person.role === "contributor" ? this._contributorsEl : this._authorsEl;
      this._addPersonRow(listEl, person);
    }
    this._setDirty(false);
  }

  _addPersonRow(listEl, { uuid = "", name = "", contribution = "" } = {}) {
    const row = document.createElement("div");
    row.className   = "author-row";
    row.dataset.uuid = uuid;

    const avatarSrc  = uuid ? _avatarUrl(uuid) : _AVATAR_EMPTY;
    const displayName = name || uuid;

    row.innerHTML = `
      <img class="author-avatar" src="${_esc(avatarSrc)}" width="16" height="16" alt=""/>
      <input class="field-input author-name" type="text" placeholder="Minecraft username" value="${_esc(displayName)}"/>
      <input class="field-input author-contribution" type="text" placeholder="Contribution (optional)" value="${_esc(contribution ?? "")}"/>
      <button class="btn-remove" title="Remove">✕</button>
    `;

    const avatarImg = row.querySelector(".author-avatar");
    const nameInput = row.querySelector(".author-name");

    nameInput.addEventListener("blur", async () => {
      const val = nameInput.value.trim();
      if (!val || val === row.dataset.uuid || val === name) return;
      try {
        const player = await api.fetchMinecraftPlayer(val);
        row.dataset.uuid = player.uuid;
        nameInput.value  = player.name;
        nameInput.title  = player.uuid;
        avatarImg.src    = _avatarUrl(player.uuid);
        nameInput.classList.remove("field-input--error");
      } catch {
        row.dataset.uuid = "";
        avatarImg.src    = _AVATAR_EMPTY;
        nameInput.classList.add("field-input--error");
        nameInput.title  = "Player not found";
      }
      this._setDirty(true);
    });

    if (uuid && !name) {
      api.fetchMinecraftPlayer(uuid).then(player => {
        nameInput.value = player.name;
        nameInput.title = player.uuid;
        avatarImg.src   = _avatarUrl(player.uuid);
      }).catch(() => {});
    }

    row.querySelector(".btn-remove").addEventListener("click", () => {
      row.remove();
      this._setDirty(true);
    });
    for (const field of row.querySelectorAll("input")) {
      field.addEventListener("input", () => this._setDirty(true));
    }
    listEl.appendChild(row);
  }

  _collectAuthors() {
    const fromList = (listEl, role) =>
      [...listEl.querySelectorAll(".author-row")]
        .map(row => ({
          uuid:         row.dataset.uuid || "",
          name:         row.querySelector(".author-name").value.trim() || null,
          role,
          contribution: row.querySelector(".author-contribution").value.trim() || null,
        }))
        .filter(e => e.uuid);
    return [
      ...fromList(this._authorsEl,      "author"),
      ...fromList(this._contributorsEl, "contributor"),
    ];
  }

  async _save() {
    if (!this._map) return;
    this._saveBtn.disabled = true;
    this._statusEl.textContent = "Saving…";
    const metadata = {
      name:      this._nameEl.value.trim()      || null,
      version:   this._versionEl.value.trim()   || null,
      objective: this._objectiveEl.value.trim() || null,
      gamemode:  this._gamemodeEl.value.trim()  || null,
      authors:   this._collectAuthors(),
    };
    try {
      await api.saveMetadata(this._map, metadata);
      this._data = { ...this._data, ...metadata };
      this._setDirty(false);
      showToast("Map metadata saved", "success");
      this._statusEl.textContent = "";
    } catch (err) {
      this._statusEl.textContent = `Save failed: ${err.message}`;
      showToast(`Save failed: ${err.message}`, "error");
      this._saveBtn.disabled = false;
    }
  }

  _setDirty(isDirty) {
    this._dirty = isDirty;
    this._saveBtn.disabled = !isDirty;
    this._updateStatusDot();
  }

  _updateStatusDot() {
    if (!this._onStatusChange) return;
    const ok = !!(
      this._nameEl.value.trim() &&
      this._versionEl.value.trim() &&
      this._gamemodeEl.value.trim()
    );
    this._onStatusChange(ok ? "green" : "yellow");
  }
}
