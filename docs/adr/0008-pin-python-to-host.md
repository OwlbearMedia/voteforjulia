# 0008. Pin the Python version to the host's interpreter, in one file

**Status:** Accepted
**Date:** 2026-07-31 (recorded; adopted after the 3.9/3.11 gap described below)

## Context

The API runs in a cPanel-managed virtualenv created by CloudLinux's Python
selector, not by us. Changing its interpreter destroys and rebuilds the venv, so
the running version is a property of the host, discovered rather than chosen.

For a long time CI tested on a modern Python while the host's venvs ran 3.9, and
nothing noticed. Then `google-auth` was pinned past 2.51, whose `Requires-Python`
is `>=3.10` — making [api/requirements.txt](../../api/requirements.txt)
**unsatisfiable on the host**. It went unnoticed for as long as nothing on the
deploy path actually read the file. CI was green throughout, because CI was
testing a Python the host did not run.

The general problem: any version number that exists in more than one place will
eventually disagree with itself, and this one disagrees silently.

## Decision

Declare the version **once**, in [.python-version](../../.python-version), and
have everything else read it:

- CI's `setup-python` reads that file, so the test interpreter cannot drift from
  the host's.
- `ruff.toml`'s `target-version` tracks it.
- The README states the requirement as "3.11" rather than "3.11 or newer",
  because newer is also wrong.

Requirements are pinned with `==`, so CI installs the exact versions production
runs. Before pinning past a dependency's major jump, check its
`Requires-Python` against the venv.

Deploys install through the CloudLinux selector rather than a direct `pip`,
because the selector resolves the virtualenv from the app's own config and keeps
working across interpreter changes.

## Consequences

- **CI tests what production runs.** That is the whole point, and it is the
  thing that was missing when the gap hid.
- **A dependency upgrade can be blocked by the host**, not by us. That is a real
  constraint on this project, and the honest response is to notice it in a PR
  rather than at deploy time.
- **Upgrading Python is a deliberate operation**, not a version bump: it
  destroys and rebuilds the venv, so the app has no packages for the duration.
  Do `api_test` first and verify. Commands are in
  [../hosting.md](../hosting.md#mind-the-interpreter-floor).
- **Old version directories linger.** Switching interpreters leaves the retired
  tree on disk, so a `~/virtualenv/api/*/bin/pip` glob is ambiguous — another
  reason never to address the venv directly.
- **`.python-version` is load-bearing configuration**, not a convenience for
  pyenv users. Deleting it breaks CI's interpreter selection.

## Alternatives considered

- **Pin the version in CI's workflow file.** What was effectively happening
  before, and exactly how the 3.9/3.11 gap survived: two numbers, one of them
  invisible.
- **Support a range of Python versions.** Reasonable for a library, meaningless
  here — there is exactly one production interpreter and testing on others buys
  nothing.
- **Run the API in a container so we choose the runtime.** Solves this decision
  entirely, and is unavailable on shared hosting
  ([0001](0001-shared-hosting-over-aws.md)). It is one of the real costs of that
  choice.
- **Vendor dependencies into the repo.** Sidesteps the install step but not the
  interpreter floor, and makes upgrades worse.
