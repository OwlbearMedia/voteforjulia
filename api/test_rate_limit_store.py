"""The SQLite-backed long-window limiter (ADR-0016).

`test_app.py` covers what the endpoints do with a 429; this covers the store
underneath — counting, the two properties it exists for (surviving a process,
failing open), and the `Retry-After` arithmetic.

Every test takes `db_path` explicitly rather than leaning on `conftest.py`'s
autouse fixture, since these call `consume` directly.
"""

from __future__ import annotations

import multiprocessing
import sqlite3
import subprocess
import sys
from pathlib import Path
from time import time

import pytest

import api.rate_limit_store as rate_limit_store
from api.rate_limit_store import (
    _add_scope_column_if_missing,
    acquire,
    consume,
    release,
    reset,
)

# The scope name is arbitrary here; what these tests exercise is the counting.
SCOPE = "submission"


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "rate-limit.sqlite3"


def test_requests_under_the_limit_are_allowed(db_path):
    results = [consume("k", limit=3, window_seconds=60, db_path=db_path) for _ in range(3)]

    assert results == [None, None, None]


def test_the_request_past_the_limit_is_refused(db_path):
    for _ in range(3):
        consume("k", limit=3, window_seconds=60, db_path=db_path)

    assert consume("k", limit=3, window_seconds=60, db_path=db_path) == 60


def test_keys_are_counted_separately(db_path):
    """The other half of "these collide" — see conventions.md.

    Four requests on one key tripping the limit would pass even if `key` were
    ignored and every request shared a counter. This is the case that catches it.
    """
    for _ in range(3):
        assert (
            consume("send-email:198.51.100.1", limit=3, window_seconds=60, db_path=db_path) is None
        )

    assert (
        consume("send-email:198.51.100.1", limit=3, window_seconds=60, db_path=db_path) is not None
    )
    assert consume("send-email:198.51.100.2", limit=3, window_seconds=60, db_path=db_path) is None
    assert consume("yard-sign:198.51.100.1", limit=3, window_seconds=60, db_path=db_path) is None


def test_requests_older_than_the_window_stop_counting(db_path):
    # `now` is injectable precisely so this does not need a sleep. Three
    # requests an hour ago, against a 60-second window, must not constrain a
    # request happening now.
    for offset in (0, 1, 2):
        consume("k", limit=3, window_seconds=60, db_path=db_path, now=1000.0 + offset)

    assert consume("k", limit=3, window_seconds=60, db_path=db_path, now=4600.0) is None


def test_retry_after_covers_the_rest_of_the_window(db_path):
    """Rounded up, and measured from the oldest request still in the window.

    The bug ADR-0014 fixed in the in-memory tier: truncating advertises a retry
    still inside the window, so honouring the header exactly earns a second 429.
    """
    consume("k", limit=1, window_seconds=60, db_path=db_path, now=1000.0)

    retry_after = consume("k", limit=1, window_seconds=60, db_path=db_path, now=1030.4)

    assert retry_after == 30
    # And honouring it exactly is enough: at now + retry_after the window is
    # clear. This is the assertion that would fail if the value were rounded
    # down, and it is the property the header actually promises.
    assert (
        consume("k", limit=1, window_seconds=60, db_path=db_path, now=1030.4 + retry_after) is None
    )


