/**
 * Pure coordinate-math and SVG-element helpers.
 * Accepts bounding_box as {min_x, min_z, max_x, max_z}.
 */

const PAD = 20;

/**
 * Build a world→SVG transform from a bounding box.
 * @param {{min_x,min_z,max_x,max_z}} bbox
 * @returns {(wx:number,wz:number)=>{x:number,y:number}}
 */
export function buildTransform(bbox, svgW, svgH) {
  const { min_x, min_z, max_x, max_z } = bbox;
  const worldW = max_x - min_x, worldH = max_z - min_z;
  const drawW = svgW - 2 * PAD, drawH = svgH - 2 * PAD;
  const scale = Math.min(drawW / worldW, drawH / worldH);
  const offX = PAD + (drawW - worldW * scale) / 2;
  const offY = PAD + (drawH - worldH * scale) / 2;
  return (wx, wz) => ({
    x: offX + (wx - min_x) * scale,
    y: offY + (wz - min_z) * scale,
  });
}

export function buildInverseTransform(bbox, svgW, svgH) {
  const { min_x, min_z, max_x, max_z } = bbox;
  const worldW = max_x - min_x, worldH = max_z - min_z;
  const drawW = svgW - 2 * PAD, drawH = svgH - 2 * PAD;
  const scale = Math.min(drawW / worldW, drawH / worldH);
  const offX = PAD + (drawW - worldW * scale) / 2;
  const offY = PAD + (drawH - worldH * scale) / 2;
  return (px, py) => ({
    x: (px - offX) / scale + min_x,
    z: (py - offY) / scale + min_z,
  });
}

/** Create an SVG element with given attributes. */
export function svgEl(tag, attrs = {}, children = []) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const ch of children) el.appendChild(ch);
  return el;
}

/** Return the x/y/width/height attributes for a centered square handle rect. */
export function handleRectAttrs(cx, cy, half) {
  return { x: cx - half, y: cy - half, width: half * 2, height: half * 2 };
}

/** Convert a polygon ring [[x,z],...] to an SVG path segment. */
export function ringToPath(ring, toSvg) {
  return ring.map(([x, z], i) => {
    const p = toSvg(x, z);
    return (i === 0 ? "M" : "L") + `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }).join(" ") + " Z";
}

/** Convert a GeoJSON-like polygon (exterior + optional holes) to a path. */
export function polyToPath(poly, toSvg) {
  if (poly.polygons) {
    return poly.polygons
      .map(p => ringToPath(p.exterior, toSvg) + (p.holes || []).map(h => " " + ringToPath(h, toSvg)).join(""))
      .join(" ");
  }
  let d = ringToPath(poly.exterior, toSvg);
  for (const hole of (poly.holes || [])) d += " " + ringToPath(hole, toSvg);
  return d;
}

/** Convert a bounds {min_x, min_z, max_x, max_z} to an SVG ring path. */
export function boundsToRingPath(bounds, toSvg) {
  const { min_x, min_z, max_x, max_z } = bounds;
  return ringToPath(
    [[min_x, min_z], [max_x, min_z], [max_x, max_z], [min_x, max_z]],
    toSvg,
  );
}

/**
 * Sutherland-Hodgman half-plane clip.
 * Clips polygon `poly` ([[x,z],...]) against the half-plane defined by
 * point (ox, oz) and inward normal (nx, nz).
 * A vertex is inside when (v.x - ox)*nx + (v.z - oz)*nz >= 0.
 */
export function clipHalfPlane(poly, ox, oz, nx, nz) {
  if (!poly.length) return [];
  const dot = ([x, z]) => (x - ox) * nx + (z - oz) * nz;
  const output = [];
  for (let i = 0; i < poly.length; i++) {
    const a = poly[(i + poly.length - 1) % poly.length];
    const b = poly[i];
    const da = dot(a);
    const db = dot(b);
    if (db >= 0) {
      if (da < 0) {
        const t = da / (da - db);
        output.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
      }
      output.push(b);
    } else if (da >= 0) {
      const t = da / (da - db);
      output.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
    }
  }
  return output;
}
