/**
 * ui-helpers.js — Shared UI utilities.
 *
 * Notification system (2 canonical types):
 *   showSystemError(message)  — Type 1: persistent top-bar error
 *   clearSystemError()        — dismiss Type 1
 *   showToast(message, type)  — Type 2: 4s auto-dismiss bottom-right toast
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

