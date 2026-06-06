/**
 * algorithms/simplify.js — Polygon simplification algorithms.
 *
 * This module is the single home for vertex-reduction algorithms. New
 * algorithms (annealing, TSP-based smoothing, etc.) should be added here
 * as named exports alongside simplifyVW.
 *
 * All functions operate on flat vertex arrays [[x, z], ...] and return a
 * new array of the same form. The input polygon need not be closed (last ≠
 * first); the output is also not closed.
 */

// ── Visvalingam–Whyatt ────────────────────────────────────────────────────────

/**
 * Return the signed area of the triangle formed by three consecutive points.
 * We use |area| as the "importance" of the middle vertex.
 */
function _triangleArea(a, b, c) {
  return Math.abs(
    (b[0] - a[0]) * (c[1] - a[1]) -
    (c[0] - a[0]) * (b[1] - a[1])
  ) / 2;
}

/**
 * Simplify a polygon using the Visvalingam–Whyatt algorithm.
 *
 * Repeatedly removes the vertex whose removal creates the smallest triangle
 * area until no triangle area falls below `tolerance`. The first and last
 * vertices are always preserved.
 *
 * @param {[number, number][]} vertices - Input vertices [[x, z], ...]
 * @param {number} tolerance - Minimum triangle area (in blocks²) to keep
 * @returns {[number, number][]} Simplified vertices
 */
export function simplifyVW(vertices, tolerance) {
  if (vertices.length <= 2) return vertices.slice();

  // Work with a doubly-linked list so removal is O(1) per step.
  const n = vertices.length;
  const prev = Array.from({ length: n }, (_, i) => i - 1);
  const next = Array.from({ length: n }, (_, i) => i + 1);
  const area = new Float64Array(n).fill(Infinity);

  // Compute initial areas for all interior vertices.
  for (let i = 1; i < n - 1; i++) {
    area[i] = _triangleArea(vertices[prev[i]], vertices[i], vertices[next[i]]);
  }

  // Iteratively remove the minimum-area vertex.
  let changed = true;
  while (changed) {
    changed = false;
    // Find the interior vertex with the smallest area.
    let minIdx = -1;
    let minArea = tolerance;
    for (let i = 1; i < n - 1; i++) {
      if (prev[i] === -1) continue; // already removed
      if (area[i] < minArea) { minArea = area[i]; minIdx = i; }
    }
    if (minIdx === -1) break;

    // Remove minIdx from the linked list.
    const p = prev[minIdx];
    const nx = next[minIdx];
    next[p]    = nx;
    prev[nx]   = p;
    prev[minIdx] = -1; // mark as removed

    // Recompute areas for affected neighbours.
    if (p > 0 && prev[p] !== -1) {
      area[p] = _triangleArea(vertices[prev[p]], vertices[p], vertices[next[p]]);
    }
    if (nx < n - 1 && next[nx] !== n) {
      area[nx] = _triangleArea(vertices[prev[nx]], vertices[nx], vertices[next[nx]]);
    }

    changed = true;
  }

  // Collect surviving vertices in order.
  const result = [];
  for (let i = 0; i < n; i++) {
    if (i === 0 || prev[i] !== -1) result.push(vertices[i]);
  }
  return result;
}
