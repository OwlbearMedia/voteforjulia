"""Covers the WSGI entry point's New Relic bootstrap.

This module is what Passenger imports to get `application`. Nothing else in the
suite touches it, so without these tests the agent bootstrap — the one piece of
this change that can fail at boot and take every form on the site down — would
ship unexercised.

Each test loads passenger_wsgi.py fresh, because the bootstrap runs at import
time and its outcome is baked into module-level state.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_PASSENGER_WSGI = Path(__file__).resolve().parent / "passenger_wsgi.py"


def _load_passenger_wsgi():
    spec = importlib.util.spec_from_file_location("passenger_wsgi_under_test", _PASSENGER_WSGI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_newrelic(*, initialize_error: Exception | None = None) -> dict[str, types.ModuleType]:
    """A stand-in for the agent package, which is not installed locally."""

    def initialize(*args, **kwargs):
        if initialize_error is not None:
            raise initialize_error

    def wsgi_application_wrapper(application):
        wrapped = types.SimpleNamespace(wrapped_app=application)
        return wrapped

    agent = types.ModuleType("newrelic.agent")
    agent.initialize = initialize
    agent.WSGIApplicationWrapper = wsgi_application_wrapper

    package = types.ModuleType("newrelic")
    package.agent = agent

    return {"newrelic": package, "newrelic.agent": agent}


class PassengerWsgiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_modules = {
            name: sys.modules.get(name) for name in ("newrelic", "newrelic.agent")
        }

    def tearDown(self) -> None:
        for name, original in self._orig_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def test_exposes_application_without_a_licence_key(self) -> None:
        # Local dev and CI have no key. The app must still boot, unwrapped.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEW_RELIC_LICENSE_KEY", None)
            module = _load_passenger_wsgi()

        self.assertIsNone(module._new_relic_wrapper)
        self.assertTrue(callable(module.application))
        self.assertFalse(hasattr(module.application, "wrapped_app"))

    def test_blank_licence_key_is_treated_as_unset(self) -> None:
        # cPanel writes empty values for variables added but not filled in.
        with mock.patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "   "}, clear=False):
            module = _load_passenger_wsgi()

        self.assertIsNone(module._new_relic_wrapper)
        self.assertTrue(callable(module.application))

    def test_wraps_the_application_when_configured(self) -> None:
        with (
            mock.patch.dict(sys.modules, _fake_newrelic()),
            mock.patch.dict(
                os.environ, {"NEW_RELIC_LICENSE_KEY": "0123456789abcdefNRAL"}, clear=False
            ),
        ):
            module = _load_passenger_wsgi()

        self.assertIsNotNone(module._new_relic_wrapper)
        self.assertTrue(hasattr(module.application, "wrapped_app"))

    def test_agent_failure_does_not_break_the_app(self) -> None:
        # A rejected key, an unwritable log path, a version mismatch — none of
        # it may cost the site its forms. This is the whole reason the
        # bootstrap swallows exceptions.
        broken = _fake_newrelic(initialize_error=RuntimeError("agent exploded"))

        with (
            mock.patch.dict(sys.modules, broken),
            mock.patch.dict(
                os.environ, {"NEW_RELIC_LICENSE_KEY": "0123456789abcdefNRAL"}, clear=False
            ),
        ):
            module = _load_passenger_wsgi()

        self.assertIsNone(module._new_relic_wrapper)
        self.assertTrue(callable(module.application))
        self.assertFalse(hasattr(module.application, "wrapped_app"))

    def test_missing_agent_package_does_not_break_the_app(self) -> None:
        # The key can reach the host before the dependency does: the deploy
        # installs requirements.txt, but the env var is set by hand in cPanel.
        absent = {"newrelic": None, "newrelic.agent": None}

        with (
            mock.patch.dict(sys.modules, absent),
            mock.patch.dict(
                os.environ, {"NEW_RELIC_LICENSE_KEY": "0123456789abcdefNRAL"}, clear=False
            ),
        ):
            module = _load_passenger_wsgi()

        self.assertIsNone(module._new_relic_wrapper)
        self.assertTrue(callable(module.application))

    def test_application_still_serves_requests_unwrapped(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEW_RELIC_LICENSE_KEY", None)
            module = _load_passenger_wsgi()

        response = module.application.test_client().get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
