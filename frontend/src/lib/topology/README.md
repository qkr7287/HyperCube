# Topology — 3D container/hub scene

A self-contained OOP 3D layer used by the main page. Built on raw
`three.js` + `d3-force-3d`, owning its scene lifecycle from mount to
dispose. Svelte components consume it through `Topology.ts`.

## Layout

```
core/         three.js runtime (Scene, Camera, Renderer, RAF, dispose)
entities/     renderable objects — ContainerNode, Hub base
hubs/         StackHub, NetworkHub, VolumeHub
lines/        Connection base + per-type line variants
layout/       force layout wrapper + cluster / focus state machines
interaction/  raycaster, camera tween, keyboard
state/        topology store (hub toggles, selection) + events
Topology.ts   facade — Svelte imports this only
```

## Phase plan

- Phase 0: scaffolding (this commit) — structure + deps, no behavior.
- Phase 1: core + Stack hub replacement.
- Phase 2: click / focus / expand / pin / camera tween.
- Phase 3: Network / Volume hubs (needs Agent schema v2).
- Phase 4: sidebar → topology event wiring.
- Phase 5: GLB low-poly meshes, line polish.
