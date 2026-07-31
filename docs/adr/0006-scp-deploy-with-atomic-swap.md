# 0006. Deploy by scp from GitHub Actions, promoted by an atomic directory swap

**Status:** Accepted
**Date:** 2026-07-31 (recorded; frontend swap adopted after the incident described below)

## Context

Shared cPanel hosting ([0001](0001-shared-hosting-over-aws.md)) offers SSH and
nothing else. There is no registry to push an image to, no deploy hook, no
blue/green facility, and no way to atomically publish a bundle — the only
primitives are "copy files" and "rename things".

The naive version of this — scp `dist/**` straight into the live document root —
was what the test environment did originally, and it had two real consequences:

- **Visitors and tests could see a half-written site.** A deploy writes hundreds
  of files over seconds; during that window the HTML can be new while
  `.htaccess` is old or mid-write. That is a plausible cause of the intermittent
  Cypress "redirected more than 20 times" failures.
- **Nothing ever pruned the directory.** Every past deploy's hashed assets and
  sourcemaps accumulated. The test root reached 70M against production's 1.7M.

There is also no rollback in that model: the previous build is simply gone.

## Decision

Deploy from GitHub Actions over SSH, staging into a scratch directory and
promoting it with renames:

```
scp dist/**   →  ./public_html_next     (clean directory, plus .htaccess as its own step)
rm -rf public_html_prev
mv public_html public_html_prev         # this is the rollback
mv public_html_next public_html
```

Two renames on one filesystem, so the live root is briefly absent rather than
inconsistent. The test environment does the same with
`public_html_test{,_next,_prev}`.

The API deploys by uploading `api/**`, installing dependencies through the
CloudLinux selector, and then touching `./api/tmp/restart.txt` — in that order,
so a failed install leaves the old worker serving the old code.

Each half is split into discrete jobs (`Build → Deploy → Verify`) linked by
`needs:`, so a transient failure in verification can be rerun without rebuilding
or re-uploading. Production is pinned to `workflow_run.head_sha` — the exact
commit CI verified — not branch HEAD.

## Consequences

- **Publishing is a sub-second rename**, so no visitor sees a mixed build, and
  files deleted in the new build genuinely disappear instead of lingering.
- **Rollback is one command**: swap `public_html` and `public_html_prev` back.
  Cheaper and faster than re-running a deploy, and it works when GitHub is down.
- **Disk holds three copies** of the frontend during a deploy. At ~2M, this is
  free.
- **`.htaccess` needs its own scp step**, because the `dist/**` glob does not
  match dot-prefixed files. Forget it and the site loses every security header
  and its clean-URL rules at once.
- **The deploy workflows cannot be tested from a PR.** GitHub always runs the
  default branch's copy of a `workflow_run`-triggered workflow, so a merge is the
  _first_ execution of any change to them — and for production, that first
  execution is against production. The failure mode is silent success. Mitigation
  and verification commands are in
  [../hosting.md](../hosting.md#deploy-workflow-changes-cannot-be-tested-from-a-pr).
- **Dependency installs must be checked by hand.** The CloudLinux selector exits
  0 even when pip fails, so both workflows parse the JSON `result` field and
  `exit 1` themselves.
- **SSH credentials live in GitHub secrets**, which makes the repo's secrets the
  keys to the host. Dependabot PRs, which cannot read secrets, are skipped by the
  gate job rather than failing.

## Alternatives considered

- **rsync over the live root with `--delete`.** Solves the accumulation problem
  and is far more efficient over the wire, but not the atomicity one: there is
  still a window where the site is a mix. Also not reliably present on shared
  hosts.
- **Deploy on the host with a `git pull`.** Attractive, and gives rollback for
  free. Rejected because the frontend needs a Node/pnpm build the host cannot
  run, so the build has to happen in CI and the artifact has to be shipped.
- **A symlinked `current/` release directory** (the Capistrano shape). Strictly
  better in theory — instant swap, N releases retained. Rejected because the
  document root is cPanel-managed and pointing it at a symlink is host
  configuration that can be silently reset by the panel; two renames need no
  cooperation from cPanel at all.
- **FTP deploy actions.** Slower, less reliable, and no better on atomicity.
