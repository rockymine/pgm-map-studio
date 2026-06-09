/**
 * Shared helpers for the canonical region tree returned by /regions/tree.
 */

export function getRegionGroups(treeData, category = null) {
  const groups = treeData?.groups ?? [];
  return category ? groups.filter(group => group.name === category) : groups;
}

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
