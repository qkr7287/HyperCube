# Development Guide

This document describes the practical development workflow for the current repository.

## Prerequisites

- Node.js 20+
- npm
- Python 3.12+ if you want to run backend code outside containers
- Docker Desktop or Docker Engine for local service dependencies

## Repository Structure

```text
frontend/   Svelte dashboard
backend/    Django backend and domain apps
docs/       project documentation
nginx/      reverse proxy configuration
```

## Frontend Workflow

From `frontend/`:

```bash
npm install
npm run dev
```

Useful scripts:

- `npm run dev`
- `npm run build`
- `npm run check`

Notes:

- the dashboard is client-heavy and uses WebSocket stores for live state
- the current frontend build/deployment path is under active cleanup, so treat production frontend docs conservatively

## Backend Workflow

The backend uses Django with PostgreSQL and Redis.
The root compose file currently defines the service dependencies used by the backend stack.

Typical local tasks:

```bash
docker compose up -d postgres redis
```

Then run backend commands in your preferred Python environment from `backend/`.

Example tasks:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

If you use Celery locally, the backend expects Redis-backed broker/result settings.

## Branching

Recommended branch flow:

1. work on `dev`
2. open a pull request into `main`
3. merge only reviewed/stable changes into `main`

Do not push directly to `main` unless you explicitly intend to trigger downstream sync automation.

## Commits

This repository follows Conventional Commits.

Examples:

- `feat(ui): add agent status badge`
- `fix(api): guard request approval transition`
- `docs(readme): rewrite architecture overview`

## Documentation Rule Of Thumb

When updating docs, keep these distinctions explicit:

- `architecture.md`: current implementation
- `to-be-architecture.md`: target state
- `README.md`: high-level overview and entry links

Mixing current state and future state in one document is what made the documentation harder to trust before.

## Current Known Friction

Be aware of these active cleanup areas:

- frontend adapter/runtime mismatch
- incomplete production backend compose path
- some older comments and docs were previously affected by encoding issues

When writing new docs, prefer short, accurate, current statements over optimistic claims.
