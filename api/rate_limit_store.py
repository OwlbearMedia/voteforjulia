"""Cross-worker counters that outlive the process that wrote them.

Two of them, both needing state no single Passenger worker can hold, because
Passenger reaps idle workers here
([../docs/hosting.md](../docs/hosting.md#watch-worker-memory)):

- `consume` — every rate-limit tier. *How often* one client may ask. Both the
  burst and the sustained window count the same rows in one transaction, so a
  request is recorded once and neither window can be spent by a request the
  other refused. See [ADR-0024](../docs/adr/0024-count-every-rate-limit-tier-in-sqlite.md).
- `acquire`/`release` — how many submissions may be in flight at once, across
  every worker. *How much* work may run at all. See
  [ADR-0018](../docs/adr/0018-cap-concurrent-submissions.md).

Every failure fails open: a limiter that cannot reach its database logs and
allows the request. That means `sqlite3.Error` *and* `OSError` — creating the
directory is a filesystem operation, and letting its failure escape would turn
the fail-open promise into a 500.

`consume` says so out loud rather than by returning nothing. Its caller has a
fallback to run when this store is unreachable, and "allowed" and "nobody
counted" have to be told apart for that to be possible at all.
"""

from __future__ import annotations

import logging
import secrets
import sqlite3
from collections.abc import Sequence
from math import ceil
from pathlib import Path
from time import time
from typing import NamedTuple

logger = logging.getLogger(__name__)


class Tier(NamedTuple):
    """One window a caller is held to, and the name a 429 reports it under."""

    name: str
    limit: int
    window_seconds: int


class Refusal(NamedTuple):
    """The tier that refused a request, and how long until one is allowed.

    `expires_in` is exact, and `retry_after` is the whole-second view of it for
    the header. Both are needed: rounding up is what makes the header safe to
    obey literally (ADR-0014), and rounding up is exactly what an in-process
    cache of this refusal must not do, because it would hold the refusal past
    the moment the window clears. See ADR-0024.
    """

    tier: str
    expires_in: float

    @property
    def retry_after(self) -> int:
        """Whole seconds, rounded up and never below one. The `Retry-After` value."""
        return max(1, ceil(self.expires_in))


class Verdict(NamedTuple):
    """What the store decided, and whether it was able to decide anything.

    `answered` is false only when the database could not be reached, and it is
    the whole reason this type exists: an unreachable store allows the request
    like an unfilled window does, and the caller has to tell those apart to know
    whether its own fallback should be counting. See ADR-0024.
    """

    refusal: Refusal | None
    answered: bool


# The two verdicts with nothing to say beyond themselves. Named so a caller
# reads `== ALLOWED` rather than unpacking a tuple of two falsy-looking values.
ALLOWED = Verdict(None, True)
UNAVAILABLE = Verdict(None, False)


# How long to stop asking a database that just failed. `_connect` carries a
# five-second busy timeout, so without this every request during an incident
# waits out that timeout before its caller can fall back -- including the
# requests the fallback is about to refuse, which is precisely a flood. Workers
# then pile up on the path that exists to keep them cheap, which is the cost
# ADR-0018 was written about. See ADR-0024 for this.
#
# Kept here rather than in app.py so every entry point below is covered by
# construction: `acquire` and `release` carry the same timeout on the same file
# and would otherwise each keep paying it.
STORE_BACKOFF_SECONDS = 10.0

# Wall clock, like every other timestamp in here, so an injected `now` drives
# it. One probe per worker per window re-opens the path: there is no success
# signal to wait for, the next call after the window simply tries again.
_backoff_until = 0.0


# The mark on a token from a call that never recorded a slot -- the store was
# unreachable, or was being left alone after a failure. `release` drops these
# without a round trip, because there is nothing on disk to delete.
#
# Telling them apart is what lets a *real* slot still be released during a
# backoff. Skipping every release leaked the cap: a slot taken before the
# failure and finished during the window survived until the TTL, so `acquire`
# counted it for another 270 seconds after the database came back. On
# `/health/deep`, whose whole budget is two slots, that is the probe refusing
# itself long after the incident. See ADR-0024.
_UNRECORDED_PREFIX = "unrecorded-"


def _clock(now: float | None) -> float:
    """The current time, unless the caller pinned one. Keeps the test seam."""
    return time() if now is None else now


def _in_backoff(now: float) -> bool:
    return now < _backoff_until


