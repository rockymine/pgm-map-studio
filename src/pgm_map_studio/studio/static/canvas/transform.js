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
