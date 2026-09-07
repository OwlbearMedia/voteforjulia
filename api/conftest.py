"""Fixtures shared by the whole API suite.

Only put things here that every module genuinely needs. Per-module fixtures
belong in the module — `test_app_pipeline.py`'s `pipeline` is the example.
"""

from __future__ import annotations

import pytest

import api.app as app_module
import api.rate_limit_store as rate_limit_store


@pytest.fixture(autouse=True)
def isolated_rate_limit_store(tmp_path, monkeypatch):
    """Point the rate limiter at a database this test alone can see.

    Autouse because every tier counts in this store (ADR-0024), so without it
    the suite shares one on-disk counter, tests hand each other 429s depending
    on run order, and `pytest` leaves a database behind.

    Patching the module attribute is what makes it cover requests served through
    the Flask test client too — `consume` resolves `DEFAULT_DB_PATH` at call
    time, so app.py needs no test-only seam.

    The backoff is cleared either side for the same reason. It is a module
    global that a single failing call arms for ten seconds, so one test using an
    unusable database would otherwise hand every test after it an `UNAVAILABLE`
    from a database that is perfectly fine — and the failures would land on
    whichever tests happened to run next.
    """
    monkeypatch.setattr(rate_limit_store, "DEFAULT_DB_PATH", tmp_path / "rate-limit.sqlite3")
    rate_limit_store.clear_backoff()
    yield
    rate_limit_store.clear_backoff()


@pytest.fixture(autouse=True)
def isolated_limiter_memory():
    """Start every test with the limiter's in-process state empty.

    Autouse for the same reason as the fixture above. Both dictionaries are
    module globals, so a test that fills one has the next test's requests
    counted or refused for reasons that test cannot see. The refusal cache leaks
    429s forward directly; the degraded counter leaks them only after some test
    has made the store unreachable, which is exactly the order dependence that
    surfaces as an unrelated failure weeks later.
    """
    refusals = app_module._RATE_LIMIT_REFUSALS
    degraded = app_module._DEGRADED_BURST_COUNTS
    next_sweep_at = app_module._next_refusal_sweep_at

    app_module._RATE_LIMIT_REFUSALS = {}
    app_module._DEGRADED_BURST_COUNTS = {}
    # In the past, so the first request of each test sweeps.
    app_module._next_refusal_sweep_at = 0.0
    yield
    app_module._RATE_LIMIT_REFUSALS = refusals
    app_module._DEGRADED_BURST_COUNTS = degraded
    app_module._next_refusal_sweep_at = next_sweep_at


@pytest.fixture(autouse=True)
def fresh_deep_health_cache():
    """Start every test with `/health/deep` having no cached probe result.

    Autouse for the same reason as the fixture above: the cache is a module
    global, so without this a test that stubs the probes to fail leaves a 503
    behind and the next test to call the endpoint is served that answer instead
    of running its own stubs. The failures are order-dependent and read as
    though the endpoint ignores its collaborators.

    Cleared afterwards as well, so a test that populates it cannot reach a
    module whose tests never touch this endpoint.
    """
    app_module._reset_deep_health_cache()
    yield
    app_module._reset_deep_health_cache()
