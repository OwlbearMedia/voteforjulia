---
name: code-review
description: Repository-specific checks for reviewing a pull request or diff in this campaign site. Covers the cross-file invariants a diff does not show — the Content-Security-Policy governing every third-party origin, per-route performance budgets, ImageKit image dimensions, deploy ordering, and the repository settings that must not be proposed.
license: MIT
---

# Reviewing this repository

A prerendered Vue 3 site (vite-ssg, Tailwind v4) and a small Flask API, both
deployed as cPanel apps on one shared LiteSpeed host. No database, no container
runtime, no server-side rendering.

Most defects that reach production here are not wrong lines in the diff. They
are a second file the change should have touched — usually in a different
language, with nothing in the diff pointing at it. The sections below are those
files. [docs/architecture.md](../../../docs/architecture.md) is the map.

## If the change adds a third-party origin

Any new `<iframe>`, `<script src>`, webfont, image host, or fetch target needs a
matching directive in the Content-Security-Policy in
[public/.htaccess](../../../public/.htaccess) — `frame-src`, `script-src`,
`font-src`, `img-src`, `connect-src`.

**This fails in production only.** The dev server sends no CSP, so an embed
missing from the policy works on every developer machine and is blocked for
every visitor. Nothing in the test suite connects the two: the markup and the
policy are different languages in different directories, and neither mentions
the other.

The header is applied at the edge, so it can only be confirmed with `curl -sI`
or devtools against the deployed test site. See
[ADR-0010](../../../docs/adr/0010-edge-policy-in-htaccess.md).

## If the change renders an image

Images go through ImageKit's `<Image>` component.

- `width` and `height` must be the asset's **real pixel size**. They reserve the
  box before the image loads, so a value copied from a differently shaped asset
  shifts the page when it arrives.
- A srcset candidate wider than the asset is wrong. ImageKit's `c-at_max` never
  upscales, so the candidate returns the asset unchanged while telling the
  browser it is larger — costing a high-DPR screen the sharper choice it thought
  it was making. Cap `image-breakpoints` at the asset's own width.

The assets are public URLs under `https://ik.imagekit.io/voteforjulia`, so their
dimensions can be measured rather than assumed.

## If the change adds a page or route

Adding a page means touching a fixed set of files, and missing one fails a test
somewhere unrelated. The checklist is in
[docs/conventions.md](../../../docs/conventions.md#adding-a-page). The one with
no test to remind you is [perf-budgets.json](../../../perf-budgets.json): CI
fails a route with no budget entry rather than skipping it, deliberately, so a
new page cannot opt itself out of the budget by existing.

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

For user text, draw inputs from
[api/test_text_corpus.py](../../../api/test_text_corpus.py) and add to it, so
the corpus grows in one place instead of per caller.

## Do not suggest

- **Making a deploy workflow's check required** — every job in
  `deploy-production.yml` and `deploy-test.yml`, such as `Build frontend`,
  `Deploy frontend` and `Verify Python API`. They run on `workflow_run` for
  pushes and never report on a PR head, so requiring one leaves every pull
  request waiting indefinitely with no error displayed.
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
