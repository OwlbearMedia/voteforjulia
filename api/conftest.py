"""Fixtures shared by the whole API suite.

Only put things here that every module genuinely needs. Per-module fixtures
belong in the module — `test_app_pipeline.py`'s `pipeline` is the example.
"""

from __future__ import annotations

import pytest

import api.rate_limit_store as rate_limit_store


@pytest.fixture(autouse=True)
def isolated_rate_limit_store(tmp_path, monkeypatch):
    """Point the long-window limiter at a database this test alone can see.

    Autouse because the second tier is consulted on every request the burst tier
    allows: without it the suite shares one on-disk counter, tests hand each
    other 429s depending on run order, and `pytest` leaves a database behind.

    Patching the module attribute is what makes it cover requests served through
    the Flask test client too — `consume` resolves `DEFAULT_DB_PATH` at call
    time, so app.py needs no test-only seam.
    """
    monkeypatch.setattr(rate_limit_store, "DEFAULT_DB_PATH", tmp_path / "rate-limit.sqlite3")
