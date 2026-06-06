/**
 * sketch/geometry.js — Boolean island computation for the Layout activity.
 *
 * Converts primitive shapes to polygon rings, runs union/difference boolean
 * operations via polygon-clipping, extracts connected-component islands, and
 * assigns shapes to the islands they contribute to.
 *
 * Also provides mirror-preview computation: given island polygons and a
 * symmetry axis, return transformed copies for the live overlay.
 *
 * Imported via importmap in the browser; resolved from node_modules in tests.
 * See docs/sketch-workflow.md §Island model and §Symmetry model.
 */

import polygonClipping from "polygon-clipping";
import { applySymmetry } from "../shared/converters.js";

// Number of vertices used to approximate a circle polygon.
const CIRCLE_POINTS = 64;

// ── Shape → ring conversion ───────────────────────────────────────────────────

/**
 * Convert a sketch shape to a closed coordinate ring [[x, z], ...].
 * The last point equals the first (polygon-clipping library requirement).
 */
export function shapeToRing(shape) {
  switch (shape.type) {
    case "rectangle": {
      const { min_x, max_x, min_z, max_z } = shape;
      return [
        [min_x, min_z], [max_x, min_z],
        [max_x, max_z], [min_x, max_z],
        [min_x, min_z],
      ];
    }
    case "circle":
      return circleToRing(shape.center_x, shape.center_z, shape.radius);
    case "polygon":
    case "lasso": {
      if (!shape.vertices || shape.vertices.length < 3) return [];
      const ring = shape.vertices.map(([x, z]) => [x, z]);
      ring.push(ring[0]);
      return ring;
    }
    default:
      throw new Error(`Unknown shape type: ${shape.type}`);
  }
}

/**
 * Approximate a circle as a polygon ring, with vertices rounded to the
 * nearest integer block coordinate.
 */
export function circleToRing(cx, cz, radius, nPoints = CIRCLE_POINTS) {
  const pts = [];
  for (let i = 0; i < nPoints; i++) {
    const angle = (2 * Math.PI * i) / nPoints;
    pts.push([
      Math.round(cx + radius * Math.cos(angle)),
      Math.round(cz + radius * Math.sin(angle)),
    ]);
  }
  pts.push(pts[0]);
  return pts;
}

/** Wrap a ring as a polygon-clipping MultiPolygon: [ [ ring ] ] */
function _toMP(ring) { return [[ring]]; }

/** Convert a shape to a polygon-clipping MultiPolygon. */
export function shapeToMultiPoly(shape) {
  const ring = shapeToRing(shape);
  if (!ring.length) return [];
  return _toMP(ring);
}

// ── Centroid + point-in-polygon ───────────────────────────────────────────────

