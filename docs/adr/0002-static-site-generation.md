# 0002. Prerender every route with vite-ssg

**Status:** Accepted
**Date:** 2026-07-31 (recorded; decided at project start)

## Context

The site is a Vue 3 app, and the content is eight routes of near-static campaign
material: biography, events, endorsements, a donate page, and three forms. Given
the host chosen in [0001](0001-shared-hosting-over-aws.md), the question was what
the browser should receive on first load.

Two forces dominate:

- **LiteSpeed is very good at exactly one thing: sending a file from disk.**
  Anything server-rendered would mean routing HTML through the Passenger app,
  which is a single Python worker on shared hardware — slower, and a dependency
  of page loads on the API's health.
- **SEO is the point.** A first-time voter searching for a candidate's name is
  the whole audience. Meta tags, canonical URLs, JSON-LD, Open Graph cards for
  when a link is shared to Facebook — these need to be in the bytes the crawler
  and the scraper receive. Facebook's and Bluesky's link scrapers do not execute
  JavaScript at all, and Google's rendering is a queue, not a promise.

## Decision

Build with **vite-ssg**: prerender each route in `appRoutePaths` to a flat
`.html` file at build time, then hydrate into a normal SPA in the browser.

Route files are emitted flat (`dirStyle: 'flat'` → `/meet-julia.html`) and
`.htaccess` maps clean URLs onto them, so `/meet-julia` is a file, not a
directory. `<head>` for every page comes from `buildPageHead`
([src/lib/pageHead.ts](../../src/lib/pageHead.ts)) so the SEO block cannot drift
per page, and the sitemap is generated from the same route list during the build.

## Consequences

- **Every page is a complete document with no JavaScript required** — correct
  title, description, canonical, og/twitter tags, and JSON-LD in the initial
  HTML. Link previews and crawlers get the real thing.
- **Serving cost is a static file read**, so LiteSpeed handles far more traffic
  than the campaign will ever produce, and an API outage cannot take the pages
  down.
- **The build is the only place content exists.** There is no CMS: a copy change
  is a commit, a PR, and a deploy. Acceptable for one developer; it would not be
  for a campaign staffer who wanted to edit events.
- **Anything the prerenderer cannot render is invisible to crawlers.** This is
  not theoretical — a custom element the compiler does not recognise renders as
  `<!---->` in the static HTML and only appears after hydration, which is why
  `grep dbox-widget dist/donate.html` is a real verification step
  ([../conventions.md](../conventions.md#custom-elements)).
- **Adding a page is a multi-file checklist**, because the route list drives the
  router, the prerenderer, and the sitemap at once. Tests enforce it.
- **Build-time work replaces request-time work**, which the build then leans on:
  CSS is inlined into each HTML file in `onFinished`, removing a render-blocking
  request that Chrome was attributing to the JS module context.

## Alternatives considered

- **Client-rendered SPA.** One `index.html` with a rewrite catch-all. Cheapest
  to build, worst possible answer for a site whose purpose is being found by
  search and shared as a link — an empty `<div id="app">` for every crawler that
  does not run JS.
- **Server-side rendering (Nuxt, or Vue SSR under Passenger).** Would give the
  same HTML dynamically, at the cost of putting a Node process on a shared host
  that has no Node app support, and making every page load depend on it. Nothing
  on the site changes per request, so there is nothing to buy with the
  complexity.
- **A static site generator with no framework (Astro, Eleventy, plain HTML).**
  Defensible, and lighter. Rejected because the forms, the modal, and the
  donation page are genuinely interactive, and Vue was already the author's
  fastest path to building them well.