def test_counts_survive_a_separate_process(db_path, tmp_path):
    """The property the whole module exists for (ADR-0016).

    Spends a real interpreter rather than asserting durability indirectly: two
    requests here, two more in a subprocess sharing nothing but the file, and
    the limit of three enforced across the boundary. Make the store in-memory
    and this is the test that fails.
    """
    repo_root = Path(__file__).resolve().parent.parent

    for _ in range(2):
        assert consume("k", limit=3, window_seconds=3600, db_path=db_path) is None

    program = (
        "from api.rate_limit_store import consume\n"
        f"path = {str(db_path)!r}\n"
        "import pathlib\n"
        "p = pathlib.Path(path)\n"
        "third = consume('k', limit=3, window_seconds=3600, db_path=p)\n"
        "fourth = consume('k', limit=3, window_seconds=3600, db_path=p)\n"
        "print(third, fourth)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    third, fourth = completed.stdout.split()
    assert third == "None", "the third request was within the limit and should have been allowed"
    assert fourth != "None", (
        "the fourth request exceeded a limit of three, but the fresh process "
        "counted from zero -- the store is not durable"
    )


def test_an_unusable_database_fails_open(tmp_path, caplog):
    """A limiter that cannot count must not be the reason a form 500s.

    A directory where the file should be makes every sqlite3 call raise, standing
    in for a read-only filesystem, a full disk, or a corrupt file.
    """
    occupied = tmp_path / "rate-limit.sqlite3"
    occupied.mkdir()

    assert consume("k", limit=1, window_seconds=60, db_path=occupied) is None
    # Repeated calls keep failing open rather than raising on the second one.
    assert consume("k", limit=1, window_seconds=60, db_path=occupied) is None
    assert "Rate-limit store" in caplog.text


def test_a_corrupt_database_fails_open(db_path, caplog):
    db_path.write_bytes(b"this is not a SQLite file, but it is the right length to look like one")

    assert consume("k", limit=1, window_seconds=60, db_path=db_path) is None
    assert "Rate-limit store" in caplog.text


def test_the_table_does_not_grow_without_bound(db_path):
    """Expired rows are pruned, so the file cannot grow forever.

    This runs for months on a host nobody logs into, so not accumulating is part
    of working. Every hit below is outside the window by the time the last lands.
    """
    for index in range(50):
        consume(f"key-{index}", limit=1, window_seconds=10, db_path=db_path, now=1000.0 + index)

    consume("final", limit=1, window_seconds=10, db_path=db_path, now=5000.0)

    with sqlite3.connect(db_path) as connection:
        remaining = connection.execute("SELECT COUNT(*) FROM hits").fetchone()[0]

    assert remaining == 1, "only the most recent hit is still inside the window"


def test_reset_clears_every_key(db_path):
    consume("k", limit=1, window_seconds=60, db_path=db_path)
    assert consume("k", limit=1, window_seconds=60, db_path=db_path) is not None

    reset(db_path=db_path)

    assert consume("k", limit=1, window_seconds=60, db_path=db_path) is None


def test_an_uncreatable_parent_directory_fails_open(tmp_path, caplog):
    """`mkdir` raises OSError, which is not a `sqlite3.Error`.

    Caught by Copilot on PR #134. `test_an_unusable_database_fails_open` above
    misses this: it puts a directory where the *file* goes, so the parent still
    exists and the failure surfaces from sqlite3. Put a *file* where the parent
    directory goes and the failure comes from `mkdir` instead — which escaped
    the fail-open path entirely and turned a submission into a 500.
    """
    blocker = tmp_path / "tmp"
    blocker.write_text("a file where the directory should be")

    assert consume("k", limit=1, window_seconds=60, db_path=blocker / "rate-limit.sqlite3") is None
    assert "Rate-limit store" in caplog.text


def test_reset_survives_an_uncreatable_parent_directory(tmp_path, caplog):
    blocker = tmp_path / "tmp"
    blocker.write_text("a file where the directory should be")

    reset(db_path=blocker / "rate-limit.sqlite3")

    assert "Rate-limit store" in caplog.text


def _attempt_at_barrier(db_path: str, barrier, queue, limit: int, window_seconds: int) -> None:
    """One worker's single `consume` call, released simultaneously with the rest.

    Module level and importable by name because `multiprocessing` uses `spawn`
    on macOS, which re-imports this module in the child rather than inheriting
    it. Takes `db_path` as a string for the same reason.
    """
    from api.rate_limit_store import consume

    barrier.wait(timeout=60)
    queue.put(consume("shared", limit=limit, window_seconds=window_seconds, db_path=Path(db_path)))


def test_concurrent_workers_cannot_both_take_the_last_slot(db_path):
    """Exactly one caller is admitted when several race for one remaining slot.

    Raised by Copilot on PR #134: nothing exercised the read-modify-write in
    `consume` under contention, so the atomicity was an unverified claim.

    Real processes rather than threads, because that is what Passenger runs and
    because POSIX advisory locks are owned per process -- intra-process locking
    goes through a different path inside SQLite than the one production uses.

    Note what this does and does not pin. Atomicity here has two independent
    guards: `BEGIN IMMEDIATE`, and the prune's `DELETE` landing before the
    `SELECT` (a write, so it takes the write lock whatever the transaction
    began as). Either alone is sufficient, so removing just one keeps this
    green. Measured over 25 runs of each arrangement:

        BEGIN IMMEDIATE + prune before count   1 admitted   (shipped)
        BEGIN           + prune before count   1 admitted
        BEGIN IMMEDIATE + prune after count    1 admitted
        BEGIN           + prune after count    4-8 admitted

    So this is a test of the property, not of either keyword. It fails when a
    refactor removes both -- which is exactly the plausible accident, since
    moving the prune below the count looks like a harmless reordering.
    """
    workers = 8
    limit = 4

    # Fill to one below the limit, so exactly one slot is available.
    for _ in range(limit - 1):
        assert consume("shared", limit=limit, window_seconds=3600, db_path=db_path) is None

    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(workers)
    queue = context.Queue()
    processes = [
        context.Process(
            target=_attempt_at_barrier, args=(str(db_path), barrier, queue, limit, 3600)
        )
        for _ in range(workers)
    ]

    for process in processes:
        process.start()
    try:
        results = [queue.get(timeout=60) for _ in range(workers)]
    finally:
        for process in processes:
            process.join(timeout=60)
            if process.is_alive():  # pragma: no cover - only on a hung child
                process.terminate()

    admitted = [result for result in results if result is None]
    assert len(admitted) == 1, (
        f"{len(admitted)} of {workers} callers were admitted to a single remaining "
        "slot -- the count and the insert are not atomic against a concurrent worker"
    )
    # And the losers got a usable Retry-After rather than a bare refusal.
    assert all(1 <= result <= 3600 for result in results if result is not None)


# --- The concurrent-submission cap, ADR-0018 --------------------------------


def test_slots_up_to_the_cap_are_granted(db_path):
    tokens = [acquire(SCOPE, limit=3, ttl_seconds=60, db_path=db_path) for _ in range(3)]

    assert all(tokens)
    assert len(set(tokens)) == 3, "each holder needs a distinct token to release its own slot"


def test_the_request_past_the_cap_is_refused(db_path):
    for _ in range(3):
        acquire(SCOPE, limit=3, ttl_seconds=60, db_path=db_path)

    assert acquire(SCOPE, limit=3, ttl_seconds=60, db_path=db_path) is None


def test_releasing_a_slot_frees_it_for_the_next_caller(db_path):
    held = [acquire(SCOPE, limit=2, ttl_seconds=60, db_path=db_path) for _ in range(2)]
    assert acquire(SCOPE, limit=2, ttl_seconds=60, db_path=db_path) is None

    release(held[0], db_path=db_path)

    assert acquire(SCOPE, limit=2, ttl_seconds=60, db_path=db_path) is not None


def test_a_slot_expires_so_a_killed_worker_cannot_leak_it(db_path):
    """The property that makes this safe without a cleanup job.

    Passenger reaps workers, and a worker killed mid-request never reaches its
    `release`. Without expiry those slots would accumulate until the cap was
    permanently full and every submission 503'd -- a self-inflicted outage that
    a restart would not even clear, because the count is on disk.
    """
    for _ in range(2):
        acquire(SCOPE, limit=2, ttl_seconds=60, db_path=db_path, now=1000.0)

    # Still held one second before the TTL is up.
    assert acquire(SCOPE, limit=2, ttl_seconds=60, db_path=db_path, now=1059.0) is None

    assert acquire(SCOPE, limit=2, ttl_seconds=60, db_path=db_path, now=1061.0) is not None


def test_releasing_an_unknown_token_is_harmless(db_path):
    """A slot reclaimed by expiry is released by its holder afterwards."""
    acquire(SCOPE, limit=1, ttl_seconds=60, db_path=db_path)

    release("a-token-that-was-never-issued", db_path=db_path)

    assert acquire(SCOPE, limit=1, ttl_seconds=60, db_path=db_path) is None, (
        "nothing else was freed"
    )


def test_an_unusable_database_lets_the_submission_through(tmp_path, caplog):
    """Fails open, like `consume`: an unreachable store must not refuse a form.

    The cost of the opposite is the whole point -- a store that failed closed
    would turn a disk problem into "no supporter can contact the campaign".
    """
    occupied = tmp_path / "rate-limit.sqlite3"
    occupied.mkdir()

    assert acquire(SCOPE, limit=1, ttl_seconds=60, db_path=occupied) is not None
    assert acquire(SCOPE, limit=1, ttl_seconds=60, db_path=occupied) is not None
    assert "Concurrency store" in caplog.text


def test_release_survives_an_unusable_database(tmp_path, caplog):
    occupied = tmp_path / "rate-limit.sqlite3"
    occupied.mkdir()

    release("token", db_path=occupied)

    assert "Concurrency store" in caplog.text


def test_reset_clears_held_slots(db_path):
    acquire(SCOPE, limit=1, ttl_seconds=60, db_path=db_path)

    reset(db_path=db_path)

    assert acquire(SCOPE, limit=1, ttl_seconds=60, db_path=db_path) is not None


def _acquire_at_barrier(db_path: str, barrier, queue, limit: int) -> None:
    """One worker's single `acquire`, released simultaneously with the rest.

    Module level and importable by name for the same reason as
    `_attempt_at_barrier`: `spawn` re-imports this module in the child.
    """
    from api.rate_limit_store import acquire as acquire_slot

    barrier.wait(timeout=60)
    queue.put(bool(acquire_slot(SCOPE, limit=limit, ttl_seconds=60, db_path=Path(db_path))))


def test_concurrent_workers_cannot_both_take_the_last_inflight_slot(db_path):
    """The cap has to hold across processes or it is not a cap at all.

    Same shape as the `consume` test above, and here for the same reason: the
    count-then-insert in `acquire` is a read-modify-write, and the whole value
    of putting this in SQLite rather than in memory is that separate Passenger
    workers see one shared number. Threads would not exercise it -- POSIX
    advisory locks are per process.
    """
    workers = 8
    limit = 4

    for _ in range(limit - 1):
        assert acquire(SCOPE, limit=limit, ttl_seconds=60, db_path=db_path) is not None

    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(workers)
    queue = context.Queue()
    processes = [
        context.Process(target=_acquire_at_barrier, args=(str(db_path), barrier, queue, limit))
        for _ in range(workers)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=60)

    granted = [queue.get(timeout=10) for _ in range(workers)]

    assert sum(granted) == 1, f"exactly one worker should get the last slot, got {sum(granted)}"


def test_scopes_have_separate_budgets(db_path):
    """A flood of one kind of work must not spend another kind's allowance.

    `/health/deep` and the form endpoints both hold slots while they do the
    same expensive I/O. Counted together, an uncapped probe flood would close
    the forms -- which is the outage the cap exists to prevent, arrived at from
    the other direction. Raised by Copilot on PR #138.
    """
    assert acquire("health-probe", limit=1, ttl_seconds=60, db_path=db_path) is not None
    assert acquire("health-probe", limit=1, ttl_seconds=60, db_path=db_path) is None

    assert acquire("submission", limit=1, ttl_seconds=60, db_path=db_path) is not None


def test_a_table_created_before_scopes_existed_is_migrated(db_path):
    """The `inflight` table shipped without `scope`, and the file outlives a deploy.

    It lives under `tmp/`, which the deploy's prune step leaves alone, so
    `CREATE TABLE IF NOT EXISTS` finds the old table and leaves it as it was --
    and every insert against it would fail, silently failing open forever.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    legacy = sqlite3.connect(db_path)
    legacy.execute("CREATE TABLE inflight (token TEXT PRIMARY KEY, started_at REAL NOT NULL)")
    # Recent, so the prune inside `acquire` does not simply expire it and make
    # the survival check below pass for the wrong reason.
    legacy.execute("INSERT INTO inflight (token, started_at) VALUES ('old', ?)", (time(),))
    legacy.commit()
    legacy.close()

    assert acquire(SCOPE, limit=1, ttl_seconds=60, db_path=db_path) is not None

    # And the pre-existing row survived the migration rather than being dropped.
    surviving = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM inflight").fetchone()[0]
    assert surviving == 2


def test_two_workers_racing_the_scope_migration_both_succeed(db_path):
    """The first request after a deploy is when this race is live.

    Both workers can read `table_info` before either has altered the table, and
    the loser gets `duplicate column name: scope`. Losing is success, so it must
    not surface as a store failure -- which fails open and logs an exception
    that reads like a real fault. Raised in review.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    legacy = sqlite3.connect(db_path)
    legacy.execute("CREATE TABLE inflight (token TEXT PRIMARY KEY, started_at REAL NOT NULL)")
    legacy.commit()
    legacy.close()

    # Two connections opened before either has migrated, which is the race.
    first = sqlite3.connect(db_path)
    second = sqlite3.connect(db_path)
    try:
        _add_scope_column_if_missing(first)
        _add_scope_column_if_missing(second)
    finally:
        first.close()
        second.close()

    assert acquire(SCOPE, limit=1, ttl_seconds=60, db_path=db_path) is not None


def test_a_failed_connection_setup_does_not_leak_the_handle(db_path, monkeypatch):
    """`_connect` owns the connection until it returns one."""
    opened = []
    real_connect = sqlite3.connect

    def tracking_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)
    monkeypatch.setattr(rate_limit_store, "_add_scope_column_if_missing", _raise_operational_error)

    with pytest.raises(sqlite3.OperationalError):
        rate_limit_store._connect(db_path)

    assert opened, "the test patched the wrong thing"
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


def _raise_operational_error(_connection) -> None:
    raise sqlite3.OperationalError("disk I/O error")
