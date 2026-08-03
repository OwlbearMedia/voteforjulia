# 0015. Gate CI on performance budgets

**Status:** Accepted
**Date:** 2026-08-02

## Context

Two build steps exist purely to protect the first paint: the `onFinished` hook
in [vite.config.ts](../../vite.config.ts) inlines every stylesheet into each
prerendered document, and `manualChunks` splits vendor and `gtag` code out of the
main bundle ([architecture.md](../architecture.md#frontend)). Both were added
deliberately, and until now nothing checked that either still worked.

That is the actual risk, and it is not hypothetical. Every mechanism here fails
_silently_ and in a direction that looks like nothing happened:

- A dependency added for one page is a static import away from landing in the
  entry chunk, where every route pays for it.
- The inlining hook matches emitted CSS with a regex over the built HTML. A Vite
  upgrade that changes the `<link>` markup would stop it matching, and the build
  would still succeed — with a render-blocking request restored on every page.
- `manualChunks` matches on `node_modules/...` path fragments. A package that
  moves or gets renamed drops out of the vendor chunk without any error.

None of this shows up in review, because none of it changes a line that a
reviewer reads. It shows up as a number, and only if something reads the number.

The runtime side of this is already covered — New Relic Browser reports real
user timings ([ADR-0011](0011-browser-side-observability.md), superseded in part
by [0013](0013-server-side-apm.md)) — but that is detection after deploy, on a
site where a bad week is measured in the days before an election. Field data
also cannot tell you _which commit_ did it. Catching it pre-merge is a different
job, and it needs a different tool.

There is also a second reader. This repo is a portfolio piece: the reasoning in
`docs/` and the checks in CI are deliverables, and "we assert the performance
work stays done" is worth more than the performance work sitting there
unguarded.

## Decision

Add a `perf-frontend` job to CI that builds the site and runs two checks
against the real output, both able to fail the build.

**A bundle size budget** ([`perf-budgets.json`](../../perf-budgets.json),
checked by [`scripts/check-bundle-budget.mjs`](../../scripts/check-bundle-budget.mjs)).
The budgeted unit is gzipped first load per route: the document, CSS already
inlined into it, plus the entry module and its preloaded chunks. Every route in
`dist/` must have an entry — an unbudgeted route is a failure, not a skip.
Third-party scripts in the initial load are reported but not counted.

**Lighthouse CI** ([`lighthouserc.cjs`](../../lighthouserc.cjs)) over `dist/`
served directly, three runs per route, asserting on category scores and the four
lab metrics. Audits that would grade the local static server rather than the
site — cache headers, CSP, HTTP/2, canonical URLs — are switched off, and
third-party weight is a warning rather than an error.

Every threshold is set just past what `main` measured on the day this landed, so
the checks fail on regression and never on the status quo. The full numbers and
the rules for moving one are in [performance.md](../performance.md).

Bundle analysis is opt-in on the same build: `pnpm analyze` sets `ANALYZE=1`,
which adds `rollup-plugin-visualizer`. It writes to `bundle-analysis/`, never
into `dist/`, and CI uploads it with the Lighthouse reports as an artifact.

## Consequences

**A blown budget blocks a deploy.** `deploy-production.yml` triggers on the CI
workflow concluding successfully, so this job gates releases exactly as the test
jobs do. That is the intent — but it means an accepted size increase has to land
together with its budget bump, not in a follow-up.

**The thresholds need maintenance, and neglecting them is the failure mode.**
Headroom that is never tightened after an improvement turns a ratchet into a
rubber stamp. This is written into `performance.md` and the config comments
because it is the only part of the design that depends on a human.

**The baseline pins two known defects rather than hiding them.** Accessibility
sits at 0.90 — failing contrast on shared links and a skipped heading level —
and the assertion is set to 0.90, not 1. The gate stops it getting worse and is
honest that it is not currently green. Both are documented with the fix that
should raise the threshold.

**CI gets slower.** Twenty-four Lighthouse runs plus a full build add several
minutes. The job runs in parallel with the existing two, so wall-clock cost is
bounded by this job rather than added to the others.

**Lighthouse in CI is not a substitute for field data.** It is emulated mobile
on a runner, with simulated throttling and real third-party requests. It answers
"did this commit make it worse", not "how fast is it for voters in Mankato" —
that stays New Relic's job ([monitoring.md](../monitoring.md)).

## Alternatives considered

**Report the numbers without failing the build.** Rejected as the primary
mechanism for the reason the checks exist at all: everything being guarded here
degrades silently, and a summary nobody is required to read is exactly as good
as no check. The compromise kept is narrower — metrics we do not control
(third-party weight, unused JS) warn, everything we own errors.

**Compare each PR against a stored baseline from `main` and fail on any delta.**
Better signal in principle, and rejected on cost: it needs baseline storage,
cache plumbing, and a story for what happens when `main` legitimately moves.
Absolute thresholds tightened by hand get most of the value with none of the
infrastructure, on a repo with one contributor.

**A hosted Lighthouse CI server.** Gives history and PR comments. Not worth a
service to run and pay for; `target: 'filesystem'` plus a CI artifact covers the
"why did it fail" case, which is the one that actually comes up.

**`vite preview` instead of LHCI's static server.** No benefit — it is another
dev server that is also not LiteSpeed, and it would need the route list
maintained by hand rather than discovered from `dist/`.

**Lighthouse against the deployed test environment**
([ADR-0007](0007-shared-test-environment.md)) instead of a local build. That
would measure the real host, headers and TLS, and it was tempting. Rejected
because it moves the check after the deploy — the point is to fail the PR — and
because the test environment is shared, so its numbers depend on who else is
using it.

**Python API benchmarks alongside this.** The API's two endpoints are dominated
by SMTP and the Sheets API, so a benchmark with those mocked would measure
almost nothing, and one without them would measure someone else's network.
Server-side timing is already covered by APM ([ADR-0013](0013-server-side-apm.md)).
