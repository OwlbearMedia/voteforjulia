"""A sliding-window request counter that outlives the process that wrote it.

Backs the long-window rate-limit tier. The burst tier in [app.py](app.py) counts
in process memory, which cannot hold an hour here because Passenger reaps idle
workers ([../docs/hosting.md](../docs/hosting.md#watch-worker-memory)).

Every failure fails open: a limiter that cannot reach its database logs and
allows the request.

See [ADR-0016](../docs/adr/0016-second-tier-rate-limiting-and-honeypot.md) for
why SQLite, and its implementation notes for the choices below.
"""

from __future__ import annotations

import logging
import sqlite3
from math import ceil
from pathlib import Path
from time import time

logger = logging.getLogger(__name__)

# Under `tmp/`, the one directory the deploy's prune step leaves alone. Resolved
# relative to this module so it follows the package into `api/` or `api_test/`.
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "tmp" / "rate-limit.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hits (
    key TEXT NOT NULL,
    ts  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_hits_key_ts ON hits (key, ts);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection and make sure the schema is there.

    A new connection per call: a `sqlite3.Connection` carried across a Passenger
    fork can corrupt the file, and opening is free next to an SMTP round trip.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.executescript(_SCHEMA)
    return connection


def consume(
    key: str,
    *,
    limit: int,
    window_seconds: int,
    db_path: Path | None = None,
    now: float | None = None,
) -> int | None:
    """Record a request against `key`, or report how long until one is allowed.

    Returns `None` when the request is within the limit, or a positive
    `Retry-After` in seconds when it is not.

    Wall clock, not `monotonic()`: every value is written by one worker and read
    by another, and a monotonic reading means nothing outside its own process.
    """
    path = db_path or DEFAULT_DB_PATH
    current = time() if now is None else now
    cutoff = current - window_seconds

    try:
        connection = _connect(path)
    except sqlite3.Error:
        logger.exception("Rate-limit store unavailable at %s; allowing request", path)
        return None

    try:
        with connection:
            # IMMEDIATE, so the count and the insert below cannot interleave with
            # another worker and quietly raise the effective limit.
            connection.execute("BEGIN IMMEDIATE")

            # Every key, not just this one -- this is the only thing bounding the
            # table, and there is no separate sweep.
            connection.execute("DELETE FROM hits WHERE ts <= ?", (cutoff,))

            row = connection.execute(
                "SELECT COUNT(*), MIN(ts) FROM hits WHERE key = ?", (key,)
            ).fetchone()
            count, oldest = (row[0], row[1]) if row else (0, None)

            if count >= limit and oldest is not None:
                # Round up: truncating advertises a retry still inside the window.
                return max(1, ceil(oldest + window_seconds - current))

            connection.execute("INSERT INTO hits (key, ts) VALUES (?, ?)", (key, current))
            return None
    except sqlite3.Error:
        # Includes the busy timeout expiring. Fail open -- the burst tier is still
        # in front of this, and refusing a real volunteer is the worse failure.
        logger.exception("Rate-limit store failed for key %r; allowing request", key)
        return None
    finally:
        connection.close()


def reset(db_path: Path | None = None) -> None:
    """Drop every recorded hit. For tests, and for clearing a limit by hand."""
    path = db_path or DEFAULT_DB_PATH
    try:
        connection = _connect(path)
    except sqlite3.Error:
        logger.exception("Rate-limit store unavailable at %s; nothing to reset", path)
        return

    try:
        with connection:
            connection.execute("DELETE FROM hits")
    except sqlite3.Error:
        logger.exception("Rate-limit store reset failed at %s", path)
    finally:
        connection.close()
