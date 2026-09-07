# 0023. Pin the SSH host key on every step of the deploy pipeline

**Status:** Accepted
**Date:** 2026-08-25

Amends [0020](0020-authenticate-the-origin-path.md), which pinned the one step
that carried a secret and recorded the other sixteen as a known gap, and closes
[#148](https://github.com/OwlbearMedia/voteforjulia/issues/148).

## Context

Both deploy workflows reach the host through `appleboy/ssh-action` and
`appleboy/scp-action`. Neither verifies the host key unless `fingerprint:` is
supplied, and **an empty one is not an error**: `easyssh-proxy` selects
`ssh.InsecureIgnoreHostKey()` when the field is blank, and `scp-action`'s own
input documentation states the default as _"skip verification"_. An unpinned
step is therefore not a weaker check. It is no check, and nothing about the
workflow looks wrong.

0020 pinned the `.htaccess` upload in each workflow, because that file carries
the edge token and is the only thing either workflow transfers that carries a
secret. That left 16 of 18 steps accepting whatever answered on the host and
port, and authenticating to it.

Those 16 carry no secret, so the exposure is integrity, not disclosure — and it
is quiet. They carry **what gets deployed**, and the commands that stage, prune,
restart and swap it. An impostor that intercepted the connection would receive a
deploy while the real host kept serving the previous release, and the `Verify`
jobs would not notice: they `curl` the public hostnames through Cloudflare, so a
site that is up but stale passes.

### What the scope argument actually cost

#148 framed scope as the open question — all 16, or only the steps that transfer
bytes, leaving the ones that merely run commands unpinned. The argument for
holding back was that a host key change would break every deploy at once, on
shared hosting where the box can be rebuilt without notice.

**That cost was already paid.** The `.htaccess` upload is pinned in both
workflows and runs early in each frontend deploy, so a rotated key already
breaks both frontend deploys today. Pinning the remaining steps in those jobs
adds no outage exposure that does not already exist. Only the two API deploy
jobs, which had no pinned step at all, gain any — and a pipeline whose frontend
half fails while its API half succeeds is not a working pipeline, it is a
half-applied release.

The rest of the scope argument goes the other way. "Every `appleboy` step has a
`fingerprint`" is an invariant a reviewer can check by eye and a test can
enforce; "the ones that transfer bytes are pinned" is a rule nobody can check
mechanically, and the unpinned remainder would still include the `rm -rf`, the
prune and the atomic swap.

### The key type is not what the obvious reading says

A single pinned SHA256 has to match whichever host key the client negotiates, so
the value cannot be scraped from the first line of `ssh-keyscan`. The host
offers RSA, ECDSA and Ed25519.

**The two actions run different Go binaries with different `x/crypto` versions**
— `scp-action@v0.1.7` is `drone-scp` 1.6.14 on v0.17.0; `ssh-action@v1.2.5`
downloads `drone-ssh` 1.8.2, on v0.45.0. Both propose `ecdsa-sha2-nistp256`
first, so one stored value serves every step, and the fingerprint
already in use is correct for the steps being added.

They agree by luck rather than by construction, and the reading that gets there
is not the obvious one. Modern `x/crypto` has **two** host-key lists.
`supportedHostKeyAlgos` is what the package implements and leads with
`rsa-sha2-256` in v0.45.0; `defaultHostKeyAlgos` is what `handshake.go` actually
proposes when `HostKeyAlgorithms` is unset, which `easyssh-proxy` never sets,
and that one leads with ECDSA. [hosting.md](../hosting.md#closing-the-direct-to-origin-path)
had recorded the first list, and taking it at face value would have meant
pinning an RSA fingerprint for `ssh-action` and failing every deploy in the
pipeline on the merge that shipped it. Corrected there, with the commands.

**Measured rather than left as a reading**, 2026-08-25, by running the exact
binary the action downloads against the production host — twice, because a run
that succeeds proves nothing on its own about whether the check was engaged:

| `drone-ssh` 1.8.2, pinned to | Result                                                 |
| ---------------------------- | ------------------------------------------------------ |
| the host's **ECDSA** key     | connected, ran the script                              |
| the host's **RSA** key       | `ssh: handshake failed: host key fingerprint mismatch` |

The second row is what every SSH step in the pipeline would have done on the
merge, had the earlier reading been carried into the pin. It is also what makes
the first row mean something: the fingerprint is being compared, not skipped.

## Decision

**Every SSH and SCP step in both deploy workflows pins the host key**, and each
deploy job refuses to start when `SSH_HOST_FINGERPRINT` is unset.

The guard is the other half of the control. Without it, removing the secret
turns all twenty pins back into `InsecureIgnoreHostKey()` with no error
anywhere —
the pins verify the host, and the guard is what stops the deploy from proceeding
unverified when the value behind them is missing. 0020's version of that guard
was conditional on the edge token being set, which covered the step whose
exposure 0020 introduced; it is now unconditional and present in all four deploy
jobs.

`SSH_HOST_FINGERPRINT` already existed as an environment secret in both `test`
and `production`, holding the same value: it is the same host either way, and a
host key fingerprint is not a credential.

**The first connection in each job is a step whose failure leaves the host
untouched.** Pinning changes what a failed handshake costs, and the two jobs
were not equally placed for it. `deploy-frontend` already opened with an
`ssh-action` that prepares a scratch directory, so a refused handshake stops it
with nothing done. `deploy-api` opened with the scp that uploads the API source
— and since `scp-action` runs the older, already-proven Go path, the exact
failure this pin could introduce is one where the upload succeeds and the step
after it does not. That leaves new source in `~/api` with dependencies
uninstalled, the prune skipped and no restart: quiet until something restarts
Passenger for an unrelated reason, and then booting new code against old
dependencies.

So `deploy-api` now opens with a connecting step that only confirms the app root
is there. It is not a formality — it converts a first-connection failure from
half-applied to a red run, for a rotated key, an unreachable host or anything
else that stops the first connection. The invariant is asserted in CI rather
than left to the next person reordering steps.

**[scripts/test_deploy_workflows.py](../../scripts/test_deploy_workflows.py)
enforces this in CI**, because a `workflow_run` deploy runs `main`'s copy of the
workflow — so a step added without a pin cannot be caught by deploying the
branch that adds it ([hosting.md](../hosting.md#deploy-workflow-changes-cannot-be-tested-from-a-pr)).
CI is the only place it is catchable before production. The tests assert that
every connecting step pins the fingerprint, that every job that connects guards
it before the first connection, that the guard actually refuses an empty value
— it is executed, not recognised by its step name, since a named step with its
emptiness check removed is not a guard — that the first connection in a job is
not an upload, and that the two actions are still the versions whose host-key
preference was measured.

One assertion is stated over every workflow rather than over the two, because
the others read `uses: appleboy/...` steps in two named files and are therefore
blind to any other way of opening a session — another publisher's action, or a
hand-rolled `ssh` in a `run:` block. The first version of it exempted the deploy
workflows from that scan, which left the evasion available in exactly the two
files the rest of this record is about; caught by Copilot on
[#166](https://github.com/OwlbearMedia/voteforjulia/pull/166), after a
`/code-review high` that had looked at the same function and improved its reach
elsewhere.

**A detector for hand-rolled commands is only as good as the shell forms it
knows about**, and the first two versions matched an ssh-family command only as
the first token on a line — so `setup && ssh …`, `cd x; ssh …`, `ENV=v ssh …`,
`timeout 30 ssh …` and `$(ssh …)` all passed. It now matches in any command
position: after a separator, a pipeline operator, a subshell or a command
substitution, and through the prefixes that keep the next word a command. It is
not a shell parser and does not try to be one, so the forms it covers are pinned
as a table of fragments with their expected verdicts, extended rather than
trusted to be read correctly from the regex. The match is case-sensitive because
the guard step's own message contains "every SSH and SCP step".

## Consequences

- **A host key rotation is now a total deploy outage rather than a partial
  one**, and the symptom is `ssh: handshake failed: ssh: host key fingerprint
mismatch` rather than anything mentioning rotation. The recovery is one secret
  update, in both environments; the procedure for deriving the new value —
  reading it over an already-trusted session rather than trusting a scan, which
  is trust-on-first-use — is in
  [hosting.md](../hosting.md#closing-the-direct-to-origin-path).
- **A Dependabot bump of either action can change the negotiated key type**, and
  the failure would land on the first deploy after the merge, which for
  `deploy-production.yml` is against production. The version assertion turns
  that into a CI failure on the Dependabot PR instead, where the fix is to
  re-derive the key type before raising the pin. It will fire on a routine bump
  and look like an obstacle; that is the point.
- **The action tag is not the client**, and only one of the two actions makes it
  so. `scp-action` is a Docker action carrying its binary in the image;
  `ssh-action` downloads `drone-ssh` at run time, defaulting to 1.8.2 at v1.2.5
  but accepting a `version:` input wired to `DRONE_SSH_VERSION`. One line in a
  `with:` block therefore swaps the client, and with it the x/crypto version
  that chooses the host key — no tag changes, and a bump-watching assertion sees
  nothing. Asserted separately, so the measured client is pinned by both links
  rather than by the visible one. Found by Copilot on
  [#166](https://github.com/OwlbearMedia/voteforjulia/pull/166); it is the same
  shape as the two findings above it, one layer further down.
- **The fingerprint is deployment state with no representation in the
  checkout**, joining the Cloudflare Transform Rule, the `monitoring/`
  definitions, the cPanel environment variables and `main`'s branch protection.
  Unlike those, it now has a checked-in consumer that fails loudly when it is
  absent — which is a weaker guarantee than syncing it, and a stronger one than
  the others have.
- **This closes the integrity gap, not an authentication one.** The SSH private
  key was never exposed by an unpinned step: an impostor host cannot recover it
  from a public-key handshake, and the passphrase decrypts the key on the
  runner. What was exposed was the deployed bytes and the commands run over the
  session.
- **The first execution of this change is against production**, like every
  deploy-workflow change. The pins reuse a value already proven by the pinned
  `.htaccess` upload on every successful deploy since 2026-08-18, so the only
  new question was whether `ssh-action` negotiates a different key type than
  `scp-action` — read from both binaries' source, then measured against the
  host, and asserted in CI.
