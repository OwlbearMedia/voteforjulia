"""Drift tests: assert api/openapi.yaml still describes the code it documents.

The spec is hand-maintained, so nothing stops it from quietly going stale. These
tests fail when it does. Written as plain pytest functions rather than
unittest.TestCase classes — both styles are collected, so this file doubles as
the worked example for new-style tests.

Three kinds of drift are covered:

1. Routes — an endpoint or method added to app.py but not documented (or the
   reverse).
2. Field limits — a MAX_* constant changed in models.py without the matching
   maxLength/maxItems being updated.
3. Error messages — a message reworded in code while the spec keeps quoting the
   old text. Rather than grepping for every string, the composed ones are
   verified by calling the real validators, so this also pins the behaviour.
"""

from pathlib import Path

import pytest
import yaml
from werkzeug.exceptions import RequestEntityTooLarge

import api.app as app_module
from api.app import (
    _missing_required_fields_message,
    _missing_required_yard_sign_fields_message,
)
from api.models import (
    MAX_ADDRESS_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_FIRST_NAME_LENGTH,
    MAX_HELP_WAY_LENGTH,
    MAX_HELP_WAYS_COUNT,
    MAX_LAST_NAME_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_PHONE_LENGTH,
    MAX_PREFERRED_PAYMENT_COUNT,
    MAX_PREFERRED_PAYMENT_LENGTH,
    Submission,
    YardSignRequest,
    validate_submission,
)

_API_DIR = Path(__file__).parent
_SPEC_PATH = _API_DIR / "openapi.yaml"

SPEC = yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))

# Flask adds HEAD to every GET route and OPTIONS to every route. Documenting
# them everywhere would describe framework defaults rather than the API, so the
# route comparison ignores both; the deliberate CORS preflight handlers are
# checked separately by test_documented_preflight_routes_accept_options.
_FRAMEWORK_METHODS = {"HEAD", "OPTIONS"}


def _spec_operations() -> set[tuple[str, str]]:
    return {
        (path, method.upper())
        for path, operations in SPEC["paths"].items()
        for method in operations
        if method.upper() not in _FRAMEWORK_METHODS
    }


def _app_routes() -> dict[str, set[str]]:
    """Registered path -> methods."""
    routes: dict[str, set[str]] = {}
    for rule in app_module.app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        routes.setdefault(rule.rule, set()).update(rule.methods or set())
    return routes


def _app_operations() -> set[tuple[str, str]]:
    return {
        (path, method)
        for path, methods in _app_routes().items()
        for method in methods
        if method not in _FRAMEWORK_METHODS
    }


def _resolve(node):
    """Follow a local $ref one level; return the node unchanged otherwise."""
    if isinstance(node, dict) and "$ref" in node:
        target = SPEC
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        return target
    return node


def _schema_property(schema_name: str, prop: str) -> dict:
    """Look up a property on a component schema, flattening allOf composition."""
    schema = _resolve(SPEC["components"]["schemas"][schema_name])
    branches = [_resolve(branch) for branch in schema["allOf"]] if "allOf" in schema else [schema]
    for branch in branches:
        if prop in branch.get("properties", {}):
            return branch["properties"][prop]
    raise AssertionError(f"{schema_name} does not document a `{prop}` property")


def _array_branch(schema_name: str, prop: str) -> dict:
    """The array alternative of a oneOf property that also accepts a string."""
    prop_schema = _schema_property(schema_name, prop)
    for branch in prop_schema["oneOf"]:
        if branch.get("type") == "array":
            return branch
    raise AssertionError(f"{schema_name}.{prop} does not document an array form")


def _documented_errors() -> set[str]:
    """Every `error` value the spec shows in a response example."""
    errors: set[str] = set()
    for response in SPEC["components"]["responses"].values():
        json_body = response.get("content", {}).get("application/json", {})
        if "error" in json_body.get("example", {}):
            errors.add(json_body["example"]["error"])
        for example in json_body.get("examples", {}).values():
            value = example.get("value", {})
            if "error" in value:
                errors.add(value["error"])
    return errors


def _contact(**overrides) -> Submission:
    fields = {
        "first_name": "Alex",
        "last_name": "",
        "name": "Alex",
        "email": "alex@example.com",
        "phone": "",
        "message": "",
        "help_ways": [],
    }
    return Submission(**{**fields, **overrides})


