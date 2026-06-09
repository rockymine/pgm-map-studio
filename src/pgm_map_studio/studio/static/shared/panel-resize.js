/**
 * Wire every sidebar handle carrying a data-resize-target attribute.
 *
 * Markup owns the target, side, and limits so Editor and Sketch use the same
 * behavior without activity-specific bootstrap code.
 */
export function connectPanelResizers(root = document) {
  root.querySelectorAll(".sidebar-handle[data-resize-target]").forEach(handle => {
    if (handle.dataset.resizeConnected === "1") return;

    const panel = document.getElementById(handle.dataset.resizeTarget);
    if (!panel) return;

    const side = handle.dataset.resizeSide === "right" ? "right" : "left";
    const min = Number(handle.dataset.resizeMin ?? 200);
    const max = Number(handle.dataset.resizeMax ?? 480);

    handle.dataset.resizeConnected = "1";
    handle.addEventListener("mousedown", event => {
      event.preventDefault();
      handle.classList.add("sidebar-handle--dragging");
      document.body.style.userSelect = "none";
      document.body.style.cursor = "ew-resize";

      const startX = event.clientX;
      const startWidth = panel.offsetWidth;

      function onMove(moveEvent) {
        const delta = side === "left"
          ? moveEvent.clientX - startX
          : startX - moveEvent.clientX;
        panel.style.width = `${Math.max(min, Math.min(max, startWidth + delta))}px`;
      }

      function onUp() {
        handle.classList.remove("sidebar-handle--dragging");
        document.body.style.userSelect = "";
        document.body.style.cursor = "";
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      }

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });
}
