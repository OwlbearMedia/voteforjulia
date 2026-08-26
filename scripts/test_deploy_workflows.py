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


# A step that reaches the host without going through `appleboy`. Matches an ssh
# family command at the start of a line in a `run:` block, so prose and flags
# that merely contain the word do not trip it.
RAW_SSH = re.compile(r"^\s*(?:ssh|scp|sftp|rsync)\s", re.MULTILINE)


def test_no_other_workflow_connects_to_the_host() -> None:
    """Pinning the deploys is only the whole pipeline while they are the only
    things that connect.

    Deliberately broader than the assertions above: those read parsed steps in
    two named files, so a third workflow -- or a hand-rolled `ssh` in a `run:`
    block -- would be invisible to every one of them, and this file would keep
    passing while the gap it exists for reopened.
    """
    offenders = []
    for path in sorted(WORKFLOWS.iterdir()):
        if path.suffix not in (".yml", ".yaml") or path.name in DEPLOY_WORKFLOWS:
            continue
        workflow = yaml.safe_load(path.read_text())
        for name, job in (workflow.get("jobs") or {}).items():
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                run = step.get("run", "")
                if any(k in uses for k in ("ssh-action", "scp-action")):
                    offenders.append(f"{path.name} / {name}: uses {uses}")
                elif RAW_SSH.search(run):
                    offenders.append(f"{path.name} / {name}: {step.get('name')!r} runs ssh")
    assert not offenders, (
        f"{offenders} reaches the host but is not covered by the assertions in this file"
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
