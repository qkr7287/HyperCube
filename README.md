# HyperCube

HyperCube is a central operations platform for monitoring multiple Docker hosts through lightweight agents.
It combines a Svelte dashboard, a Django API/WebSocket backend, Redis, PostgreSQL, and Celery-based background jobs.

## What This Project Is Trying To Become

The target product is not just a container viewer.
The long-term goal is:

- monitor multiple servers from one central dashboard
- separate admin, user, and diagnostic workflows
- handle container operations through `request -> approve -> agent execute`
- extend the platform with anomaly detection, forecasting, and LLM-assisted analysis

The target architecture is documented in [docs/to-be-architecture.md](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/docs/to-be-architecture.md:1).

## Current Snapshot

The repository already includes:

- a Svelte frontend for login, server selection, and live topology monitoring
- a Django backend with DRF, Channels, JWT auth, and Django admin
- domain apps for `agents`, `containers`, `metrics`, `users`, and shared utilities
- Redis and PostgreSQL service definitions for runtime state and persistence
- Celery worker/beat wiring for background cleanup and metrics persistence

The current implementation details are described in [docs/architecture.md](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/docs/architecture.md:1).

## Important Note

Do not push directly to `main`.
This repository has an automation that syncs `main` to another repository's `dev` branch for deployment-related flow.

Current sync workflow:

1. Work on `dev`
2. Open a pull request into `main`
3. After merge, GitHub Actions syncs `main` to `dev-agics/DCMTool:dev`

See [docs/cicd.md](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/docs/cicd.md:1) for deployment notes.

## Repository Layout

```text
frontend/   Svelte dashboard and WebSocket client
backend/    Django backend, API, auth, Channels, Celery apps
nginx/      Reverse proxy configuration
docs/       Architecture, development, API, and protocol docs
.github/    GitHub Actions workflows
```

## Tech Stack

| Area | Stack |
| --- | --- |
| Frontend | SvelteKit 2, Svelte 5, Three.js, 3d-force-graph |
| Backend | Django 5, DRF, Channels, SimpleJWT |
| Async | Celery, Redis |
| Database | PostgreSQL 16, pgvector |
| Infra | Docker Compose, nginx, GitHub Actions |

## Documents

- [docs/architecture.md](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/docs/architecture.md:1): current codebase structure and runtime layout
- [docs/to-be-architecture.md](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/docs/to-be-architecture.md:1): target product direction and phased architecture
- [docs/development.md](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/docs/development.md:1): local workflow, branching, and contribution notes
- [docs/api.md](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/docs/api.md:1): API overview for the current backend
- [docs/agent-protocol.md](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/docs/agent-protocol.md:1): agent-side protocol reference

## Known Gaps

This repository is in transition from an earlier single-app implementation to the current split architecture.
Because of that, some infra paths are not fully aligned yet.

Known examples:

- production compose references still need cleanup
- frontend deployment strategy needs to be reconciled with the current runtime entrypoint
- some older docs still reflect the previous architecture

The goal of this documentation refresh is to make the current state and the intended state easier to understand separately.