def _note_unreachable(now: float) -> None:
    global _backoff_until
    _backoff_until = now + STORE_BACKOFF_SECONDS


def clear_backoff() -> None:
    """Forget that the database ever failed. For tests, and for clearing by hand."""
    global _backoff_until
    _backoff_until = 0.0


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

    # Anything below can raise, and an unclosed connection holds a file
    # descriptor and its lock for as long as the worker lives.
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.executescript(_SCHEMA)
        _add_scope_column_if_missing(connection)
    except BaseException:
        connection.close()
        raise

    return connection


def _add_scope_column_if_missing(connection: sqlite3.Connection) -> None:
    """Bring a pre-`scope` `inflight` table up to date.

    `inflight` shipped without this column, and the file outlives a deploy -- it
    is under `tmp/`, which the prune step leaves alone -- so
    CREATE TABLE IF NOT EXISTS finds the old table, leaves it as it was, and
    every insert then fails against it.

    The duplicate-column error is caught rather than prevented: two workers can
    read `table_info` before either has altered the table, and on the first
    request after a deploy that is a live race. Losing it is success, so
    treating it as failure would fail the request open for no reason.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(inflight)")}
    if "scope" in columns:
        return

    try:
        connection.execute("ALTER TABLE inflight ADD COLUMN scope TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise
        logger.debug("Another worker added inflight.scope first")


def consume(
    key: str,
    *,
    tiers: Sequence[Tier],
    db_path: Path | None = None,
    now: float | None = None,
) -> Verdict:
    """Record a request against `key`, or report the tier still holding it out.

    Returns `ALLOWED` when the request is within every tier, `UNAVAILABLE` when
    the database could not be reached, or a `Verdict` carrying a `Refusal` whose
    wait clears every full tier -- the latest of them, since a caller is allowed
    again only when the last window does. The tier named is the one holding that
    deadline.

    One transaction for all of them, and one row per allowed request, which is
    what makes the tiers agree with each other: a request refused by any tier is
    never recorded, so it cannot spend another tier's allowance. See ADR-0024.

    Wall clock, not `monotonic()`: every value is written by one worker and read
    by another, and a monotonic reading means nothing outside its own process.
    """
    if not tiers:
        # No windows configured is no limit, not a crash. `max()` below is the
        # only expression in here that can raise outside a handler, and this
        # module's whole contract is that it never does.
        return ALLOWED

    path = db_path or DEFAULT_DB_PATH
    current = _clock(now)

    if _in_backoff(current):
        # Answer from the last failure rather than waiting for this one. The
        # caller's fallback is already the right answer and costs nothing.
        return UNAVAILABLE

    # The widest window, because the narrower tiers count the same rows. Pruning
    # at anything shorter would delete the history the hour-long tier is for.
    prune_cutoff = current - max(tier.window_seconds for tier in tiers)

    try:
        connection = _connect(path)
    except (sqlite3.Error, OSError):
        # OSError covers `mkdir` as much as sqlite: an inaccessible `tmp/`, or a
        # file sitting where the directory should be, raises NotADirectoryError
        # rather than anything sqlite3 defines.
        logger.exception("Rate-limit store unavailable at %s; allowing request", path)
        # Re-read the clock rather than reusing `current`. The failure that
        # matters most here is the busy timeout, which takes five seconds to
        # arrive -- charging those to the backoff would halve a window that
        # exists precisely because that failure is slow.
        _note_unreachable(_clock(now))
        return UNAVAILABLE

    try:
        with connection:
            # IMMEDIATE, so the counts and the insert below cannot interleave
            # with another worker and quietly raise the effective limit.
            connection.execute("BEGIN IMMEDIATE")

            # Every key, not just this one -- this is the only thing bounding the
            # table, and there is no separate sweep.
            connection.execute("DELETE FROM hits WHERE ts <= ?", (prune_cutoff,))

            # Every tier, not the first one that is full. A caller is allowed
            # again only once the *last* full window clears, so stopping early
            # advertises a wait that another tier is still holding -- and a
            # client obeying `Retry-After` exactly earns a second 429, which is
            # the one thing this header must never do (ADR-0014).
            refusal = None

            for tier in tiers:
                # The newest `limit` rows, never all of them. A window can hold
                # more than its limit -- an old worker inserting under a wider
                # window during a mixed-version restart, or a limit lowered in
                # config -- and then the oldest row is not the one whose expiry
                # frees the caller. Counting only these makes `MIN` the row that
                # actually does: the (count - limit + 1)-th oldest. With the
                # window merely full the two are the same row.
                row = connection.execute(
                    "SELECT COUNT(*), MIN(ts) FROM ("
                    "  SELECT ts FROM hits WHERE key = ? AND ts > ? ORDER BY ts DESC LIMIT ?"
                    ")",
                    (key, current - tier.window_seconds, tier.limit),
                ).fetchone()
                count, frees_the_window = (row[0], row[1]) if row else (0, None)

                if count >= tier.limit and frees_the_window is not None:
                    # Exact here; `Refusal.retry_after` rounds it up for the
                    # header. Strictly positive, because a row counted above is
                    # by definition still inside the window.
                    expires_in = frees_the_window + tier.window_seconds - current

                    # The binding tier is the one reported, not the first one
                    # asked. It is the window the caller is actually waiting
                    # out, so it is the name that agrees with the wait they were
                    # given -- and for triage it is the one that matters, since
                    # `hourly` means a patient caller and `burst` a hasty one.
                    # Ties keep the earlier tier, so the order still decides
                    # when the windows do not.
                    if refusal is None or expires_in > refusal.expires_in:
                        refusal = Refusal(tier.name, expires_in)

            if refusal is not None:
                return Verdict(refusal, True)

            connection.execute("INSERT INTO hits (key, ts) VALUES (?, ?)", (key, current))
            return ALLOWED
    except (sqlite3.Error, OSError):
        # Includes the busy timeout expiring. Fail open -- refusing a real
        # volunteer is the worse failure. Saying so rather than returning
        # ALLOWED is what lets app.py fall back to a per-worker count instead of
        # serving an unlimited endpoint for the length of a disk incident.
        logger.exception("Rate-limit store failed for key %r; allowing request", key)
        _note_unreachable(_clock(now))
        return UNAVAILABLE
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
    cannot reach yields a token anyway, so the request proceeds -- marked, so
    that releasing it costs nothing, because no slot was ever recorded.

    The TTL is what makes this safe without a cleanup job. A worker killed
    mid-request never calls `release`, and Passenger reaps workers here — so
    slots are reclaimed by expiry rather than by anyone remembering to free
    them. Set it above the longest a request can take, or a slow request has its
    own slot handed to someone else while it is still using it.
    """
    path = db_path or DEFAULT_DB_PATH
    current = _clock(now)
    token = secrets.token_hex(16)

    if _in_backoff(current):
        # Fail open immediately, which is what an unreachable store does anyway
        # -- the difference is not spending the busy timeout to find out.
        return _UNRECORDED_PREFIX + token

    try:
        connection = _connect(path)
    except (sqlite3.Error, OSError):
        logger.exception("Concurrency store unavailable at %s; allowing request", path)
        _note_unreachable(_clock(now))
        return _UNRECORDED_PREFIX + token

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
        _note_unreachable(_clock(now))
        return _UNRECORDED_PREFIX + token
    finally:
        connection.close()


