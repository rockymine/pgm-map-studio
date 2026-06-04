/**
 * ui-helpers.js — Shared UI utilities.
 *
 * Notification system (4 canonical types):
 *   showSystemError(message)     — Type 1: persistent top-bar error
 *   clearSystemError()           — dismiss Type 1
 *   showToast(message, type)     — Type 2: 4s auto-dismiss bottom-right
 *   showCanvasHint(el, message)  — Type 3: canvas overlay hint
 *   hideCanvasHint(el)           — dismiss Type 3
 *   (Type 4 = .panel-warning in HTML, shown/hidden by activity logic)
 */

// ── Toast singleton ─────────────────────────────────────────────────────────

let _toastEl = null;
let _toastTimer = null;

function _getToast() {
  if (!_toastEl) {
    _toastEl = document.createElement("div");
    _toastEl.className = "toast";
    document.body.appendChild(_toastEl);
  }
  return _toastEl;
}

/**
 * Show an operation result toast.
 * @param {string} message
 * @param {"success"|"error"} type
 */
export function showToast(message, type = "success") {
  const el = _getToast();
  el.textContent = message;
  el.className   = `toast toast--${type} visible`;

  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => {
    el.classList.remove("visible");
  }, 4000);
}

// ── System error (Type 1) ──────────────────────────────────────────────────

let _errorEl = null;

function _getErrorEl() {
  if (!_errorEl) {
    _errorEl = document.getElementById("topbar-error");
  }
  return _errorEl;
}

/** Show a persistent system error in the top bar. Never shows raw status codes. */
export function showSystemError(message) {
  const el = _getErrorEl();
  if (!el) return;
  const textNode = el.querySelector(".topbar-error-text");
  if (textNode) textNode.textContent = message;
  else el.prepend(Object.assign(document.createElement("span"), { className: "topbar-error-text", textContent: message }));
  el.classList.add("visible");
}

export function clearSystemError() {
  _getErrorEl()?.classList.remove("visible");
}

// ── Canvas drawing hint (Type 3) ──────────────────────────────────────────

/**
 * Show a hint overlay inside a canvas wrapper element.
 * @param {HTMLElement} canvasWrap - the element that contains the canvas
 * @param {string} message
 */
export function showCanvasHint(canvasWrap, message) {
  let hint = canvasWrap.querySelector(".canvas-hint");
  if (!hint) {
    hint = document.createElement("div");
    hint.className = "canvas-hint";
    canvasWrap.style.position = "relative";
    canvasWrap.appendChild(hint);
  }
  hint.textContent = message;
  hint.classList.add("visible");
}

export function hideCanvasHint(canvasWrap) {
  canvasWrap?.querySelector(".canvas-hint")?.classList.remove("visible");
}

// ── Swatch helper ─────────────────────────────────────────────────────────

export function updateSwatch(el, hex) {
  if (el) el.style.backgroundColor = hex;
}

// ── URL param helper ──────────────────────────────────────────────────────

export function getMapParam() {
  return new URLSearchParams(window.location.search).get("map") ?? "";
}

// ── Human-readable HTTP error helper ─────────────────────────────────────

const _HTTP_MESSAGES = {
  400: "Bad request",
  401: "Unauthorized",
  403: "Forbidden",
  404: "Not found",
  409: "Conflict",
  500: "Server error",
  503: "Service unavailable",
};

export function httpErrorMessage(status, fallback = "Request failed") {
  return _HTTP_MESSAGES[status] ?? fallback;
}

// ── Panel warning helpers ─────────────────────────────────────────────────

export function showPanelWarning(containerEl, message) {
  let w = containerEl.querySelector(".panel-warning");
  if (!w) {
    w = document.createElement("div");
    w.className = "panel-warning";
    w.innerHTML = `<span class="panel-warning-icon">⚠</span><span class="panel-warning-text"></span>`;
    containerEl.prepend(w);
  }
  w.querySelector(".panel-warning-text").textContent = message;
  w.hidden = false;
}

export function hidePanelWarning(containerEl) {
  const w = containerEl.querySelector(".panel-warning");
  if (w) w.hidden = true;
}
