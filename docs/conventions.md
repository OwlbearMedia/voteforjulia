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
- `scripts` — extra `<script>` tags, emitted before the JSON-LD (e.g. Donate's
  Donorbox loader).
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
  `.ts`/`.vue` script (e.g. the `BTN` constants in `JuliaFooter.vue`) are picked
  up — but only if the full class string appears literally, not concatenated
  fragments.
- Rules utilities can't express (the multi-image `hr`, `sprout-bullet`, Vue
  `<Transition>` classes) live in the `components` layer of `style.css`. A
  `<Transition name="foo">` is styled by hand-written `.foo-enter-active` /
  `.foo-enter-from` / `.foo-leave-active` / `.foo-leave-to` rules there — grep the
  name to find them. Every transition also gets a `prefers-reduced-motion: reduce`
  branch that zeroes it out; add new ones to that shared block.

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
`/donate`) must be listed in **`isCustomElement`** in
[vue-compiler-options.ts](../vue-compiler-options.ts). That module is the single
source shared by `vite.config.ts` and `vitest.config.ts` — add the tag there
once, never to a config directly.

The failure mode is quiet: an undeclared tag is compiled as a _component_
lookup, which fails. Vitest and the dev server still render it (the client
falls back to the raw tag), but SSG emits `<!---->` in its place, so the
element is missing from the prerendered HTML and only appears after hydration
— a hydration mismatch that no test catches. Verify with
`grep dbox-widget dist/donate.html` after a build.

Why `<dbox-widget>` is an in-page element rather than an iframe, and what that
implies for the security headers, is in
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
  applies to anything keyed, cached, or deduplicated.
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
- **"The application redirected to … more than 20 times" is the host's WAF, not
  the app.** When the runner's IP is graylisted, Imunify360 answers every URL
  with a challenge page that reloads itself every 5 seconds, and Cypress counts
  each reload as a redirect — so all three specs die on their first `cy.visit`,
  in a run where the app's own code never executes (the tell is `0 uncaught
exception(s)` alongside 21 loads). Cypress's headless Chrome fails the
  challenge's bot checks, so it can never clear;
  [hosting.md](hosting.md#an-imunify360-waf-sits-in-front-of-litespeed) has the
  detail and the remedy. Raising `redirectionLimit`, adding retries, or
  re-running the job are not fixes — a re-run only helps because it lands on a
  different IP.
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
