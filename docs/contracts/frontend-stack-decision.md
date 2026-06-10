# Frontend Stack Decision (D1)

Status: **decided 2026-06-10** (rockymine + Opus). The target stack for the **framework switch
(D1)**. This is a decision record, not a how-to — it fixes *what* we port to and *what stays*, so the
implementing session builds against a settled target. Plan item: `plans/refactor-plan.md` D1; the
"D1 de-risker" is B4 + B4a + C6 + C1.

## Decision summary

| Question | Decision | Why |
|---|---|---|
| Backend | **Keep Python; stay on Flask** (FastAPI optional, later) | The Python pipeline is the crown jewel; the switch is a *frontend* job |
| Frontend library | **React** | Components replace hand-rolled DOM; mainstream, hireable, well-supported |
| Language | **TypeScript** | Compile-time safety against the typed API contract (B1–B4) |
| Build tool / dev server | **Vite** | Modern default; fast HMR; outputs plain static files Flask can serve |
| **Not** Next.js | **Avoid** | Its value (SSR/SEO, a Node backend) is dead weight for a private editor |
| **Not** a full-stack JS rewrite | **Avoid** | Would discard the round-trip core — the hardest, most valuable code |
| Canvas | **Stay SVG**, inside React | The geometry math is the asset, not the rendering tech |
| Migration | **Incremental**, activity by activity, against the *same* API | Low-risk; old + new can run side by side |

## The current stack (what we're porting *from*)

```
BACKEND  Python / Flask                          FRONTEND  vanilla JS, no build
  pgm/ (round-trip core), layout/, symmetry/,      46 ES modules under studio/static/
  categorization, studio/services/*.py     HTTP    (canvas/, panels/, activities/, shared/)
  studio/routes/*.py  (thin Flask layer)  ◄────►   4 Jinja templates, SVG canvas, api.js
                                            JSON    root package.json = vitest only; no TS
```

The refactor's entire purpose is the **seam in the middle**: a clean, typed, stable JSON API
(the contract). Once solid, the frontend box is replaced **without touching the backend box**.

## The one principle that matters most

There are two opposite things "switch frameworks" can mean:

- ✅ **Replace the frontend only (SPA).** A new React app talks to the *existing* Flask API over
  JSON. Keeps all the Python. **This is the path.**
- ❌ **Full-stack JS rewrite** (e.g. all-in Next.js, backend rebuilt in Node). Throws away the
  round-trip core. **Do not.** The Python pipeline is the asset.

The word "Next.js" tempts people toward the second. The React features we want come from React +
Vite; Next.js adds SSR/SEO/routing/a Node server that a **private, authenticated editor tool** does
not need and would have to maintain for no benefit.

## The tools are *layers*, not competitors

```
[ Python backend: Flask (→ FastAPI optional) ]
              ▲  HTTP + JSON
              ▼
[ Frontend:  React  (UI library — the components)            ]
[            TypeScript  (types — safety vs the API contract) ]
[            built by Vite  (bundler + dev server)            ]
```

- **React** — the UI library you write the interface in. *(Alternatives: Svelte, Vue, Solid.)*
- **TypeScript** — JS + a type system; catches field mismatches at compile time.
- **Vite** — build tool + dev server; bundles TS/React into static files, gives hot reload.
- **Next.js** — a framework *on top of* React (routing + SSR + Node backend). Not for us.
- **FastAPI** — a Python backend (Flask alternative) that auto-generates an API schema → can
  *generate* the TS types. Optional upgrade whose one real payoff is typed-schema generation.

## What stays vs. what changes

**Stays (the majority of the value):**
- **All of `pgm/`, `layout/`, `symmetry/`, `studio/services/`** — framework-agnostic Python. On
  Flask, the routes stay too. (A future FastAPI move rewrites only the *thin* route layer, keeping
  every service.)
