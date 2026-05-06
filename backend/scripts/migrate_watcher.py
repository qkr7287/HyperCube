"""Auto-migrate watcher for the dev container.

Watches `apps/**/migrations/*.py` for changes and runs `manage.py migrate
--noinput` once per *batch* of file events, never concurrently. This avoids
the failure mode where saving multiple files in quick succession (or rsync /
git pull touching N files) causes watchfiles to SIGINT a half-finished
`migrate` and leave the schema mid-flight.

Single-instance guarantee: an `asyncio.Lock` serialises migrate runs. While a
run is in progress, further file events accumulate and the next run starts as
soon as the current one finishes — there is at most one queued run at a time
to coalesce bursts.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from watchfiles import PythonFilter, awatch

# Settle window before kicking off a migrate. Long enough that a batch of
# saves / rsync writes registers as one event, short enough that interactive
# `makemigrations` doesn't feel laggy.
DEBOUNCE_SECONDS = 1.0

# Where Django apps live, relative to /app (the bind-mounted backend root).
WATCH_ROOT = Path("/app/apps")

logger = logging.getLogger("migrate-watcher")


async def run_migrate() -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "manage.py",
        "migrate",
        "--noinput",
        cwd="/app",
    )
    rc = await proc.wait()
    if rc != 0:
        logger.warning("migrate exited with code %s", rc)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    logger.info("watching %s for migration changes", WATCH_ROOT)

    # Initial pass: catch up on anything that was applied while the watcher
    # was down.
    async with _Coalescer() as coalescer:
        await coalescer.kick("startup")
        async for changes in awatch(
            WATCH_ROOT,
            watch_filter=PythonFilter(),
            debounce=int(DEBOUNCE_SECONDS * 1000),
        ):
            await coalescer.kick(f"{len(changes)} file change(s)")


class _Coalescer:
    """At most one migrate runs at a time; further kicks queue at most once."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pending = False

    async def __aenter__(self) -> "_Coalescer":
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def kick(self, reason: str) -> None:
        if self._lock.locked():
            # A migrate is already running. Mark that we want another pass
            # afterwards; multiple kicks during a run collapse into one.
            self._pending = True
            logger.info("migrate already running; queued (%s)", reason)
            return
        async with self._lock:
            logger.info("running migrate (%s)", reason)
            try:
                await run_migrate()
                while self._pending:
                    self._pending = False
                    logger.info("running queued migrate")
                    await run_migrate()
            except Exception:
                logger.exception("migrate failed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
