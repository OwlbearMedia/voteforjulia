"""Drift tests for the host-key pinning in both deploy workflows.

`appleboy`'s SSH and SCP actions do not verify the host key unless a
`fingerprint` is supplied, and an empty one is not an error: easyssh-proxy
selects `ssh.InsecureIgnoreHostKey()`. So an unpinned step is not a weaker
check, it is no check -- and nothing about the workflow looks wrong.

These assertions exist because a `workflow_run` deploy runs `main`'s copy of
the workflow, so a step added without a pin cannot be caught by deploying the
branch that adds it (docs/hosting.md). CI is the only place it is catchable
before production. See ADR-0023.
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
DEPLOY_WORKFLOWS = ("deploy-production.yml", "deploy-test.yml")

PINNED = "${{ secrets.SSH_HOST_FINGERPRINT }}"
GUARD_STEP = "Require a pinned host key before connecting"

# The single stored fingerprint is the host's ECDSA key, and that only stays
# correct while both actions keep asking for ECDSA first. They do it via
# different Go crypto versions -- drone-scp 1.6.14 pins x/crypto v0.17.0, which
# proposes `supportedHostKeyAlgos`; drone-ssh 1.8.2 pins v0.45.0, which proposes
# `defaultHostKeyAlgos`. Both happen to lead with ecdsa-sha2-nistp256, checked
# in the source rather than inferred. A bump can change that list, and the
# symptom is a failed production deploy after the merge, so re-derive the key
# type before raising these. Procedure in docs/hosting.md.
REVIEWED_VERSIONS = {
    "appleboy/ssh-action": "v1.2.5",
    "appleboy/scp-action": "v0.1.7",
}


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def connecting_steps(job: dict) -> list[dict]:
    return [s for s in job.get("steps", []) if s.get("uses", "").startswith("appleboy/")]


@pytest.fixture(params=DEPLOY_WORKFLOWS)
def workflow(request: pytest.FixtureRequest) -> dict:
    return load(request.param)


def test_every_step_that_connects_pins_the_host_key(workflow: dict) -> None:
    for name, job in workflow["jobs"].items():
        for step in connecting_steps(job):
            assert step["with"].get("fingerprint") == PINNED, (
                f"{name} / {step['name']}: connects without a pinned host key, "
                f"which silently means no host-key verification at all"
            )


def test_every_job_that_connects_guards_the_pin_before_connecting(
    workflow: dict,
) -> None:
    """An unset secret would leave the pins above resolving to empty strings.

    The pin and the guard are two halves of one control: the `fingerprint:`
    lines are what verifies the host, and the guard is what stops the deploy
    from proceeding unverified when the secret behind them is missing.
    """
    for name, job in workflow["jobs"].items():
        steps = job.get("steps", [])
        if not connecting_steps(job):
            continue
        guards = [i for i, s in enumerate(steps) if s.get("name") == GUARD_STEP]
        assert guards, f"{name}: connects to the host with no {GUARD_STEP!r} step"
        first_connection = next(
            i for i, s in enumerate(steps) if s.get("uses", "").startswith("appleboy/")
        )
        assert guards[0] < first_connection, (
            f"{name}: {GUARD_STEP!r} runs after the first connection, so an "
            f"unset fingerprint is caught only once it no longer matters"
        )


def test_the_guard_refuses_an_empty_fingerprint(workflow: dict) -> None:
    """Run the guard rather than recognising it by name.

    Matching the step name proves a step is there, which is not the property
    being relied on: strip the emptiness check, drop the `env` binding, or add
    `continue-on-error`, and a named step still sits in the job while an unset
    secret goes back to permitting unverified connections. Found by Copilot on
    #166 -- the assertion above located the guard by name and called that a
    test of it.

    The `run:` block is plain shell, so it can simply be executed both ways.
    """
    for name, job in workflow["jobs"].items():
        if not connecting_steps(job):
            continue
        guard = next((s for s in job["steps"] if s.get("name") == GUARD_STEP), None)
        assert guard is not None, f"{name}: no {GUARD_STEP!r} step"

        assert (guard.get("env") or {}).get("HOST_FINGERPRINT") == PINNED, (
            f"{name}: the guard does not read {PINNED}, so it would pass while "
            f"the value the pins resolve to is missing"
        )
        assert "if" not in guard and not guard.get("continue-on-error"), (
            f"{name}: the guard is skippable, which makes it decorative"
        )

        for label, env in (
            ("empty", {"HOST_FINGERPRINT": ""}),
            ("unset", {}),
        ):
            refused = subprocess.run(
                ["bash", "-c", guard["run"]],
                env={"PATH": "/usr/bin:/bin", **env},
                capture_output=True,
                text=True,
            )
            assert refused.returncode != 0, (
                f"{name}: the guard exits 0 on an {label} fingerprint, so the "
                f"deploy would continue with host-key verification disabled"
            )

        allowed = subprocess.run(
            ["bash", "-c", guard["run"]],
            env={"PATH": "/usr/bin:/bin", "HOST_FINGERPRINT": "SHA256:" + "a" * 43},
            capture_output=True,
            text=True,
        )
        assert allowed.returncode == 0, (
            f"{name}: the guard rejects a real fingerprint, which would stop "
            f"every deploy: {allowed.stderr.strip()}"
        )


def test_the_actions_are_the_versions_whose_host_key_order_was_checked(
    workflow: dict,
) -> None:
    for name, job in workflow["jobs"].items():
        for step in connecting_steps(job):
            action, _, version = step["uses"].partition("@")
            assert version == REVIEWED_VERSIONS[action], (
                f"{name} / {step['name']}: {action} moved to {version}. "
                f"Re-derive which host key the client negotiates before raising "
                f"this -- see the note above REVIEWED_VERSIONS and "
                f"docs/hosting.md"
            )


# A step that reaches the host without going through `appleboy`. Only `run:` is
# scanned: the `script:` of an appleboy step already executes on the host, so an
# `ssh` there is the host reaching somewhere else and none of this file's
# business.
#
# Matching only at the start of a line was the first version and was far too
# narrow -- `setup && ssh ...`, `cd x; ssh ...`, `ENV=v ssh ...` and
# `$(ssh ...)` all slipped past it (Copilot, #166). So the detector looks for
# the command in any *command position* instead: after a separator, a pipeline
# operator, a subshell or a command substitution, and through the prefixes that
# keep the following word a command. This is not a shell parser and does not
# try to be one; the forms it covers are pinned in RAW_SSH_FORMS below.
#
# Case-sensitive on purpose. The guard step's own message contains "every SSH
# and SCP step", and prose about SSH is common in these files -- an
# uppercase-insensitive match would flag both.
_COMMAND_POSITION = r"(?:^|[\n;&|(){}`]|\$\()"
_COMMAND_PREFIX = (
    r"(?:\s*(?:"
    r"[A-Za-z_][A-Za-z0-9_]*=[^\s;&|]*"  # FOO=bar ssh ...
    r"|command|env|exec|nohup|sudo|time|if|while|until|then|else|do|!"
    r"|timeout\s+\S+"
    r"|xargs(?:\s+-\S+)*"
    r")\s+)*"
)
RAW_SSH = re.compile(
    _COMMAND_POSITION + r"\s*" + _COMMAND_PREFIX + r"(?:ssh|scp|sftp|rsync)\s",
    re.MULTILINE,
)

# (fragment, should it be flagged) -- the forms an unpinned connection could
# plausibly be written in, and the near misses that must not cost a false
# alarm. Extend this rather than trusting the regex to be read correctly.
RAW_SSH_FORMS = [
    ("ssh host true", True),
    ("scp -P 50288 a user@host:b", True),
    ("rsync -e ssh dist/ host:/var/www/", True),
    ("setup && ssh host true", True),
    ("cd /tmp; ssh host true", True),
    ("command ssh host true", True),
    ("ENV=value ssh host true", True),
    ("timeout 30 ssh host true", True),
    ("if ssh host true; then echo ok; fi", True),
    ("out=$(ssh host uptime)", True),
    ("find . -print0 | xargs -0 scp -t host:", True),
    ("sudo ssh host true", True),
    ("# the deploy reaches the host over ssh", False),
    ("ssh-keygen -F '[host]:50288' -l", False),
    ('echo "unset; every SSH and SCP step would skip verification"', False),
    ("echo pushed", False),
]


@pytest.mark.parametrize("fragment,flagged", RAW_SSH_FORMS)
def test_the_raw_connection_detector_covers_the_shell_forms(fragment: str, flagged: bool) -> None:
    assert bool(RAW_SSH.search(fragment)) is flagged, fragment


# Anything else that looks like it opens a session. Matching the name is a
# heuristic and may catch an action that only loads a key rather than
# connecting; treat a hit as a prompt to decide which it is, not as a verdict.
CONNECTING_ACTION = re.compile(r"ssh|scp|sftp|rsync")
APPROVED_ACTIONS = ("appleboy/ssh-action", "appleboy/scp-action")


def test_nothing_reaches_the_host_outside_the_pinned_steps() -> None:
    """Every connection must be an `appleboy` step in a deploy workflow.

    The assertions above read `uses: appleboy/...` steps in two named files, so
    everything else that could open a session is invisible to all of them: a
    third workflow, an action from another publisher, or a hand-rolled `ssh` in
    a `run:` block -- **including one added to a deploy workflow itself**, which
    an earlier version of this test skipped over while claiming to be the broad
    check. Found by Copilot on #166.

    So the rule is stated over every workflow rather than over the two: a step
    that connects has to be one of the approved actions, and it has to live
    where the pin, guard and ordering assertions can see it.
    """
    offenders = []
    for path in sorted(WORKFLOWS.iterdir()):
        if path.suffix not in (".yml", ".yaml"):
            continue
        workflow = yaml.safe_load(path.read_text())
        for name, job in (workflow.get("jobs") or {}).items():
            for step in job.get("steps", []):
                where = f"{path.name} / {name}: {step.get('name') or step.get('uses')!r}"
                uses = step.get("uses", "")
                if RAW_SSH.search(step.get("run", "")):
                    offenders.append(f"{where} -- reaches the host from a `run:` block")
                elif uses.startswith(APPROVED_ACTIONS):
                    if path.name not in DEPLOY_WORKFLOWS:
                        offenders.append(f"{where} -- connects from outside the deploy workflows")
                elif CONNECTING_ACTION.search(uses):
                    offenders.append(f"{where} -- connects through an unapproved action")
    assert not offenders, (
        f"{offenders}: reaches the host without the pin, guard and ordering "
        f"that the rest of this file asserts"
    )


def test_the_first_connection_in_a_job_does_not_transfer_bytes(
    workflow: dict,
) -> None:
    """A first-connection failure must leave the host untouched.

    `scp-action` first means a failed handshake lands after the new source is
    on disk and before the install, prune and restart -- a half-applied deploy
    that stays quiet until something restarts the app. `ssh-action` first makes
    the same failure cost a red run. The check is the action rather than what
    the step does, because "changes nothing durable" is not readable from YAML;
    the steps this admits stage into scratch paths, which the swap and the
    prune are separately guarded against. See ADR-0023.
    """
    for name, job in workflow["jobs"].items():
        steps = connecting_steps(job)
        if not steps:
            continue
        assert steps[0]["uses"].startswith("appleboy/ssh-action"), (
            f"{name}: opens with {steps[0]['name']!r}, an upload -- a failed "
            f"handshake would leave the host half-deployed"
        )
