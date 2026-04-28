"""Helpers shared between Celery flush and metrics viewsets.

Stack resolution mirrors the frontend `resolveGroup` priority chain
(`frontend/src/lib/utils/container-grouping.ts`) so dashboard groupings stay
consistent regardless of which side computed them.
"""

from __future__ import annotations

import re

UNMANAGED = "Unmanaged"

_NAME_NORMALIZE_PUNCT = re.compile(r"[-_]+")


def _normalize_name(raw: str) -> str:
    trimmed = (raw or "").strip()
    if not trimmed:
        return UNMANAGED
    trimmed = trimmed.removesuffix("_default") if trimmed.endswith("_default") else trimmed
    return _NAME_NORMALIZE_PUNCT.sub(" ", trimmed).strip() or UNMANAGED


def _folder_basename(working_dir: str) -> str:
    if not working_dir:
        return ""
    trimmed = working_dir.rstrip("/\\")
    parts = re.split(r"[/\\]", trimmed)
    return parts[-1] if parts else ""


def resolve_stack(labels: dict | None) -> str:
    """Compute the stack bucket for a container from its labels.

    Priority chain (must match `container-grouping.ts:resolveGroup`):
      1. `hypercube.stack`
      2. `com.docker.compose.project`
      3. `com.docker.compose.project.working_dir` (folder basename)
      4. `Unmanaged`
    """
    if not isinstance(labels, dict):
        return UNMANAGED

    hc = labels.get("hypercube.stack")
    if hc:
        return _normalize_name(str(hc))

    compose = labels.get("com.docker.compose.project")
    if compose:
        return _normalize_name(str(compose))

    working_dir = labels.get("com.docker.compose.project.working_dir")
    if working_dir:
        folder = _folder_basename(str(working_dir))
        if folder:
            return _normalize_name(folder)

    return UNMANAGED
