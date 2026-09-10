---
name: code-review
description: Repository-specific checks for reviewing a pull request or diff in this campaign site. Covers the cross-file invariants a diff does not show — the Content-Security-Policy governing every third-party origin, per-route performance budgets, ImageKit image dimensions, deploy ordering, and the repository settings that must not be proposed.
license: MIT
---

# Reviewing this repository

A prerendered Vue 3 site (vite-ssg, Tailwind v4) and a small Flask API, both
deployed as cPanel apps on one shared LiteSpeed host. No container runtime and
no server-side rendering.

Submissions have no database — email and a Google Sheet are the system of record
([ADR-0004](../../../docs/adr/0004-no-database.md)). The API does keep
operational state, though: every rate-limit tier counts in SQLite under the
app's `tmp/`
([ADR-0024](../../../docs/adr/0024-count-every-rate-limit-tier-in-sqlite.md)),
so a change there carries locking, schema and fail-open consequences that the
rest of the codebase does not have.

Most defects that reach production here are not wrong lines in the diff. They
are a second file the change should have touched — usually in a different
language, with nothing in the diff pointing at it. The sections below are those
files. [docs/architecture.md](../../../docs/architecture.md) is the map.

## If the change adds a third-party origin

Any new `<iframe>`, `<script src>`, stylesheet, webfont, image host, or fetch
target needs a matching directive in the Content-Security-Policy in
[public/.htaccess](../../../public/.htaccess) — `frame-src`, `script-src`,
`style-src`, `font-src`, `img-src`, `connect-src`. A remotely hosted webfont
needs two: `style-src` for the stylesheet and `font-src` for the files it then
pulls, which is why `rsms.me` appears in both.

**This fails in production only.** The dev server sends no CSP, so an embed
missing from the policy works on every developer machine and is blocked for
every visitor.

One directive is covered:
[tests/unit/embedOrigins.spec.ts](../../../tests/unit/embedOrigins.spec.ts)
fails if a static `<iframe>` anywhere under `src/` has an origin the
`frame-src` allowlist does not name, and fails on an iframe whose `src` is
bound, because it cannot resolve one. `script-src`, `font-src`, `img-src` and
`connect-src` have no such test — check those by hand.

The header is applied at the edge, so it can only be confirmed with `curl -sI`
or devtools against the deployed test site. See
[ADR-0010](../../../docs/adr/0010-edge-policy-in-htaccess.md).

## If the change renders an image

Content imagery goes through ImageKit's `<Image>` component. Small static
assets — icons, favicons, the social banner, `src/assets/sprout.png` — stay in
the repository and render as a native `<img>` or a CSS background. That split is
[ADR-0012](../../../docs/adr/0012-imagekit-for-images.md), so an icon change
using neither of the rules below is not a defect. For the ImageKit path:

- `width` and `height` must be the asset's **real pixel size**. They reserve the
  box before the image loads, so a value copied from a differently shaped asset
  shifts the page when it arrives.
- A srcset candidate wider than the asset is wrong. ImageKit's `c-at_max` never
  upscales, so the candidate returns the asset unchanged while telling the
  browser it is larger — costing a high-DPR screen the sharper choice it thought
  it was making. Cap `image-breakpoints` at the asset's own width;
  `logoBreakpoints` in
  [src/lib/endorsements.ts](../../../src/lib/endorsements.ts) does this for the
  endorsement logos, and is the pattern to follow for a new list of images.

The assets are public URLs under `https://ik.imagekit.io/voteforjulia`, so their
dimensions can be measured rather than assumed.

## If the change adds a page or route

Adding a page means touching a fixed set of files, and missing one fails a test
somewhere unrelated. The checklist is in
[docs/conventions.md](../../../docs/conventions.md#adding-a-page).

The entry that fails furthest from the change is
[perf-budgets.json](../../../perf-budgets.json). The budget script exits 1 on a
built route with no entry rather than skipping it, so a missing budget turns up
in the performance job rather than in the frontend tests — deliberately, so that
a new page cannot opt itself out of the budget by existing.

## If the change is applied at deploy time

For anything templated, staged, or substituted during deployment, say **which
change has to be on `main` first**, and what the half-applied state does.

Deploy workflows start on `workflow_run` and therefore run `main`'s copy of the
workflow, not the branch's. A branch can be entirely self-consistent and still
be undeployable in the order it is being merged — this shipped a placeholder
`.htaccess` once, and 403'd the whole test site. See
[docs/hosting.md](../../../docs/hosting.md).

## If the change explains itself in a comment

Comments here are pointers; the reasoning lives in `docs/`. Review the claim
rather than the prose. A comment that overstates what the code does is worse
than no comment, because the next reader believes it — so check every path the
sentence covers, not the one it was written for.

## Tests

A test named for a class — "every", "any", "no other" — is checked by its name
rather than its body by whoever reads it next. Ask whether the test would still
pass if the thing it names were gutted, and whether a matcher standing in for a
concept pins the near misses that must not fire as well as the cases that must.

Anything that transforms user text — a name, an address, a message — belongs in
`TEXT_TRANSFORMERS` in
[api/test_text_corpus.py](../../../api/test_text_corpus.py). That registration
is the whole interface: one line inherits normalisation-invariance and
idempotence across every script in the corpus. New cases go in the corpus when
real input breaks something, not in one caller's test file.

## Do not suggest

- **Making a deploy workflow's check required** — every job in
  `deploy-production.yml` and `deploy-test.yml`, such as `Build frontend`,
  `Deploy frontend` and `Verify Python API`. They are triggered by
  `workflow_run` when a CI run completes, and a `workflow_run` job's check
  never reports on the pull request's head, so requiring one leaves every pull
  request waiting indefinitely with nothing displayed to explain it.
- **Requiring approvals, or `codecov/patch`.** One maintainer has write access
  and GitHub does not allow approving your own pull request, so a required
  approval makes every PR unmergeable. Codecov runs with `continue-on-error` and
  does not run at all for Dependabot.
- **A Python version other than 3.11.** [.python-version](../../../.python-version),
  the cPanel virtualenv and `ruff.toml`'s `target-version` all track each other.
- **Cutting scope for being more than a site this size needs.** The ADRs,
  budgets, spec drift tests and monitoring are deliberate.

## Where the reasoning lives

| Question                                     | File                                                          |
| -------------------------------------------- | ------------------------------------------------------------- |
| How does the whole thing fit together?       | [docs/architecture.md](../../../docs/architecture.md)         |
| Why was this decided?                        | [docs/adr/](../../../docs/adr/)                               |
| How do I add a page, a style, an icon?       | [docs/conventions.md](../../../docs/conventions.md)           |
| What breaks on this host?                    | [docs/hosting.md](../../../docs/hosting.md)                   |
| What budget did this blow, and can it move?  | [docs/performance.md](../../../docs/performance.md)           |
| What watches production?                     | [docs/monitoring.md](../../../docs/monitoring.md)             |
| Why does the CSP have those entries?         | [docs/donate-integration.md](../../../docs/donate-integration.md) |