def _yard_sign(**overrides) -> YardSignRequest:
    fields = {
        "first_name": "Sam",
        "last_name": "",
        "name": "Sam",
        "email": "sam@example.com",
        "phone": "",
        "address": "123 Riverfront Dr",
        "preferred_payment": [],
    }
    return YardSignRequest(**{**fields, **overrides})


# Errors the spec documents that are assembled at runtime (f-strings, joined
# label lists) and so never appear verbatim in the source. Each is verified by
# invoking the code that produces it. Anything documented but absent from both
# this table and the source literals fails test_documented_errors_exist.
GENERATED_ERRORS = {
    "Email and Address are required.": lambda: _missing_required_yard_sign_fields_message(
        _yard_sign(email="", address="")
    ),
    "Message must be 500 characters or fewer.": lambda: validate_submission(
        _contact(message="x" * (MAX_MESSAGE_LENGTH + 1))
    ),
    # Not ours: the size cap is enforced by Werkzeug, and `json_http_error`
    # relays its stock description. Sourced from the exception rather than
    # copied so a Werkzeug upgrade that rewords it fails here instead of
    # leaving the spec quoting text the API no longer sends.
    "The data value transmitted exceeds the capacity limit.": (
        lambda: RequestEntityTooLarge().description
    ),
    # Long enough that app.py composes it across two source lines, so it never
    # appears as a single literal. Keyed on the constant rather than a copy of
    # its text: that makes the lookup itself the drift check, because a spec
    # that quotes anything other than what app.py sends will not find an entry
    # here and falls through to the literal search, which fails.
    app_module._HONEYPOT_MESSAGE: lambda: app_module._HONEYPOT_MESSAGE,
}

_SOURCE = "\n".join(
    (_API_DIR / name).read_text(encoding="utf-8") for name in ("app.py", "models.py")
)


def test_spec_is_valid_openapi():
    from openapi_spec_validator import validate

    validate(SPEC)


@pytest.mark.parametrize("path", sorted(SPEC["paths"]))
def test_documented_paths_are_registered(path):
    registered = {rule.rule for rule in app_module.app.url_map.iter_rules()}
    assert path in registered


@pytest.mark.parametrize("path", sorted(SPEC["paths"]))
def test_no_same_origin_api_prefix_alias_exists(path):
    """Guard the removal of the `/api/*` aliases against a well-meaning revival.

    Every route used to be registered twice, the second under `/api/`, so the
    forms could post to the site's own origin with JavaScript disabled. That
    never worked: [ADR-0003](../docs/adr/0003-separate-api-subdomain.md) puts
    the API on its own host and rejects both a path mount and an `.htaccess`
    proxy, so `voteforjulia.com/api/send-email` reached the static document
    root and 404'd — losing the submission it was meant to save. The forms now
    carry an absolute action pointing here (src/lib/api.ts), which is the only
    thing that can work across origins.

    Re-adding the alias would not break a test without this one, and it would
    read as support for a same-origin fallback that the hosting cannot provide.
    """
    assert f"/api{path}" not in {rule.rule for rule in app_module.app.url_map.iter_rules()}


def test_documented_operations_match_the_app():
    assert _spec_operations() == _app_operations()


@pytest.mark.parametrize(
    "path",
    sorted(path for path, operations in SPEC["paths"].items() if "options" in operations),
)
def test_documented_preflight_returns_the_documented_status(path):
    # Asserting OPTIONS is in url_map would be vacuous: Flask adds it to every
    # route automatically. The status code is what separates a real preflight
    # handler (returns 204, and the after_request hook attaches CORS headers)
    # from Flask's default OPTIONS response (200 with an Allow header). So make
    # the request and compare against the status the spec documents.
    #
    # The preflight matters more than it looks: every form post is cross-origin
    # by construction (ADR-0003), so a browser will not send one without it.
    documented = set(SPEC["paths"][path]["options"]["responses"])
    response = app_module.app.test_client().options(path)
    assert str(response.status_code) in documented, (
        f"OPTIONS {path} returned {response.status_code}, spec documents {sorted(documented)}"
    )


@pytest.mark.parametrize(
    ("constant", "schema_name", "prop"),
    [
        (MAX_FIRST_NAME_LENGTH, "NameFields", "firstName"),
        (MAX_LAST_NAME_LENGTH, "NameFields", "lastName"),
        (MAX_EMAIL_LENGTH, "ContactSubmission", "email"),
        (MAX_PHONE_LENGTH, "ContactSubmission", "phone"),
        (MAX_MESSAGE_LENGTH, "ContactSubmission", "message"),
        (MAX_EMAIL_LENGTH, "YardSignRequest", "email"),
        (MAX_PHONE_LENGTH, "YardSignRequest", "phone"),
        (MAX_ADDRESS_LENGTH, "YardSignRequest", "address"),
    ],
)
def test_documented_max_length_matches_models(constant, schema_name, prop):
    assert _schema_property(schema_name, prop)["maxLength"] == constant


