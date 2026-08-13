"""Cross-worker counters that outlive the process that wrote them.

Two of them, both needing state no single Passenger worker can hold, because
Passenger reaps idle workers here
([../docs/hosting.md](../docs/hosting.md#watch-worker-memory)):

- `consume` — the long-window rate-limit tier. *How often* one client may ask.
  The burst tier in [app.py](app.py) counts in process memory, which cannot hold
  an hour. See [ADR-0016](../docs/adr/0016-second-tier-rate-limiting-and-honeypot.md).
- `acquire`/`release` — how many submissions may be in flight at once, across
  every worker. *How much* work may run at all. See
  [ADR-0018](../docs/adr/0018-cap-concurrent-submissions.md).

Every failure fails open: a limiter that cannot reach its database logs and
allows the request. That means `sqlite3.Error` *and* `OSError` — creating the
directory is a filesystem operation, and letting its failure escape would turn
the fail-open promise into a 500.
"""

from __future__ import annotations

import logging
import secrets
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

CREATE TABLE IF NOT EXISTS inflight (
    token      TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    scope      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_inflight_started_at ON inflight (started_at);
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

    # `inflight` shipped without `scope`, and this file outlives a deploy -- it
    # lives under `tmp/`, which the prune step leaves alone -- so
    # CREATE TABLE IF NOT EXISTS silently leaves an old table as it was and
    # every insert would fail against it. Cheap enough to check per connection.
    columns = {row[1] for row in connection.execute("PRAGMA table_info(inflight)")}
    if "scope" not in columns:
        connection.execute("ALTER TABLE inflight ADD COLUMN scope TEXT NOT NULL DEFAULT ''")

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
    except (sqlite3.Error, OSError):
        # OSError covers `mkdir` as much as sqlite: an inaccessible `tmp/`, or a
        # file sitting where the directory should be, raises NotADirectoryError
        # rather than anything sqlite3 defines.
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
    except (sqlite3.Error, OSError):
        # Includes the busy timeout expiring. Fail open -- the burst tier is still
        # in front of this, and refusing a real volunteer is the worse failure.
        logger.exception("Rate-limit store failed for key %r; allowing request", key)
        return None
    finally:
        connection.close()


def acquire(
    scope: str,
    *,
    limit: int,
    ttl_seconds: float,
    db_path: Path | None = None,
    now: float | None = None,
) -> str | None:
    """Take one of `scope`'s `limit` concurrent slots, or None if all are taken.

    Scopes are counted separately, so the deep health probe cannot consume the
    budget a supporter's submission needs, or the other way round.

    The caller must pass the returned token to `release`. Fails open: a store it
    cannot reach yields a token, so the request proceeds.

    The TTL is what makes this safe without a cleanup job. A worker killed
    mid-request never calls `release`, and Passenger reaps workers here — so
    slots are reclaimed by expiry rather than by anyone remembering to free
    them. Set it above the longest a request can take, or a slow request has its
    own slot handed to someone else while it is still using it.
    """
    path = db_path or DEFAULT_DB_PATH
    current = time() if now is None else now
    token = secrets.token_hex(16)

    try:
        connection = _connect(path)
    except (sqlite3.Error, OSError):
        logger.exception("Concurrency store unavailable at %s; allowing request", path)
        return token

    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            # Every scope, not just this one: the prune is the only thing
            # bounding the table.
            connection.execute(
                "DELETE FROM inflight WHERE started_at <= ?", (current - ttl_seconds,)
            )

            (count,) = connection.execute(
                "SELECT COUNT(*) FROM inflight WHERE scope = ?", (scope,)
            ).fetchone()
            if count >= limit:
                return None

            connection.execute(
                "INSERT INTO inflight (token, started_at, scope) VALUES (?, ?, ?)",
                (token, current, scope),
            )
            return token
    except (sqlite3.Error, OSError):
        logger.exception("Concurrency store failed at %s; allowing request", path)
        return token
    finally:
        connection.close()


def release(token: str, db_path: Path | None = None) -> None:
    """Give back a slot taken by `acquire`. Safe to call with an expired token."""
    path = db_path or DEFAULT_DB_PATH

    try:
        connection = _connect(path)
    except (sqlite3.Error, OSError):
        logger.exception("Concurrency store unavailable at %s; slot will expire instead", path)
        return

    try:
        with connection:
            connection.execute("DELETE FROM inflight WHERE token = ?", (token,))
    except (sqlite3.Error, OSError):
        # Not fatal, and not worth retrying: the TTL reclaims the slot.
        logger.exception("Could not release slot %r; it will expire instead", token)
    finally:
        connection.close()


def reset(db_path: Path | None = None) -> None:
    """Drop every recorded hit and in-flight slot. For tests, and for clearing by hand."""
    path = db_path or DEFAULT_DB_PATH
    try:
        connection = _connect(path)
    except (sqlite3.Error, OSError):
        logger.exception("Rate-limit store unavailable at %s; nothing to reset", path)
        return

    try:
        with connection:
            connection.execute("DELETE FROM hits")
            connection.execute("DELETE FROM inflight")
    except (sqlite3.Error, OSError):
        logger.exception("Rate-limit store reset failed at %s", path)
    finally:
        connection.close()
