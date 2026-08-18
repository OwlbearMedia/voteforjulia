"""Tests for scripts/arm-edge-gate.sh, the deploy's edge-token substitution.

This logic used to be inline shell inside both deploy workflows, where it could
only ever run at deploy time -- and a `workflow_run` deploy uses `main`'s copy
of the workflow, so a change to it could not be exercised from the PR making it
(docs/hosting.md). As a script it is reachable from CI instead. See ADR-0020.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "arm-edge-gate.sh"
SHIPPED_HTACCESS = REPO_ROOT / "public" / ".htaccess"

VALID_TOKEN = "a" * 32
GATE_RULE = "RewriteRule ^ - [F]"
AUTODISCOVER_COND = "RewriteCond %{REQUEST_URI} !^/[Aa]utodiscover/"
WELL_KNOWN_COND = r"RewriteCond %{REQUEST_URI} !^/\.well-known/"

# Stands in for public/.htaccess: the gate as it ships, with enough of the file
# either side to exercise the guards that read the far end of it.
HTACCESS_WITH_GATE = f"""\
RewriteEngine On

# BEGIN EDGE GATE
{WELL_KNOWN_COND}
{AUTODISCOVER_COND}
RewriteCond %{{HTTP:X-Origin-Token}} !^@@EDGE_TOKEN@@$
{GATE_RULE}
# END EDGE GATE

RewriteRule ^assets/.+$ - [E=IS_VITE_ASSET:1]

<IfModule mod_headers.c>
\tHeader always set Content-Security-Policy "default-src 'self'"
</IfModule>
"""


def arm(path: Path, token: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SCRIPT), str(path)],
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "EDGE_TOKEN": token},
        capture_output=True,
        text=True,
    )


@pytest.fixture
def staged(tmp_path: Path) -> Path:
    target = tmp_path / ".htaccess"
    target.write_text(HTACCESS_WITH_GATE)
    return target


def test_the_shipped_htaccess_matches_what_the_script_expects(tmp_path: Path) -> None:
    """The drift check the inline version could not have.

    If public/.htaccess changes its gate and the script is not updated to match,
    this fails here rather than at deploy time against production.
    """
    if "# BEGIN EDGE GATE" not in SHIPPED_HTACCESS.read_text():
        pytest.skip("the gate block lands with the enforcement PR; nothing to compare yet")

    target = tmp_path / ".htaccess"
    shutil.copy(SHIPPED_HTACCESS, target)

    result = arm(target, VALID_TOKEN)

    assert result.returncode == 0, result.stderr
    assert f"!^{VALID_TOKEN}$" in target.read_text()


def test_a_configured_token_arms_the_gate(staged: Path) -> None:
    result = arm(staged, VALID_TOKEN)

    assert result.returncode == 0, result.stderr
    assert "Edge gate armed." in result.stdout
    body = staged.read_text()
    assert f"!^{VALID_TOKEN}$" in body
    assert "@@EDGE_TOKEN@@" not in body
    assert "Content-Security-Policy" in body


def test_an_unset_token_strips_the_gate_and_fails_open(staged: Path) -> None:
    # A missing secret must leave the origin reachable, never a rule demanding a
    # header nobody can send.
    result = arm(staged, "")

    assert result.returncode == 0, result.stderr
    body = staged.read_text()
    assert "X-Origin-Token" not in body
    assert "@@EDGE_TOKEN@@" not in body
    assert "Content-Security-Policy" in body


@pytest.mark.parametrize("token", ["a", "short", "a" * 31])
def test_a_token_under_the_length_floor_is_refused(staged: Path, token: str) -> None:
    # A caller refused at the origin never reached the edge's rate limiting, so
    # the 403 is an unmetered oracle and the token's entropy is the control.
    result = arm(staged, token)

    assert result.returncode == 1
    assert "at least 32 characters" in result.stderr
    assert "@@EDGE_TOKEN@@" in staged.read_text(), "aborted before touching the file"


@pytest.mark.parametrize("token", ["abc$def" + "a" * 30, "tok en" + "a" * 30, "tökén" + "a" * 30])
def test_a_non_alphanumeric_token_is_refused(staged: Path, token: str) -> None:
    result = arm(staged, token)

    assert result.returncode == 1
    assert "alphanumeric" in result.stderr
    assert "@@EDGE_TOKEN@@" in staged.read_text()


@pytest.mark.parametrize(
    ("description", "removed"),
    [
        ("the [F] rule", GATE_RULE),
        ("the autodiscover exception", AUTODISCOVER_COND),
        ("the .well-known exception", WELL_KNOWN_COND),
    ],
)
def test_a_gutted_stanza_is_refused(staged: Path, description: str, removed: str) -> None:
    # Each of these leaves the placeholder's own line intact, so checking that
    # line alone would arm a gate refusing nothing. Dropping the rule is the
    # worst: the conditions then attach to the next RewriteRule in the file
    # rather than becoming inert.
    staged.write_text(staged.read_text().replace(removed + "\n", ""))

    result = arm(staged, VALID_TOKEN)

    assert result.returncode == 1, f"removing {description} was accepted"
    assert "not the expected block" in result.stderr
    assert VALID_TOKEN not in staged.read_text()


def test_a_weakened_rule_is_refused(staged: Path) -> None:
    staged.write_text(staged.read_text().replace(GATE_RULE, "RewriteRule ^ - [R=302]"))

    result = arm(staged, VALID_TOKEN)

    assert result.returncode == 1
    assert "not the expected block" in result.stderr


def test_a_second_placeholder_never_receives_the_token(staged: Path) -> None:
    # `sed` substitutes the first match on every LINE, so an extra placeholder
    # on a served header line would be given the real token while the
    # placeholder-survived check still passed.
    staged.write_text(staged.read_text() + '\nHeader always set X-Debug "@@EDGE_TOKEN@@"\n')

    result = arm(staged, VALID_TOKEN)

    assert result.returncode == 1
    assert "found 2" in result.stderr
    assert VALID_TOKEN not in staged.read_text(), "token reached the file despite the abort"


def test_a_lost_end_marker_is_caught_by_the_csp_check(staged: Path) -> None:
    # The range delete runs to EOF without the END marker, truncating the file.
    # The placeholder is gone either way and the file is still non-empty, so
    # only something from the far end of the file detects it.
    staged.write_text(staged.read_text().replace("# END EDGE GATE\n", ""))

    result = arm(staged, "")

    assert result.returncode == 1
    assert "lost its CSP" in result.stderr


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    result = arm(tmp_path / "nope.htaccess", VALID_TOKEN)

    assert result.returncode == 1
    assert "missing or empty" in result.stderr