@pytest.mark.parametrize(
    ("max_count", "max_item_length", "schema_name", "prop"),
    [
        (MAX_HELP_WAYS_COUNT, MAX_HELP_WAY_LENGTH, "ContactSubmission", "helpWays"),
        (
            MAX_PREFERRED_PAYMENT_COUNT,
            MAX_PREFERRED_PAYMENT_LENGTH,
            "YardSignRequest",
            "preferredPayment",
        ),
    ],
)
def test_documented_array_limits_match_models(max_count, max_item_length, schema_name, prop):
    branch = _array_branch(schema_name, prop)
    assert branch["maxItems"] == max_count
    assert branch["items"]["maxLength"] == max_item_length


@pytest.mark.parametrize("message", sorted(_documented_errors()))
def test_documented_errors_exist(message):
    if message in GENERATED_ERRORS:
        assert GENERATED_ERRORS[message]() == message
    else:
        # Quote-agnostic: `ruff format` normalizes to double quotes, but a
        # message containing an apostrophe keeps single quotes, and the check
        # should not depend on formatter configuration either way.
        quoted = {f'"{message}"', f"'{message}'"}
        assert any(literal in _SOURCE for literal in quoted), (
            f"{message!r} is documented in openapi.yaml but is neither a literal in "
            f"app.py/models.py nor listed in GENERATED_ERRORS"
        )


def test_required_field_messages_match_the_spec():
    # The 400 examples name these specific combinations; they are composed from
    # separate branches, so pin each one the spec shows.
    assert _missing_required_fields_message(_contact(first_name="", email="")) == (
        "First name and email are required."
    )
    assert _missing_required_yard_sign_fields_message(_yard_sign(email="", address="")) == (
        "Email and Address are required."
    )


def test_rate_limit_defaults_match_the_spec():
    # The 429 description quotes these numbers as the defaults.
    description = SPEC["components"]["responses"]["RateLimited"]["description"]
    assert f"{app_module._RATE_LIMIT_MAX_REQUESTS} requests" in description
    assert f"{app_module._RATE_LIMIT_WINDOW_SECONDS} seconds" in description


def test_long_rate_limit_defaults_match_the_spec():
    # Same drift check for the second tier (ADR-0016). Kept as its own test
    # rather than four asserts in the one above so a failure names which tier
    # drifted -- the two are configured independently and change independently.
    description = SPEC["components"]["responses"]["RateLimited"]["description"]
    assert f"{app_module._LONG_RATE_LIMIT_MAX_REQUESTS} requests" in description
    assert f"{app_module._LONG_RATE_LIMIT_WINDOW_SECONDS} seconds" in description


def test_health_deep_allowance_matches_the_spec():
    # `/health/deep` is documented as having its own, larger hourly allowance.
    description = SPEC["components"]["responses"]["RateLimited"]["description"]
    assert f"{app_module._HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS} per hour" in description


def test_documented_request_size_limit_matches_the_app():
    # The 413 description quotes the byte cap as the default, the same way the
    # 429 description quotes the rate-limit numbers.
    description = SPEC["components"]["responses"]["PayloadTooLarge"]["description"]
    assert str(app_module.app.config["MAX_CONTENT_LENGTH"]) in description


@pytest.mark.parametrize("path", ["/send-email", "/yard-sign"])
def test_oversized_body_returns_the_documented_status(path):
    # The route-level drift tests compare paths and methods; nothing otherwise
    # checks that a documented *status* is one the app can actually produce. A
    # 413 documented on an endpoint whose cap was lifted would go unnoticed.
    assert "413" in SPEC["paths"][path]["post"]["responses"]

    oversized = "x" * (app_module.app.config["MAX_CONTENT_LENGTH"] + 1)
    response = app_module.app.test_client().post(
        path, data=oversized, content_type="application/json"
    )

    assert response.status_code == 413
    assert response.mimetype == "application/json"


def test_documented_cors_origins_match_the_defaults():
    header = SPEC["components"]["headers"]["AccessControlAllowOrigin"]
    assert "http://localhost:5173" in header["description"]
    assert "http://localhost:5173" in app_module._CORS_ALLOWED_ORIGINS
