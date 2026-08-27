# Code conventions

The rules this codebase follows that the source does not announce. Most of them
have a quiet failure mode: break one and nothing errors, the result is just
subtly wrong — a utility class that does nothing, an element missing from the
prerendered HTML, a test that passes while asserting nothing.

For the runtime environment and deploys see [hosting.md](hosting.md); for the
Donorbox/Stripe integration on `/donate` see
[donate-integration.md](donate-integration.md).

## Adding a page

Pages are prerendered from a canonical path list, and several tests assert that
list is complete, so adding a page means touching a fixed set of files. Miss one
and tests fail in a non-obvious place. Checklist (see the `/endorsements` page as
a worked example):

1. **[src/lib/routePaths.ts](../src/lib/routePaths.ts)** — add the path to
   `appRoutePaths`. This single list drives the router _and_ the sitemap.
2. **[src/lib/routes.ts](../src/lib/routes.ts)** — add a lazy `import()` for the
   page component in the `pageImports` map.
3. **[src/App.vue](../src/App.vue)** — add the page's `<h1>` header title to the
   `pageHeaderTitle` map (this is the visually-hidden page title, distinct from
   the `<title>` tag).
4. **`src/pages/JuliaXxx.vue`** — create the component. Set `defineOptions({ name })`
   and call `useHead(buildPageHead({ ... }))` (see SEO below).
5. **[src/components/JuliaHeader.vue](../src/components/JuliaHeader.vue)** — add a
   nav link to `navLinks` if the page should be in the menu.
6. **Tests** — update the ones that assert the full route/title set:
   - `tests/unit/App.spec.ts` (`expectedHeaderTitles` — add the `<h1>` set in
     step 3; a companion test cross-checks the table against `appRoutePaths` and
     fails if it is missing)
   - `tests/unit/pages.spec.ts` (a render + SEO assertion for the new page)
   - `tests/unit/routes.spec.ts` passes automatically (it derives from
     `appRoutePaths`), as does the sitemap and `App.spec.ts`'s router setup.
