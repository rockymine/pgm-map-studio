export const TYPE_ICON = {
  // PGM region primitives
  point:      lucide.Dot,
  block:      lucide.Square,
  rectangle:  lucide.RectangleHorizontal,
  cuboid:     lucide.Box,
  cylinder:   lucide.Cylinder,
  circle:     lucide.Circle,
  sphere:     lucide.Globe,
  // PGM compound / boolean
  complement: lucide.SquaresSubtract,
  union:      lucide.SquaresUnite,
  negative:   lucide.SquareSquare,
  intersect:  lucide.SquaresIntersect,
  reference:  lucide.SquareArrowOutUpRight,
  mirror:     lucide.SquareSplitHorizontal,
  half:       lucide.ArrowsUpFromLine,
  translate:  lucide.Move3d,
  // Sketch-only shape types (not PGM region types)
  polygon:    lucide.Pentagon,
  lasso:      lucide.Lasso,
  island:     lucide.Layers,
};

export function deriveBoundsFromCoords(type, coords) {
  if (type === "cylinder") {
    const bx = coords.base_x ?? 0, bz = coords.base_z ?? 0, r = coords.radius ?? 0;
    return { min_x: bx - r, max_x: bx + r, min_z: bz - r, max_z: bz + r };
  }
  if (type === "circle") {
    const cx = coords.center_x ?? 0, cz = coords.center_z ?? 0, r = coords.radius ?? 0;
    return { min_x: cx - r, max_x: cx + r, min_z: cz - r, max_z: cz + r };
  }
  if (type === "sphere") {
    const ox = coords.origin_x ?? 0, oz = coords.origin_z ?? 0, r = coords.radius ?? 0;
    return { min_x: ox - r, max_x: ox + r, min_z: oz - r, max_z: oz + r };
  }
  if (type === "block") {
    const x = coords.x ?? 0, z = coords.z ?? 0;
    return { min_x: x, max_x: x + 1, min_z: z, max_z: z + 1 };
  }
  if (type === "point") {
    const x = coords.x ?? 0, z = coords.z ?? 0;
    return { min_x: x - 0.5, max_x: x + 0.5, min_z: z - 0.5, max_z: z + 0.5 };
  }
  return null;
}

export function typeIcon(type, size = 13) {
  const IconFn = TYPE_ICON[type];
  if (!IconFn) return "";
  const svg = lucide.createSvgIcon(IconFn);
  svg.setAttribute("width",  size);
  svg.setAttribute("height", size);
  svg.setAttribute("stroke-width", "1.5");
  return svg.outerHTML;
}
