/**
 * canvas-helpers.js — shared utilities for activity→canvas wiring.
 *
 * normalizeIslands   — coerce island polygon to simplified_polygon format
 * drawResultToPayload — convert an EditorCanvas drawResult into a createRegion payload
 */

/**
 * Ensure every island has a simplified_polygon (exterior/holes) that
 * EditorCanvas.render() expects.
 */
export function normalizeIslands(islands) {
  return (islands ?? []).map(isl => ({
    ...isl,
    simplified_polygon: isl.simplified_polygon ?? _geojsonToSimplified(isl.polygon),
  }));
}

function _geojsonToSimplified(polygon) {
  if (!polygon?.coordinates?.length) return null;
  return { exterior: polygon.coordinates[0] || [], holes: polygon.coordinates.slice(1) };
}

/**
 * Convert a raw drawResult from EditorCanvas into a POST /regions payload.
 *
 * @param {object} drawResult  — shape from onRegionDraw callback
 * @param {string} category    — "spawn" | "build" | "wool" | "other"
 * @param {object} [extra]     — any extra fields to merge (e.g. { height: 10 })
 */
export function drawResultToPayload(drawResult, category, extra = {}) {
  const { type, min_x, min_z, max_x, max_z,
          base_x, base_z, center_x, center_z, radius } = drawResult;
  const base = { category, ...extra };
  switch (type) {
    case "cylinder":
      return { ...base, type, base_x, base_y: 0, base_z, radius, height: extra.height ?? 10 };
    case "circle":
      return { ...base, type, center_x, center_z, radius };
    case "point":
    case "block":
      return { ...base, type, x: min_x + 0.5, y: 0, z: min_z + 0.5 };
    default:
      // rectangle, cuboid
      return { ...base, type, min_x, min_z, max_x, max_z };
  }
}