def release(token: str, db_path: Path | None = None, now: float | None = None) -> None:
    """Give back a slot taken by `acquire`. Safe to call with an expired token.

    Unlike its siblings this is attempted even while the store is backed off,
    and deliberately. A token that holds a real slot is worth the wait: skipping
    it leaves a row that `acquire` counts against the cap until the TTL expires,
    turning a ten-second incident into minutes of refusals afterwards. The
    The common case during an incident costs nothing anyway, because `acquire`
    will have handed back an unrecorded token, which the check below drops.

    The wait is bounded by how many slots exist -- a dozen submissions and two
    probes -- and paid once each, at the end of a request whose work is already
    done.
    """
    path = db_path or DEFAULT_DB_PATH

    if token.startswith(_UNRECORDED_PREFIX):
        return

    try:
        connection = _connect(path)
    except (sqlite3.Error, OSError):
        logger.exception("Concurrency store unavailable at %s; slot will expire instead", path)
        _note_unreachable(_clock(now))
        return

    try:
        with connection:
            connection.execute("DELETE FROM inflight WHERE token = ?", (token,))
    except (sqlite3.Error, OSError):
        # Not fatal, and not worth retrying: the TTL reclaims the slot.
        logger.exception("Could not release slot %r; it will expire instead", token)
        _note_unreachable(_clock(now))
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