- **Pure-logic JS** — `static/shared/transform.js`, `converters.js`, the future `geometry.js`
  (B12), rasterisation, boolean island computation. Ports to TypeScript almost mechanically and is
  *reused* by the new canvas. (B12's "one implementation per converter" goal makes this clean.)
- **The CSS design system** — `tokens.css`, `components.css`, the `/design` system. React components
  use the **same class names**; carries over nearly as-is. (D1 already says "keep HTML/CSS patterns.")
- **The contracts/docs** — they *are* the spec the new frontend builds against.

**Changes (the view layer only):**
- The 4 Jinja templates + the *view* parts of the 46 JS modules → React components.
- Ad-hoc state juggling → React state / a small store.
- `api.js` → a typed API client (generated or hand-written against the TS types).

## The typed contract — TS types for the B1–B4 view-models

B1–B4 define the typed view-models (Region, Filter, ApplyRule, Wool, Symmetry, SketchShape, the
`/regions/tree` node). Express those exact shapes as **TypeScript types** so the frontend is
compile-time-guaranteed to match the API's JSON — it cannot read a missing field or misname
`min_x`/`cx`. Two ways:

- **(a) Hand-write** TS interfaces mirroring the contract — simple, but two copies that can drift.
- **(b) Generate** from one source of truth — pydantic/FastAPI → OpenAPI → `openapi-typescript`, or
  JSON Schema → types. **The "do it right once" option**: the Python contract emits the TS types.

This is why **B4 + B4a + C6 + C1** are the D1 de-risker: nail the typed shapes + consistent naming
(`{min_x,min_z,max_x,max_z}` / `{cx,cz}`) + the `{error:{code,message}}` envelope **once**, and the
port becomes mechanical — a cheaper model (Sonnet) can largely drive it.

## Migration strategy

1. Scaffold a Vite + React + TypeScript app in a new folder (e.g. `frontend/`); it builds to static
   assets Flask serves (or runs on Vite's dev server proxying to Flask in dev).
2. Define/generate the TS contract types from B1–B4.
3. Port **one activity at a time** (Overview → Teams → … → the canvas activities), each against the
   **existing** Flask API. Old (Jinja) and new (React) can coexist during the migration.
4. Build a shared TS canvas/geometry layer first (ports `transform.js`/`converters.js`/`geometry.js`),
   since both the editor and sketch canvases depend on it.
5. Retire the Jinja templates + old JS per activity as each is replaced.

## Local dev & run experience

Two different "users", two different answers:

- **End user (a mapmaker)** — per the hosting vision (E1) they **run nothing**: a hosted URL, or
  `/map-studio` on the build server returns an edit link. The switch makes this *easy to deliver*
  because a React app builds to plain static files any server can host (no Node runtime — that's a
  Next.js thing we avoid).
- **Developer** — the day-to-day workflow improves, with one caveat.

**Today:** one process — Flask serves both the API and the frontend, started by the bespoke per-OS
wrappers `tools/studio-dev.sh` / `studio-dev.ps1` (16-line scripts that pick the Python + port and do
start/stop/restart/status). No Mac script. The `/root/ctw-venv` path is hardcoded because the
VirtualBox shared folder can't host a venv.

**After the switch (development):** two processes — the **Flask API** (Python) and the **Vite dev
server** (Node, React + HMR, proxies API calls to Flask). This nets out *better*:

| | Today | After |
|---|---|---|
| Frontend start | bespoke `.sh` / `.ps1` | standard **`npm install` + `npm run dev`** |
| Cross-platform | Linux + Windows, **no Mac** | identical on **Mac / Windows / Linux** |
| One command | yes (one process) | yes — a root **`npm run dev`** can launch *both* via `concurrently` |
| Reload | manual restart/reload | automatic (Vite HMR) |

**After the switch (production / hosting):** `npm run build` → static bundle → Flask serves it →
back to **one process**; end users run nothing.

**Caveat the switch does *not* fix:** the `/root/ctw-venv` path quirk is a **VirtualBox-shared-folder**
problem, not a framework one — and **`node_modules` hits the same wall** (it's already why the JS
test runner lives outside the shared folder at `/root/pgm-studio-tests`). The clean fix is
independent of the stack: **stop developing through the shared folder** (clone into the VM's native
filesystem, or use WSL2, or develop on the host). The framework switch is a good moment to do this —
then plain `npm run dev` / `python -m ...` work with no path-hacking wrapper at all.

**Net:** `npm` becomes the familiar, cross-platform front door (Python still runs underneath as the
API; a one-liner orchestrates both halves) — a real DX improvement *if* dev also moves off the shared
folder; the switch alone won't erase the venv/`node_modules` path quirk.

## To decide at kickoff (not now)

- **State/data layer:** plain React state + context vs. a small store (Zustand) vs. a server-cache
  library (TanStack Query) for the API calls. *(Lean: TanStack Query for API + light local state.)*
- **TS types: generate vs. hand-write** — tied to whether C-series adds a pydantic/OpenAPI schema
  layer or a FastAPI move happens first.
- **Component styling:** keep the global CSS classes (recommended — preserves the design system) vs.
  CSS modules / a component lib (avoid; would fork the design system).
- **Routing:** a light client router (the app has a handful of activities) — no SSR needed.

## Cross-references

- `plans/refactor-plan.md` — D1 (the switch), B1–B4 (typed models), B4a (tree-as-view), C1 (error
  envelope), C6 (naming unify), B12 (geometry-module/converter consolidation feeding the shared TS layer).
- `docs/contracts/studio-domain-and-api-contract.md` — the API surface the frontend consumes.
- `docs/cross-cutting.md` — canvas base, `transform.js` interface, required converters (the shared
  geometry layer to port to TS).
- `docs/ui-conventions.md` + `/design` — the CSS/design system that carries over.