7. **[perf-budgets.json](../perf-budgets.json)** — add a first-load budget for
   the new route's `.html`. CI fails on a route with no entry rather than
   skipping it, so this is not optional; the point is that a new page cannot
   opt itself out of the budget by existing. Build, run `pnpm perf:budget` to
   read the route's actual size off the table, and set the budget a little above
   it. See [performance.md](performance.md#moving-a-budget).

The one file that looks like a page but deliberately skips all of this is
`api-docs.html` at the repo root — the local Swagger UI viewer (see the
README). Staying out of `appRoutePaths` is what keeps it off the live site: add
it and you would prerender it into `dist` and list it in the sitemap.

## SEO / `<head>`

Every page's `<head>` is built by **`buildPageHead`** in
[src/lib/pageHead.ts](../src/lib/pageHead.ts) — do **not** hand-write the
og/twitter meta block. Pass the essentials and override only what differs:

```ts
useHead(
  buildPageHead({
    path: '/endorsements',
    title: 'Endorsements | Julia Hamann for Mankato Mayor',
    description: '…' // used for meta description + og/twitter description
  })
);
```

The helper generates the canonical link, the full og/twitter/robots/image block,
and a JSON-LD graph containing the shared `campaignWebSiteNode` +
`campaignPersonNode`. Options for the variations that exist today:

- `socialTitle` / `socialDescription` — when og/twitter text differs from the
  page title/description (e.g. Home uses the bare candidate name).
- `keywords` — optional keywords meta.
- `schemaNodes` — extra JSON-LD `@graph` nodes appended after the shared two
  (e.g. Events' `Event` entries).
- `schemaGraph` — fully replace the graph when node order matters (e.g. Donate
  inserts a `WebPage` node between WebSite and Person). Compose it from the
  exported `campaignWebSiteNode` / `campaignPersonNode`.
- `scripts` — extra `<script>` tags, emitted before the JSON-LD. No caller today:
  Donate used it for the Donorbox loader until that moved to `onMounted`.
- `extraLinks` — extra `<link>` tags (e.g. Donate's `modulepreload` for the
  Donorbox loader, which is preloaded here but _executed_ from `onMounted` — see
  [Custom elements](#custom-elements)).
- `extraMeta` — meta tags appended after the standard block.

## Tailwind

Tailwind CSS v4 with **CSS-first config** in [src/style.css](../src/style.css).
There is no `tailwind.config.js`.

- **Only the campaign theme tokens exist.** `src/style.css` resets Tailwind's
  default palette/fonts/shadows to `initial`, so there is no `bg-red-500` etc.
  Colors are `forest`, `fern`, `leaf`, `sprout`, `lime`, `mint`, `mist`, `ink`,
  `white`, `link`, `error`, `warning`. Fonts: `font-display` (Mickle), `font-accent`
  (Orelega One), `font-action` (TheBoldFont), `font-sans`. A stray default
  utility silently does nothing.
- **Prose typography is element-level.** `h2`, `h3`, `p`, `a`, `blockquote`,
  `hr`, `section` are styled in `style.css`'s `base` layer so content-heavy pages
  stay mostly unclassed. Match that: don't reclass every paragraph.
- **Prefer the standard scale over arbitrary values.** Font sizes and radii use
  Tailwind's built-in scale (`text-xl`, `rounded-md`); only genuine off-scale
  values earn an `@theme` token (`--text-event: 2rem` → `text-event`). Reserve
  `[…]` for true one-offs (layout `calc()`s, `grid-cols-[…]`, optical nudges).
  Two gotchas: v4's `text-*` utilities carry a **bundled line-height**, so
  `--text-{sm,xl,2xl}--line-height` are pinned to `1.6` to preserve the site's
  uniform body leading (a bare `text-[…]` used to inherit it). And stacking
  order lives in `--z-index-*` tokens (`z-sticky`/`z-dropdown`/`z-overlay`/
  `z-floating`), not magic numbers.
- **The `md` breakpoint is Tailwind's default (48rem / 768px).** Mobile-specific
  overrides use `max-md:` throughout.
- **Tailwind's scanner reads plain string literals**, so class names assembled in
  `.ts`/`.vue` script (e.g. the `BUTTON_BASE` / `BUTTON_VARIANTS` constants in
  `JuliaButton.vue`) are picked up — but only if the full class string appears
  literally, not concatenated fragments. **This includes comments**: the scanner
  reads text, not code, so naming a utility in a comment about why the code no
  longer applies it emits it into the stylesheet as dead CSS.

  Worth knowing, not worth contorting prose over — **plain English words are
  utilities too**. `visible`, `static`, `outline` and `ring` are all real
  classes, so a comment cannot reliably avoid them, and the whole set costs
  **29 bytes gzipped**. Rewrite a distinctive token you are not applying
  (`hover:bg-sprout/70` → "sprout at 70% opacity") and leave the English alone.
  Tailwind's `blocklist` would fix it properly but lives in the JS-config
  compatibility layer, which would mean reintroducing `tailwind.config.js` for
  those 29 bytes — see the note above on not having one. To audit the current
  set, list the class selectors in `dist/assets/*.css` and find the ones whose
  only occurrence in `src/` is on a comment line.

- **`prettier-plugin-tailwindcss` sorts class attributes**, so class order is not
  yours to choose and `pnpm format` will rewrite it. Two consequences. It only
  sorts _markup_ — a class string in script (the `JuliaButton.vue` constants) is
  left alone and drifts from the house order silently, so re-derive it by pasting
  the string into a scratch `class=""` and running Prettier on that. And the
  plugin is configured with `tailwindStylesheet` in `.prettierrc`, which v4 needs
  in place of the `tailwind.config.js` this project deliberately does not have —
  without it the sort falls back to stock Tailwind and mis-orders the theme's
  own utilities.
- **Class order never decides which of two conflicting utilities wins — CSS
  order does.** `px-4 px-6` on one element resolves to whichever Tailwind emits
  later, regardless of how they are written, so an override can silently do
  nothing. The flip side is useful: `flex-1 basis-1/2` works precisely because
  `.basis-1\/2` is emitted after `.flex-1`, which is why the pages use it rather
  than an arbitrary `flex-[1_1_50%]`. When leaning on that, check the built CSS.
- Rules utilities can't express (the multi-image `hr`, `sprout-bullet`, Vue
  `<Transition>` classes) live in the `components` layer of `style.css`. A
  `<Transition name="foo">` is styled by hand-written `.foo-enter-active` /
  `.foo-enter-from` / `.foo-leave-active` / `.foo-leave-to` rules there — grep the
  name to find them. Every transition also gets a `prefers-reduced-motion: reduce`
  branch that zeroes it out; add new ones to that shared block.

## Buttons

Every pill-shaped action on the site — footer, header, hero, modal, both form
submits — renders through
[src/components/JuliaButton.vue](../src/components/JuliaButton.vue). Don't
hand-roll another one; the classes drifted three ways before this existed.

- `variant` is `primary` (filled leaf, white text), `secondary` (white, fern
  text — for dark surfaces) or `danger` (the destructive form of primary; only
  the modal's confirm button uses it). Secondary's text is **fern, not leaf**:
  leaf on white is 4.52:1, clearing AA for normal text by a hair, where fern is
  5.47:1. Same reasoning as `--color-link` in `style.css`.
- The rendered tag follows the props: `to` → `RouterLink`, `href` → `<a>`,
  neither → `<button>` (always with an explicit `type`, so one inside a `<form>`
  never submits by accident).
- **Hover darkens.** Primary goes leaf → fern. The obvious-looking lighter
  hover is a trap: white on sprout at 70% is 1.69:1 against the page and 3.19:1
  on the footer, against 4.52:1 at rest. Neither Lighthouse nor axe evaluates
  hover state, so CI stays green through it — check any new hover colour by
  hand. Forest is the other tempting choice and is wrong for a different
  reason: it is the footer's own background, so the Donate button would vanish
  into the bar.
- **A disabled link is rendered as a disabled `<button>`, not a faded `<a>`.**
  `disabled` is not an attribute anchors have, and the styling-only hardening
  that looks sufficient is not: `pointer-events-none` only stops the mouse and
  `tabindex="-1"` only stops tabbing, so `element.click()` — scripts, and some
  assistive-tech activation paths — still navigated and still ran the caller's
  `@click`. Swapping the tag closes it, because the platform will not dispatch
  a click on a disabled form control at all. A unit test pins that.
- **Size and layout classes are the caller's**, passed through the fallthrough
  `class` attr and merged with the variant's — the base deliberately sets no
  font size, because the footer/header/hero buttons run at body size and the
  modal and form buttons at `text-sm`. Beware that a caller class overriding a
  base one (`px-4` against the base `px-6`) is decided by Tailwind's own CSS
  order, not by which is written last, so it may silently do nothing.
- Focus goes through the exposed `focus()`, not the element: a template ref on
  the component yields a component instance, and the root is a `RouterLink`
  instance rather than an element whenever `to` is set. Testing that branch
  needs a **real** router — `RouterLinkStub` renders an anchor with no `href`,
  and an anchor without one cannot take focus, so a stubbed test fails while
  the component is working.
- **The focus ring is two-tone and that is not decoration.** These buttons sit
  on the light page background, the forest footer, the leaf nav dropdown and the
  mint modal; no single colour clears 3:1 against all four. `focus-visible:ring-4`
  fills the 0–4px band with near-black and the offset outline paints white over
  its outer half, so whichever band a background swallows, the other shows. It is
  the only custom focus indicator on the site — everything else uses the UA
  default — and a unit test pins it, because deleting it fails silently.

The two icon-only controls — the header's hamburger and the modal's X — are
plain `<button>`s on purpose; they share none of the pill styling.

## Icons

Icons are hand-rolled single-file components in
[src/components/icons/](../src/components/icons/) (`IconEnvelope.vue`,
`IconSpinner.vue`, …) — there is no icon library. Each is a bare `<svg>` sized in
`em` (`width="1em" height="1em"`), `fill="currentColor"`, and `aria-hidden="true"`,
so it inherits the parent's `font-size` and `color`; scale it with a `text-*`
utility. Paths come from Font Awesome (free). To add one, copy an existing icon,
keep the SVG's own `viewBox`, and drop in the new path.

## Custom elements

Third-party custom elements (currently only Donorbox's `<dbox-widget>` on
`/donate`) go in as **raw markup — a module-level string rendered with
`v-html` — never as a tag in a template.**

That is not a style preference. Vue creates elements with
`document.createElement`, which runs a registered custom element's constructor
synchronously and then rejects the result if that constructor gave itself
attributes. Vendor constructors do exactly that, so the call throws and the
widget never renders. Assigning `innerHTML` parses a fragment instead, and
fragment parsing always defers custom elements to the _upgrade_ path, where the
same constructor is legal. It also keeps the vendor's DOM outside Vue's vdom, so
shadow roots and injected scripts cannot register as a hydration mismatch.

Load the vendor's script from the component's `onMounted`, not from
`buildPageHead`'s `scripts` — anything that defines the element before hydration
finishes brings the race back. A `modulepreload` entry in `extraLinks` keeps the
download early.

SSG renders `v-html` content into the static HTML, so prerendering is unaffected
and the verification step is unchanged — a typo'd string fails just as quietly
as an undeclared tag did:

```
grep dbox-widget dist/donate.html
```

The crash this avoids, why `<dbox-widget>` is an in-page element rather than an
iframe, and what that implies for the security headers are all in
[donate-integration.md](donate-integration.md).

## Diagrams in docs

Diagrams are Mermaid in fenced ` ```mermaid ` blocks, rendered by GitHub. They
live only in [architecture.md](architecture.md) — keep them there rather than
scattering them through the ADRs, which are meant to be readable as plain text.

**A broken diagram fails silently and nothing in CI catches it.** GitHub renders
a block it cannot parse as a raw code block, with no error shown. Prettier
formats the fence but never parses its contents, so a broken diagram passes
`format:check` and merges green; the first sign of trouble is someone looking at
the rendered page. This has already happened once, in the submission-flow
sequence diagram.

The trap that caused it: **`;` inside sequence-diagram message text ends the
statement**, exactly as a newline would, so

```
A->>A: parse + validate; log field NAMES only
```

parses `log field NAMES only` as a statement of its own and fails. Use a comma
or an em dash. Unbalanced quotes and braces in message text bite the same way;
`<br/>` for line breaks in node labels is fine and is used in the flowchart.

Check a block before pushing by pasting it into <https://mermaid.live>, which
shows the parse error and the line. To check the file's blocks
programmatically, install `mermaid` in a scratch directory and call
`mermaid.parse()` on each block with the repo's `jsdom` supplying `window` and
`document` (mermaid needs `navigator` defined via `Object.defineProperty`, not
assignment). Both approaches use their own mermaid version rather than GitHub's,
so they catch syntax errors, not rendering differences.

## Testing

Commands are in the [README](../README.md#testing); this section covers the
conventions and the traps.

- Page components mock `@unhead/vue`'s `useHead` and assert on `title` + canonical
  link (see `tests/unit/pages.spec.ts`). `buildPageHead` is unit-tested directly
  in `tests/unit/pageHead.spec.ts`.
- `routes.spec.ts` and `sitemap.spec.ts` both derive expectations from
  `appRoutePaths`, so keeping that list correct keeps them green.
- **[vitest.setup.ts](../vitest.setup.ts) clears `document.body` after every
  test**, so markup from an `attachTo: document.body` mount never reaches the
  next one and `document.activeElement` resets with it. Two things follow. A
  wrapper left unmounted is not a DOM leak here — but the global hook strips
  nodes without running Vue's unmount lifecycle, so a component holding
  listeners, observers or timers (`JuliaFooter`, `JuliaModal`) still has to be
  unmounted explicitly or its teardown never runs. And a test asserting "the
  previous test left nothing behind" is worthless: the setup file guarantees it
  whether or not the spec's own cleanup works, so it passes with the cleanup
  deleted.
- **A test gated on git history does not run in CI.** `ci.yml` checks out with
  `fetch-depth: 1`, so `canReadHistory()` is false there and anything behind it
  returns early — the assertion only ever fires on a full local clone, where it
  is also hostage to what the history happens to look like. `sitemap.build.ts`
  takes its `GitRunner` as an argument for this reason; test the dating logic by
  injecting one (`sitemapLastmod.spec.ts`) rather than against the live repo.
  Only the deploy workflows use `fetch-depth: 0`, because that is where the
  sitemap is actually built.
- **The honeypot's hiding mechanism is a correctness property, not a style
  choice.** `.honeypot-field` is `display: none` because that removes the
  element from the accessibility tree; `.sr-only` is the off-screen idiom, which
  exists precisely so screen readers _do_ announce what it hides. Swapping one
  for the other reads as an equivalent refactor and would make the field a trap
  only screen-reader users can fall into. `tests/unit/honeypot.spec.ts` parses
  `src/style.css` and asserts the declaration directly, so the invariant fails
  in unit tests rather than in production —
  [ADR-0016](adr/0016-second-tier-rate-limiting-and-honeypot.md) has the
  reasoning.
- **Backend tests are split by what they cover.**
  [api/test_app.py](../api/test_app.py) has the happy paths, CORS, rate limiting,
  and input validation; [api/test_app_pipeline.py](../api/test_app_pipeline.py)
  has the form-encoded submission path and every failure branch of
  `_handle_form_submission`. New failure-path tests belong in the latter — its
  `pipeline` fixture already lets you make any collaborator raise or refuse.
- **A "these two collide" assertion is only half a test.** The rate limiter keys
  buckets on the _last_ `X-Forwarded-For` hop, and the original test sent two
  requests sharing a last hop and asserted they were limited together. That
  passes even if `X-Forwarded-For` is ignored outright, because both then fall
  back to the same `remote_addr` — deleting the entire branch kept the suite
  green. Any test of the form "these requests should share a bucket" needs the
  matching "these requests should not" to actually pin the key. The same trap
  applies to anything keyed, cached, or deduplicated. **Assert it through the
  responses, not off the counters** — since
  [ADR-0024](adr/0024-count-every-rate-limit-tier-in-sqlite.md) the counts live
  in SQLite and an allowed request leaves nothing in the process to inspect, so
  "two requests were keyed apart" is shown by a third request being refused.
- **A test that restates the diff is not a test**, and the trap is worst right
  after fixing something, because listing what you just added _feels_ like
  checking it. `JuliaButton`'s disabled-link test asserted the three things the
  fix had added — `aria-disabled`, `tabindex="-1"`, `pointer-events-none` —
  while `element.click()` still navigated and still ran the caller's handler,
  which is exactly what "disabled" was claiming to prevent. Assert the property
  being claimed (is it actually inoperable?), then **delete the fix locally and
  watch the test fail**. If it stays green it is decorative. Cheap enough to do
  every time; it is how the sitemap dating tests, the modal-cleanup test and
  this one were each shown to be worth keeping or worth deleting.
- **Cypress `cy.visit` is overridden** in [cypress/support/e2e.ts](../cypress/support/e2e.ts)
  to seed `sessionStorage` before the app mounts — it dismisses the primary-election
  modal (`JuliaPrimaryModal`, mounted by `App.vue`) whose full-viewport backdrop
  would otherwise intercept the form specs' clicks. Any new full-viewport overlay
  that opens on load needs the same seeding here, or e2e clicks silently fail.
- **A failed e2e test prints `[diagnostics]` lines** — the same support file
  records every page load in the app under test (href, title, `navigationType`,
  the head of the HTML) plus any uncaught exception, and dumps them with a fresh
  request's status and headers through the `log` task in
  [cypress.config.ts](../cypress.config.ts). Browser console output never reaches
  `cypress run`'s stdout, so that task is the only way anything from the app
  reaches a CI log. They were added for, and identified, the failure below. The
  e2e job also curls the site before running and uploads screenshots and video
  on failure.
- **"The application redirected to … more than 20 times" was the host's WAF, not
  the app** — and the WAF has been off for **every** hostname the suite touches
  since **2026-08-15**, so this should no longer occur. The 2026-08-01 request
  this list credited until now covered `test.voteforjulia.com` alone;
  `test-api.voteforjulia.com` stayed graylisted for two more weeks, producing a
  separate intermittent failure — one that passed whenever a re-run happened to
  draw a different runner address. When the runner's IP was graylisted, Imunify360
  answered every URL with a challenge page that reloaded itself every 5 seconds,
  and Cypress counted each reload as a redirect — so all three specs died on
  their first `cy.visit`, in a run where the app's own code never executed (the
  tell is `0 uncaught exception(s)` alongside 21 loads). Cypress's headless
  Chrome failed the challenge's bot checks, so it could never clear.
  [hosting.md](hosting.md#imunify360-waf-disabled) has the detail and how it was
  resolved. **If this returns, it means the WAF is back** — raising
  `redirectionLimit`, adding retries, or re-running the job are not fixes, and a
  re-run only ever helped because it landed on a different IP.
- **`1 passing` plus a `(failed).png` screenshot means a test lost its first
  attempt** and was saved by `retries.runMode: 1`. Cypress fails a test on any
  uncaught exception from the app, and `donate.cy.ts` hits one from Donorbox's
  widget on most runs — see
  [donate-integration.md](donate-integration.md#their-constructor-throws-when-vue-creates-the-element).
- **Prettier's `format:check` globs cover `src/`, `scripts/`, `docs/`, and root
  files but not `tests/`** — run `npx prettier --write` on new frontend test files
  manually.
- **[api/test_openapi_spec.py](../api/test_openapi_spec.py) keeps the OpenAPI spec
  honest.** It cross-checks [api/openapi.yaml](../api/openapi.yaml) against the
  app: documented routes vs `app.url_map`, documented `maxLength`/`maxItems` vs
  the `MAX_*` constants in `models.py`, and every documented error message
  against the source. Change a limit or reword an error and it fails until the
  spec follows. Two things to know when extending it: a message the code
  _composes_ (f-strings, joined label lists) won't appear as a source literal, so
  add it to the `GENERATED_ERRORS` table with a callable that produces it; and
  never assert a route accepts `OPTIONS` via `url_map` — Flask adds `OPTIONS` to
  every route automatically, so that check silently always passes. Make the
  request and assert the status instead (an explicit preflight handler returns
  204, Flask's default returns 200).
- **The coverage gate is Codecov, not the test runners.** Neither
  `vitest.config.ts` nor `.coveragerc` sets a threshold, so coverage never fails
  locally; the pass/fail bar is 80% in [codecov.yml](../codecov.yml). Frontend
  and backend upload separately as the `frontend` and `backend` flags, giving
  four statuses: `project`, `project/frontend`, `project/backend`, and `patch`.
  Two things that file can't tell you: Codecov reads its config **from the
  default branch**, so editing `codecov.yml` in a PR does nothing for that PR (it
  takes effect once merged), and a repo-level YAML in Codecov's web UI merges on
  top of it.
- **Coverage exclusions live in three files and must agree**: `coverage.exclude`
  in `vitest.config.ts`, `omit` in [.coveragerc](../.coveragerc), and `ignore` in
  `codecov.yml`. Two entries are deliberate rather than incidental —
  `src/main.ts` and `api/passenger_wsgi.py` are the two entry points, executed
  only by Vite and by Passenger respectively, so no test can reach either.
