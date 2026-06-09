/**
 * RegionRegistry — tracks the region tree and selection state.
 * Selection is single-primary: selecting a node also selects all descendants.
 */
export class RegionRegistry {
  #entries = new Map();   // id → { parentId, childIds, node }
  #onSelectionChange;
  #selectedIds = new Set();
  #primaryId   = null;

  constructor({ onSelectionChange } = {}) {
    this.#onSelectionChange = onSelectionChange || null;
  }

  clear() {
    this.#entries.clear();
    this.#selectedIds.clear();
    this.#primaryId = null;
  }

  register(node, parentId = null) {
    const childIds = (node.children || []).map(c => c.id).filter(Boolean);
    this.#entries.set(node.id, { parentId, childIds, node });
    for (const child of (node.children || [])) this.register(child, node.id);
  }

  select(id) {
    const info = this.#entries.get(id);
    if (!info) return;
    this.#primaryId = id;
    this.#selectedIds.clear();
    this.#collectDescendants(id, this.#selectedIds);
    this.#onSelectionChange?.(info.node, [...this.#selectedIds]);
  }

  deselect() {
    this.#primaryId = null;
    this.#selectedIds.clear();
    this.#onSelectionChange?.(null, []);
  }

  getNode(id) { return this.#entries.get(id)?.node ?? null; }
  has(id) { return this.#entries.has(id); }

  renameNode(oldId, newId) {
    const entry = this.#entries.get(oldId);
    if (!entry) return;
    this.#entries.delete(oldId);
    this.#entries.set(newId, entry);
    if (entry.parentId) {
      const p = this.#entries.get(entry.parentId);
      if (p) { const idx = p.childIds.indexOf(oldId); if (idx !== -1) p.childIds[idx] = newId; }
    }
    for (const cid of entry.childIds) {
      const c = this.#entries.get(cid);
      if (c) c.parentId = newId;
    }
    if (this.#primaryId === oldId) this.#primaryId = newId;
    if (this.#selectedIds.has(oldId)) { this.#selectedIds.delete(oldId); this.#selectedIds.add(newId); }
  }

  recomputeAncestorBounds(startId) {
    const updated = [];
    let currentId = this.#entries.get(startId)?.parentId;
    while (currentId) {
      const entry = this.#entries.get(currentId);
      if (!entry) break;
      const { node } = entry;
      let newBounds = null;
      if (node.type === "union")     newBounds = this.#unionOfChildren(node);
      if (node.type === "intersect") newBounds = this.#intersectOfChildren(node);
      if (newBounds && node.bounds) { Object.assign(node.bounds, newBounds); updated.push(node); }
      currentId = entry.parentId;
    }
    return updated;
  }

  #unionOfChildren(node) {
    let minX = Infinity, minZ = Infinity, maxX = -Infinity, maxZ = -Infinity, found = false;
    for (const child of (node.children || [])) {
      if (!child.bounds) continue; found = true;
      minX = Math.min(minX, child.bounds.min_x); minZ = Math.min(minZ, child.bounds.min_z);
      maxX = Math.max(maxX, child.bounds.max_x); maxZ = Math.max(maxZ, child.bounds.max_z);
    }
    return found ? { min_x: minX, min_z: minZ, max_x: maxX, max_z: maxZ } : null;
  }

  #intersectOfChildren(node) {
    let minX = -Infinity, minZ = -Infinity, maxX = Infinity, maxZ = Infinity, found = false;
    for (const child of (node.children || [])) {
      if (!child.bounds) continue; found = true;
      minX = Math.max(minX, child.bounds.min_x); minZ = Math.max(minZ, child.bounds.min_z);
      maxX = Math.min(maxX, child.bounds.max_x); maxZ = Math.min(maxZ, child.bounds.max_z);
    }
    return (found && minX < maxX && minZ < maxZ) ? { min_x: minX, min_z: minZ, max_x: maxX, max_z: maxZ } : null;
  }

  unregister(id) {
    const entry = this.#entries.get(id);
    if (!entry) return;
    if (entry.parentId) {
      const p = this.#entries.get(entry.parentId);
      if (p) p.childIds = p.childIds.filter(cid => cid !== id);
    }
    const wasSelected = this.#selectedIds.has(id) || this.#primaryId === id;
    this.#removeSubtree(id);
    if (wasSelected) this.deselect();
  }

  #removeSubtree(id) {
    const entry = this.#entries.get(id);
    if (!entry) return;
    for (const cid of entry.childIds) this.#removeSubtree(cid);
    this.#entries.delete(id);
    this.#selectedIds.delete(id);
    if (this.#primaryId === id) this.#primaryId = null;
  }

  #collectDescendants(id, out) {
    out.add(id);
    const info = this.#entries.get(id);
    if (!info) return;
    for (const cid of info.childIds) this.#collectDescendants(cid, out);
  }
}
