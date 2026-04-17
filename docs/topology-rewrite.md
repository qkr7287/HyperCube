# Topology Rewrite — Context Brief

> Reviewer context for cross-session work (Codex / Agent double-checks).
> This file ships with the work; delete once the rewrite lands.

## Why

The 3D topology in `frontend/src/routes/+page.svelte` grew by patching
onto a `3d-force-graph` instance across many sessions. Server-switch
residue, camera flicker on delta sync, mixed concerns in
`refreshGraphData()` — all fixable, but each fix made the layer
harder to reason about. Owner decided to **rebuild it from scratch**
as an OOP layer that the existing Svelte page embeds.

## Hard requirements (owner's wording, numbered)

1. Must render containers, grouped the same way the right sidebar
   groups them (stack / compose project).
2. Container add / delete must stream in real time (already via WS
   delta sync — new layer must respect it).
3. Containers sharing a Docker **network** connect to a network hub
   with a line.
4. Containers sharing a **mounted volume folder** connect to a volume
   hub with a line.
5. Each hub type (stack / network / volume) has an independent
   on/off toggle. All three off ⇒ containers alone floating.
6. Initial load: containers + every visible hub clustered together
   (one tight cloud).
7. Clicking an entity camera-tweens (smooth curve) to fit it. For
   hubs, the fit bound must include all connected members.
8. On zoom-in (click), related entities stay/gather, unrelated ones
   are pushed outward (visual emphasis on the focused cluster).
9. Zoom-out returns to the initial clustered state.
10. When already zoomed-in, clicking a different hub: the already-
    scattered nodes stay where they are; only still-clustered nodes
    reorganize (scatter the ones not related to the new focus).
11. Mouse-wheel zoom triggers no focus/expand behaviour — it only
    dollies the camera via OrbitControls.
12. Line styles must be distinguishable across types.
13. Code must be organized by feature folders, OOP, easy to extend.
14. Visual polish: "flashy but clean".
15. Right-sidebar interactions drive the 3D:
    - container click → focus that ContainerNode;
    - group card click → focus the stack hub (same as hub click);
    - LIST tab → detail button → focus that ContainerNode.

## Decisions (already agreed with owner)

| # | Decision | Rationale |
|---|---|---|
| Q1 | **A** — extend the existing `containers` WS message with optional `networks` and `mounts` fields. See `docs/agent-schema-v2.md`. | Backward-compatible; no new endpoint; hubs degrade gracefully when Agent is still v1. |
| Q2 | **B** — drop `3d-force-graph`; go raw `three.js` + `d3-force-3d`. | Feature-folder OOP, GLB swap later, finer control. |
| Q3 | Interpretation of req 10 is the **pin-on-scatter** model: once a node is pushed outward, freeze it; next focus only moves still-clustered nodes. | Matches owner description exactly. |
| Q4 | Zoom-out triggers: **ESC key + Reset button.** No blank-space click. | Avoids accidental dezoom during orbit. |
| Q5/6 | **Simple show/hide toggles.** Defaults: stack=ON, network=OFF, volume=OFF. | Server-16 data shows stack/network hubs 95% overlap, so networks hidden by default avoids clutter. Named volumes only (bind mounts redundant with stack). |
| Q7 | three.js primitives for now, swap in low-poly GLB later via a shared mesh factory. Network hub will not be a cube (overlaps container look). | Mesh decoupled from entity. |
| Q8 | Folder structure approved as scaffolded. | See `frontend/src/lib/topology/README.md`. |

## Phases

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffolding: folders, stubs, deps (`d3-force-3d`, `@tweenjs/tween.js`), schema-v2 doc. **No runtime impact.** | **Done — `fa3cf22`** |
| 1 | `SceneManager` + `RenderLoop` + `Disposer` + `Entity` + `ContainerNode` + `StackHub` + `StackLine` + `ForceLayout` + `ClusterState` + `Topology` facade. Replaces current 3D block inside `+page.svelte` via a new Svelte component. Stack hub only. | Next |
| 2 | Raycaster / CameraAnimator / InputController / FocusState / NodePinner. Click-focus, scatter, pin, ESC reset, Reset button. | - |
| 3 | NetworkHub / VolumeHub / NetworkLine / VolumeLine + hub toggle UI. Depends on Agent schema v2 being shipped. | - |
| 4 | Right-sidebar → `topologyEvents` wiring (container / group / LIST detail). | - |
| 5 | GLB low-poly meshes, line-style polish, perf pass. | - |

## Phase 0 — what landed

- `frontend/src/lib/topology/` with 23 stub files, each carrying a
  one-line comment naming its phase.
- `frontend/package.json`: `d3-force-3d ^3.0.5`, `@tweenjs/tween.js ^25.0.0`.
- `docs/agent-schema-v2.md`: Agent-side change, optional fields,
  forward-compatible.
- `docs/topology-rewrite.md` (this file).
- Legacy 3D in `+page.svelte` untouched. App runs identically.

## What Codex is asked to verify on Phase 0

1. Folder split (core / entities / hubs / lines / layout / interaction
   / state) — does anything force a cross-folder coupling that the
   structure cannot carry (e.g. texture/material sharing, theme
   constants)?
2. `docs/agent-schema-v2.md` — is the `networks` / `mounts` shape
   friendly for the Agent to emit (any `docker inspect` gotcha we
   are ignoring)?
3. Stub files — anything obviously missing for Phases 1 and 2?
4. Dependency choice — any reason to prefer `three-forcegraph` or a
   different force library over `d3-force-3d`?
5. Hub toggle defaults (stack=ON, network=OFF, volume=OFF) — does
   this match the "show/hide" model, or is it worth keeping the
   "meaningful-only vs all" fallback for completeness?

## How Codex should report back

- Inline comments / diff suggestions are fine.
- If a Phase 1 contract needs to change (e.g. different facade
  signature), flag it **before** Phase 1 starts — interface changes
  after Phase 1 will cost more.
- If nothing to change, a one-line "Phase 0 OK, proceed" is enough.
