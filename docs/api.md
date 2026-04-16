# API Overview

This document is a high-level guide to the backend API shape that exists in the current Django stack.
For exact request and response details, the generated schema and serializers are the source of truth.

## Entry Points

Core paths defined in [backend/config/urls.py](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/backend/config/urls.py:1):

- `/api/health/`
- `/api/schema/`
- `/api/docs/`
- `/api/auth/token/`
- `/api/auth/token/refresh/`
- `/api/auth/logout/`

App routes are mounted under `/api/` from:

- `apps.agents.urls`
- `apps.containers.urls`
- `apps.users.urls`
- `apps.metrics.urls`

## Authentication

The current backend uses JWT authentication through SimpleJWT.

Typical flow:

1. `POST /api/auth/token/`
2. receive access and refresh tokens
3. send `Authorization: Bearer <access-token>`
4. refresh through `/api/auth/token/refresh/` when needed

## Agents

Primary responsibilities:

- register and identify agents
- list active or historical agents
- expose current status
- expose latest cached metrics

Representative endpoints:

- `GET /api/agents/`
- `POST /api/agents/`
- `GET /api/agents/{id}/status/`
- `GET /api/agents/{id}/latest-metrics/`

Implementation reference:

- [backend/apps/agents/viewsets.py](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/backend/apps/agents/viewsets.py:1)

## Containers

Primary responsibilities:

- inspect containers recorded by the backend
- manage templates
- submit create/delete requests
- approve or reject requests as admin

Representative endpoint groups:

- `/api/containers/`
- `/api/templates/`
- `/api/requests/`

Implementation reference:

- [backend/apps/containers/viewsets.py](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/backend/apps/containers/viewsets.py:1)

## Users

The backend uses a custom user model and role-based permission checks.

Implementation reference:

- [backend/apps/users/models.py](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/backend/apps/users/models.py:1)
- [backend/apps/common/permissions.py](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/backend/apps/common/permissions.py:1)

## Metrics

Metrics data is split between:

- live state and cache paths
- persisted history tables
- periodic Celery maintenance and cleanup

Implementation reference:

- [backend/apps/metrics/viewsets.py](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/backend/apps/metrics/viewsets.py:1)
- [backend/apps/metrics/tasks.py](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/backend/apps/metrics/tasks.py:1)

## WebSocket Layer

The monitoring path is not REST-only.
Live updates depend on Django Channels and the frontend WebSocket store.

Relevant references:

- [backend/config/routing.py](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/backend/config/routing.py:1)
- [backend/apps/common/consumers.py](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/backend/apps/common/consumers.py:1)
- [frontend/src/lib/stores/ws-store.ts](/C:/Users/agics/Desktop/workspace/01.%20git/HyperCube/frontend/src/lib/stores/ws-store.ts:1)

## Recommendation

For day-to-day backend work, use the generated schema UI at `/api/docs/` as the quickest inspection surface.
This file is meant to explain the API shape, not duplicate every serializer field manually.
