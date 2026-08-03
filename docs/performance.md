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

### What fails the build, and why it is not everything

**What fails is decided by measured stability on the CI runner, not by
importance.** These were bit-identical across all 24 runs of the first CI
execution (8 routes × 3), so any change in them is a change we made:

| Enforced       | Observed in CI | Threshold |
| -------------- | -------------- | --------- |
| Accessibility  | 1.00 – 1.00    | ≥ 1.00    |
| SEO            | 1.00 – 1.00    | ≥ 1.00    |
| Best practices | 1.00 – 1.00    | ≥ 1.00    |
| CLS            | 0.000 – 0.000  | ≤ 0.05    |

Every timing metric, by contrast, ran past its threshold on at least one of
those 24 runs. These **warn**, and do not fail the build:

| Advisory    | Observed in CI | Warns above |
| ----------- | -------------- | ----------- |
| Performance | 0.49 – 0.96    | < 0.90      |
| FCP         | 1362 – 3951 ms | > 2200 ms   |
| LCP         | 2579 – 7530 ms | > 3600 ms   |
| TBT         | 132 – 566 ms   | > 400 ms    |

Those spreads are the runner, not the site. **TBT measured 11–13 ms on a laptop
and 132–566 ms in CI on identical bytes** — the numbers in this table replaced
a set calibrated locally, which is the mistake worth not repeating: a threshold
is only meaningful in the environment that will enforce it. LHCI asserts on the
median of three, so the first CI run passed with a 0.49 outlier and a 566 ms
outlier both outvoted; a threshold that survives on that is not a gate.

A job that fails randomly gets re-run until it is green. That is worse than one
that warns, because it looks like enforcement while training everyone to bypass
it. So the timing metrics stay visible in the summary and the artifact, and the
deterministic half of this gate does the actual gating.

**Promoting an advisory metric to enforced means removing its variance, not
widening its number.** For LCP that is the ImageKit logo fetch
([ADR-0012](adr/0012-imagekit-for-images.md)) — a `preconnect` to
`ik.imagekit.io`, or serving the logo from the origin. For TBT and the
performance score it is CPU contention on a shared runner, which is harder; more
runs would buy a sturdier median at roughly 13 minutes per PR.

**The bundle budget is the check that carries the weight here.** It is
byte-exact and showed zero variance between laptop and runner, and it is what
actually guards the chunking and CSS-inlining work
([ADR-0015](adr/0015-performance-budgets-in-ci.md)). When something in this doc
has to be trusted, trust that one.

**When a fix improves an enforced number, tighten it in the same commit.**
Otherwise the headroom silently becomes the new normal, which is how a ratchet
turns into a rubber stamp.

### Why the link colour is what it is

Accessibility is 1.00, but it started at 0.90, and the three defects that held it
there are worth recording because two of them are properties of the palette
rather than of any one component.

Every flagged node was inside [JuliaModal.vue](../src/components/JuliaModal.vue)
— the primary-election modal opens on first visit to any route and is dismissed
via `sessionStorage`, so Lighthouse, arriving with empty storage every time,
always audits it.

- **Contrast.** `--color-link` was `#0070f3`, which is **4.55:1 on white** — it
  cleared AA by 0.05. On the modal body's `bg-mint/60` (`#eff9eb`) that fell to
  **4.21:1**, and on the page background (`#e5f4de`, from `body`'s
  `sprout/20%`) to **3.97:1**. The modal was not an outlier; it was the first
  tinted surface to expose a token with no margin.

  It is now `#407628` — the same value as `--color-fern`, kept as its own
  semantic token — which clears **5.47 / 5.06 / 4.77** on those three
  backgrounds. `--color-sprout` and `--color-lime` were considered and are far
  too light to be link text at all (2.01:1 and 1.41:1 on white).

- **Links identified by colour alone.** No link colour can satisfy both
  constraints at once: contrast against a light background pulls the colour
  darker, and the 3:1 required against surrounding body text pulls it lighter.
  Fern is 1.72:1 against the modal's `text-ink/80` (`#454744`). So prose links
  carry an underline at rest — `p a { text-decoration: underline }` — and the
  distinction stops depending on colour. Scoped to `p a` rather than `a` because
  nav and footer links are not children of a `<p>` and keep their plain look.

- **Heading order.** `JuliaModal`'s own title bar emitted an `<h3>` under the
  page's visually-hidden `<h1>`. It is now an `<h2>` with `mt-0` to cancel the
  base `h2` prose margin, and
  [tests/unit/JuliaModal.spec.ts](../../tests/unit/JuliaModal.spec.ts) asserts
  the level so a change back fails a unit test rather than only Lighthouse.

**A caveat that still applies at 1.00.** Nothing in page content was ever
flagged, before or after. The modal sets `aria-modal="true"` and covers the
viewport, so content behind it is largely excluded from these audits — a perfect
score here is close to a statement about the modal, not the whole page. Auditing
page content properly would mean seeding `sessionStorage` so the modal stays
shut, which Lighthouse's static-server run does not currently do.

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
