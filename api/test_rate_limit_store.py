"""The SQLite-backed limiter behind every tier (ADR-0016, ADR-0024).

`test_app.py` covers what the endpoints do with a 429; this covers the store
underneath — counting, the two properties it exists for (surviving a process,
failing open), the `Retry-After` arithmetic, and what several tiers over one set
of rows have to guarantee each other.

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
    ALLOWED,
    UNAVAILABLE,
    Refusal,
    Tier,
    _add_scope_column_if_missing,
    acquire,
    consume,
    release,
    reset,
)

# The scope name is arbitrary here; what these tests exercise is the counting.
SCOPE = "submission"

# The two names app.py reports a 429 under. Nothing in the store cares which is
# which -- it counts whatever windows it is handed, in the order given.
BURST = "burst"
HOURLY = "hourly"


def tiers(limit: int, window_seconds: int, name: str = BURST) -> list[Tier]:
    """One window, for the tests whose subject is the counting rather than the tiers."""
    return [Tier(name, limit, window_seconds)]


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "rate-limit.sqlite3"


def test_requests_under_the_limit_are_allowed(db_path):
    results = [consume("k", tiers=tiers(3, 60), db_path=db_path) for _ in range(3)]

    assert results == [ALLOWED, ALLOWED, ALLOWED]


def test_the_request_past_the_limit_is_refused(db_path):
    for _ in range(3):
        consume("k", tiers=tiers(3, 60), db_path=db_path)

    assert consume("k", tiers=tiers(3, 60), db_path=db_path).refusal == Refusal(BURST, 60)


def test_keys_are_counted_separately(db_path):
    """The other half of "these collide" — see conventions.md.

    Four requests on one key tripping the limit would pass even if `key` were
    ignored and every request shared a counter. This is the case that catches it.
    """
    for _ in range(3):
        assert consume("send-email:198.51.100.1", tiers=tiers(3, 60), db_path=db_path) == ALLOWED

    assert consume("send-email:198.51.100.1", tiers=tiers(3, 60), db_path=db_path) != ALLOWED
    assert consume("send-email:198.51.100.2", tiers=tiers(3, 60), db_path=db_path) == ALLOWED
    assert consume("yard-sign:198.51.100.1", tiers=tiers(3, 60), db_path=db_path) == ALLOWED


def test_requests_older_than_the_window_stop_counting(db_path):
    # `now` is injectable precisely so this does not need a sleep. Three
    # requests an hour ago, against a 60-second window, must not constrain a
    # request happening now.
    for offset in (0, 1, 2):
        consume("k", tiers=tiers(3, 60), db_path=db_path, now=1000.0 + offset)

    assert consume("k", tiers=tiers(3, 60), db_path=db_path, now=4600.0) == ALLOWED


def test_retry_after_covers_the_rest_of_the_window(db_path):
    """Rounded up, and measured from the oldest request still in the window.

    The bug ADR-0014 fixed in the tier that then lived in memory: truncating
    advertises a retry still inside the window, so honouring the header exactly
    earns a second 429.
    """
    consume("k", tiers=tiers(1, 60), db_path=db_path, now=1000.0)

    verdict = consume("k", tiers=tiers(1, 60), db_path=db_path, now=1030.4)

    assert verdict.refusal == Refusal(BURST, 30)
    retry_after = verdict.refusal.retry_after
    # And honouring it exactly is enough: at now + retry_after the window is
    # clear. This is the assertion that would fail if the value were rounded
    # down, and it is the property the header actually promises.
    assert consume("k", tiers=tiers(1, 60), db_path=db_path, now=1030.4 + retry_after) == ALLOWED


# --- Several windows over one set of rows, ADR-0024 -------------------------


def test_a_wider_window_still_counts_what_a_narrower_one_has_forgotten(db_path):
    """The hour-long tier's rows must survive the burst tier's cutoff.

    Every tier counts the same rows, so there is exactly one prune and it has to
    use the widest window. Prune at the narrowest instead and each request wipes
    the history the hourly tier is made of -- ten requests spread across half an
    hour then read as one, and the tier that caught the 2026-08-10 abuse never
    fires again.
    """
    both = [Tier(BURST, 5, 60), Tier(HOURLY, 10, 3600)]

    # 200 seconds apart: never five in any minute, so the burst tier is silent
    # throughout and the hourly one is the only thing counting.
    for index in range(10):
        assert consume("k", tiers=both, db_path=db_path, now=1000.0 + index * 200) == ALLOWED

    verdict = consume("k", tiers=both, db_path=db_path, now=3000.0)

    assert verdict.refusal is not None, "ten requests inside the hour, and the eleventh was allowed"
    assert verdict.refusal.tier == HOURLY
    # Measured from the oldest request still inside the hour, at t=1000.
    assert verdict.refusal.retry_after == 1600


def test_a_refused_request_does_not_spend_another_tiers_allowance(db_path):
    """A burst refusal costs the caller nothing at the hour scale.

    The property the single insert buys: nothing is recorded until every tier
    has passed. Record refusals as well and a caller who trips the burst limit
    burns their hourly allowance on requests that were never served.
    """
    both = [Tier(BURST, 2, 60), Tier(HOURLY, 5, 3600)]

    for offset in (0.0, 0.1):
        assert consume("k", tiers=both, db_path=db_path, now=1000.0 + offset) == ALLOWED
    for offset in (1.0, 2.0, 3.0):
        refused = consume("k", tiers=both, db_path=db_path, now=1000.0 + offset)
        assert refused.refusal.tier == BURST

    # Well clear of the burst window, so only the hourly tier is still counting.
    # Three more requests are inside its allowance of five -- but only if the
    # three refusals above cost nothing.
    for now in (1100.0, 1200.0, 1300.0):
        assert consume("k", tiers=both, db_path=db_path, now=now) == ALLOWED

    assert consume("k", tiers=both, db_path=db_path, now=1301.0).refusal.tier == HOURLY


def test_the_first_tier_to_refuse_is_the_one_reported(db_path):
    """Which name a 429 carries, in every arrangement of full and not full.

    app.py hands them narrowest first so a caller over both is told about the
    window that clears sooner. Nothing in here knows that, so the list order has
    to be what decides -- and a tier that is not first still has to report
    itself, which is the case that catches a refusal labelled `tiers[0]`
    whatever actually refused.
    """
    full = Tier(BURST, 1, 60)
    also_full = Tier(HOURLY, 1, 3600)
    roomy = Tier(BURST, 50, 60)

    assert consume("k", tiers=[full, also_full], db_path=db_path, now=1000.0) == ALLOWED

    # Over both: the earlier tier wins.
    assert consume("k", tiers=[full, also_full], db_path=db_path, now=1001.0).refusal.tier == BURST
    assert consume("k", tiers=[also_full, full], db_path=db_path, now=1001.0).refusal.tier == HOURLY

    # Over only the second: it is reported as itself, not as whatever is first.
    assert (
        consume("k", tiers=[roomy, also_full], db_path=db_path, now=1001.0).refusal.tier == HOURLY
    )


def test_an_allowed_request_is_recorded_once_and_a_refused_one_not_at_all(db_path):
    """One row per served request, however many tiers counted it."""
    both = [Tier(BURST, 3, 60), Tier(HOURLY, 10, 3600)]

    for offset in range(3):
        assert consume("k", tiers=both, db_path=db_path, now=1000.0 + offset) == ALLOWED
    assert consume("k", tiers=both, db_path=db_path, now=1003.0).refusal is not None

    connection = sqlite3.connect(db_path)
    try:
        (recorded,) = connection.execute("SELECT COUNT(*) FROM hits").fetchone()
    finally:
        connection.close()

    assert recorded == 3


def test_counts_survive_a_separate_process(db_path, tmp_path):
    """The property the whole module exists for (ADR-0016).

    Spends a real interpreter rather than asserting durability indirectly: two
    requests here, two more in a subprocess sharing nothing but the file, and
    the limit of three enforced across the boundary. Make the store in-memory
    and this is the test that fails.
    """
    repo_root = Path(__file__).resolve().parent.parent

    for _ in range(2):
        assert consume("k", tiers=tiers(3, 3600), db_path=db_path) == ALLOWED

    program = (
        "from api.rate_limit_store import Tier, consume\n"
        f"path = {str(db_path)!r}\n"
        "import pathlib\n"
        "p = pathlib.Path(path)\n"
        "tiers = [Tier('burst', 3, 3600)]\n"
        "third = consume('k', tiers=tiers, db_path=p)\n"
        "fourth = consume('k', tiers=tiers, db_path=p)\n"
        "print(third.refusal is None, fourth.refusal is None)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    third_allowed, fourth_allowed = completed.stdout.split()
    assert third_allowed == "True", (
        "the third request was within the limit and should have been allowed"
    )
    assert fourth_allowed == "False", (
        "the fourth request exceeded a limit of three, but the fresh process "
        "counted from zero -- the store is not durable"
    )


def test_an_unusable_database_fails_open(tmp_path, caplog):
    """A limiter that cannot count must not be the reason a form 500s.

    A directory where the file should be makes every sqlite3 call raise, standing
    in for a read-only filesystem, a full disk, or a corrupt file.

    `UNAVAILABLE` and not `ALLOWED`, and the difference is load-bearing: both let
    the request through here, but only one of them tells app.py to start
    counting the burst window itself. Return `ALLOWED` from this path and the
    endpoint is unlimited for the length of the incident (ADR-0024).
    """
    occupied = tmp_path / "rate-limit.sqlite3"
    occupied.mkdir()

    assert consume("k", tiers=tiers(1, 60), db_path=occupied) == UNAVAILABLE
    # Repeated calls keep failing open rather than raising on the second one.
    assert consume("k", tiers=tiers(1, 60), db_path=occupied) == UNAVAILABLE
    assert "Rate-limit store" in caplog.text


def test_a_corrupt_database_fails_open(db_path, caplog):
    db_path.write_bytes(b"this is not a SQLite file, but it is the right length to look like one")

    assert consume("k", tiers=tiers(1, 60), db_path=db_path) == UNAVAILABLE
    assert "Rate-limit store" in caplog.text


class _ConnectionThatLocksMidTransaction:
    """A real connection whose first statement inside the transaction raises.

    Not a mock of the store: everything except that one call is the genuine
    sqlite3 connection, so the code under test opens, begins and closes for
    real. `sqlite3.Connection` will not accept a patched `execute` -- the
    attribute is read-only -- which is why this is a wrapper rather than a
    monkeypatch.
    """

    def __init__(self, real: sqlite3.Connection) -> None:
        self._real = real

    def execute(self, sql: str, *args):
        if sql.startswith("DELETE"):
            raise sqlite3.OperationalError("database is locked")
        return self._real.execute(sql, *args)

    def __enter__(self):
        return self._real.__enter__()

    def __exit__(self, *exc_info):
        return self._real.__exit__(*exc_info)

    def close(self) -> None:
        self._real.close()


def test_a_database_that_fails_mid_transaction_reports_unavailable(db_path, caplog, monkeypatch):
    """The busy timeout expiring, which is the likeliest of these in production.

    A separate branch from the unusable-file tests above, and easy to miss: they
    all fail inside `_connect`, so a regression that returned `ALLOWED` from the
    *other* handler would leave every one of them green. It matters for the same
    reason as the rest — `ALLOWED` here tells app.py the shared tiers counted
    this request, and its fallback would stand down for the length of the
    incident (ADR-0024).
    """
    real_connect = rate_limit_store._connect
    monkeypatch.setattr(
        rate_limit_store,
        "_connect",
        lambda path: _ConnectionThatLocksMidTransaction(real_connect(path)),
    )

    assert consume("k", tiers=tiers(1, 60), db_path=db_path) == UNAVAILABLE
    assert "Rate-limit store" in caplog.text


def test_no_tiers_at_all_allows_the_request_rather_than_raising(db_path):
    # Unreachable from app.py, which always passes two. Pinned because the one
    # expression in `consume` that can raise outside a handler is the `max()`
    # over this list, and a limiter that raises is a 500 on a form -- the exact
    # thing every other path in here bends over backwards to avoid.
    assert consume("k", tiers=[], db_path=db_path) == ALLOWED


def test_the_table_does_not_grow_without_bound(db_path):
    """Expired rows are pruned, so the file cannot grow forever.

    This runs for months on a host nobody logs into, so not accumulating is part
    of working. Every hit below is outside the window by the time the last lands.
    """
    for index in range(50):
        consume(f"key-{index}", tiers=tiers(1, 10), db_path=db_path, now=1000.0 + index)

    consume("final", tiers=tiers(1, 10), db_path=db_path, now=5000.0)

    with sqlite3.connect(db_path) as connection:
        remaining = connection.execute("SELECT COUNT(*) FROM hits").fetchone()[0]

    assert remaining == 1, "only the most recent hit is still inside the window"


def test_reset_clears_every_key(db_path):
    consume("k", tiers=tiers(1, 60), db_path=db_path)
    assert consume("k", tiers=tiers(1, 60), db_path=db_path) != ALLOWED

    reset(db_path=db_path)

    assert consume("k", tiers=tiers(1, 60), db_path=db_path) == ALLOWED


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

    assert consume("k", tiers=tiers(1, 60), db_path=blocker / "rate-limit.sqlite3") == UNAVAILABLE
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
    queue.put(consume("shared", tiers=tiers(limit, window_seconds), db_path=Path(db_path)))


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
        assert consume("shared", tiers=tiers(limit, 3600), db_path=db_path) == ALLOWED

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

    admitted = [result for result in results if result == ALLOWED]
    assert len(admitted) == 1, (
        f"{len(admitted)} of {workers} callers were admitted to a single remaining "
        "slot -- the count and the insert are not atomic against a concurrent worker"
    )
    # And the losers got a usable Retry-After rather than a bare refusal.
    assert all(1 <= result.refusal.retry_after <= 3600 for result in results if result != ALLOWED)


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
