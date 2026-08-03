# Performance budgets

What CI measures about the built site, where the thresholds live, and how to
move one without quietly deleting the signal. The decision to gate on this is
[ADR-0015](adr/0015-performance-budgets-in-ci.md); the runtime side — what New
Relic watches once the site is live — is [monitoring.md](monitoring.md).

## The two checks

Both run in the `perf-frontend` job in
[ci.yml](../.github/workflows/ci.yml), against a real `pnpm build`.

| Check              | Command                | Config              | Measures                                           |
| ------------------ | ---------------------- | ------------------- | -------------------------------------------------- |
| Bundle size budget | `pnpm perf:budget`     | `perf-budgets.json` | Bytes on the wire for a cold visit to each route   |
| Lighthouse CI      | `pnpm perf:lighthouse` | `lighthouserc.cjs`  | Lab metrics and category scores on emulated mobile |

`pnpm perf` runs both. Neither builds first — run `pnpm build` (or `pnpm
analyze`) yourself, so a slow rebuild isn't hidden inside a check you're
iterating on.

## Bundle size budget

The number budgeted is **first load, gzipped**: the prerendered document plus
the JavaScript the browser needs before it can hydrate. Concretely, per route:

- the `.html` file, which already contains all the CSS — the `onFinished` hook
  in [vite.config.ts](../vite.config.ts) inlines it, so the stylesheet's bytes
  are inside this number and are not counted twice;
- the entry `<script type="module">` and every `<link rel="modulepreload">`
  Vite emits beside it. That set is the initial payload by construction: route
  chunks Vite does _not_ preload are fetched on navigation and are correctly
  excluded.

Sizes are gzipped because LiteSpeed compresses text responses
([public/.htaccess](../public/.htaccess)); budgeting raw disk bytes would be
budgeting a number no visitor experiences.

Third-party scripts in the initial load — today only Donorbox on `/donate`
([donate-integration.md](donate-integration.md)) — are **listed in the report
but not counted**. Their size is not ours to control, and a build that fails
because someone else shipped a bigger widget is a build that gets ignored.

### What fails the check

Four things, all of them errors:

- **over budget** — the route exceeds its number in `perf-budgets.json`;
- **no budget** — a route in `dist/` has no entry. Adding a page is already a
  checklist ([conventions.md](conventions.md#adding-a-page)); this makes the
  budget part of it non-optional, because the alternative is that a new page
  opts itself out of the thing meant to watch it;
- **stale budget** — an entry names a route that no longer exists, which reads
  as coverage that isn't there;
- **missing asset** — a document references a chunk that isn't in `dist/`.
  That's a build bug, not a size problem.

### Moving a budget

Budgets are set just above what `main` measures, so headroom is small on
purpose. When a change genuinely needs more room, **raise the number in the same
commit as the change and say why in the message.** A budget bumped in its own
follow-up commit is indistinguishable from a budget bumped to make CI shut up,
and the git history is the only record of which one it was.

Before raising it, look at where the bytes went:

```sh
pnpm analyze   # ANALYZE=1 pnpm build
open bundle-analysis/stats.html
```

The treemap attributes every byte in every client chunk to a module, with gzip
and brotli sizes. It is written outside `dist/` deliberately — anything in
`dist/` is deployed verbatim, and a page listing every module path in the app is
not something to publish. CI uploads it as the `performance-reports` artifact on
every run.

## Lighthouse CI

Runs against `dist/` served by LHCI's own static server, so what it measures is
byte-for-byte what deploys — no `vite preview` in between. Three runs per route,
asserted on the median.

Two things about the URLs are worth knowing:

- They are `/meet-julia.html`, not `/meet-julia`. Extensionless URLs are a
  LiteSpeed rewrite, not a property of the files, and the rewrite changes
  nothing that Lighthouse measures.
- Routes are **auto-discovered** from `dist/`, so a new page is audited as soon
  as it is built. This needs `maxAutodiscoverUrls: 0` in the config: the default
  is 5, and it drops the rest alphabetically without saying so. If you ever see
  fewer routes in the output than exist, that setting is why.

### Audits that are switched off

Four, all for the same reason — LHCI's static server is not the host, so these
would grade the test harness rather than the site:

| Audit                 | Why it's off                                                        |
| --------------------- | ------------------------------------------------------------------- |
| `uses-long-cache-ttl` | Cache-Control comes from `.htaccess`; the dev server sets none      |
| `csp-xss`             | The CSP is an edge header, applied by LiteSpeed                     |
| `uses-http2`          | localhost is HTTP/1.1                                               |
| `canonical`           | Canonicals point at voteforjulia.com, so they always "fail" locally |

`third-party-summary`, `unused-javascript`, `legacy-javascript` and
`unminified-javascript` are set to **warn**, not error. They are dominated by
GA4, the New Relic browser agent and Donorbox, which change size without any
commit here — worth seeing in the log, wrong to fail a build on.

### The thresholds are a ratchet, not a target

Every number in `lighthouserc.cjs` is set just past what `main` measured on
2026-08-02, so the build fails when a change makes things worse and never fails
for the state already shipped. Baseline medians across all eight routes:

| Metric         | Observed      | Threshold |
| -------------- | ------------- | --------- |
| Performance    | 0.93 – 0.95   | ≥ 0.92    |
| Accessibility  | 0.90          | ≥ 0.90    |
| SEO            | 1.00          | ≥ 1.00    |
| Best practices | 1.00          | ≥ 1.00    |
| FCP            | 1.75 – 1.90 s | ≤ 2.2 s   |
| LCP            | 2.75 – 3.03 s | ≤ 3.4 s   |
| TBT            | 11 – 13 ms    | ≤ 200 ms  |
| CLS            | 0             | ≤ 0.05    |

**When a fix improves one of these, tighten the number in the same commit.**
Otherwise the headroom silently becomes the new normal, which is how a ratchet
turns into a rubber stamp.

TBT has the widest headroom by far because it is the metric most sensitive to
how loaded the runner is. The rest are stable under simulated throttling, which
normalises the network and is why a laptop and a CI runner produce comparable
numbers at all.

### Known failures pinned by the baseline

The accessibility floor is **0.90, and that is not a passing grade** — it is
where the site is. Three real defects hold it there, all in shared markup so
they appear on every route:

- **Contrast.** Link text `#0070f3` on the `#eff9eb` background is 4.21:1, under
  the 4.5:1 WCAG AA needs at 16px.
- **Links identified by colour alone.** The same links sit at 2.06:1 against
  surrounding body text, under the 3:1 minimum, with no underline to fall back on.
- **Heading order.** The events widget emits an `<h3>` with no `<h2>` above it.

Fixing these should come with raising `categories:accessibility` to `1` in the
same commit. Until then the floor stops it getting worse, which is the most a
newly-added gate can honestly claim.

Separately, LCP is dominated by the header logo fetched from ImageKit
([ADR-0012](adr/0012-imagekit-for-images.md)). It already has `fetchpriority="high"`
and `loading="eager"`; the remaining time is the connection to a third-party
origin on a throttled mobile profile.

## Running it locally

```sh
pnpm build                # or: pnpm analyze, to also get the treemap
pnpm perf                 # both checks
pnpm perf:budget          # bundle sizes only — fast
pnpm perf:lighthouse      # Lighthouse only — a few minutes
```

Lighthouse needs a Chrome installation for `chrome-launcher` to find; on the
`ubuntu-latest` runner one is preinstalled, which is why CI has no browser setup
step. Reports land in `.lighthouseci/` — open the `.report.html` files for the
full audit, which is far more useful than the assertion output when something
fails.
