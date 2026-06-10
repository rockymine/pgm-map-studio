/**
 * Shared helpers for the canonical region tree returned by /regions/tree.
 */

export function getRegionGroups(treeData, category = null) {
  const groups = treeData?.groups ?? [];
  if (!category) return groups;
  const wanted = Array.isArray(category) ? new Set(category) : new Set([category]);
  return groups.filter(group => wanted.has(group.name));
}

// The objective categories (wool room / monument / wool spawner) that together
// make up the "wool" view in the Objectives activity.
export const WOOL_CATEGORIES = ["wool_room", "monument", "wool_spawner"];

export function registerRegionGroups(registry, groups) {
  for (const group of groups) {
    for (const root of group.regions ?? []) {
      if (root.id) registry.register(root);
    }
  }
}

export function findRegionNode(groups, regionId) {
  const visit = (node) => {
    if (node.id === regionId) return node;
    for (const child of node.children ?? []) {
      const found = visit(child);
      if (found) return found;
    }
    if (node.source) return visit(node.source);
    return null;
  };

  for (const group of groups) {
    for (const root of group.regions ?? []) {
      const found = visit(root);
      if (found) return found;
    }
  }
  return null;
}

export function regionIdExists(groups, candidateId, currentId = null) {
  if (!candidateId || candidateId === currentId) return false;
  return findRegionNode(groups, candidateId) !== null;
}

export function applyRegionPatchToNode(node, payload, result = {}) {
  if (!node || !payload) return;

  if (payload.coords && node.coords) {
    Object.assign(node.coords, payload.coords);
  }

  if (payload.bounds) {
    node.bounds = { ...payload.bounds };
  } else if (result.bounds) {
    node.bounds = { ...result.bounds };
  }
}
