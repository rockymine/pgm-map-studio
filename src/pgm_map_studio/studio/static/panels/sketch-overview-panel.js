import * as api from "../api.js";
import { showToast } from "../shared/ui-helpers.js";

const _AVATAR_EMPTY = "data:image/gif;base64,R0lGODlhEAAQAAAAACwAAAAAEAAQAAABEIQBADs=";

function _avatarUrl(uuid) {
  return `https://mc-heads.net/avatar/${encodeURIComponent(uuid)}/16`;
}

function _esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

export class SketchOverviewPanel {
  #el;
  #sketchId       = null;
  #data           = null;
  #dirty          = false;
  #onStatusChange = null;

  #nameEl;
  #versionEl;
  #objectiveEl;
  #authorsEl;
  #contributorsEl;
  #saveBtn;
  #statusEl;

  constructor(el, { onStatusChange } = {}) {
    this.#el             = el;
    this.#onStatusChange = onStatusChange ?? null;

    this.#nameEl         = el.querySelector("#sk-name");
    this.#versionEl      = el.querySelector("#sk-version");
    this.#objectiveEl    = el.querySelector("#sk-objective");
    this.#authorsEl      = el.querySelector("#sk-authors-list");
    this.#contributorsEl = el.querySelector("#sk-contributors-list");
    this.#saveBtn        = el.querySelector("#sk-save-btn");
    this.#statusEl       = el.querySelector("#sk-save-status");

    for (const field of [this.#nameEl, this.#versionEl, this.#objectiveEl]) {
      field.addEventListener("input", () => this.#setDirty(true));
    }
    this.#saveBtn.addEventListener("click", () => this.#save());

    el.querySelector("#sk-add-author").addEventListener("click", () => {
      this.#addPersonRow(this.#authorsEl, {});
      this.#setDirty(true);
    });
    el.querySelector("#sk-add-contributor").addEventListener("click", () => {
      this.#addPersonRow(this.#contributorsEl, {});
      this.#setDirty(true);
    });
  }

  async load(sketchId) {
    this.#sketchId = sketchId;
    this.#setDirty(false);
    this.#statusEl.textContent = "";

    try {
      this.#data = await api.fetchSketch(sketchId);
      this.#populate();
    } catch (err) {
      this.#statusEl.textContent = `Failed to load: ${err.message}`;
    }
  }

  // ── private ───────────────────────────────────────────────────────────────

  #populate() {
    const d = this.#data;
    this.#nameEl.value      = d.name      ?? "";
    this.#versionEl.value   = d.version   ?? "";
    this.#objectiveEl.value = d.objective ?? "";
    this.#authorsEl.innerHTML      = "";
    this.#contributorsEl.innerHTML = "";
    for (const person of (d.authors ?? [])) {
      const listEl = person.role === "contributor" ? this.#contributorsEl : this.#authorsEl;
      this.#addPersonRow(listEl, person);
    }
    this.#setDirty(false);
    this.#updateTopbarName();
  }

  #addPersonRow(listEl, { uuid = "", name = "", contribution = "" } = {}) {
    const row = document.createElement("div");
    row.className    = "author-row";
    row.dataset.uuid = uuid;

    const avatarSrc   = uuid ? _avatarUrl(uuid) : _AVATAR_EMPTY;
    const displayName = name || uuid;

    row.innerHTML = `
      <img class="author-avatar" src="${_esc(avatarSrc)}" width="16" height="16" alt=""/>
      <input class="field-input author-name" type="text" placeholder="Minecraft username" value="${_esc(displayName)}"/>
      <input class="field-input author-contribution" type="text" placeholder="Contribution (optional)" value="${_esc(contribution ?? "")}"/>
      <button class="btn-remove" title="Remove"><i data-lucide="x"></i></button>
    `;

    const avatarImg = row.querySelector(".author-avatar");
    const nameInput = row.querySelector(".author-name");

    nameInput.addEventListener("blur", async () => {
      const val = nameInput.value.trim();
      if (!val || val === row.dataset.uuid || val === name) return;
      try {
        const player = await api.fetchMinecraftPlayer(val);
        row.dataset.uuid      = player.uuid;
        nameInput.value       = player.name;
        nameInput.title       = player.uuid;
        avatarImg.src         = _avatarUrl(player.uuid);
        nameInput.classList.remove("field-input--error");
      } catch {
        row.dataset.uuid = "";
        avatarImg.src    = _AVATAR_EMPTY;
        nameInput.classList.add("field-input--error");
        nameInput.title  = "Player not found";
      }
      this.#setDirty(true);
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
      this.#setDirty(true);
      lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "16", height: "16" } });
    });
    for (const field of row.querySelectorAll("input")) {
      field.addEventListener("input", () => this.#setDirty(true));
    }

    listEl.appendChild(row);
    lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "16", height: "16" } });
  }

  #collectAuthors() {
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
      ...fromList(this.#authorsEl,      "author"),
      ...fromList(this.#contributorsEl, "contributor"),
    ];
  }

  async #save() {
    if (!this.#sketchId) return;
    this.#saveBtn.disabled     = true;
    this.#statusEl.textContent = "Saving…";
    const payload = {
      name:      this.#nameEl.value.trim()      || "",
      version:   this.#versionEl.value.trim()   || "",
      objective: this.#objectiveEl.value.trim() || "",
      authors:   this.#collectAuthors(),
    };
    try {
      await api.saveSketchOverview(this.#sketchId, payload);
      this.#data = { ...this.#data, ...payload };
      this.#setDirty(false);
      this.#updateTopbarName();
      showToast("Overview saved", "success");
      this.#statusEl.textContent = "";
    } catch (err) {
      this.#statusEl.textContent = `Save failed: ${err.message}`;
      showToast(`Save failed: ${err.message}`, "error");
      this.#saveBtn.disabled = false;
    }
  }

  #setDirty(isDirty) {
    this.#dirty                = isDirty;
    this.#saveBtn.disabled     = !isDirty;
    this.#updateStatusDot();
  }

  #updateStatusDot() {
    if (!this.#onStatusChange) return;
    const hasName   = !!this.#nameEl.value.trim();
    const hasAuthor = this.#authorsEl.querySelectorAll(".author-row").length > 0;
    this.#onStatusChange(hasName && hasAuthor ? "green" : "yellow");
  }

  #updateTopbarName() {
    const nameEl = document.getElementById("topbar-sketch-name");
    if (nameEl) nameEl.textContent = this.#nameEl.value.trim() || "New sketch";
  }
}