/** Ray-casting point-in-polygon test for a ring [[x, z], ...]. */
export function pointInRing(px, pz, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, zi] = ring[i];
    const [xj, zj] = ring[j];
    if ((zi > pz) !== (zj > pz) && px < (xj - xi) * (pz - zi) / (zj - zi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/** Point-in-island test: inside exterior and outside all holes. */
export function pointInIsland(px, pz, island) {
  if (!pointInRing(px, pz, island.exterior)) return false;
  return !island.holes.some(h => pointInRing(px, pz, h));
}

/** Centroid of a closed ring (last point == first). */
export function ringCentroid(ring) {
  const n = ring.length - 1; // exclude closing repeat
  let sumX = 0, sumZ = 0;
  for (let i = 0; i < n; i++) { sumX += ring[i][0]; sumZ += ring[i][1]; }
  return [sumX / n, sumZ / n];
}

// ── Main boolean computation ──────────────────────────────────────────────────

/**
 * Compute islands from the given list of shapes.
 *
 * Evaluation order (see docs/sketch-workflow.md §Island model):
 *   1. union(normal adds)
 *   2. − union(normal subtracts)
 *   3. ∪ union(override adds)       ← immune to normal subtracts
 *   4. − union(override subtracts)  ← cuts through everything
 *
 * Returns:
 *   {
 *     islands:          [{ id, name, exterior, holes, shapeIds, mirrors }]
 *     addUnion:         MultiPolygon from step 1 (used by assignShapesToIslands)
 *     overrideAddUnion: MultiPolygon after step 3 (used for override-sub assignment)
 *   }
 *
 * `islands` contains raw geometry only — names and mirror flags are preserved
 * from `previousIslands` when an island can be matched by centroid proximity.
 */
export function computeIslands(shapes, previousIslands = []) {
  const normalAdds    = shapes.filter(s => s.operation !== "subtract" && !s.override);
  const overrideAdds  = shapes.filter(s => s.operation !== "subtract" &&  s.override);
  const normalSubs    = shapes.filter(s => s.operation === "subtract"  && !s.override);
  const overrideSubs  = shapes.filter(s => s.operation === "subtract"  &&  s.override);

  if (normalAdds.length === 0 && overrideAdds.length === 0) {
    return { islands: [], addUnion: [], overrideAddUnion: [] };
  }

  // Step 1 — union normal adds.
  let normalUnion = [];
  if (normalAdds.length > 0) {
    try {
      const polys = normalAdds.map(shapeToMultiPoly).filter(p => p.length);
      if (polys.length) normalUnion = polygonClipping.union(polys[0], ...polys.slice(1));
    } catch (err) { console.warn("geometry: normal-add union error", err); }
  }

  // Step 2 — subtract normal subs from the union.
  let afterSub = normalUnion;
  if (normalSubs.length > 0 && normalUnion.length > 0) {
    try {
      const subPolys = normalSubs.map(shapeToMultiPoly).filter(p => p.length);
      if (subPolys.length) afterSub = polygonClipping.difference(normalUnion, ...subPolys);
    } catch (err) { console.warn("geometry: normal-sub difference error", err); }
  }

  // Step 3 — union override adds (immune to normal subtracts).
  let afterOverrideAdd = afterSub;
  if (overrideAdds.length > 0) {
    try {
      const polys = overrideAdds.map(shapeToMultiPoly).filter(p => p.length);
      if (polys.length) {
        afterOverrideAdd = afterSub.length > 0
          ? polygonClipping.union(afterSub, ...polys)
          : polygonClipping.union(polys[0], ...polys.slice(1));
      }
    } catch (err) { console.warn("geometry: override-add union error", err); }
  }

  // Step 4 — override subs cut last (through everything).
  let result = afterOverrideAdd;
  if (overrideSubs.length > 0 && afterOverrideAdd.length > 0) {
    try {
      const subPolys = overrideSubs.map(shapeToMultiPoly).filter(p => p.length);
      if (subPolys.length) result = polygonClipping.difference(afterOverrideAdd, ...subPolys);
    } catch (err) { console.warn("geometry: override-sub difference error", err); }
  }

  // Build island objects, preserving name/mirror from previous islands by
  // matching on centroid proximity (nearest previous centroid within threshold).
  const prevCentroids = previousIslands.map(isl => ({
    isl,
    cx: ringCentroid(isl.exterior)[0],
    cz: ringCentroid(isl.exterior)[1],
  }));

  const MATCH_THRESHOLD = 32; // blocks — centroids further apart → new island
  const matchedPrev = new Set(); // each previous island may be claimed by at most one new island

  const islands = result.map((poly, i) => {
    const exterior = poly[0];
    const holes    = poly.slice(1);
    const [ncx, ncz] = ringCentroid(exterior);

    // Find the closest unclaimed previous island whose centroid is within threshold.
    let best = null, bestDist = MATCH_THRESHOLD, bestIdx = -1;
    for (let j = 0; j < prevCentroids.length; j++) {
      if (matchedPrev.has(j)) continue;
      const { cx, cz, isl } = prevCentroids[j];
      const d = Math.hypot(ncx - cx, ncz - cz);
      if (d < bestDist) { bestDist = d; best = isl; bestIdx = j; }
    }
    if (bestIdx !== -1) matchedPrev.add(bestIdx);

    return {
      id:       best?.id      ?? `isl_${Date.now()}_${i}`,
      name:     best?.name    ?? `Island ${i + 1}`,
      mirrors:  best?.mirrors ?? true,
      exterior,
      holes,
      shapeIds: [],
    };
  });

  return { islands, addUnion: normalUnion, afterSub, overrideAddUnion: afterOverrideAdd };
}

// ── Shape → island assignment ─────────────────────────────────────────────────

/**
 * Assign each shape to the island(s) it contributes to and populate
 * island.shapeIds. Uses polygon intersection, not centroid, so subtract
 * shapes spanning multiple islands appear under all affected islands.
 *
 * Mutates the islands array in place.
 */
export function assignShapesToIslands(shapes, islands, addUnion, overrideAddUnion, afterSub) {
  if (!islands.length) return;

  const islandPolys = islands.map(isl => [[isl.exterior, ...isl.holes]]);

  // Map each island to its source component index in addUnion / overrideAddUnion.
  const toNormalIdx   = _mapIslandsToUnion(islands, addUnion);
  const toOverrideIdx = _mapIslandsToUnion(islands, overrideAddUnion ?? []);

  // Islands whose exterior polygon has solid area in afterSub were produced by the
  // normal-subtract path and can legitimately receive subtract attribution.
  // Pure override-add islands (sitting in holes) must not inherit subtract shapes.
  const normalPath = _normalPathSet(islands, afterSub);

  for (const shape of shapes) {
    const sp = shapeToMultiPoly(shape);
    if (!sp.length) continue;
    const toAssign = new Set();

    if (shape.operation === "subtract" && !shape.override) {
      // Normal subtract: assign to islands from every addUnion component it intersects,
      // restricted to islands that were on the normal computation path.
      for (let j = 0; j < addUnion.length; j++) {
        if (!_intersects(sp, [addUnion[j]])) continue;
        for (let i = 0; i < islands.length; i++) {
          if (toNormalIdx[i] === j && normalPath.has(i)) toAssign.add(i);
        }
      }

    } else if (shape.operation === "subtract" && shape.override) {
      // Override subtract: assigned to islands from overrideAddUnion it intersects.
      _intersectUnionComponents(sp, overrideAddUnion ?? [], toOverrideIdx, islands, toAssign);

    } else if (shape.override) {
      // Override add: intersect directly against final island polygons.
      for (let i = 0; i < islands.length; i++) {
        if (_intersects(sp, islandPolys[i])) toAssign.add(i);
      }

    } else {
      // Normal add: find addUnion components it overlaps, then resolve to final islands.
      for (let j = 0; j < addUnion.length; j++) {
        if (!_intersects(sp, [addUnion[j]])) continue;
        const peers = islands.reduce((acc, _, i) => {
          if (toNormalIdx[i] === j && normalPath.has(i)) acc.push(i);
          return acc;
        }, []);
        if (peers.length === 1) {
          toAssign.add(peers[0]);
        } else {
          // A subtract split the component into several islands — intersect each.
          for (const i of peers) {
            if (_intersects(sp, islandPolys[i])) toAssign.add(i);
          }
        }
      }
    }

    for (const i of toAssign) islands[i].shapeIds.push(shape.id);
  }
}

function _mapIslandsToUnion(islands, union) {
  return islands.map(isl => {
    if (!union.length) return -1;
    const [cx, cz] = ringCentroid(isl.exterior);
    for (let j = 0; j < union.length; j++) {
      const comp = union[j];
      if (pointInIsland(cx, cz, { exterior: comp[0], holes: comp.slice(1) })) return j;
    }
    return -1;
  });
}

function _intersectUnionComponents(sp, union, toComponentIdx, islands, toAssign) {
  for (let j = 0; j < union.length; j++) {
    if (!_intersects(sp, [union[j]])) continue;
    for (let i = 0; i < islands.length; i++) {
      if (toComponentIdx[i] === j) toAssign.add(i);
    }
  }
}

function _intersects(a, b) {
  try { return polygonClipping.intersection(a, b).length > 0; } catch { return false; }
}

// Returns the set of island indices that have solid area in afterSub (i.e. they were
// produced by the normal-subtract step, not purely by an override-add inside a hole).
// When afterSub is unavailable, all islands are assumed to be on the normal path.
function _normalPathSet(islands, afterSub) {
  if (!afterSub || !afterSub.length) return new Set(islands.map((_, i) => i));
  const result = new Set();
  for (let i = 0; i < islands.length; i++) {
    const extPoly = [[islands[i].exterior]]; // exterior ring treated as filled polygon
    for (const comp of afterSub) {
      if (_intersects(extPoly, [comp])) { result.add(i); break; }
    }
  }
  return result;
}

// ── Mirror preview ────────────────────────────────────────────────────────────

/**
 * Compute the live mirror-preview polygons for a given set of islands.
 *
 * For rot_90: generates three rotated copies (90°, 180°, 270°).
 * For all other modes: generates one reflected/rotated copy.
 *
 * Returns an array of { exterior, holes, sourceId } objects — one entry per
 * copy (three for rot_90, one for others). Only participating islands are
 * included (mirrors === true).
 *
 * @param {object[]} islands - From computeIslands (with .exterior, .holes, .mirrors, .id)
 * @param {string} axis - "mirror_x" | "mirror_z" | "rot_180" | "rot_90"
 * @param {number} cx - Center x
 * @param {number} cz - Center z
 * @returns {{ exterior: [number,number][], holes: [number,number][][], sourceId: string }[]}
 */
export function computeMirrorPreview(islands, axis, cx, cz) {
  const result = [];
  for (const isl of islands) {
    if (!isl.mirrors) continue;
    const copies = axis === "rot_90" ? ["rot_90", "rot_180", "rot_270"] : [axis];
    for (const copyAxis of copies) {
      result.push({
        sourceId: isl.id,
        exterior: _transformRing(isl.exterior, copyAxis, cx, cz),
        holes:    isl.holes.map(h => _transformRing(h, copyAxis, cx, cz)),
      });
    }
  }
  return result;
}

function _transformRing(ring, axis, cx, cz) {
  // rot_270 = three times rot_90 CCW = once rot_90 CW
  // We express it as applying applySymmetry("rot_90") twice + mirror, or
  // simply compute manually: rot_270 CCW = rot_90 CW: (Δx,Δz) → (Δz, -Δx)
  if (axis === "rot_270") {
    return ring.map(([x, z]) => {
      const dx = x - cx, dz = z - cz;
      return [cx + dz, cz - dx];
    });
  }
  return ring.map(([x, z]) => applySymmetry(x, z, axis, cx, cz));
}

/**
 * Apply saved island metadata to computed islands by matching on shapeId overlap.
 * @param {object[]} islands   - From computeIslands (with .shapeIds populated by assignShapesToIslands)
 * @param {object[]} savedMeta - Persisted island records ({shapeIds, ...fields})
 * @param {string[]} fields    - Which fields to copy from the best match onto each island
 */
export function restoreIslandMeta(islands, savedMeta, fields) {
  if (!savedMeta.length) return;
  for (const isl of islands) {
    let best = null, bestScore = 0;
    for (const meta of savedMeta) {
      const overlap = isl.shapeIds.filter(sid => (meta.shapeIds ?? []).includes(sid)).length;
      if (overlap > bestScore) { bestScore = overlap; best = meta; }
    }
    if (!best || bestScore === 0) continue;
    for (const field of fields) {
      if (best[field] !== undefined) isl[field] = best[field];
    }
  }
}
