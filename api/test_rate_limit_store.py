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

import pytest

from api.rate_limit_store import consume, reset


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
